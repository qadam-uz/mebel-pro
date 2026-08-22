"""Confirming an order requires every material it sells to have a price.

Both catalogs list materials a branch carries but has not priced — a branch
registers its whole format list long before it prices it, and a client browsing
the shelf should see all of it. That makes the confirm step the only thing
standing between an unpriced material and an order line that charges nothing,
so these tests pin it from both sides: it must refuse the unpriced order, and it
must not refuse the orders that are legitimately free of charge.
"""

import uuid

from app.models.enums import DecorType, MaterialStatus
from app.modules.catalog.contracts import BranchMaterial, DecorFormat
from app.modules.cutting.contracts import CuttingResult
from app.modules.sales.contracts import Order, OrderItem
from app.modules.sales.service import (
    PriceOverrides,
    _price_result,
    _unpriced_material_ids,
)
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_sales_api import _auth, _placed_order


async def _unprice(db: AsyncSession, branch_material_id: uuid.UUID) -> None:
    """Put a material back to "not priced yet" — 0 means unset, not free."""
    material = await db.get(BranchMaterial, branch_material_id)
    assert material is not None
    material.price_tiyin = 0
    await db.flush()


async def _order_placed_with_an_unpriced_panel(
    client: AsyncClient,
    db: AsyncSession,
    *,
    login: str = "unpriced-owner",
) -> tuple[dict[str, object], str, uuid.UUID]:
    """Place a client order whose panel had NO price when the order was frozen.

    The distinction matters and is the whole point of these tests. Unpricing a
    material *after* placement does not make the order unpriced — its money was
    already frozen at the real rate, and the client owes it. Only a material
    that was unpriced at placement leaves a zero in the bill.
    """
    from tests.test_sales_api import (
        _client_access,
        _materials,
        _optimized_draft,
        _workshop_setup,
    )

    owner_access, _, branch_id, _ = await _workshop_setup(db, login=login)
    panel, edge = await _materials(db, branch_id=branch_id)
    await _unprice(db, panel.id)
    client_access, _ = await _client_access(db, phone=f"+99890{uuid.uuid4().int % 10**7:07d}")
    draft = await _optimized_draft(
        client, client_access, branch_id=branch_id, panel=panel, edge=edge
    )
    placed = await client.post(
        "/api/v1/client/orders",
        headers=_auth(client_access),
        json={
            "draft_id": draft["id"],
            "branch_id": str(branch_id),
            "contact_name": "Unpriced Probe",
            "contact_phone": "+998901555444",
        },
    )
    assert placed.status_code == 201, placed.text
    return placed.json(), owner_access, panel.id


async def _panel_material_id(db: AsyncSession, order_id: object) -> uuid.UUID:
    """The branch material behind a shop-supplied panel line on this order."""
    row = await db.scalar(
        select(OrderItem)
        .join(BranchMaterial, BranchMaterial.id == OrderItem.branch_material_id)
        # The substrate hangs off the format now, one join further out: the
        # branch row carries only the commercial decision.
        .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
        .where(
            OrderItem.order_id == uuid.UUID(str(order_id)),
            DecorFormat.type != DecorType.KROMKA,
        )
    )
    assert row is not None, "the placed order should have a panel line"
    return row.branch_material_id


