import uuid
from datetime import UTC, datetime, timedelta

from app.models.enums import AuthenticatedPrincipalType, WorkshopStatus
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PlatformUser, Session, WorkshopUser
from app.modules.catalog.contracts import BranchPricing
from app.modules.platform import service as platform_service
from app.modules.platform.api import record_application_error
from app.modules.platform.contracts import ErrorRecord, JobDefinition
from app.modules.platform.scheduler import RegisteredJob, registry
from app.modules.platform.service import ensure_default_jobs_registered, run_due_platform_jobs
from app.modules.support.contracts import ActionLog, Notification, StatusChangeLog
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _default_working_hours() -> dict[str, dict[str, str | None]]:
    return {
        "monday": {"open": "09:00", "close": "18:00"},
        "tuesday": {"open": "09:00", "close": "18:00"},
        "wednesday": {"open": "09:00", "close": "18:00"},
        "thursday": {"open": "09:00", "close": "18:00"},
        "friday": {"open": "09:00", "close": "18:00"},
        "saturday": {"open": "10:00", "close": "16:00"},
        "sunday": {"open": None, "close": None},
    }


async def _platform_access_token(client: AsyncClient, db_session: AsyncSession) -> str:
    await seed_platform_user(
        db_session,
        login="platformer",
        password="Admin123",
        password_reset_required=False,
    )
    response = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "platformer", "password": "Admin123"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _provision_payload() -> dict[str, object]:
    return {
        "workshop": {
            "name": "Atlas Mebel",
        },
        "branch": {
            "name": "Main",
            "address": "Tashkent, Chilonzor",
            "phone": "+998902020202",
            "working_hours": _default_working_hours(),
        },
        "owner": {
            "login": "owner",
        },
    }


async def test_platform_can_provision_workshop_owner_and_first_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)

    response = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json=_provision_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["workshop"]["name"] == "Atlas Mebel"
    assert "code" not in body["workshop"]
    assert "phone" not in body["workshop"]
    assert "address" not in body["workshop"]
    assert body["workshop"]["status"] == "active"
    assert body["branch"]["status"] == "active"
    assert body["branch"]["latitude"] is None
    assert body["branch"]["longitude"] is None
    assert body["owner"]["login"] == "owner"
    assert "full_name" not in body["owner"]
    assert "phone" not in body["owner"]
    assert body["owner"]["is_owner"] is True
    assert body["owner"]["home_branch_id"] == body["branch"]["id"]
    assert body["owner"]["password_reset_required"] is True
    assert body["temp_password"]
    branch_pricing_count = await db_session.scalar(select(func.count()).select_from(BranchPricing))
    action_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.action == "platform.workshop.provision")
    )
    owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "login": "owner",
            "password": body["temp_password"],
        },
    )
    listed = await client.get("/api/v1/platform/workshops", headers=_auth(access_token))
    detail = await client.get(
        f"/api/v1/platform/workshops/{body['workshop']['id']}",
        headers=_auth(access_token),
    )

    assert branch_pricing_count == 1
    assert action_count == 1
    assert owner_login.status_code == 200
    assert owner_login.json()["me"]["workshop_id"] == body["workshop"]["id"]
    assert owner_login.json()["me"]["password_reset_required"] is True
    assert listed.status_code == 200
    assert [row["name"] for row in listed.json()] == ["Atlas Mebel"]
    assert detail.status_code == 200
    assert detail.json()["owner"]["login"] == "owner"


async def test_provisioning_rejects_an_owner_login_taken_by_another_workshop(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Workshop logins are globally unique — the second workshop reaching for the
    # same owner login is refused up front instead of tripping the unique index.
    access_token = await _platform_access_token(client, db_session)
    first = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json=_provision_payload(),
    )

    collision = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={
            **_provision_payload(),
            "workshop": {"name": "Nur Mebel"},
            "owner": {"login": "OWNER"},
        },
    )

    assert first.status_code == 201
    assert collision.status_code == 409
    assert collision.json()["code"] == "login_exists"


