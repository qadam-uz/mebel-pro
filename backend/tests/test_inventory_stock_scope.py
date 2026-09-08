"""The Zaxira tab's contract: what the alarm means, and what counts as stock.

Two rules the stock surface stands on:

- the alarm is **`on_hand < 0`** and nothing else. It used to have a second arm,
  a per-material `min_stock` threshold, which fired for `0 <= 0` and put the
  warning pill on every never-stocked row a branch had ever attached. The
  threshold was retired 2026-09-08 and the arm with it, so the chip reads
  «Manfiy» and the query param is `negative`.
- `moved_only=true` narrows the list to rows that have actually moved, so the
  warehouse stops being a mirror of the catalog. It is **off by default**: the
  pickers and the global search preview must keep seeing everything.
"""

import uuid
from datetime import UTC, datetime

from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    Currency,
    OrderStatus,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.inventory.api import consume_order_stock
from app.modules.inventory.contracts import StockItem
from app.modules.sales.contracts import Order
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    MaterialFixture,
    seed_kromka_material,
    seed_manufacturer,
    seed_panel_material,
    seed_workshop_with_owner,
)


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _owner_access(
    db: AsyncSession, *, login: str = "owner"
) -> tuple[str, uuid.UUID, uuid.UUID]:
    """An owner's bearer token plus the workshop and branch it owns."""
    workshop, branch, owner = await seed_workshop_with_owner(db, login=login)
    owner.password_reset_required = False
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, workshop.id, branch.id


async def _staff_access(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    permission: Permission | None,
) -> str:
    """A non-owner's token, holding one grant on the branch — or none at all."""
    staff = WorkshopUser(
        workshop_id=workshop_id,
        login=f"staff-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("StaffTemp123"),
        full_name="Scoped Staff",
        phone="+998901234111",
        is_owner=False,
        home_branch_id=branch_id,
        status=UserStatus.ACTIVE,
        password_reset_required=False,
    )
    db.add(staff)
    await db.flush()
    if permission is not None:
        db.add(
            PermissionGrant(
                workshop_user_id=staff.id,
                permission=permission,
                branch_id=branch_id,
                granted_by_user_id=staff.id,
                granted_at=datetime.now(UTC),
            )
        )
        await db.flush()
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )
    return tokens.access_token