async def test_confirm_is_refused_when_the_order_froze_a_material_at_zero(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, material_id = await _order_placed_with_an_unpriced_panel(
        client, db_session
    )
    assert order["subtotal_materials_tiyin"] == 0, "the bill really does charge nothing"

    refused = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert refused.status_code == 400, refused.text
    body = refused.json()
    assert body["code"] == "order_has_unpriced_materials"
    # The screen has to name what to fix, not merely that something is wrong.
    assert str(material_id) in body["details"]["material_ids"]
    assert body["details"]["material_names"], "the operator needs a name, not a uuid"


async def test_pricing_the_catalog_after_placement_does_not_unlock_confirm(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The guard reads the order's frozen bill, never the live rate card.

    An order placed while a material was unpriced bills 0 for it forever. If a
    live read were used, the branch pricing its catalog afterwards would satisfy
    the guard while the order still charged nothing — money out the door with
    nobody having priced THAT order.
    """
    order, owner_access, material_id = await _order_placed_with_an_unpriced_panel(
        client, db_session
    )
    material = await db_session.get(BranchMaterial, material_id)
    assert material is not None
    material.price_tiyin = 250_000
    await db_session.flush()

    refused = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "order_has_unpriced_materials"


async def test_unpricing_the_catalog_after_placement_does_not_block_a_priced_order(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The mirror case, and the reason a live read is wrong in both directions.

    This order froze a real 250 000. The branch later unpricing that format
    changes nothing about what the client owes, so confirm must still work.
    """
    order, _, owner_access, _, _, _ = await _placed_order(client, db_session)
    await _unprice(db_session, await _panel_material_id(db_session, order["id"]))

    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "confirmed"


async def test_an_order_level_price_unblocks_confirm(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Pricing the material for THIS order is how staff resolve it.

    The branch row stays at zero — the workshop agreed a price for one order,
    not for its catalog — so the guard has to read the resolved price, not the
    stored one.
    """
    order, owner_access, material_id = await _order_placed_with_an_unpriced_panel(
        client, db_session
    )

    priced = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/prices",
        headers=_auth(owner_access),
        json={"version": order["version"], "material_prices": {str(material_id): 250_000}},
    )
    assert priced.status_code == 200, priced.text
    assert priced.json()["subtotal_materials_tiyin"] > 0, "the bill must actually change"

    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": priced.json()["version"]},
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "confirmed"
    stored = await db_session.get(BranchMaterial, material_id)
    assert stored is not None
    assert stored.price_tiyin == 0, "an order override must not rewrite the branch's rate card"


async def test_a_deactivated_material_still_confirms_when_priced(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """QAD-150: a catalog change after the order must not block recording work.

    The guard fetches materials without the active filter on purpose — a
    deactivated material still has to be paid for — so deactivating a *priced*
    material must leave confirm working.
    """
    order, _, owner_access, _, _, _ = await _placed_order(client, db_session)
    material = await db_session.get(
        BranchMaterial, await _panel_material_id(db_session, order["id"])
    )
    assert material is not None
    material.status = MaterialStatus.INACTIVE
    await db_session.flush()

    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert approved.status_code == 200, approved.text


async def test_placing_and_reading_stay_open_with_an_unpriced_material(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The guard belongs at confirm and nowhere earlier.

    A client must be able to see the shelf, build a draft and place the order;
    the branch prices it afterwards. If this starts failing, the guard has crept
    up the flow and the feature is gone.
    """
    order, client_access, owner_access, _, _, _ = await _placed_order(client, db_session)
    await _unprice(db_session, await _panel_material_id(db_session, order["id"]))

    workshop_read = await client.get(
        f"/api/v1/workshop/orders/{order['id']}", headers=_auth(owner_access)
    )
    client_read = await client.get("/api/v1/client/orders", headers=_auth(client_access))

    assert workshop_read.status_code == 200, workshop_read.text
    assert workshop_read.json()["status"] == "new"
    assert client_read.status_code == 200, client_read.text


async def test_a_second_prices_call_cannot_un_price_a_confirmed_order(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """`material_prices` replaces the stored map — it does not merge into it.

    So a follow-up call that only edits the cutting rate drops every material
    override with it, including the one that was the sole price a material had.
    On a confirmed order that silently takes money back off the bill.
    """
    order, owner_access, material_id = await _order_placed_with_an_unpriced_panel(
        client, db_session
    )
    priced = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/prices",
        headers=_auth(owner_access),
        json={"version": order["version"], "material_prices": {str(material_id): 250_000}},
    )
    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": priced.json()["version"]},
    )
    assert approved.status_code == 200, approved.text
    confirmed_total = approved.json()["total_tiyin"]

    # Edit only the cutting rate — the material override goes with it.
    refused = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/prices",
        headers=_auth(owner_access),
        json={"version": approved.json()["version"], "cutting_rate_tiyin": 60_000},
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "order_has_unpriced_materials"
    reread = await client.get(f"/api/v1/workshop/orders/{order['id']}", headers=_auth(owner_access))
    assert reread.json()["total_tiyin"] == confirmed_total, "the bill must be untouched"


async def test_a_new_order_may_still_be_re_priced_to_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The rule is about orders that already owe money.

    A `new` order landing back at zero is the ordinary state this whole feature
    creates; confirm is still ahead of it. Only past `new` does a re-price have
    to keep the bill whole.
    """
    order, owner_access, material_id = await _order_placed_with_an_unpriced_panel(
        client, db_session
    )

    repriced = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/prices",
        headers=_auth(owner_access),
        json={"version": order["version"], "cutting_rate_tiyin": 60_000},
    )

    assert repriced.status_code == 200, repriced.text
    assert [row["material_id"] for row in repriced.json()["unpriced_materials"]] == [
        str(material_id)
    ]


async def test_a_staff_walk_in_order_does_not_auto_confirm_while_unpriced(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The one path that reaches CONFIRMED without going through Approve.

    A staff-placed order is created and confirmed in one call — the creator is
    the approver. That reasoning holds only when there is nothing left to
    decide, and an unpriced material is something left to decide, so the
    auto-confirm is skipped and the order waits at `new`. Without this the
    guard is trivially bypassed: place the order from the counter instead.
    """
    from tests.test_workshop_order_create_api import (
        _materials,
        _optimized_workshop_draft,
        _priced_workshop,
        _resolve_client,
    )

    access, _, branch_id, _ = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    client_id = await _resolve_client(client, access, phone="+998901112255", name="Walk-in")
    draft_id = await _optimized_workshop_draft(
        client, access, client_id=client_id, branch_id=branch_id, panel=panel, edge=edge
    )
    # Unpriced only AFTER the draft exists, so the picker and optimize steps are
    # untouched — this test is about the confirm decision, not about selection.
    await _unprice(db_session, panel.id)

    placed = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "Walk-in",
            "contact_phone": "+998901112255",
        },
    )

    assert placed.status_code == 201, placed.text
    body = placed.json()
    assert body["status"] == "new", "an unpriced staff order must not auto-confirm"
    assert [row["material_id"] for row in body["unpriced_materials"]] == [str(panel.id)]


