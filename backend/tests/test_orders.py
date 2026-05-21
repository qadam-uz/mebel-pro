"""Integration tests for the orders module — placement, pricing, the state
machine, stock seam, optimistic locking, assignment guards, and reads."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.security import hash_password
from app.models.catalog import BranchMaterial, BranchPricing, Material
from app.models.cutting import CuttingResult
from app.models.enums import (
    BranchStatus,
    CatalogStatus,
    CuttingModel,
    MaterialKind,
    MaterialType,
    Permission,
    PrincipalType,
    WorkshopStatus,
)
from app.models.identity import Client, PermissionGrant, WorkshopUser
from app.models.inventory import StockItem
from app.models.sales import Order
from app.models.workshop import Branch, Workshop
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

C = "/api/v1/c"
W = "/api/v1/workshop"

AuthFactory = Callable[[PrincipalType, uuid.UUID], Awaitable[dict[str, str]]]


@dataclass
class World:
    workshop: Workshop
    branch: Branch
    owner: WorkshopUser
    client: Client
    sheet_material: Material
    edge_material: Material
    client_headers: dict[str, str]
    owner_headers: dict[str, str]


async def _build_world(
    db: AsyncSession,
    auth_headers: AuthFactory,
    *,
    cutting_model: CuttingModel = CuttingModel.PER_SHEET,
    cutting_rate: int = 50000,
    edge_rates: dict[str, int] | None = None,
    sheet_price: int = 1_000_000,
    branch_status: BranchStatus = BranchStatus.ACTIVE,
    workshop_status: WorkshopStatus = WorkshopStatus.ACTIVE,
    carry_sheet: bool = True,
    carry_edge: bool = True,
    sheet_on_hand: int = 100,
    edge_on_hand: int = 1000,
) -> World:
    ws = Workshop(name="WS", phone="+998900000001", status=workshop_status)
    db.add(ws)
    await db.flush()
    owner = WorkshopUser(
        workshop_id=ws.id,
        login="owner",
        password_hash=hash_password("Passw0rd!"),
        full_name="Owner",
        phone="+998900000002",
        is_owner=True,
        force_password_change=False,
    )
    db.add(owner)
    await db.flush()
    ws.owner_user_id = owner.id
    branch = Branch(
        workshop_id=ws.id,
        name="Chilonzor",
        address="A",
        phone="+998900000003",
        status=branch_status,
    )
    db.add(branch)
    await db.flush()

    db.add(
        BranchPricing(
            branch_id=branch.id,
            cutting_model=cutting_model,
            cutting_rate_tiyin=cutting_rate,
            edge_banding_rates=edge_rates if edge_rates is not None else {"2.0": 300000},
        )
    )

    sheet = Material(
        kind=MaterialKind.SHEET,
        type=MaterialType.DSP,
        name="DSP 18",
        thickness_mm=18,
        color="white",
        sheet_length_mm=2800,
        sheet_width_mm=2070,
        grain_direction=False,
        status=CatalogStatus.ACTIVE,
    )
    edge = Material(
        kind=MaterialKind.EDGE,
        type=None,
        name="PVC 2.0",
        thickness_mm=2.0,
        color="white",
        status=CatalogStatus.ACTIVE,
    )
    db.add_all([sheet, edge])
    await db.flush()

    if carry_sheet:
        db.add(
            BranchMaterial(
                branch_id=branch.id,
                material_id=sheet.id,
                price_tiyin=sheet_price,
                status=CatalogStatus.ACTIVE,
            )
        )
        db.add(StockItem(branch_id=branch.id, material_id=sheet.id, on_hand=sheet_on_hand))
    if carry_edge:
        db.add(
            BranchMaterial(
                branch_id=branch.id,
                material_id=edge.id,
                price_tiyin=200000,
                status=CatalogStatus.ACTIVE,
            )
        )
        db.add(StockItem(branch_id=branch.id, material_id=edge.id, on_hand=edge_on_hand))

    c = Client(
        telegram_id=int(uuid.uuid4().int % 10**12), phone="+998901112233", first_name="Client"
    )
    db.add(c)
    await db.commit()

    client_headers = await auth_headers(PrincipalType.CLIENT, c.id)
    owner_headers = await auth_headers(PrincipalType.WORKSHOP_USER, owner.id)
    return World(
        workshop=ws,
        branch=branch,
        owner=owner,
        client=c,
        sheet_material=sheet,
        edge_material=edge,
        client_headers=client_headers,
        owner_headers=owner_headers,
    )


async def _make_draft_with_result(
    client: AsyncClient,
    db: AsyncSession,
    world: World,
    headers: dict[str, str],
    *,
    banded: bool = False,
    quantity: int = 4,
) -> uuid.UUID:
    r = await client.post(f"{C}/cutting", headers=headers)
    draft_id = r.json()["id"]
    part: dict = {
        "material_id": str(world.sheet_material.id),
        "material_source": "shop",
        "length_mm": 600,
        "width_mm": 400,
        "quantity": quantity,
    }
    if banded:
        part["edge_top_mm"] = 2.0
        part["edge_bottom_mm"] = 2.0
    await client.put(f"{C}/cutting/{draft_id}", headers=headers, json={"parts": [part]})
    await client.post(f"{C}/cutting/{draft_id}/optimise", headers=headers)
    return uuid.UUID(draft_id)


async def _place(
    client: AsyncClient, world: World, draft_id: uuid.UUID, headers: dict[str, str] | None = None
):
    return await client.post(
        f"{C}/orders",
        headers=headers or world.client_headers,
        json={
            "draft_id": str(draft_id),
            "branch_id": str(world.branch.id),
            "contact_name": "Client",
            "contact_phone": "+998901112233",
        },
    )


def _grant(
    db: AsyncSession, user_id: uuid.UUID, branch_id: uuid.UUID, perm: Permission, by: uuid.UUID
):
    db.add(
        PermissionGrant(
            workshop_user_id=user_id, permission=perm, branch_id=branch_id, granted_by_user_id=by
        )
    )


async def _staff(
    db: AsyncSession,
    world: World,
    *,
    login: str,
    perms: list[Permission],
    home_branch_id: uuid.UUID | None,
) -> WorkshopUser:
    u = WorkshopUser(
        workshop_id=world.workshop.id,
        login=login,
        password_hash=hash_password("Passw0rd!"),
        full_name=login,
        phone="+99890" + str(uuid.uuid4().int % 10**7).zfill(7),
        is_owner=False,
        home_branch_id=home_branch_id,
        force_password_change=False,
    )
    db.add(u)
    await db.flush()
    for p in perms:
        _grant(db, u.id, world.branch.id, p, world.owner.id)
    await db.commit()
    return u


# --- placement + pricing ----------------------------------------------------


async def test_place_order_per_sheet_pricing(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers, cutting_model=CuttingModel.PER_SHEET)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)

    r = await _place(client, world, draft_id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "new"
    assert body["order_number"].startswith("ORD-")

    # find the order to inspect sheets used
    order = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(body["id"])))
    ).scalar_one()
    price = body["price"]
    # cutting = rate * sheets; materials = sheet_price * sheets; edge = 0 (not banded)
    result = await db_session.get(CuttingResult, order.cutting_result_id)
    assert result is not None
    total_sheets = sum(int(v) for v in result.sheets_used_by_material.values())
    assert price["subtotal_cutting_tiyin"] == 50000 * total_sheets
    assert price["subtotal_materials_tiyin"] == 1_000_000 * total_sheets
    assert price["subtotal_edge_banding_tiyin"] == 0
    assert (
        price["total_tiyin"] == price["subtotal_cutting_tiyin"] + price["subtotal_materials_tiyin"]
    )
    # line totals reconstruct the total
    assert sum(i["line_total_tiyin"] for i in body["items"]) == price["total_tiyin"]


async def test_place_order_per_cut_and_edge_pricing(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(
        db_session,
        auth_headers,
        cutting_model=CuttingModel.PER_CUT,
        cutting_rate=1000,
        edge_rates={"2.0": 300000},
    )
    draft_id = await _make_draft_with_result(
        client, db_session, world, world.client_headers, banded=True
    )
    r = await _place(client, world, draft_id)
    assert r.status_code == 201, r.text
    price = r.json()["price"]
    # per_cut: cutting = rate * cut_count (>0). edge subtotal > 0 since banded.
    assert price["subtotal_cutting_tiyin"] > 0
    assert price["subtotal_edge_banding_tiyin"] > 0
    assert (
        price["total_tiyin"]
        == price["subtotal_cutting_tiyin"]
        + price["subtotal_materials_tiyin"]
        + price["subtotal_edge_banding_tiyin"]
    )


async def test_place_order_missing_edge_rate(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers, edge_rates={})  # no rate for 2.0
    draft_id = await _make_draft_with_result(
        client, db_session, world, world.client_headers, banded=True
    )
    r = await _place(client, world, draft_id)
    assert r.status_code == 422 and r.json()["code"] == "missing_edge_rate"


async def test_place_order_missing_cutting_model(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    # wipe the cutting model
    pricing = await db_session.get(BranchPricing, world.branch.id)
    assert pricing is not None
    pricing.cutting_model = None
    await db_session.commit()
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    assert r.status_code == 422 and r.json()["code"] == "missing_cutting_model"


async def test_place_order_branch_closed(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(
        db_session, auth_headers, branch_status=BranchStatus.TEMPORARILY_CLOSED
    )
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    assert r.status_code == 409 and r.json()["code"] == "branch_closed"


async def test_place_order_workshop_blocked(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers, workshop_status=WorkshopStatus.BLOCKED)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    assert r.status_code == 409 and r.json()["code"] == "workshop_blocked"


async def test_place_order_branch_missing_material(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers, carry_sheet=False)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    assert r.status_code == 409 and r.json()["code"] == "branch_closed"


async def test_place_order_result_not_usable_when_reused(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r1 = await _place(client, world, draft_id)
    assert r1.status_code == 201
    # draft is consumed; second placement fails
    r2 = await _place(client, world, draft_id)
    assert r2.status_code in (404, 409)


# --- happy path + stock seam ------------------------------------------------


async def _approve(client, world, order_id, headers=None):
    return await client.post(
        f"{W}/orders/{order_id}/approve", headers=headers or world.owner_headers, json={}
    )


async def test_full_happy_path_with_stock(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers, sheet_on_hand=50, edge_on_hand=500)
    draft_id = await _make_draft_with_result(
        client, db_session, world, world.client_headers, banded=True
    )
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]

    # approve (owner)
    r = await _approve(client, world, order_id)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"

    # assign owner as cutter + edger (owner exempt from home-branch check)
    r = await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(world.owner.id), "edger_user_id": str(world.owner.id)},
    )
    assert r.status_code == 200 and r.json()["status"] == "cutting", r.text

    sheet_item = (
        await db_session.execute(
            select(StockItem).where(StockItem.material_id == world.sheet_material.id)
        )
    ).scalar_one()
    edge_item = (
        await db_session.execute(
            select(StockItem).where(StockItem.material_id == world.edge_material.id)
        )
    ).scalar_one()
    sheet_before = sheet_item.on_hand
    edge_before = edge_item.on_hand

    # cutting done -> edge_banding; sheets consumed
    r = await client.post(
        f"{W}/orders/{order_id}/cutting-done", headers=world.owner_headers, json={}
    )
    assert r.status_code == 200 and r.json()["status"] == "edge_banding"
    await db_session.refresh(sheet_item)
    await db_session.refresh(edge_item)
    assert sheet_item.on_hand < sheet_before  # sheets decremented
    assert edge_item.on_hand == edge_before  # edge not yet

    # banding done -> ready; edge consumed
    r = await client.post(
        f"{W}/orders/{order_id}/banding-done", headers=world.owner_headers, json={}
    )
    assert r.status_code == 200 and r.json()["status"] == "ready"
    await db_session.refresh(edge_item)
    assert edge_item.on_hand < edge_before  # edge decremented

    # mark collected -> completed
    r = await client.post(
        f"{W}/orders/{order_id}/mark-collected", headers=world.owner_headers, json={}
    )
    assert r.status_code == 200 and r.json()["status"] == "completed"

    order = await db_session.get(Order, uuid.UUID(order_id))
    assert order is not None
    assert order.cutter_user_id == world.owner.id
    assert order.edger_user_id == world.owner.id
    assert order.cut_completed_at is not None
    assert order.edge_completed_at is not None
    assert order.picked_up_at is not None
    assert order.sheets_used_snapshot is not None and order.sheets_used_snapshot > 0
    assert order.cut_count_snapshot is not None and order.cut_count_snapshot > 0


async def test_no_banded_parts_skips_edge_banding(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(
        client, db_session, world, world.client_headers, banded=False
    )
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(world.owner.id)},
    )
    r = await client.post(
        f"{W}/orders/{order_id}/cutting-done", headers=world.owner_headers, json={}
    )
    assert r.status_code == 200 and r.json()["status"] == "ready"  # straight to ready


# --- revert + cancel stock semantics ----------------------------------------


async def test_revert_restores_sheet_stock_and_clears_stamps(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(world.owner.id)},
    )
    sheet_item = (
        await db_session.execute(
            select(StockItem).where(StockItem.material_id == world.sheet_material.id)
        )
    ).scalar_one()
    before = sheet_item.on_hand
    await client.post(f"{W}/orders/{order_id}/cutting-done", headers=world.owner_headers, json={})
    await db_session.refresh(sheet_item)
    consumed = before - sheet_item.on_hand
    assert consumed > 0

    # revert ready -> cutting (no banding) restores sheets and clears cut stamps
    r = await client.post(
        f"{W}/orders/{order_id}/revert",
        headers=world.owner_headers,
        json={"reason": "miscut, redo"},
    )
    assert r.status_code == 200 and r.json()["status"] == "cutting"
    await db_session.refresh(sheet_item)
    assert sheet_item.on_hand == before  # restored exactly
    order = await db_session.get(Order, uuid.UUID(order_id))
    assert order is not None
    assert order.cutter_user_id is None
    assert order.cut_completed_at is None
    assert order.sheets_used_snapshot is None


async def test_cancel_after_consume_does_not_restore(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(world.owner.id)},
    )
    sheet_item = (
        await db_session.execute(
            select(StockItem).where(StockItem.material_id == world.sheet_material.id)
        )
    ).scalar_one()
    before = sheet_item.on_hand
    await client.post(f"{W}/orders/{order_id}/cutting-done", headers=world.owner_headers, json={})
    await db_session.refresh(sheet_item)
    after_consume = sheet_item.on_hand
    assert after_consume < before

    # cancel from ready: consumed stock stays
    r = await client.post(
        f"{W}/orders/{order_id}/cancel",
        headers=world.owner_headers,
        json={"reason": "client changed mind"},
    )
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    await db_session.refresh(sheet_item)
    assert sheet_item.on_hand == after_consume  # NOT restored


# --- optimistic lock --------------------------------------------------------


async def test_optimistic_lock_conflict(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    order = await db_session.get(Order, uuid.UUID(order_id))
    assert order is not None
    stale_version = order.version

    # first approve with the correct version succeeds
    r1 = await client.post(
        f"{W}/orders/{order_id}/approve",
        headers=world.owner_headers,
        json={"expected_version": stale_version},
    )
    assert r1.status_code == 200
    # second action with the now-stale version conflicts
    r2 = await client.post(
        f"{W}/orders/{order_id}/cancel",
        headers=world.owner_headers,
        json={"reason": "racing", "expected_version": stale_version},
    )
    assert r2.status_code == 409 and r2.json()["code"] == "order_conflict"


# --- assignment guards ------------------------------------------------------


async def test_assign_non_owner_cross_branch_rejected(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    # a second branch the worker is "home" at
    other = Branch(workshop_id=world.workshop.id, name="Other", address="B", phone="+998900000099")
    db_session.add(other)
    await db_session.flush()
    # worker has process_production on the ORDER's branch but is home at `other`
    worker = await _staff(
        db_session,
        world,
        login="cutter",
        perms=[Permission.PROCESS_PRODUCTION],
        home_branch_id=other.id,
    )
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    r = await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(worker.id)},
    )
    assert r.status_code == 422 and r.json()["code"] == "invalid_assignee"


async def test_assign_home_branch_worker_ok(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    worker = await _staff(
        db_session,
        world,
        login="cutter",
        perms=[Permission.PROCESS_PRODUCTION],
        home_branch_id=world.branch.id,
    )
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    r = await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(worker.id)},
    )
    assert r.status_code == 200 and r.json()["status"] == "cutting"

    # the worker themselves can mark cutting done (process_production)
    worker_headers = await auth_headers(PrincipalType.WORKSHOP_USER, worker.id)
    r = await client.post(f"{W}/orders/{order_id}/cutting-done", headers=worker_headers, json={})
    assert r.status_code == 200
    order = await db_session.get(Order, uuid.UUID(order_id))
    assert order is not None and order.cutter_user_id == worker.id  # credited to the worker


async def test_on_behalf_credits_chosen_user(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    worker = await _staff(
        db_session,
        world,
        login="cutter",
        perms=[Permission.PROCESS_PRODUCTION],
        home_branch_id=world.branch.id,
    )
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(worker.id)},
    )
    # owner (manage_orders) completes on-behalf, crediting the worker explicitly
    r = await client.post(
        f"{W}/orders/{order_id}/cutting-done",
        headers=world.owner_headers,
        json={"on_behalf_user_id": str(worker.id)},
    )
    assert r.status_code == 200
    order = await db_session.get(Order, uuid.UUID(order_id))
    assert order is not None and order.cutter_user_id == worker.id


# --- client cancel rules ----------------------------------------------------


async def test_client_can_cancel_only_while_new(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]

    # cancel while new: ok
    r = await client.post(
        f"{C}/orders/{order_id}/cancel",
        headers=world.client_headers,
        json={"reason": "made a mistake"},
    )
    assert r.status_code == 200 and r.json()["status"] == "cancelled"


async def test_client_cannot_cancel_after_confirmed(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    r = await client.post(
        f"{C}/orders/{order_id}/cancel",
        headers=world.client_headers,
        json={"reason": "too late now"},
    )
    assert r.status_code == 400 and r.json()["code"] == "invalid_transition"


# --- reads ------------------------------------------------------------------


async def test_client_settlement_visibility_gate(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]

    # while new: no settlement to the client
    r = await client.get(f"{C}/orders/{order_id}", headers=world.client_headers)
    assert r.status_code == 200 and r.json()["settlement"] is None

    # drive to ready
    await _approve(client, world, order_id)
    await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(world.owner.id)},
    )
    await client.post(f"{W}/orders/{order_id}/cutting-done", headers=world.owner_headers, json={})

    r = await client.get(f"{C}/orders/{order_id}", headers=world.client_headers)
    body = r.json()
    assert body["status"] == "ready"
    assert body["settlement"] is not None
    assert body["settlement"]["total_tiyin"] == body["price"]["total_tiyin"]


async def test_workshop_board_and_detail(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]

    r = await client.get(f"{W}/orders", headers=world.owner_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["new"] == 1
    assert any(o["id"] == order_id for o in body["orders"])

    r = await client.get(f"{W}/orders/{order_id}", headers=world.owner_headers)
    detail = r.json()
    assert "approve" in detail["available_actions"]
    # owner sees settlement at any status
    assert detail["settlement"] is not None


async def test_apply_discount_reduces_total(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    pre_total = r.json()["price"]["total_tiyin"]

    r = await client.post(
        f"{W}/orders/{order_id}/apply-discount",
        headers=world.owner_headers,
        json={"discount_tiyin": 10000, "reason": "loyal customer"},
    )
    assert r.status_code == 200
    order = await db_session.get(Order, uuid.UUID(order_id))
    assert order is not None
    assert order.discount_tiyin == 10000
    assert order.total_tiyin == pre_total - 10000


async def test_cutter_workspace_lists_my_orders(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    worker = await _staff(
        db_session,
        world,
        login="cutter",
        perms=[Permission.PROCESS_PRODUCTION],
        home_branch_id=world.branch.id,
    )
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(worker.id)},
    )
    worker_headers = await auth_headers(PrincipalType.WORKSHOP_USER, worker.id)
    r = await client.get(f"{W}/cutting", headers=worker_headers)
    assert r.status_code == 200
    assert any(o["id"] == order_id for o in r.json()["orders"])
