"""Catalog: platform materials, branch selection, branch pricing."""

from app.core.security import hash_password
from app.models.catalog import Material
from app.models.enums import CatalogStatus, MaterialKind, Permission
from app.models.identity import PermissionGrant, PlatformUser, WorkshopUser
from app.models.inventory import StockItem
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
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _workshop(db: AsyncSession) -> tuple[Workshop, WorkshopUser, Branch]:
    ws = Workshop(name="WS", phone="+998900000001")
    db.add(ws)
    await db.flush()
    branch = Branch(workshop_id=ws.id, name="B", address="A", phone="+998900000002")
    db.add(branch)
    owner = WorkshopUser(
        workshop_id=ws.id,
        login="owner",
        password_hash=hash_password(GOOD_PW),
        full_name="Owner",
        phone="+998900000003",
        is_owner=True,
        force_password_change=False,
    )
    db.add(owner)
    await db.flush()
    ws.owner_user_id = owner.id
    await db.commit()
    return ws, owner, branch


async def _owner_login(client: AsyncClient, login: str = "owner") -> dict:
    r = await client.post("/api/v1/auth/workshop/login", json={"login": login, "password": GOOD_PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sheet_payload(**over) -> dict:
    base = {
        "kind": "sheet",
        "type": "dsp",
        "name": "Kronospan White 18",
        "thickness_mm": 18,
        "color": "white",
        "sheet_length_mm": 2800,
        "sheet_width_mm": 2070,
        "grain_direction": True,
    }
    base.update(over)
    return base


# --- platform materials -----------------------------------------------------


async def test_create_sheet_material(client: AsyncClient, db_session: AsyncSession):
    headers = await _platform_login(client, db_session)
    r = await client.post("/api/v1/admin/materials", headers=headers, json=_sheet_payload())
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "sheet"


async def test_sheet_length_must_be_ge_width(client: AsyncClient, db_session: AsyncSession):
    headers = await _platform_login(client, db_session)
    r = await client.post(
        "/api/v1/admin/materials",
        headers=headers,
        json=_sheet_payload(sheet_length_mm=2000, sheet_width_mm=2070),
    )
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_material"


async def test_sheet_requires_type_and_grain(client: AsyncClient, db_session: AsyncSession):
    headers = await _platform_login(client, db_session)
    r = await client.post(
        "/api/v1/admin/materials",
        headers=headers,
        json=_sheet_payload(type=None),
    )
    assert r.status_code == 400


async def test_edge_rejects_sheet_fields(client: AsyncClient, db_session: AsyncSession):
    headers = await _platform_login(client, db_session)
    r = await client.post(
        "/api/v1/admin/materials",
        headers=headers,
        json={
            "kind": "edge",
            "name": "PVC 2mm white",
            "thickness_mm": 2.0,
            "color": "white",
            "sheet_length_mm": 100,
        },
    )
    assert r.status_code == 400


async def test_create_edge_material_ok(client: AsyncClient, db_session: AsyncSession):
    headers = await _platform_login(client, db_session)
    r = await client.post(
        "/api/v1/admin/materials",
        headers=headers,
        json={"kind": "edge", "name": "PVC 2mm", "thickness_mm": 2.0, "color": "white"},
    )
    assert r.status_code == 201, r.text


async def test_materials_owner_only_platform(client: AsyncClient, db_session: AsyncSession):
    await _workshop(db_session)
    headers = await _owner_login(client)
    r = await client.post("/api/v1/admin/materials", headers=headers, json=_sheet_payload())
    assert r.status_code == 403


async def test_deactivate_material_hidden_from_active_picker(
    client: AsyncClient, db_session: AsyncSession
):
    headers = await _platform_login(client, db_session)
    r = await client.post("/api/v1/admin/materials", headers=headers, json=_sheet_payload())
    mat_id = r.json()["id"]
    await client.post(f"/api/v1/admin/materials/{mat_id}/deactivate", headers=headers)
    # workshop picker only shows active
    await _workshop(db_session)
    owner_headers = await _owner_login(client)
    r = await client.get("/api/v1/workshop/materials", headers=owner_headers)
    assert r.status_code == 200
    assert all(m["id"] != mat_id for m in r.json())


# --- branch material selection ----------------------------------------------


async def _active_material(db: AsyncSession, kind: MaterialKind = MaterialKind.SHEET) -> Material:
    m = Material(
        kind=kind,
        type="dsp" if kind is MaterialKind.SHEET else None,
        name="M",
        thickness_mm=18,
        color="white",
        sheet_length_mm=2800 if kind is MaterialKind.SHEET else None,
        sheet_width_mm=2070 if kind is MaterialKind.SHEET else None,
        grain_direction=True if kind is MaterialKind.SHEET else None,
        status=CatalogStatus.ACTIVE,
    )
    db.add(m)
    await db.flush()
    return m


async def test_add_branch_material_creates_stock_item(
    client: AsyncClient, db_session: AsyncSession
):
    ws, _, branch = await _workshop(db_session)
    m = await _active_material(db_session)
    await db_session.commit()
    headers = await _owner_login(client)
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/materials",
        headers=headers,
        json={"material_id": str(m.id), "price_tiyin": 5000000, "min_stock": 3},
    )
    assert r.status_code == 201, r.text
    stock = (
        await db_session.execute(
            select(StockItem).where(StockItem.branch_id == branch.id, StockItem.material_id == m.id)
        )
    ).scalar_one()
    assert stock.on_hand == 0
    assert stock.min_stock == 3


async def test_add_inactive_material_rejected(client: AsyncClient, db_session: AsyncSession):
    ws, _, branch = await _workshop(db_session)
    m = await _active_material(db_session)
    m.status = CatalogStatus.INACTIVE
    await db_session.commit()
    headers = await _owner_login(client)
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/materials",
        headers=headers,
        json={"material_id": str(m.id), "price_tiyin": 100, "min_stock": 0},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "material_inactive"


async def test_duplicate_branch_material_rejected(client: AsyncClient, db_session: AsyncSession):
    ws, _, branch = await _workshop(db_session)
    m = await _active_material(db_session)
    await db_session.commit()
    headers = await _owner_login(client)
    payload = {"material_id": str(m.id), "price_tiyin": 100, "min_stock": 0}
    await client.post(
        f"/api/v1/workshop/branches/{branch.id}/materials", headers=headers, json=payload
    )
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/materials", headers=headers, json=payload
    )
    assert r.status_code == 409


