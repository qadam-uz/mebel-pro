"""Workshop administration: provisioning, profile, branches, block/unblock."""

import uuid

from app.core.security import hash_password
from app.models.catalog import BranchPricing
from app.models.enums import Permission, PrincipalType
from app.models.identity import PermissionGrant, PlatformUser, Session, WorkshopUser
from app.models.workshop import Branch, Workshop
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

GOOD_PW = "Passw0rd!"


async def _platform_login(client: AsyncClient, db: AsyncSession, login: str = "op") -> dict:
    db.add(
        PlatformUser(
            login=login,
            password_hash=hash_password(GOOD_PW),
            full_name="Operator",
            phone="+998900000000",
            force_password_change=False,
        )
    )
    await db.commit()
    r = await client.post("/api/v1/auth/platform/login", json={"login": login, "password": GOOD_PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _make_workshop(db: AsyncSession, name: str = "WS") -> tuple[Workshop, WorkshopUser]:
    ws = Workshop(name=name, phone="+998900000001")
    db.add(ws)
    await db.flush()
    owner = WorkshopUser(
        workshop_id=ws.id,
        login="owner",
        password_hash=hash_password(GOOD_PW),
        full_name="Owner",
        phone="+998900000002",
        is_owner=True,
        force_password_change=False,
    )
    db.add(owner)
    await db.flush()
    ws.owner_user_id = owner.id
    await db.commit()
    return ws, owner


async def _owner_login(client: AsyncClient, login: str = "owner") -> dict:
    r = await client.post("/api/v1/auth/workshop/login", json={"login": login, "password": GOOD_PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- provisioning -----------------------------------------------------------


async def test_provision_creates_workshop_and_owner_atomically(
    client: AsyncClient, db_session: AsyncSession
):
    headers = await _platform_login(client, db_session)
    r = await client.post(
        "/api/v1/admin/workshops",
        headers=headers,
        json={
            "name": "Mebel Star",
            "phone": "+998901112233",
            "owner_full_name": "Boss",
            "owner_login": "boss",
            "owner_phone": "+998901112244",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["owner_login"] == "boss"
    assert len(body["temp_password"]) >= 8
    ws_id = uuid.UUID(body["workshop"]["id"])

    ws = await db_session.get(Workshop, ws_id)
    assert ws is not None
    owner = await db_session.get(WorkshopUser, uuid.UUID(body["owner_id"]))
    assert owner is not None
    assert owner.is_owner is True
    assert owner.force_password_change is True
    assert ws.owner_user_id == owner.id


async def test_provision_atomicity_no_partial_workshop(
    client: AsyncClient, db_session: AsyncSession
):
    """A weak manual owner password aborts before either row persists."""
    headers = await _platform_login(client, db_session)
    before = len((await db_session.execute(select(Workshop))).scalars().all())
    r = await client.post(
        "/api/v1/admin/workshops",
        headers=headers,
        json={
            "name": "Doomed",
            "phone": "+998901112233",
            "owner_full_name": "Boss",
            "owner_login": "boss",
            "owner_phone": "+998901112244",
            "owner_password": "weak",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "weak_password"
    after = len((await db_session.execute(select(Workshop))).scalars().all())
    assert after == before  # nothing persisted


async def test_provision_requires_platform_user(client: AsyncClient, db_session: AsyncSession):
    ws, _ = await _make_workshop(db_session)
    headers = await _owner_login(client)
    r = await client.post(
        "/api/v1/admin/workshops",
        headers=headers,
        json={
            "name": "X",
            "phone": "+998901112233",
            "owner_full_name": "B",
            "owner_login": "b",
            "owner_phone": "+998901112244",
        },
    )
    assert r.status_code == 403


# --- block / unblock --------------------------------------------------------


async def test_block_workshop_revokes_sessions_unblock_does_not_restore(
    client: AsyncClient, db_session: AsyncSession
):
    ws, owner = await _make_workshop(db_session)
    owner_headers = await _owner_login(client)
    op_headers = await _platform_login(client, db_session, login="op2")

    # owner has a live session
    sess = (
        (
            await db_session.execute(
                select(Session).where(
                    Session.principal_type == PrincipalType.WORKSHOP_USER,
                    Session.principal_id == owner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(sess) == 1

    r = await client.post(
        f"/api/v1/admin/workshops/{ws.id}/block",
        headers=op_headers,
        json={"reason": "fraud investigation"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"

    # owner's session is gone
    sess = (
        (
            await db_session.execute(
                select(Session).where(
                    Session.principal_type == PrincipalType.WORKSHOP_USER,
                    Session.principal_id == owner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(sess) == 0

    # owner's old token now rejected
    me = await client.get("/api/v1/auth/me", headers=owner_headers)
    assert me.status_code == 401

    # unblock does not restore sessions
    r = await client.post(
        f"/api/v1/admin/workshops/{ws.id}/unblock",
        headers=op_headers,
        json={"reason": "cleared"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    sess = (
        (
            await db_session.execute(
                select(Session).where(
                    Session.principal_type == PrincipalType.WORKSHOP_USER,
                    Session.principal_id == owner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(sess) == 0


# --- profile ----------------------------------------------------------------


async def test_owner_edits_own_workshop_profile(client: AsyncClient, db_session: AsyncSession):
    ws, _ = await _make_workshop(db_session)
    headers = await _owner_login(client)
    r = await client.patch(
        "/api/v1/workshop/settings/profile",
        headers=headers,
        json={"name": "Renamed", "address": "New St"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Renamed"
    assert r.json()["address"] == "New St"


async def test_operator_edits_workshop_profile_for_incident(
    client: AsyncClient, db_session: AsyncSession
):
    ws, _ = await _make_workshop(db_session)
    headers = await _platform_login(client, db_session)
    r = await client.patch(
        f"/api/v1/admin/workshops/{ws.id}/profile",
        headers=headers,
        json={"phone": "+998905556677"},
    )
    assert r.status_code == 200
    assert r.json()["phone"] == "+998905556677"


# --- branches ---------------------------------------------------------------


async def test_create_branch_creates_pricing_row(client: AsyncClient, db_session: AsyncSession):
    ws, _ = await _make_workshop(db_session)
    headers = await _owner_login(client)
    r = await client.post(
        "/api/v1/workshop/branches",
        headers=headers,
        json={"name": "Yunusobod", "address": "Tashkent", "phone": "+998900000003"},
    )
    assert r.status_code == 201, r.text
    branch_id = uuid.UUID(r.json()["id"])
    pricing = await db_session.get(BranchPricing, branch_id)
    assert pricing is not None
    assert pricing.cutting_model is None


async def test_branch_writes_owner_only(client: AsyncClient, db_session: AsyncSession):
    ws, owner = await _make_workshop(db_session)
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="staff",
        password_hash=hash_password(GOOD_PW),
        full_name="Staff",
        phone="+998900000009",
        is_owner=False,
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.commit()
    headers = await _owner_login(client, login="staff")
    r = await client.post(
        "/api/v1/workshop/branches",
        headers=headers,
        json={"name": "B", "address": "A", "phone": "+998900000004"},
    )
    assert r.status_code == 403


async def test_branch_status_change_clears_reason(client: AsyncClient, db_session: AsyncSession):
    ws, _ = await _make_workshop(db_session)
    db_session.add(b := Branch(workshop_id=ws.id, name="B", address="A", phone="+998900000005"))
    await db_session.commit()
    headers = await _owner_login(client)

    r = await client.post(
        f"/api/v1/workshop/branches/{b.id}/status",
        headers=headers,
        json={"status": "temporarily_closed", "closed_reason": "holiday"},
    )
    assert r.status_code == 200
    assert r.json()["closed_reason"] == "holiday"

    r = await client.post(
        f"/api/v1/workshop/branches/{b.id}/status",
        headers=headers,
        json={"status": "active"},
    )
    assert r.status_code == 200
    assert r.json()["closed_reason"] is None


async def test_branch_tenancy_isolation(client: AsyncClient, db_session: AsyncSession):
    """An owner cannot read or edit another workshop's branch."""
    ws_a, _ = await _make_workshop(db_session, name="A")
    ws_b = Workshop(name="B", phone="+998900000010")
    db_session.add(ws_b)
    await db_session.flush()
    other_owner = WorkshopUser(
        workshop_id=ws_b.id,
        login="owner2",
        password_hash=hash_password(GOOD_PW),
        full_name="Other",
        phone="+998900000011",
        is_owner=True,
        force_password_change=False,
    )
    db_session.add(other_owner)
    db_session.add(
        b_other := Branch(workshop_id=ws_b.id, name="OtherB", address="X", phone="+998900000012")
    )
    await db_session.flush()
    ws_b.owner_user_id = other_owner.id
    await db_session.commit()

    headers = await _owner_login(client)  # logs in ws_a's owner
    r = await client.get(f"/api/v1/workshop/branches/{b_other.id}", headers=headers)
    assert r.status_code == 404


async def test_staff_branch_visibility_scoped_by_grant(
    client: AsyncClient, db_session: AsyncSession
):
    ws, owner = await _make_workshop(db_session)
    db_session.add(b1 := Branch(workshop_id=ws.id, name="B1", address="A", phone="+998900000006"))
    db_session.add(Branch(workshop_id=ws.id, name="B2", address="A", phone="+998900000007"))
    await db_session.flush()
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="staff",
        password_hash=hash_password(GOOD_PW),
        full_name="Staff",
        phone="+998900000008",
        is_owner=False,
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=Permission.MANAGE_INVENTORY,
            branch_id=b1.id,
            granted_by_user_id=owner.id,
        )
    )
    await db_session.commit()

    staff_headers = await _owner_login(client, login="staff")
    r = await client.get("/api/v1/workshop/branches", headers=staff_headers)
    assert r.status_code == 200
    names = {row["name"] for row in r.json()}
    assert names == {"B1"}  # only the granted branch

    # owner sees both
    owner_headers = await _owner_login(client)
    r = await client.get("/api/v1/workshop/branches", headers=owner_headers)
    assert {row["name"] for row in r.json()} == {"B1", "B2"}