async def test_platform_overview_reports_provisioning_and_actor_counts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)
    db_session.add(Client(phone="+998904040404", name="Client User"))
    await db_session.flush()

    first = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={
            **_provision_payload(),
            "owner": {
                **_provision_payload()["owner"],
                "login": "owner-a",
            },
        },
    )
    second = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={
            **_provision_payload(),
            "owner": {
                **_provision_payload()["owner"],
                "login": "owner-b",
            },
        },
    )
    assert first.status_code == 201
    assert second.status_code == 201

    block = await client.post(
        f"/api/v1/platform/workshops/{second.json()['workshop']['id']}/block",
        headers=_auth(access_token),
        json={"reason": "Contract paused"},
    )
    overview = await client.get("/api/v1/platform/overview", headers=_auth(access_token))

    assert block.status_code == 200
    assert overview.status_code == 200
    body = overview.json()
    assert {key: value for key, value in body.items() if isinstance(value, int)} == {
        "workshops_total": 2,
        "workshops_active": 1,
        "workshops_blocked": 1,
        "branches_total": 2,
        "clients_total": 1,
        "platform_users_active": 1,
    }
    # AB-119: everything above was created in this test run, so today's numbers
    # equal the lifetime ones — what this pins is that each metric is wired to
    # its own table and the three are never conflated.
    assert body["workshop_signups"]["daily"] == 2
    assert body["client_signups"]["daily"] == 1
    assert body["orders"]["daily"] == 0
    assert body["orders"]["spark"]["weekly"][-1] == 0
    assert len(body["client_signups"]["spark"]["daily"]) == 14
    assert "weekly" not in body["client_signups"]


async def test_platform_provision_rejects_non_canonical_working_hours(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)

    missing_days = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={
            **_provision_payload(),
            "branch": {
                **_provision_payload()["branch"],
                "working_hours": {"monday": {"open": "09:00", "close": "18:00"}},
            },
        },
    )
    bad_range = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={
            **_provision_payload(),
            "branch": {
                **_provision_payload()["branch"],
                "working_hours": {
                    **_default_working_hours(),
                    "monday": {"open": "18:00", "close": "09:00"},
                },
            },
        },
    )

    assert missing_days.status_code == 422
    assert bad_range.status_code == 422


async def test_platform_provision_rejects_removed_workshop_owner_and_coordinate_fields(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)

    response = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={
            **_provision_payload(),
            "workshop": {
                **_provision_payload()["workshop"],
                "code": "removed-fields",
                "phone": "+998901010101",
                "address": "Tashkent",
            },
            "branch": {
                **_provision_payload()["branch"],
                "latitude": "41.2995",
                "longitude": "69.2401",
            },
            "owner": {
                **_provision_payload()["owner"],
                "full_name": "Atlas Owner",
                "phone": "+998903030303",
            },
        },
    )

    assert response.status_code == 422


async def test_block_and_unblock_workshop_revoke_staff_sessions_but_not_client_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)
    provisioned = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={**_provision_payload(), "temp_password": "OwnerTemp123"},
    )
    assert provisioned.status_code == 201
    workshop_id = provisioned.json()["workshop"]["id"]
    workshop_uuid = uuid.UUID(workshop_id)
    owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "login": "owner",
            "password": "OwnerTemp123",
        },
    )
    owner_access = owner_login.json()["access_token"]
    client_row = Client(phone="+998904040404", name="Client User")
    db_session.add(client_row)
    await db_session.flush()
    client_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client_row.id,
    )

    block = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/block",
        headers=_auth(access_token),
        json={"reason": "Contract paused"},
    )
    blocked_owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "login": "owner",
            "password": "OwnerTemp123",
        },
    )
    client_me = await client.get("/api/v1/auth/me", headers=_auth(client_tokens.access_token))
    unblock = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/unblock",
        headers=_auth(access_token),
    )
    unblocked_owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "login": "owner",
            "password": "OwnerTemp123",
        },
    )
    status_logs = (
        await db_session.scalars(
            select(StatusChangeLog).where(StatusChangeLog.entity_id == workshop_uuid)
        )
    ).all()
    remaining_owner_sessions = await db_session.scalar(
        select(func.count())
        .select_from(Session)
        .join(WorkshopUser, WorkshopUser.id == Session.principal_id)
        .where(WorkshopUser.workshop_id == workshop_uuid)
    )

    assert block.status_code == 200
    assert block.json()["status"] == WorkshopStatus.BLOCKED.value
    assert (await client.get("/api/v1/auth/me", headers=_auth(owner_access))).status_code == 401
    assert blocked_owner_login.status_code == 403
    assert blocked_owner_login.json()["code"] == "account_blocked"
    assert client_me.status_code == 200
    assert unblock.status_code == 200
    assert unblock.json()["status"] == WorkshopStatus.ACTIVE.value
    assert unblocked_owner_login.status_code == 200
    assert [(row.from_status, row.to_status) for row in status_logs] == [
        ("active", "blocked"),
        ("blocked", "active"),
    ]
    assert remaining_owner_sessions == 1


