"""Customer-supplied boards: the walk-in's sheet, isolated from the catalog.

A customer board used to be a `branch_materials` row flagged `customer_supplied`,
hanging off a seeded `Mijoz` manufacturer and decor. That made every catalog
listing, the attach uniqueness index and the stock screen carry an exclusion for
something that was never an offer — and one missed exclusion leaked one
customer's sheet into another customer's picker. It is its own table now
(`customer_boards`), owned by the drawing and then by the order, and these tests
pin the isolation that buys:

- recording one writes nothing to `branch_materials`, `decors` or `stock_items`;
- it is pickable in its own draft's editor and nowhere else;
- the cutting panel and the order item carry `customer_board_id` and a NULL
  `branch_material_id` (the DB CHECK says exactly one);
- «Kesish tugadi» consumes the **substitute** the shortfall was billed from, and
  nothing for the board itself — the shop never owned it.

The per-sheet arithmetic (sheets off the top of the demand, substitute pricing,
zero-shortfall orders moving nothing) is unit-tested in
tests/test_sales_own_material.py; this file is the end-to-end proof that the
wiring lands on the right rows.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models.enums import AuthenticatedPrincipalType, Permission
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.catalog.contracts import BranchMaterial, BranchPricing, Decor
from app.modules.cutting.contracts import CustomerBoard, CuttingPanel, CuttingResult
from app.modules.inventory.contracts import StockItem
from app.modules.sales.contracts import OrderItem
from app.modules.workshop.contracts import Branch
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    MaterialFixture,
    seed_manufacturer,
    seed_panel_material,
    seed_workshop_with_owner,
)
from tests.test_sales_api import _staff


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _priced_workshop(
    db: AsyncSession, *, login: str = "owner"
) -> tuple[str, uuid.UUID, uuid.UUID]:
    workshop, branch, owner = await seed_workshop_with_owner(db, login=login)
    owner.password_reset_required = False
    # A walk-in's own sheets only count against the layout on a branch that has
    # opted into client-supplied material; without this the draft's claim is
    # cleared on the next read and every sheet is billed. A shop that lets
    # customers carry boards in has opted in by definition.
    branch.own_material_allowed = True
    db.add(
        BranchPricing(
            branch_id=branch.id,
            cutting_rate_tiyin=50_000,
            edge_banding_rate_tiyin=20_000,
            updated_at=datetime.now(UTC),
            updated_by_user_id=owner.id,
        )
    )
    await db.flush()
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, workshop.id, branch.id


async def _client_access(db: AsyncSession) -> str:
    row = Client(phone=f"+99890{uuid.uuid4().int % 10**7:07d}", name="Browser")
    db.add(row)
    await db.flush()
    tokens = await create_session(
        db, principal_type=AuthenticatedPrincipalType.CLIENT, principal_id=row.id
    )
    return tokens.access_token


async def _stocked_panel(
    db: AsyncSession, *, branch_id: uuid.UUID, on_hand: int
) -> MaterialFixture:
    """The branch's own 900x600x18 sheet — the size the walk-in's board will match."""
    manufacturer = await seed_manufacturer(db, name=f"Maker {uuid.uuid4().hex[:6]}")
    panel = await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        code=f"CB-{uuid.uuid4().hex[:4]}",
        name="White",
        thickness_mm=Decimal("18"),
        length_mm=900,
        width_mm=600,
        price_tiyin=250_000,
    )
    db.add(
        StockItem(
            branch_id=branch_id,
            branch_material_id=panel.id,
            on_hand=on_hand,
            updated_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return panel


async def _workshop_draft(client: AsyncClient, access: str, *, branch_id: uuid.UUID) -> str:
    resolved = await client.post(
        "/api/v1/workshop/clients/resolve",
        headers=_auth(access),
        json={"phone": f"+99890{uuid.uuid4().int % 10**7:07d}", "name": "Walk-in"},
    )
    assert resolved.status_code == 200, resolved.text
    created = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access),
        json={"client_id": resolved.json()["id"], "branch_id": str(branch_id)},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def _record_board(
    client: AsyncClient, access: str, draft_id: str, *, sheets: int = 1
) -> dict[str, Any]:
    created = await client.post(
        f"/api/v1/workshop/cutting-drafts/{draft_id}/customer-materials",
        headers=_auth(access),
        json={
            "name": "Mijoz listi",
            "length_mm": 600,
            "width_mm": 900,
            "thickness_mm": "18",
            "sheets": sheets,
        },
    )
    assert created.status_code == 201, created.text
    board: dict[str, Any] = created.json()
    return board


def _parts(material_id: str, *, quantity: int) -> list[dict[str, Any]]:
    # 800x500 on a 900x600 sheet: one part per sheet, so `quantity` is also the
    # number of sheets the layout will need.
    return [
        {
            "part_ref": "door",
            "material_id": material_id,
            "material_source": "shop",
            "length_mm": 800,
            "width_mm": 500,
            "quantity": quantity,
            "edge_top": None,
            "edge_bottom": None,
            "edge_left": None,
            "edge_right": None,
        }
    ]


async def _picker_ids(
    client: AsyncClient, access: str, *, branch_id: uuid.UUID, draft_id: str | None
) -> set[str]:
    query = f"branch_id={branch_id}" + (f"&draft_id={draft_id}" if draft_id else "")
    listed = await client.get(f"/api/v1/workshop/catalog/materials?{query}", headers=_auth(access))
    assert listed.status_code == 200, listed.text
    return {row["id"] for row in listed.json()}


async def test_recording_a_board_touches_no_catalog_table(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The branch does not carry it, so no catalog row and no stock row exist.

    A stock row in particular would be actively harmful: a board the shop never
    owned would read 0/0 on the Ombor screen as "low stock" and page the owner
    about it.
    """
    access, _, branch_id = await _priced_workshop(db_session)
    panel = await _stocked_panel(db_session, branch_id=branch_id, on_hand=5)
    draft_id = await _workshop_draft(client, access, branch_id=branch_id)
    materials_before = await db_session.scalar(select(func.count(BranchMaterial.id)))
    decors_before = await db_session.scalar(select(func.count(Decor.id)))
    stock_before = await db_session.scalar(select(func.count(StockItem.branch_material_id)))

    board = await _record_board(client, access, draft_id, sheets=2)

    assert board["customer_supplied"] is True
    assert board["id"] != str(panel.id)
    # Typed 600x900, stored long-side-first like every other sheet.
    assert (board["length_mm"], board["width_mm"]) == (900, 600)
    # The substitute is the branch's own sheet of that exact size, and its price
    # is what the shortfall will be billed at.
    assert board["price_tiyin"] == 250_000
    assert await db_session.scalar(select(func.count(BranchMaterial.id))) == materials_before
    assert await db_session.scalar(select(func.count(Decor.id))) == decors_before
    assert await db_session.scalar(select(func.count(StockItem.branch_material_id))) == stock_before
    row = await db_session.get(CustomerBoard, uuid.UUID(board["id"]))
    assert row is not None
    assert row.branch_id == branch_id
    assert row.stock_material_id == panel.id
    assert row.source_draft_id == uuid.UUID(draft_id)
    # The sheet count the operator typed IS the draft's own-material claim.
    draft = await client.get(f"/api/v1/workshop/cutting-drafts/{draft_id}", headers=_auth(access))
    assert draft.json()["own_panel_counts"] == {board["id"]: 2}


