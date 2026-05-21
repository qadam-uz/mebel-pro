"""Platform ops — jobs console, error monitor + 500 handler, audit, dashboard."""

import uuid

from app.core.principal import Principal
from app.core.security import hash_password
from app.models.enums import PrincipalType
from app.models.identity import Client, PlatformUser, WorkshopUser
from app.models.workshop import Branch, Workshop
from app.services import audit as audit_service
from app.services import errors as error_service
from app.services.scheduler import scheduler
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _platform_user(db: AsyncSession, login: str = "op") -> PlatformUser:
    u = PlatformUser(
        login=login,
        password_hash=hash_password("Passw0rd!"),
        full_name="Operator",
        phone="+998900000001",
        force_password_change=False,
    )
    db.add(u)
    await db.commit()
    return u


# --- jobs console -----------------------------------------------------------


async def test_jobs_list_and_run_now(client: AsyncClient, db_session, auth_headers):
    # The scheduler registers its default jobs on start; ensure they're present.
    from app.services import jobs as job_impls

    job_impls.register_default_jobs(scheduler)
    op = await _platform_user(db_session)
    headers = await auth_headers(PrincipalType.PLATFORM_USER, op.id)

    listed = await client.get("/api/v1/admin/platform/jobs", headers=headers)
    assert listed.status_code == 200, listed.text
    names = {j["name"] for j in listed.json()}
    assert "cleanup-expired-sessions" in names

    run = await client.post(
        "/api/v1/admin/platform/jobs/cleanup-expired-sessions/run", headers=headers
    )
    assert run.status_code == 200, run.text
    assert run.json()["last_result"] == "ok"


async def test_run_unknown_job_is_404(client, db_session, auth_headers):
    op = await _platform_user(db_session)
    headers = await auth_headers(PrincipalType.PLATFORM_USER, op.id)
    r = await client.post("/api/v1/admin/platform/jobs/nope/run", headers=headers)
    assert r.status_code == 404


async def test_run_now_already_running_is_409(client, db_session, auth_headers):
    from app.services import jobs as job_impls

    job_impls.register_default_jobs(scheduler)
    op = await _platform_user(db_session)
    headers = await auth_headers(PrincipalType.PLATFORM_USER, op.id)

    job = scheduler.jobs["cleanup-expired-sessions"]
    await job.lock.acquire()
    try:
        r = await client.post(
            "/api/v1/admin/platform/jobs/cleanup-expired-sessions/run", headers=headers
        )
        assert r.status_code == 409
        assert r.json()["code"] == "job_already_running"
    finally:
        job.lock.release()


async def test_jobs_require_platform_user(client, db_session, auth_headers):
    c = Client(telegram_id=1, phone="+998900000000", first_name="C")
    db_session.add(c)
    await db_session.commit()
    headers = await auth_headers(PrincipalType.CLIENT, c.id)
    r = await client.get("/api/v1/admin/platform/jobs", headers=headers)
    assert r.status_code == 403


# --- error monitor ----------------------------------------------------------