async def test_platform_resets_workshop_owner_password(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)
    provisioned = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={**_provision_payload(), "temp_password": "OwnerTemp123"},
    )
    assert provisioned.status_code == 201
    workshop_id = provisioned.json()["workshop"]["id"]
    owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "owner", "password": "OwnerTemp123"},
    )
    owner_access = owner_login.json()["access_token"]

    forbidden = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/owner/reset-password",
        headers=_auth(owner_access),
    )
    missing = await client.post(
        f"/api/v1/platform/workshops/{uuid.uuid4()}/owner/reset-password",
        headers=_auth(access_token),
    )
    reset = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/owner/reset-password",
        headers=_auth(access_token),
    )
    old_password_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "owner", "password": "OwnerTemp123"},
    )
    new_password_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "owner", "password": reset.json()["temp_password"]},
    )
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.action == "platform.workshop.owner.password.reset")
    )
    # The documented support path: reset still works while the workshop is blocked.
    block = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/block",
        headers=_auth(access_token),
        json={"reason": "Contract paused"},
    )
    reset_while_blocked = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/owner/reset-password",
        headers=_auth(access_token),
    )

    assert forbidden.status_code == 403
    assert missing.status_code == 404
    assert missing.json()["code"] == "workshop_not_found"
    assert reset.status_code == 200
    assert reset.json()["owner"]["login"] == "owner"
    assert reset.json()["owner"]["password_reset_required"] is True
    assert reset.json()["temp_password"]
    assert (await client.get("/api/v1/auth/me", headers=_auth(owner_access))).status_code == 401
    assert old_password_login.status_code == 401
    assert new_password_login.status_code == 200
    assert new_password_login.json()["me"]["password_reset_required"] is True
    assert audit_count == 1
    assert block.status_code == 200
    assert reset_while_blocked.status_code == 200