async def test_a_board_is_pickable_only_in_the_draft_that_recorded_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """One customer's property must not appear in the next walk-in's picker.

    That leak is exactly what the old "exclude customer_supplied rows" pattern
    risked every time a listing forgot the predicate. Scoping is by the draft
    that created the board, never by branch.
    """
    access, _, branch_id = await _priced_workshop(db_session)
    panel = await _stocked_panel(db_session, branch_id=branch_id, on_hand=5)
    draft_id = await _workshop_draft(client, access, branch_id=branch_id)
    other_draft_id = await _workshop_draft(client, access, branch_id=branch_id)
    client_access = await _client_access(db_session)
    board = await _record_board(client, access, draft_id)

    own_picker = await _picker_ids(client, access, branch_id=branch_id, draft_id=draft_id)
    other_picker = await _picker_ids(client, access, branch_id=branch_id, draft_id=other_draft_id)
    unscoped_picker = await _picker_ids(client, access, branch_id=branch_id, draft_id=None)
    branch_catalog = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials", headers=_auth(access)
    )
    client_catalog = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials", headers=_auth(client_access)
    )
    client_picker = await client.get(
        f"/api/v1/client/catalog/materials?branch_id={branch_id}", headers=_auth(client_access)
    )

    assert own_picker == {str(panel.id), board["id"]}
    assert other_picker == {str(panel.id)}
    assert unscoped_picker == {str(panel.id)}
    assert [row["id"] for row in branch_catalog.json()] == [str(panel.id)]
    assert [row["id"] for row in client_catalog.json()] == [str(panel.id)]
    assert [row["id"] for row in client_picker.json()] == [str(panel.id)]


