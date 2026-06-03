import uuid

from app.models.support import ActionLog, StatusChangeLog
from app.services.seed import seed_workshop_with_owner
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _owner_login(client: AsyncClient, db_session: AsyncSession) -> tuple[str, str, str]:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    response = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": workshop.code,
            "login": "owner",
            "password": "Owner123",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"], str(branch.id), workshop.code


async def test_owner_creates_staff_with_initial_grants_and_staff_gets_branch_context(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id, workshop_code = await _owner_login(client, db_session)

    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Cutter One",
            "phone": "+998905050505",
            "login": "cutter",
            "home_branch_id": branch_id,
            "temp_password": "StaffTemp123",
            "grants": [{"permission": "manage_orders", "branch_id": branch_id}],
        },
    )
    staff_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": workshop_code,
            "login": "cutter",
            "password": "StaffTemp123",
        },
    )
    staff_access = staff_login.json()["access_token"]
    changed = await client.post(
        "/api/v1/auth/password/change",
        headers=_auth(staff_access),
        json={"current_password": "StaffTemp123", "new_password": "StaffNew123"},
    )
    context = await client.get("/api/v1/workshop/branch-context", headers=_auth(staff_access))

    assert created.status_code == 201
    assert created.json()["user"]["grants"] == [
        {"permission": "manage_orders", "branch_id": branch_id}
    ]
    assert created.json()["temp_password"] == "StaffTemp123"
    assert staff_login.status_code == 200
    assert changed.status_code == 204
    assert context.status_code == 200
    assert context.json()["branches"] == [
        {
            "id": branch_id,
            "name": "Yunusobod",
            "address": "Tashkent, Yunusobod",
            "phone": "+998902222222",
            "status": "active",
            "closed_reason": None,
            "permissions": ["manage_orders"],
        }
    ]


async def test_grant_replacement_takes_effect_on_staff_next_request(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id, workshop_code = await _owner_login(client, db_session)
    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Zero Grant",
            "phone": "+998906060606",
            "login": "zerogrant",
            "temp_password": "StaffTemp123",
            "grants": [],
        },
    )
    user_id = created.json()["user"]["id"]
    staff_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": workshop_code,
            "login": "zerogrant",
            "password": "StaffTemp123",
        },
    )
    staff_access = staff_login.json()["access_token"]
    await client.post(
        "/api/v1/auth/password/change",
        headers=_auth(staff_access),
        json={"current_password": "StaffTemp123", "new_password": "StaffNew123"},
    )
    before = await client.get("/api/v1/workshop/branch-context", headers=_auth(staff_access))
    replaced = await client.put(
        f"/api/v1/workshop/users/{user_id}/grants",
        headers=_auth(owner_access),
        json={"grants": [{"permission": "process_production", "branch_id": branch_id}]},
    )
    after = await client.get("/api/v1/workshop/branch-context", headers=_auth(staff_access))

    assert before.status_code == 200
    assert before.json()["branches"] == []
    assert replaced.status_code == 200
    assert replaced.json()["grants"] == [
        {"permission": "process_production", "branch_id": branch_id}
    ]
    assert after.status_code == 200
    assert after.json()["branches"][0]["permissions"] == ["process_production"]


async def test_owner_resets_blocks_unblocks_and_revokes_staff_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, _, workshop_code = await _owner_login(client, db_session)
    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Office Staff",
            "phone": "+998907070707",
            "login": "office",
            "temp_password": "StaffTemp123",
        },
    )
    user_id = created.json()["user"]["id"]
    user_uuid = uuid.UUID(user_id)
    first_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={"workshop_code": workshop_code, "login": "office", "password": "StaffTemp123"},
    )
    first_access = first_login.json()["access_token"]
    await client.post(
        "/api/v1/auth/password/change",
        headers=_auth(first_access),
        json={"current_password": "StaffTemp123", "new_password": "StaffNew123"},
    )
    second_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={"workshop_code": workshop_code, "login": "office", "password": "StaffNew123"},
    )
    sessions = await client.get(
        f"/api/v1/workshop/users/{user_id}/sessions",
        headers=_auth(owner_access),
    )
    delete_one = await client.delete(
        f"/api/v1/workshop/users/{user_id}/sessions/{second_login.json()['me']['session_id']}",
        headers=_auth(owner_access),
    )
    reset = await client.post(
        f"/api/v1/workshop/users/{user_id}/reset-password",
        headers=_auth(owner_access),
    )
    blocked = await client.post(
        f"/api/v1/workshop/users/{user_id}/block",
        headers=_auth(owner_access),
        json={"reason": "Left company"},
    )
    blocked_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": workshop_code,
            "login": "office",
            "password": reset.json()["temp_password"],
        },
    )
    unblocked = await client.post(
        f"/api/v1/workshop/users/{user_id}/unblock",
        headers=_auth(owner_access),
    )
    unblocked_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": workshop_code,
            "login": "office",
            "password": reset.json()["temp_password"],
        },
    )
    action_count = await db_session.scalar(
        select(func.count()).select_from(ActionLog).where(ActionLog.entity_id == user_uuid)
    )
    status_logs = (
        await db_session.scalars(
            select(StatusChangeLog).where(StatusChangeLog.entity_id == user_uuid)
        )
    ).all()

    assert sessions.status_code == 200
    assert len(sessions.json()["sessions"]) == 2
    assert delete_one.status_code == 204
    assert reset.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=_auth(first_access))).status_code == 401
    assert blocked.status_code == 200
    assert blocked_login.status_code == 403
    assert blocked_login.json()["code"] == "account_blocked"
    assert unblocked.status_code == 200
    assert unblocked_login.status_code == 200
    assert action_count == 5
    assert [(row.from_status, row.to_status) for row in status_logs] == [
        ("active", "blocked"),
        ("blocked", "active"),
    ]


async def test_non_owner_staff_cannot_manage_users(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, _, workshop_code = await _owner_login(client, db_session)
    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Staff",
            "phone": "+998908080808",
            "login": "staff",
            "temp_password": "StaffTemp123",
        },
    )
    staff_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={"workshop_code": workshop_code, "login": "staff", "password": "StaffTemp123"},
    )
    staff_access = staff_login.json()["access_token"]
    await client.post(
        "/api/v1/auth/password/change",
        headers=_auth(staff_access),
        json={"current_password": "StaffTemp123", "new_password": "StaffNew123"},
    )

    response = await client.get("/api/v1/workshop/users", headers=_auth(staff_access))

    assert created.status_code == 201
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