async def test_platform_routes_reject_non_platform_principals(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, _, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )

    response = await client.get("/api/v1/platform/workshops", headers=_auth(tokens.access_token))

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_platform_user_registry_create_reset_block_and_unblock(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)

    created = await client.post(
        "/api/v1/platform/users",
        headers=_auth(access_token),
        json={
            "full_name": "Ops Two",
            "login": "ops-two",
            "phone": "+998905050505",
            "temp_password": "OpsTemp123",
        },
    )
    users = await client.get("/api/v1/platform/users", headers=_auth(access_token))
    user_id = created.json()["user"]["id"]
    reset = await client.post(
        f"/api/v1/platform/users/{user_id}/reset-password",
        headers=_auth(access_token),
    )
    block = await client.post(
        f"/api/v1/platform/users/{user_id}/block",
        headers=_auth(access_token),
        json={"reason": "Role changed"},
    )
    blocked_login = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "ops-two", "password": reset.json()["temp_password"]},
    )
    unblock = await client.post(
        f"/api/v1/platform/users/{user_id}/unblock",
        headers=_auth(access_token),
    )
    patched = await client.patch(
        f"/api/v1/platform/users/{user_id}",
        headers=_auth(access_token),
        json={"full_name": "Ops Two Updated", "phone": "+998906060606"},
    )
    current_user_id = next(row["id"] for row in users.json() if row["login"] == "platformer")
    self_block = await client.post(
        f"/api/v1/platform/users/{current_user_id}/block",
        headers=_auth(access_token),
        json={"reason": "Bad idea"},
    )
    action_count = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.action.in_(["platform.user.create", "platform.user.block"]))
    )
    status_count = await db_session.scalar(
        select(func.count())
        .select_from(StatusChangeLog)
        .where(StatusChangeLog.entity_type == "platform_user")
    )
    stored = await db_session.scalar(select(PlatformUser).where(PlatformUser.login == "ops-two"))

    assert created.status_code == 201
    assert created.json()["user"]["password_reset_required"] is True
    assert created.json()["temp_password"] == "OpsTemp123"
    assert users.status_code == 200
    assert {row["login"] for row in users.json()} == {"ops-two", "platformer"}
    assert reset.status_code == 200
    assert reset.json()["temp_password"] != "OpsTemp123"
    assert block.status_code == 200
    assert block.json()["status"] == "blocked"
    assert blocked_login.status_code == 403
    assert blocked_login.json()["code"] == "account_blocked"
    assert unblock.status_code == 200
    assert unblock.json()["status"] == "active"
    assert patched.status_code == 200
    assert patched.json()["full_name"] == "Ops Two Updated"
    assert self_block.status_code == 400
    assert self_block.json()["code"] == "cannot_block_self"
    assert action_count == 2
    assert status_count == 2
    assert stored is not None
    assert stored.phone == "+998906060606"


async def test_platform_jobs_errors_and_audit_surfaces(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)
    record = await record_application_error(
        db_session,
        code="platform.test_error",
        module="tests",
        message="password=secret surfaced",
        trace_id="trace-platform-error",
        context={"token": "secret", "safe": "kept"},
    )
    db_session.expire(record, ["updated_at"])

    jobs = await client.get("/api/v1/platform/jobs", headers=_auth(access_token))
    repeated_jobs = await client.get("/api/v1/platform/jobs", headers=_auth(access_token))
    run = await client.post(
        "/api/v1/platform/jobs/cleanup-expired-sessions/run",
        headers=_auth(access_token),
    )
    errors = await client.get("/api/v1/platform/errors", headers=_auth(access_token))
    detail = await client.get(
        f"/api/v1/platform/errors/{record.id}",
        headers=_auth(access_token),
    )
    resolved = await client.post(
        f"/api/v1/platform/errors/{record.id}/resolve",
        headers=_auth(access_token),
    )
    reopened = await record_application_error(
        db_session,
        code="platform.test_error",
        module="tests",
        message="new occurrence",
        trace_id="trace-platform-error-2",
    )
    actions = await client.get("/api/v1/platform/audit/actions", headers=_auth(access_token))
    statuses = await client.get(
        "/api/v1/platform/audit/status-changes",
        headers=_auth(access_token),
    )

    assert jobs.status_code == 200
    assert {row["definition"]["name"] for row in jobs.json()} == {"cleanup-expired-sessions"}
    assert repeated_jobs.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(JobDefinition)) == 1
    assert run.status_code == 200
    assert run.json()["status"] == "ok"
    assert run.json()["brief_log"] == "Pruned 0 expired sessions, 0 OTP challenges"
    assert errors.status_code == 200
    assert [row["code"] for row in errors.json()] == ["platform.test_error"]
    assert detail.status_code == 200
    assert detail.json()["record"]["code"] == "platform.test_error"
    assert detail.json()["occurrences"][0]["message"] == "password=*** surfaced"
    assert detail.json()["occurrences"][0]["context"] == {"token": "***", "safe": "kept"}
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert reopened.status.value == "open"
    assert actions.status_code == 200
    assert "platform.job.run" in {row["action"] for row in actions.json()}
    assert "platform.error.resolve" in {row["action"] for row in actions.json()}
    assert statuses.status_code == 200
    assert statuses.json() == []