async def _carried(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    name: str,
    on_hand: int,
) -> MaterialFixture:
    """A carried panel and the balance row attaching it would have created."""
    material = await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=await seed_manufacturer(db, name=f"Maker {uuid.uuid4().hex[:8]}"),
        name=name,
    )
    db.add(
        StockItem(
            branch_id=branch_id,
            branch_material_id=material.id,
            on_hand=on_hand,
            updated_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return material


async def _stock_index(
    client: AsyncClient, access: str, branch_id: uuid.UUID, query: str = ""
) -> dict[str, dict[str, object]]:
    """The stock list keyed by branch-material id, so a test names rows not offsets."""
    response = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock{query}", headers=_auth(access)
    )
    assert response.status_code == 200, response.text
    return {str(row["branch_material_id"]): row for row in response.json()}


async def test_the_stock_alarm_is_the_negative_balance_and_nothing_else(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The whole matrix, in the response flag and in the server-side filter.

    A zero balance is not an alarm — that was the threshold arm, and a warning on
    every freshly registered price list row is a warning nobody reads. Only the
    books going below zero is: an unrecorded arrival somebody has to enter.
    """

    access, _, branch_id = await _owner_access(db_session)
    never_stocked = await _carried(db_session, branch_id=branch_id, name="A", on_hand=0)
    thin = await _carried(db_session, branch_id=branch_id, name="B", on_hand=3)
    negative = await _carried(db_session, branch_id=branch_id, name="D", on_hand=-2)
    stocked = await _carried(db_session, branch_id=branch_id, name="E", on_hand=7)

    rows = await _stock_index(client, access, branch_id)
    negative_only = await _stock_index(client, access, branch_id, "?negative=true")

    assert rows[str(never_stocked.id)]["is_low_stock"] is False
    assert rows[str(thin.id)]["is_low_stock"] is False
    assert rows[str(negative.id)]["is_low_stock"] is True
    assert rows[str(stocked.id)]["is_low_stock"] is False
    # No row carries the retired threshold any more.
    assert "min_stock" not in rows[str(negative.id)]
    # The filter and the flag are the same predicate — a row may never be low in
    # one and not the other.
    assert set(negative_only) == {str(negative.id)}


async def test_moved_only_admits_a_row_the_moment_it_first_moves(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Any movement makes a row warehouse — an adjust, or a consume into the red."""

    access, _, branch_id = await _owner_access(db_session)
    never_moved = await _carried(db_session, branch_id=branch_id, name="Idle", on_hand=0)
    adjusted = await _carried(db_session, branch_id=branch_id, name="Counted", on_hand=0)
    consumed = await _carried(db_session, branch_id=branch_id, name="Cut", on_hand=0)

    # A stock-take correction and a production consume that took the books
    # negative: neither is an arrival, and both are movement.
    adjust = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-adjustments",
        headers=_auth(access),
        json={"branch_material_id": str(adjusted.id), "quantity": 4, "note": "Sanoq"},
    )
    assert adjust.status_code == 201, adjust.text
    await consume_order_stock(
        db_session,
        branch_id=branch_id,
        branch_material_id=consumed.id,
        order_id=uuid.uuid4(),
        quantity=2,
    )

    moved = await _stock_index(client, access, branch_id, "?moved_only=true")
    default_scope = await _stock_index(client, access, branch_id)
    whole_catalog = await _stock_index(client, access, branch_id, "?moved_only=false")

    assert set(moved) == {str(adjusted.id), str(consumed.id)}
    # Default off: the pickers and the global search preview call this endpoint
    # with no scope and must keep seeing a material nobody has stocked yet.
    assert str(never_moved.id) in default_scope
    assert str(never_moved.id) in whole_catalog


async def test_tur_filter_reads_one_shelf_at_a_time_and_composes_with_the_scope(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`types` narrows the browse; it never widens the scope the way search does.

    A board and its matching kromka are two FORMATS of one decor now, sharing a
    name and a photo — so the substrate is a fact about the format, and reading
    one shelf at a time means filtering on `decor_formats.type`. The param is
    plural because one browse the operator asks for can span several substrates:
    «listlar» is `ldsp` + `dsp` + `mdf` on one screen.
    """

    access, _, branch_id = await _owner_access(db_session)
    maker = await seed_manufacturer(db_session, name=f"Maker {uuid.uuid4().hex[:8]}")
    panel = await seed_panel_material(db_session, branch_id=branch_id, manufacturer=maker, name="P")
    # The tape of the SAME pattern — one decor, two formats, two shelves.
    tape = await seed_kromka_material(db_session, branch_id=branch_id, decor=panel.decor)
    for material, on_hand in ((panel, 4), (tape, 12_000)):
        db_session.add(
            StockItem(
                branch_id=branch_id,
                branch_material_id=material.id,
                on_hand=on_hand,
                updated_at=datetime.now(UTC),
            )
        )
    # One never-moved kromka: proof that `type` narrows *within* the moved scope
    # rather than dragging the catalog's untouched rows back in.
    idle_tape = await seed_kromka_material(
        db_session,
        branch_id=branch_id,
        manufacturer=maker,
        name="Idle",
        code="H9999",
        tape_width_mm=22,
    )
    db_session.add(
        StockItem(
            branch_id=branch_id,
            branch_material_id=idle_tape.id,
            on_hand=0,
            updated_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    for material in (panel, tape):
        adjust = await client.post(
            f"/api/v1/workshop/branches/{branch_id}/stock-adjustments",
            headers=_auth(access),
            json={"branch_material_id": str(material.id), "quantity": 1, "note": "Sanoq"},
        )
        assert adjust.status_code == 201, adjust.text

    kromka = await _stock_index(client, access, branch_id, "?types=kromka")
    # Repeated, the way the client sends a multi-substrate browse.
    panels = await _stock_index(client, access, branch_id, "?types=ldsp&types=dsp")
    kromka_moved = await _stock_index(client, access, branch_id, "?types=kromka&moved_only=true")

    assert set(kromka) == {str(tape.id), str(idle_tape.id)}
    assert set(panels) == {str(panel.id)}
    assert set(kromka_moved) == {str(tape.id)}


async def test_an_arrival_still_books_for_a_material_that_never_moved(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The picker regression guard behind the store's split collection.

    The table now loads `moved_only=true`. If the invoice-line picker were fed
    from that same list, the single most common first arrival — for a material
    nobody has ever stocked — would have no reachable material to pick.
    """

    access, _, branch_id = await _owner_access(db_session)
    fresh = await _carried(db_session, branch_id=branch_id, name="Never", on_hand=0)

    invoice = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(access),
        json={
            "branch_id": str(branch_id),
            "supplier": {"name": f"Ta'minotchi {uuid.uuid4().hex[:6]}"},
            "lines": [
                {
                    "branch_material_id": str(fresh.id),
                    "quantity": 3,
                    "unit_price_tiyin": 250000,
                }
            ],
        },
    )

    assert invoice.status_code == 201, invoice.text
    rows = await _stock_index(client, access, branch_id, "?moved_only=true")
    assert rows[str(fresh.id)]["on_hand"] == 3


async def test_material_page_reads_its_own_row_and_names_the_documents(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The material page's two contracts: address by material, name the documents.

    The page is opened from a link or a reload, so it resolves the branch from
    the material rather than from whatever the topbar happens to say. And its
    sections are only navigable if each movement carries the document it belongs
    to — an order's own number, not an id prefix.
    """

    access, workshop_id, branch_id = await _owner_access(db_session)
    material = await _carried(db_session, branch_id=branch_id, name="Sonoma", on_hand=6)

    buyer = Client(phone="+998901112255", name="Dilshod")
    db_session.add(buyer)
    await db_session.flush()
    order = Order(
        order_number="482917",
        client_id=buyer.id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        cutting_result_id=uuid.uuid4(),
        status=OrderStatus.NEW,
        version=1,
        contact_name="Dilshod",
        contact_phone="+998901112255",
        subtotal_cutting_tiyin=0,
        subtotal_materials_tiyin=0,
        subtotal_edge_banding_tiyin=0,
        discount_tiyin=0,
        surcharge_tiyin=0,
        total_tiyin=0,
        currency=Currency.UZS,
    )
    db_session.add(order)
    await db_session.flush()
    await consume_order_stock(
        db_session,
        branch_id=branch_id,
        branch_material_id=material.id,
        order_id=order.id,
        quantity=2,
    )

    row = await client.get(
        f"/api/v1/workshop/inventory/materials/{material.id}/stock", headers=_auth(access)
    )
    assert row.status_code == 200, row.text
    # The branch comes back with the row: the page needs it for every follow-up
    # read, and never had it from the URL.
    assert row.json()["branch_id"] == str(branch_id)
    assert row.json()["on_hand"] == 4

    movements = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions"
        f"?branch_material_id={material.id}",
        headers=_auth(access),
    )
    assert movements.status_code == 200, movements.text
    consumed = [tx for tx in movements.json() if tx["type"] == "consume"]
    assert [tx["order_number"] for tx in consumed] == ["482917"]


async def test_material_page_refuses_a_reader_outside_the_material_s_branch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deriving the branch must not widen who may read it."""

    _, workshop_id, branch_id = await _owner_access(db_session)
    material = await _carried(db_session, branch_id=branch_id, name="Oq", on_hand=1)
    other_access, _, other_branch_id = await _owner_access(db_session, login="rival")

    denied = await client.get(
        f"/api/v1/workshop/inventory/materials/{material.id}/stock", headers=_auth(other_access)
    )
    assert denied.status_code in {403, 404}, denied.text
    assert other_branch_id != branch_id and workshop_id is not None

    missing = await client.get(
        f"/api/v1/workshop/inventory/materials/{uuid.uuid4()}/stock", headers=_auth(other_access)
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "stock_item_not_found"