async def test_manage_catalog_grantee_can_add(client: AsyncClient, db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _active_material(db_session)
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="cat",
        password_hash=hash_password(GOOD_PW),
        full_name="Cat",
        phone="+998900000020",
        is_owner=False,
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=Permission.MANAGE_CATALOG,
            branch_id=branch.id,
            granted_by_user_id=owner.id,
        )
    )
    await db_session.commit()
    headers = await _owner_login(client, login="cat")
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/materials",
        headers=headers,
        json={"material_id": str(m.id), "price_tiyin": 100, "min_stock": 0},
    )
    assert r.status_code == 201


async def test_staff_without_grant_cannot_add(client: AsyncClient, db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _active_material(db_session)
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="nogrant",
        password_hash=hash_password(GOOD_PW),
        full_name="No",
        phone="+998900000021",
        is_owner=False,
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.commit()
    headers = await _owner_login(client, login="nogrant")
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/materials",
        headers=headers,
        json={"material_id": str(m.id), "price_tiyin": 100, "min_stock": 0},
    )
    assert r.status_code == 403


# --- branch pricing ---------------------------------------------------------


async def test_owner_sets_branch_pricing(client: AsyncClient, db_session: AsyncSession):
    ws, _, branch = await _workshop(db_session)
    # branch created directly, so ensure pricing exists via GET (lazy)
    headers = await _owner_login(client)
    r = await client.put(
        f"/api/v1/workshop/branches/{branch.id}/pricing",
        headers=headers,
        json={
            "cutting_model": "per_sheet",
            "cutting_rate_tiyin": 1500000,
            "edge_banding_rates": {"0.4": 300000, "2.0": 500000},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["cutting_model"] == "per_sheet"
    assert r.json()["edge_banding_rates"]["2.0"] == 500000
    assert r.json()["updated_by_user_id"] is not None


async def test_branch_pricing_owner_only(client: AsyncClient, db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="cat",
        password_hash=hash_password(GOOD_PW),
        full_name="Cat",
        phone="+998900000022",
        is_owner=False,
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.flush()
    # even with manage_catalog, pricing is owner-only
    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=Permission.MANAGE_CATALOG,
            branch_id=branch.id,
            granted_by_user_id=owner.id,
        )
    )
    await db_session.commit()
    headers = await _owner_login(client, login="cat")
    r = await client.put(
        f"/api/v1/workshop/branches/{branch.id}/pricing",
        headers=headers,
        json={"cutting_model": "per_cut", "cutting_rate_tiyin": 100, "edge_banding_rates": {}},
    )
    assert r.status_code == 403


async def test_pricing_tenancy_isolation(client: AsyncClient, db_session: AsyncSession):
    ws_a, _, _ = await _workshop(db_session)
    ws_b = Workshop(name="B", phone="+998900000030")
    db_session.add(ws_b)
    await db_session.flush()
    b_other = Branch(workshop_id=ws_b.id, name="OB", address="X", phone="+998900000031")
    db_session.add(b_other)
    owner_b = WorkshopUser(
        workshop_id=ws_b.id,
        login="ob",
        password_hash=hash_password(GOOD_PW),
        full_name="OB",
        phone="+998900000032",
        is_owner=True,
        force_password_change=False,
    )
    db_session.add(owner_b)
    await db_session.flush()
    ws_b.owner_user_id = owner_b.id
    await db_session.commit()

    headers = await _owner_login(client)  # ws_a owner
    r = await client.put(
        f"/api/v1/workshop/branches/{b_other.id}/pricing",
        headers=headers,
        json={"cutting_model": "per_cut", "cutting_rate_tiyin": 100, "edge_banding_rates": {}},
    )
    assert r.status_code == 404
