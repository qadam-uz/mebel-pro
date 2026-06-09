import uuid

from app.models.enums import AuthenticatedPrincipalType, WorkshopStatus
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PlatformUser, Session, WorkshopUser
from app.modules.catalog.contracts import BranchPricing
from app.modules.platform.api import record_application_error
from app.modules.platform.contracts import JobDefinition
from app.modules.support.contracts import ActionLog, StatusChangeLog
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


def _provision_payload(code: str | None = None) -> dict[str, object]:
    return {
        "workshop": {
            "name": "Atlas Mebel",
            "code": code,
            "phone": "+998901010101",
            "address": "Tashkent",
        },
        "branch": {
            "name": "Main",
            "address": "Tashkent, Chilonzor",
            "phone": "+998902020202",
            "latitude": "41.2995",
            "longitude": "69.2401",
            "working_hours": _default_working_hours(),
        },
        "owner": {
            "full_name": "Atlas Owner",
            "login": "owner",
            "phone": "+998903030303",
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
        json=_provision_payload(code="atlas"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["workshop"]["code"] == "atlas"
    assert body["workshop"]["status"] == "active"
    assert body["branch"]["status"] == "active"
    assert body["owner"]["login"] == "owner"
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
            "workshop_code": "ATLAS",
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
    assert [row["code"] for row in listed.json()] == ["atlas"]
    assert detail.status_code == 200
    assert detail.json()["owner"]["login"] == "owner"


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
            **_provision_payload(code="overview-a"),
            "owner": {
                **_provision_payload()["owner"],
                "login": "owner-a",
                "phone": "+998903030301",
            },
        },
    )
    second = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={
            **_provision_payload(code="overview-b"),
            "owner": {
                **_provision_payload()["owner"],
                "login": "owner-b",
                "phone": "+998903030302",
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
    assert overview.json() == {
        "workshops_total": 2,
        "workshops_active": 1,
        "workshops_blocked": 1,
        "branches_total": 2,
        "clients_total": 1,
        "platform_users_active": 1,
    }


async def test_platform_provision_rejects_non_canonical_working_hours(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)

    missing_days = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={
            **_provision_payload(code="bad-hours"),
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
            **_provision_payload(code="bad-range"),
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


async def test_block_and_unblock_workshop_revoke_staff_sessions_but_not_client_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token = await _platform_access_token(client, db_session)
    provisioned = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(access_token),
        json={**_provision_payload(code="blockable"), "temp_password": "OwnerTemp123"},
    )
    assert provisioned.status_code == 201
    workshop_id = provisioned.json()["workshop"]["id"]
    workshop_uuid = uuid.UUID(workshop_id)
    owner_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": "blockable",
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
            "workshop_code": "blockable",
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
            "workshop_code": "blockable",
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
    assert {row["definition"]["name"] for row in jobs.json()} == {
        "cleanup-expired-sessions",
        "daily-low-stock-summary",
    }
    assert repeated_jobs.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(JobDefinition)) == 2
    assert run.status_code == 200
    assert run.json()["status"] == "ok"
    assert run.json()["brief_log"] == "Pruned 0 expired sessions"
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
