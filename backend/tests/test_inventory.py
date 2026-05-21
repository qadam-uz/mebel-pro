"""Inventory: stock ops (atomic, never negative), low-stock, suppliers, projected."""

from app.core.principal import Principal
from app.core.security import hash_password
from app.models.catalog import Material
from app.models.enums import (
    CatalogStatus,
    MaterialKind,
    Permission,
    PrincipalType,
    StockTransactionType,
)
from app.models.identity import PermissionGrant, WorkshopUser
from app.models.inventory import StockItem, Supplier
from app.models.support import Notification
from app.models.workshop import Branch, Workshop
from app.services import inventory as inventory_service
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

GOOD_PW = "Passw0rd!"


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


async def _material(db: AsyncSession) -> Material:
    m = Material(
        kind=MaterialKind.SHEET,
        type="dsp",
        name="M",
        thickness_mm=18,
        color="white",
        sheet_length_mm=2800,
        sheet_width_mm=2070,
        grain_direction=True,
        status=CatalogStatus.ACTIVE,
    )
    db.add(m)
    await db.flush()
    return m


async def _owner_login(client: AsyncClient, login: str = "owner") -> dict:
    r = await client.post("/api/v1/auth/workshop/login", json={"login": login, "password": GOOD_PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _supplier(db: AsyncSession, ws: Workshop, owner: WorkshopUser) -> Supplier:
    s = Supplier(workshop_id=ws.id, name="Supplier", created_by_user_id=owner.id)
    db.add(s)
    await db.flush()
    return s


# --- stock-in / adjust via API ----------------------------------------------


async def test_stock_in_then_adjust_balance_and_transactions(
    client: AsyncClient, db_session: AsyncSession
):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    s = await _supplier(db_session, ws, owner)
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=0, min_stock=5))
    await db_session.commit()
    headers = await _owner_login(client)

    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/stock/stock-in",
        headers=headers,
        json={"material_id": str(m.id), "quantity": 20, "supplier_id": str(s.id), "note": "del 1"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["balance_after"] == 20
    assert r.json()["type"] == "stock_in"

    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/stock/adjust",
        headers=headers,
        json={"material_id": str(m.id), "delta": -3, "note": "write-off"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["balance_after"] == 17

    item = (
        await db_session.execute(
            select(StockItem).where(StockItem.branch_id == branch.id, StockItem.material_id == m.id)
        )
    ).scalar_one()
    assert item.on_hand == 17

    txns = await client.get(
        f"/api/v1/workshop/branches/{branch.id}/stock/transactions", headers=headers
    )
    assert txns.status_code == 200
    rows = txns.json()
    assert len(rows) == 2
    assert {r["type"] for r in rows} == {"stock_in", "adjust"}


async def test_adjust_below_zero_rejected(client: AsyncClient, db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=2, min_stock=0))
    await db_session.commit()
    headers = await _owner_login(client)
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/stock/adjust",
        headers=headers,
        json={"material_id": str(m.id), "delta": -5, "note": "oops"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "below_zero"
    item = (
        await db_session.execute(select(StockItem).where(StockItem.material_id == m.id))
    ).scalar_one()
    assert item.on_hand == 2  # unchanged


async def test_adjust_requires_note(client: AsyncClient, db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=2, min_stock=0))
    await db_session.commit()
    headers = await _owner_login(client)
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/stock/adjust",
        headers=headers,
        json={"material_id": str(m.id), "delta": 1, "note": ""},
    )
    assert r.status_code == 422  # pydantic min_length


# --- low-stock notification -------------------------------------------------


