import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.models.enums import MaterialKind, PanelMaterialType
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.inventory.contracts import StockItem
from app.modules.support.contracts import ActionLog, StatusChangeLog
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import default_working_hours, seed_workshop_with_owner


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


async def _ready_staff_access(
    client: AsyncClient,
    *,
    workshop_code: str,
    login: str,
    password: str = "StaffTemp123",
    new_password: str = "StaffNew123",
) -> str:
    staff_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": workshop_code,
            "login": login,
            "password": password,
        },
    )
    assert staff_login.status_code == 200
    staff_access = staff_login.json()["access_token"]
    changed = await client.post(
        "/api/v1/auth/password/change",
        headers=_auth(staff_access),
        json={"current_password": password, "new_password": new_password},
    )
    assert changed.status_code == 204
    return str(staff_access)


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


async def test_staff_branch_context_includes_multiple_active_grant_branches(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id, workshop_code = await _owner_login(client, db_session)
    second_branch = await client.post(
        "/api/v1/workshop/branches",
        headers=_auth(owner_access),
        json={
            "name": "Chilonzor",
            "address": "Tashkent, Chilonzor",
            "phone": "+998904040404",
            "latitude": "41.28",
            "longitude": "69.20",
            "working_hours": default_working_hours(),
        },
    )
    second_branch_id = second_branch.json()["id"]
    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Multi Grant",
            "phone": "+998905151515",
            "login": "multigrant",
            "home_branch_id": branch_id,
            "temp_password": "StaffTemp123",
            "grants": [
                {"permission": "manage_orders", "branch_id": branch_id},
                {"permission": "manage_inventory", "branch_id": branch_id},
                {"permission": "process_production", "branch_id": second_branch_id},
            ],
        },
    )
    staff_access = await _ready_staff_access(
        client,
        workshop_code=workshop_code,
        login="multigrant",
    )

    context = await client.get("/api/v1/workshop/branch-context", headers=_auth(staff_access))
    branches = {row["id"]: row for row in context.json()["branches"]}

    assert second_branch.status_code == 201
    assert created.status_code == 201
    assert context.status_code == 200
    assert set(branches) == {branch_id, second_branch_id}
    assert branches[branch_id]["permissions"] == ["manage_inventory", "manage_orders"]
    assert branches[second_branch_id]["permissions"] == ["process_production"]


async def test_staff_branch_context_excludes_inactive_grant_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id, workshop_code = await _owner_login(client, db_session)
    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Inactive Grant",
            "phone": "+998905252525",
            "login": "inactivegrant",
            "home_branch_id": branch_id,
            "temp_password": "StaffTemp123",
            "grants": [{"permission": "manage_inventory", "branch_id": branch_id}],
        },
    )
    staff_access = await _ready_staff_access(
        client,
        workshop_code=workshop_code,
        login="inactivegrant",
    )
    before = await client.get("/api/v1/workshop/branch-context", headers=_auth(staff_access))
    inactive = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/status",
        headers=_auth(owner_access),
        json={"status": "inactive", "reason": "Closed"},
    )
    after = await client.get("/api/v1/workshop/branch-context", headers=_auth(staff_access))

    assert created.status_code == 201
    assert before.status_code == 200
    assert before.json()["branches"][0]["id"] == branch_id
    assert inactive.status_code == 200
    assert inactive.json()["status"] == "inactive"
    assert after.status_code == 200
    assert after.json()["branches"] == []


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
            "home_branch_id": branch_id,
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