async def test_order_detail_names_the_materials_confirm_will_refuse_on(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The screen has to know before it hits the wall.

    Detail reports exactly what the guard checks, from the same helper, so the
    workshop can price the gap instead of discovering it on a failed confirm.
    """
    unpriced_order, owner_access, material_id = await _order_placed_with_an_unpriced_panel(
        client, db_session
    )
    priced_order, _, priced_owner, _, _, _ = await _placed_order(
        client, db_session, login="priced-owner"
    )

    listed = (
        await client.get(
            f"/api/v1/workshop/orders/{unpriced_order['id']}", headers=_auth(owner_access)
        )
    ).json()["unpriced_materials"]
    clean = (
        await client.get(
            f"/api/v1/workshop/orders/{priced_order['id']}", headers=_auth(priced_owner)
        )
    ).json()["unpriced_materials"]

    assert [row["material_id"] for row in listed] == [str(material_id)]
    assert listed[0]["material_label"], "the operator needs a name, not a uuid"
    assert clean == []


async def test_the_itemized_breakdown_reads_through_the_override(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Quote lines resolve prices the same way the subtotal does.

    They used to read the branch price straight while the subtotal applied the
    override, so the breakdown disagreed with the total whenever one existed —
    harmless while overrides were a rare negotiation, permanent now that pricing
    an unpriced material IS an override.
    """
    order_payload, _, _, _, branch_id, _ = await _placed_order(client, db_session)
    order = await db_session.get(Order, uuid.UUID(str(order_payload["id"])))
    assert order is not None
    result = await db_session.get(CuttingResult, order.cutting_result_id)
    assert result is not None
    material_id = await _panel_material_id(db_session, order_payload["id"])

    pricing = await _price_result(
        db_session,
        branch_id=branch_id,
        result=result,
        overrides=PriceOverrides(material_prices={material_id: 999_000}),
    )

    line = next(row for row in pricing.material_lines if row.material_id == material_id)
    assert line.unit_price_tiyin == 999_000
    assert sum(row.line_total_tiyin for row in pricing.material_lines) == (
        pricing.subtotal_materials_tiyin
    )


def test_a_material_the_client_supplied_entirely_needs_no_price() -> None:
    """A sheet the client brought is not "unpriced" — it is not sold at all.

    `_panel_stock_demands` keeps such a material's key at zero so pricing still
    checks the branch carries it. Requiring a price there would block an order
    that is entirely correct, so any demand of zero is skipped.
    """
    material_id = uuid.uuid4()

    assert (
        _unpriced_material_ids(
            panel_demands={material_id: 0},
            edge_demands={},
            frozen_prices={material_id: 0},
        )
        == []
    )
    assert _unpriced_material_ids(
        panel_demands={material_id: 1},
        edge_demands={},
        frozen_prices={material_id: 0},
    ) == [material_id]


def test_a_frozen_price_from_an_override_counts_as_priced() -> None:
    """`set_order_prices` re-prices and rewrites the snapshots, so an override
    reaches this function as an ordinary frozen price."""
    material_id = uuid.uuid4()

    assert (
        _unpriced_material_ids(
            panel_demands={material_id: 3},
            edge_demands={},
            frozen_prices={material_id: 120_000},
        )
        == []
    )