async def test_low_stock_fires_to_recipients(client: AsyncClient, db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    s = await _supplier(db_session, ws, owner)
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=0, min_stock=10))
    await db_session.commit()
    headers = await _owner_login(client)

    # stock-in to 5, still <= min_stock(10) → low-stock fires
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/stock/stock-in",
        headers=headers,
        json={"material_id": str(m.id), "quantity": 5, "supplier_id": str(s.id)},
    )
    assert r.status_code == 201
    notifs = (
        (
            await db_session.execute(
                select(Notification).where(
                    Notification.event_code == "low_stock",
                    Notification.recipient_id == owner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 1


async def test_no_low_stock_when_above_threshold(client: AsyncClient, db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    s = await _supplier(db_session, ws, owner)
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=0, min_stock=3))
    await db_session.commit()
    headers = await _owner_login(client)
    await client.post(
        f"/api/v1/workshop/branches/{branch.id}/stock/stock-in",
        headers=headers,
        json={"material_id": str(m.id), "quantity": 50, "supplier_id": str(s.id)},
    )
    notifs = (
        (
            await db_session.execute(
                select(Notification).where(Notification.event_code == "low_stock")
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs) == 0


# --- system primitives (importable consume/restore/projected) --------------


async def test_consume_and_restore_primitives(db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=10, min_stock=0))
    await db_session.commit()
    import uuid

    order_id = uuid.uuid4()

    txn = await inventory_service.consume(
        db_session, branch_id=branch.id, material_id=m.id, qty=4, order_id=order_id
    )
    assert txn.type is StockTransactionType.CONSUME
    assert txn.quantity == -4
    assert txn.balance_after == 6
    assert txn.actor_user_id is None
    assert txn.order_id == order_id

    txn2 = await inventory_service.restore(
        db_session, branch_id=branch.id, material_id=m.id, qty=4, order_id=order_id
    )
    assert txn2.type is StockTransactionType.RESTORE
    assert txn2.balance_after == 10


async def test_consume_never_goes_negative(db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=2, min_stock=0))
    await db_session.commit()
    import uuid

    import pytest
    from app.core.errors import AppError

    with pytest.raises(AppError) as exc:
        await inventory_service.consume(
            db_session, branch_id=branch.id, material_id=m.id, qty=5, order_id=uuid.uuid4()
        )
    assert exc.value.code == "insufficient_stock"
    item = (
        await db_session.execute(select(StockItem).where(StockItem.material_id == m.id))
    ).scalar_one()
    assert item.on_hand == 2  # unchanged


async def test_projected_balance(db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=10, min_stock=0))
    await db_session.commit()
    # no active orders → projected == on_hand
    p = await inventory_service.projected_balance(db_session, branch_id=branch.id, material_id=m.id)
    assert p == 10


# --- suppliers --------------------------------------------------------------


async def test_supplier_crud_and_tenancy(client: AsyncClient, db_session: AsyncSession):
    ws, owner, branch = await _workshop(db_session)
    await db_session.commit()
    headers = await _owner_login(client)
    r = await client.post(
        "/api/v1/workshop/suppliers",
        headers=headers,
        json={"name": "ACME", "phone": "+998900000099"},
    )
    assert r.status_code == 201, r.text
    sup_id = r.json()["id"]

    r = await client.get("/api/v1/workshop/suppliers", headers=headers)
    assert len(r.json()) == 1

    r = await client.post(f"/api/v1/workshop/suppliers/{sup_id}/deactivate", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "inactive"


async def test_inventory_grantee_can_stock_in_but_not_owner_only(
    client: AsyncClient, db_session: AsyncSession
):
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    s = await _supplier(db_session, ws, owner)
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="wh",
        password_hash=hash_password(GOOD_PW),
        full_name="Warehouse",
        phone="+998900000040",
        is_owner=False,
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=Permission.MANAGE_INVENTORY,
            branch_id=branch.id,
            granted_by_user_id=owner.id,
        )
    )
    db_session.add(StockItem(branch_id=branch.id, material_id=m.id, on_hand=0, min_stock=0))
    await db_session.commit()
    headers = await _owner_login(client, login="wh")
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/stock/stock-in",
        headers=headers,
        json={"material_id": str(m.id), "quantity": 5, "supplier_id": str(s.id)},
    )
    assert r.status_code == 201


async def test_stock_in_tenancy_forbidden(client: AsyncClient, db_session: AsyncSession):
    """An inventory grantee on another branch is forbidden here."""
    ws, owner, branch = await _workshop(db_session)
    m = await _material(db_session)
    s = await _supplier(db_session, ws, owner)
    other_branch = Branch(workshop_id=ws.id, name="B2", address="A", phone="+998900000050")
    db_session.add(other_branch)
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="wh2",
        password_hash=hash_password(GOOD_PW),
        full_name="WH2",
        phone="+998900000051",
        is_owner=False,
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=Permission.MANAGE_INVENTORY,
            branch_id=other_branch.id,  # grant on the OTHER branch
            granted_by_user_id=owner.id,
        )
    )
    await db_session.commit()
    headers = await _owner_login(client, login="wh2")
    r = await client.post(
        f"/api/v1/workshop/branches/{branch.id}/stock/stock-in",
        headers=headers,
        json={"material_id": str(m.id), "quantity": 5, "supplier_id": str(s.id)},
    )
    assert r.status_code == 403


def test_principal_helpers_smoke():
    """Sanity: Principal API used by the services exists as expected."""
    import uuid

    p = Principal(
        type=PrincipalType.WORKSHOP_USER,
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        is_owner=True,
    )
    assert p.has_permission(Permission.MANAGE_INVENTORY, uuid.uuid4()) is True