async def test_owner_filters_users_and_sees_last_login(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id, workshop_code = await _owner_login(client, db_session)
    second_branch = await client.post(
        "/api/v1/workshop/branches",
        headers=_auth(owner_access),
        json={
            "name": "Sergeli",
            "address": "Tashkent, Sergeli",
            "phone": "+998906262600",
            "latitude": "41.22",
            "longitude": "69.22",
            "working_hours": default_working_hours(),
        },
    )
    assert second_branch.status_code == 201
    second_branch_id = second_branch.json()["id"]
    cutter = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Cutter Filter",
            "phone": "+998906161616",
            "login": "cutterfilter",
            "home_branch_id": branch_id,
            "temp_password": "StaffTemp123",
            "grants": [{"permission": "process_production", "branch_id": branch_id}],
        },
    )
    office = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Office Filter",
            "phone": "+998906262626",
            "login": "officefilter",
            "home_branch_id": second_branch_id,
            "temp_password": "StaffTemp123",
            "grants": [],
        },
    )
    staff_login = await client.post(
        "/api/v1/auth/workshop/login",
        json={
            "workshop_code": workshop_code,
            "login": "cutterfilter",
            "password": "StaffTemp123",
        },
    )
    filtered = await client.get(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        params={"search": "cut", "branch_id": branch_id, "status": "active"},
    )
    no_branch_match = await client.get(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        params={"search": "office", "branch_id": branch_id},
    )

    assert cutter.status_code == 201
    assert cutter.json()["user"]["last_login_at"] is None
    assert office.status_code == 201
    assert staff_login.status_code == 200
    assert filtered.status_code == 200
    assert [row["login"] for row in filtered.json()] == ["cutterfilter"]
    assert filtered.json()[0]["last_login_at"] is not None
    assert no_branch_match.status_code == 200
    assert no_branch_match.json() == []


async def test_owner_branch_response_includes_operational_counts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id, _ = await _owner_login(client, db_session)
    manufacturer = Manufacturer(name="Count Maker", country="UZ")
    db_session.add(manufacturer)
    await db_session.flush()
    material = Material(
        kind=MaterialKind.PANEL,
        manufacturer_id=manufacturer.id,
        type=PanelMaterialType.DSP,
        name="Count Panel",
        thickness_mm=Decimal("18"),
        color="White",
        decor_code="COUNT-P",
        panel_length_mm=2800,
        panel_width_mm=2070,
        grain_direction=False,
    )
    db_session.add(material)
    await db_session.flush()
    db_session.add_all(
        [
            BranchMaterial(branch_id=uuid.UUID(branch_id), material_id=material.id, price_tiyin=1),
            StockItem(
                branch_id=uuid.UUID(branch_id),
                material_id=material.id,
                on_hand=1,
                min_stock=2,
                updated_at=datetime.now(UTC),
            ),
        ]
    )
    staff = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Count Staff",
            "phone": "+998906363636",
            "login": "countstaff",
            "home_branch_id": branch_id,
            "temp_password": "StaffTemp123",
            "grants": [{"permission": "manage_orders", "branch_id": branch_id}],
        },
    )
    branches = await client.get("/api/v1/workshop/branches", headers=_auth(owner_access))

    assert staff.status_code == 201
    assert branches.status_code == 200
    [branch] = branches.json()
    assert branch["material_count"] == 1
    assert branch["low_stock_count"] == 1
    assert branch["staff_count"] == 2


async def test_owner_updates_staff_profile_fields(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id, _ = await _owner_login(client, db_session)
    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Editable Staff",
            "phone": "+998906464646",
            "login": "editable",
            "home_branch_id": branch_id,
            "temp_password": "StaffTemp123",
            "grants": [],
        },
    )
    user_id = created.json()["user"]["id"]
    updated = await client.patch(
        f"/api/v1/workshop/users/{user_id}",
        headers=_auth(owner_access),
        json={
            "full_name": "Edited Staff",
            "phone": "+998906565656",
            "login": "edited",
        },
    )
    null_home_branch = await client.patch(
        f"/api/v1/workshop/users/{user_id}",
        headers=_auth(owner_access),
        json={"home_branch_id": None},
    )
    duplicate = await client.patch(
        f"/api/v1/workshop/users/{user_id}",
        headers=_auth(owner_access),
        json={"login": "owner"},
    )

    assert created.status_code == 201
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Edited Staff"
    assert updated.json()["phone"] == "+998906565656"
    assert updated.json()["login"] == "edited"
    assert updated.json()["home_branch_id"] == branch_id
    assert null_home_branch.status_code == 422
    assert null_home_branch.json()["code"] == "home_branch_required"
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "login_exists"


async def test_owner_resets_blocks_unblocks_and_revokes_staff_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, branch_id, workshop_code = await _owner_login(client, db_session)
    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Office Staff",
            "phone": "+998907070707",
            "login": "office",
            "home_branch_id": branch_id,
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
    owner_access, branch_id, workshop_code = await _owner_login(client, db_session)
    created = await client.post(
        "/api/v1/workshop/users",
        headers=_auth(owner_access),
        json={
            "full_name": "Staff",
            "phone": "+998908080808",
            "login": "staff",
            "home_branch_id": branch_id,
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