async def test_the_panel_and_the_order_item_carry_the_board_id_and_no_branch_material(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Exactly one of the two FKs, and it is the board's.

    The response schemas expose a single opaque `material_id` for both cases —
    the same key `own_panel_counts` and `material_snapshots` already use — so
    the client never had to learn a second identity.
    """
    access, _, branch_id = await _priced_workshop(db_session)
    await _stocked_panel(db_session, branch_id=branch_id, on_hand=5)
    draft_id = await _workshop_draft(client, access, branch_id=branch_id)
    board = await _record_board(client, access, draft_id, sheets=1)

    patched = await client.patch(
        f"/api/v1/workshop/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": _parts(board["id"], quantity=2)},
    )
    assert patched.status_code == 200, patched.text
    optimized = await client.post(
        f"/api/v1/workshop/cutting-drafts/{draft_id}/optimize", headers=_auth(access)
    )
    assert optimized.status_code == 200, optimized.text
    result = optimized.json()["results"][0]
    assert {panel["material_id"] for panel in result["panels"]} == {board["id"]}
    assert len(result["panels"]) == 2
    stored_panels = (
        await db_session.scalars(
            select(CuttingPanel).where(CuttingPanel.cutting_result_id == uuid.UUID(result["id"]))
        )
    ).all()
    assert len(stored_panels) == 2
    for stored in stored_panels:
        assert stored.customer_board_id == uuid.UUID(board["id"])
        assert stored.branch_material_id is None

    placed = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "Walk-in",
            "contact_phone": "+998901112233",
        },
    )
    assert placed.status_code == 201, placed.text
    order = placed.json()
    assert [item["material_id"] for item in order["items"]] == [board["id"]]
    items = (
        await db_session.scalars(
            select(OrderItem).where(OrderItem.order_id == uuid.UUID(order["id"]))
        )
    ).all()
    assert len(items) == 1
    assert items[0].customer_board_id == uuid.UUID(board["id"])
    assert items[0].branch_material_id is None
    # The frozen snapshot says what it was, so history renders without the row.
    assert items[0].material_snapshot["customer_supplied"] is True
    # The draft is gone, and the board survives it — the order owns it now.
    stored_result = await db_session.get(CuttingResult, uuid.UUID(result["id"]))
    assert stored_result is not None
    assert await db_session.get(CustomerBoard, uuid.UUID(board["id"])) is not None


async def test_cutting_done_consumes_the_substitute_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The shop never owned the board; it sells — and moves — the shortfall.

    Two sheets needed, one brought: one sheet leaves the substitute's shelf. A
    stock row for the board itself would be invented stock, and the shortfall
    coming off it instead of the substitute would leave the branch's real shelf
    uncounted.
    """
    access, workshop_id, branch_id = await _priced_workshop(db_session)
    panel = await _stocked_panel(db_session, branch_id=branch_id, on_hand=5)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    draft_id = await _workshop_draft(client, access, branch_id=branch_id)
    board = await _record_board(client, access, draft_id, sheets=1)
    await client.patch(
        f"/api/v1/workshop/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": _parts(board["id"], quantity=2)},
    )
    optimized = await client.post(
        f"/api/v1/workshop/cutting-drafts/{draft_id}/optimize", headers=_auth(access)
    )
    assert optimized.status_code == 200, optimized.text
    placed = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "Walk-in",
            "contact_phone": "+998901112244",
        },
    )
    assert placed.status_code == 201, placed.text
    order = placed.json()
    # One sheet billed at the substitute's price: the one the customer did not
    # bring.
    assert order["subtotal_materials_tiyin"] == 250_000
    order_id = order["id"]

    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(access),
        json={
            # No edger: these parts carry no edge banding, and assigning one is
            # refused with `edger_not_required`.
            "version": order["version"],
            "cutter_user_id": str(worker.id),
        },
    )
    assert assigned.status_code == 200, assigned.text
    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(access),
        json={"version": assigned.json()["version"]},
    )
    assert started.status_code == 200, started.text
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(access),
        json={"version": started.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    assert cut_done.status_code == 200, cut_done.text
    assert cut_done.json()["stock_shortfall"] is False

    substitute_on_hand = await db_session.scalar(
        select(StockItem.on_hand).where(StockItem.branch_material_id == panel.id)
    )
    assert substitute_on_hand == 4
    # No stock row was ever opened for the board — not at record time, not at
    # consume time.
    board_stock = await db_session.scalar(
        select(func.count())
        .select_from(StockItem)
        .where(StockItem.branch_material_id == uuid.UUID(board["id"]))
    )
    assert board_stock == 0


async def test_a_board_needs_a_branch_and_the_manage_orders_permission(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guard rails around the write: a board belongs to a branch's drawing."""
    access, workshop_id, branch_id = await _priced_workshop(db_session)
    await _stocked_panel(db_session, branch_id=branch_id, on_hand=5)
    draft_id = await _workshop_draft(client, access, branch_id=branch_id)
    # Production staff can cut; they do not build drawings.
    cutter = await _staff(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.PROCESS_PRODUCTION,
    )
    cutter_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=cutter.id,
    )

    forbidden = await client.post(
        f"/api/v1/workshop/cutting-drafts/{draft_id}/customer-materials",
        headers=_auth(cutter_tokens.access_token),
        json={"length_mm": 900, "width_mm": 600, "thickness_mm": "18", "sheets": 1},
    )
    unknown_draft = await client.post(
        f"/api/v1/workshop/cutting-drafts/{uuid.uuid4()}/customer-materials",
        headers=_auth(access),
        json={"length_mm": 900, "width_mm": 600, "thickness_mm": "18", "sheets": 1},
    )

    assert forbidden.status_code in (403, 404), forbidden.text
    assert unknown_draft.status_code == 404, unknown_draft.text
    assert await db_session.scalar(select(func.count(CustomerBoard.id))) == 0


async def test_a_board_is_refused_on_a_branch_that_does_not_take_own_material(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`own_material_allowed` is the branch's policy, and the counter obeys it too.

    The switch already hides the own-material controls from the client; a board
    typed in by staff on such a branch would mint a claim the next draft read
    silently clears. A named 409 is the honest answer.
    """

    access, _, branch_id = await _priced_workshop(db_session)
    draft_id = await _workshop_draft(client, access, branch_id=branch_id)
    branch = await db_session.get(Branch, branch_id)
    assert branch is not None
    branch.own_material_allowed = False
    await db_session.flush()

    refused = await client.post(
        f"/api/v1/workshop/cutting-drafts/{draft_id}/customer-materials",
        headers=_auth(access),
        json={"length_mm": 600, "width_mm": 900, "thickness_mm": "18", "sheets": 1},
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "own_material_not_allowed"
    assert await db_session.scalar(select(func.count(CustomerBoard.id))) == 0