async def test_platform_scheduler_runs_due_jobs_and_reports_failures(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)

    listed = await client.get("/api/v1/platform/jobs", headers=_auth(access_token))
    assert listed.status_code == 200

    definition = await db_session.scalar(
        select(JobDefinition).where(JobDefinition.name == "cleanup-expired-sessions")
    )
    assert definition is not None
    definition.last_run_at = datetime.now(UTC) - timedelta(hours=2)

    runs = await run_due_platform_jobs(
        db_session,
        now=datetime.now(UTC),
        trace_id="test-scheduler",
    )
    scheduler_actions = (
        await db_session.scalars(
            select(ActionLog).where(
                ActionLog.action == "platform.job.run",
                ActionLog.trace_id == "test-scheduler",
            )
        )
    ).all()

    assert len(runs) == 1
    assert runs[0].job_name == "cleanup-expired-sessions"
    assert runs[0].status.value == "ok"
    assert len(scheduler_actions) == 1

    async def failing_handler(_: AsyncSession) -> str | None:
        raise RuntimeError("planned failure")

    failing_job = RegisteredJob(
        name="cleanup-expired-sessions",
        schedule="hourly",
        handler=failing_handler,
    )
    original_defaults = platform_service.DEFAULT_JOBS
    platform_service.DEFAULT_JOBS = (failing_job,)
    registry.register(failing_job)
    try:
        failed = await client.post(
            "/api/v1/platform/jobs/cleanup-expired-sessions/run",
            headers=_auth(access_token),
        )
    finally:
        platform_service.DEFAULT_JOBS = original_defaults
        ensure_default_jobs_registered()

    failure_notice = await db_session.scalar(
        select(Notification).where(Notification.event_code == "job.failed")
    )

    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failure_notice is not None
    assert failure_notice.payload["job_name"] == "cleanup-expired-sessions"
    assert failure_notice.payload["error_message"] == "planned failure"


async def test_platform_audit_filters_and_offsets_are_server_side(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access = await _platform_access_token(client, db_session)
    provisioned = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access),
        json=_provision_payload(),
    )
    assert provisioned.status_code == 201
    workshop_id = provisioned.json()["workshop"]["id"]
    today = datetime.now(UTC).date().isoformat()

    block = await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/block",
        headers=_auth(access),
        json={"reason": "Audit filter check"},
    )
    assert block.status_code == 200

    actions = await client.get(
        "/api/v1/platform/audit/actions",
        headers=_auth(access),
        params={
            "module": "platform",
            "action_prefix": "platform.workshop",
            "actor": "platform_user",
            "entity_type": "workshop",
            "entity_id": workshop_id,
            "date_from": today,
            "date_to": today,
            "limit": 1,
            "offset": 0,
        },
    )
    next_actions = await client.get(
        "/api/v1/platform/audit/actions",
        headers=_auth(access),
        params={
            "entity_id": workshop_id,
            "limit": 1,
            "offset": 1,
        },
    )
    statuses = await client.get(
        "/api/v1/platform/audit/status-changes",
        headers=_auth(access),
        params={
            "entity_type": "workshop",
            "entity_id": workshop_id,
            "to_status": "blocked",
            "actor": "platform_user",
            "date_from": today,
            "date_to": today,
            "limit": 10,
            "offset": 0,
        },
    )
    invalid_range = await client.get(
        "/api/v1/platform/audit/actions",
        headers=_auth(access),
        params={"date_from": "2026-06-21", "date_to": "2026-06-20"},
    )

    assert actions.status_code == 200
    assert len(actions.json()) == 1
    assert actions.json()[0]["action"].startswith("platform.workshop")
    assert next_actions.status_code == 200
    assert len(next_actions.json()) == 1
    assert statuses.status_code == 200
    assert [row["to_status"] for row in statuses.json()] == ["blocked"]
    assert invalid_range.status_code == 400
    assert invalid_range.json()["code"] == "invalid_date_range"