async def test_record_upsert_list_detail_resolve(client, db_session, auth_headers):
    await error_service.record_error(
        db_session,
        code="app.boom",
        module="orders",
        message="kaboom",
        stack="Traceback...",
        context={"password": "hunter2", "path": "/x"},
        trace_id="abc123",
        workshop_id=uuid.uuid4(),
    )
    grp = await error_service.record_error(
        db_session, code="app.boom", module="orders", message="kaboom again"
    )
    await db_session.commit()
    assert grp.count_total == 2  # upsert by code

    op = await _platform_user(db_session)
    headers = await auth_headers(PrincipalType.PLATFORM_USER, op.id)

    listed = await client.get("/api/v1/admin/platform/errors", headers=headers)
    assert listed.status_code == 200
    row = next(r for r in listed.json() if r["code"] == "app.boom")
    assert row["count_total"] == 2
    assert row["count_24h"] == 2

    detail = await client.get(f"/api/v1/admin/platform/errors/{row['id']}", headers=headers)
    assert detail.status_code == 200
    d = detail.json()
    assert len(d["events"]) == 2
    # sensitive context masked
    masked = [e["context"] for e in d["events"] if e["context"]]
    assert any(c.get("password") == "***" for c in masked)
    assert len(d["affected_workshops"]) == 1

    resolved = await client.post(
        f"/api/v1/admin/platform/errors/{row['id']}/resolve", headers=headers
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


async def test_500_handler_records_error_with_trace(db_session, monkeypatch):
    """A handler that raises produces a trace envelope and records an error.

    Build a non-debug app (in debug mode Starlette returns a raw traceback and
    skips custom handlers — prod runs ``DEBUG=False``). The 500 handler records
    via its own ``SessionLocal``, which the conftest fixture has pointed at this
    test's schema-bearing engine, so the record survives the request rollback.
    """
    from app.core.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "DEBUG", False)
    boom_app = create_app()

    @boom_app.get("/_test_boom")
    async def _boom() -> None:
        raise RuntimeError("intentional test failure")

    transport = ASGITransport(app=boom_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/_test_boom")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "internal_error"
    # the trace id is captured from the request context into the error envelope
    assert body["trace_id"]

    # The 500 handler recorded the error on its own session — visible to ours.
    groups = await error_service.list_groups(db_session)
    codes = {g["code"] for g in groups}
    assert any("RuntimeError" in c for c in codes)


async def test_error_spike_notifies_operators(db_session):
    op = await _platform_user(db_session)
    # Threshold is 50; drive the 24h count to exactly that.
    for i in range(50):
        await error_service.record_error(db_session, code="app.spike", message=f"e{i}")
    await db_session.commit()
    from app.services import notifications as notif_service

    assert (await notif_service.unread_count(db_session, PrincipalType.PLATFORM_USER, op.id)) == 1


# --- audit viewer -----------------------------------------------------------


async def test_audit_actions_and_status_changes(client, db_session, auth_headers):
    ws = Workshop(name="W", phone="+998900000000")
    db_session.add(ws)
    await db_session.flush()
    branch = Branch(workshop_id=ws.id, name="B", address="A", phone="+998900000002")
    db_session.add(branch)
    await db_session.flush()
    owner = WorkshopUser(
        workshop_id=ws.id,
        login="owner",
        password_hash=hash_password("Passw0rd!"),
        full_name="Owner",
        phone="+998900000003",
        is_owner=True,
        force_password_change=False,
    )
    db_session.add(owner)
    await db_session.flush()
    actor = Principal(
        type=PrincipalType.WORKSHOP_USER,
        id=owner.id,
        session_id=uuid.uuid4(),
        workshop_id=ws.id,
        is_owner=True,
    )
    order_id = uuid.uuid4()
    await audit_service.record_action(
        db_session,
        actor=actor,
        action="order.confirmed",
        entity_type="order",
        entity_id=order_id,
        workshop_id=ws.id,
        branch_id=branch.id,
        summary="Order confirmed",
    )
    await audit_service.record_status_change(
        db_session,
        entity_type="order",
        entity_id=order_id,
        from_status="new",
        to_status="confirmed",
        actor=actor,
        workshop_id=ws.id,
        branch_id=branch.id,
    )
    await db_session.commit()

    op = await _platform_user(db_session)
    headers = await auth_headers(PrincipalType.PLATFORM_USER, op.id)

    actions = await client.get("/api/v1/admin/audit/actions?module=order", headers=headers)
    assert actions.status_code == 200
    assert len(actions.json()) == 1
    assert actions.json()[0]["action"] == "order.confirmed"

    # workshop filter
    wrong_ws = await client.get(
        f"/api/v1/admin/audit/actions?workshop_id={uuid.uuid4()}", headers=headers
    )
    assert wrong_ws.json() == []

    changes = await client.get(
        f"/api/v1/admin/audit/status-changes?entity_id={order_id}&to_status=confirmed",
        headers=headers,
    )
    assert len(changes.json()) == 1
    assert changes.json()[0]["from_status"] == "new"


async def test_audit_requires_platform_user(client, db_session, auth_headers):
    c = Client(telegram_id=5, phone="+998900000005", first_name="C")
    db_session.add(c)
    await db_session.commit()
    headers = await auth_headers(PrincipalType.CLIENT, c.id)
    r = await client.get("/api/v1/admin/audit/actions", headers=headers)
    assert r.status_code == 403


# --- dashboard --------------------------------------------------------------


async def test_dashboard_counts(client, db_session, auth_headers):
    ws = Workshop(name="W", phone="+998900000000")
    db_session.add(ws)
    await db_session.flush()
    db_session.add(Branch(workshop_id=ws.id, name="B", address="A", phone="+998900000002"))
    db_session.add(Client(telegram_id=7, phone="+998900000007", first_name="C"))
    await db_session.commit()
    op = await _platform_user(db_session)
    headers = await auth_headers(PrincipalType.PLATFORM_USER, op.id)

    r = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["workshops_count"] == 1
    assert d["branches_count"] == 1
    assert d["clients_count"] == 1
    assert len(d["recent_workshops"]) == 1
    assert "failed_jobs_24h" in d
    assert "open_error_groups" in d