async def test_error_records_group_by_code_and_module_and_emit_spike_notice(
    db_session: AsyncSession,
) -> None:
    platform_user = await seed_platform_user(
        db_session,
        login="spike-admin",
        password="Admin123",
        password_reset_required=False,
    )
    sales_record = None
    for index in range(9):
        sales_record = await record_application_error(
            db_session,
            code="shared.code",
            module="sales",
            message=f"sales boom {index}",
            trace_id=f"trace-sales-{index}",
            workshop_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )
    assert sales_record is not None
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == 0

    tenth = await record_application_error(
        db_session,
        code="shared.code",
        module="sales",
        message="sales boom threshold",
        trace_id="trace-sales-threshold",
    )
    workshop_record = await record_application_error(
        db_session,
        code="shared.code",
        module="workshop",
        message="workshop boom",
        trace_id="trace-workshop",
    )
    await record_application_error(
        db_session,
        code="shared.code",
        module="sales",
        message="sales boom after threshold",
        trace_id="trace-sales-after",
    )

    notices = (
        await db_session.scalars(
            select(Notification).where(Notification.event_code == "error.spike")
        )
    ).all()
    records = (
        await db_session.scalars(
            select(ErrorRecord)
            .where(ErrorRecord.code == "shared.code")
            .order_by(ErrorRecord.module)
        )
    ).all()

    assert tenth.id == sales_record.id
    assert workshop_record.id != sales_record.id
    assert [record.module for record in records] == ["sales", "workshop"]
    assert len(notices) == 1
    assert notices[0].recipient_id == platform_user.id
    assert notices[0].payload == {
        "code": "shared.code",
        "module": "sales",
        "count_24h": 10,
        "threshold": 10,
    }


async def test_workshop_detail_surfaces_block_reason(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # AB-20: a blocked workshop's detail carries the reason captured at block time;
    # an active workshop (and one later unblocked) reports None.
    access = await _platform_access_token(client, db_session)
    provisioned = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access),
        json=_provision_payload(),
    )
    assert provisioned.status_code == 201
    workshop_id = provisioned.json()["workshop"]["id"]

    active = await client.get(f"/api/v1/platform/workshops/{workshop_id}", headers=_auth(access))
    assert active.status_code == 200
    assert active.json()["block_reason"] is None

    await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/block",
        headers=_auth(access),
        json={"reason": "Unpaid invoice"},
    )
    blocked = await client.get(f"/api/v1/platform/workshops/{workshop_id}", headers=_auth(access))
    assert blocked.json()["block_reason"] == "Unpaid invoice"

    await client.post(
        f"/api/v1/platform/workshops/{workshop_id}/unblock",
        headers=_auth(access),
    )
    unblocked = await client.get(f"/api/v1/platform/workshops/{workshop_id}", headers=_auth(access))
    assert unblocked.json()["block_reason"] is None


async def test_workshops_list_reports_owner_login_and_branch_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # AB-37: the list row carries the owner login (not just the UUID) and a count
    # of the workshop's branches, both derived via join/aggregate.
    access = await _platform_access_token(client, db_session)
    provisioned = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access),
        json=_provision_payload(),
    )
    assert provisioned.status_code == 201
    workshop_id = provisioned.json()["workshop"]["id"]
    owner_login = provisioned.json()["owner"]["login"]

    listing = await client.get("/api/v1/platform/workshops", headers=_auth(access))
    assert listing.status_code == 200
    row = next(w for w in listing.json() if w["id"] == workshop_id)
    assert row["owner_login"] == owner_login
    assert row["branch_count"] == 1


async def test_error_record_manual_reopen_clears_resolution(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # AB-25: the operator reopen endpoint flips a resolved record back to open and
    # clears the resolution metadata, writing a platform.error.reopen action.
    access = await _platform_access_token(client, db_session)
    record = await record_application_error(
        db_session,
        code="platform.reopen_me",
        module="tests",
        message="boom",
        trace_id="trace-reopen",
    )

    resolved = await client.post(
        f"/api/v1/platform/errors/{record.id}/resolve",
        headers=_auth(access),
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None
    assert resolved.json()["resolved_by_user_id"] is not None

    reopened = await client.post(
        f"/api/v1/platform/errors/{record.id}/reopen",
        headers=_auth(access),
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
    assert reopened.json()["resolved_at"] is None
    assert reopened.json()["resolved_by_user_id"] is None

    actions = await client.get("/api/v1/platform/audit/actions", headers=_auth(access))
    assert "platform.error.reopen" in {row["action"] for row in actions.json()}
