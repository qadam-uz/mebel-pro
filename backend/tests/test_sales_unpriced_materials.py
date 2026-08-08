"""Confirming an order requires every material it sells to have a price.

Both catalogs list materials a branch carries but has not priced — a branch
registers its whole format list long before it prices it, and a client browsing
the shelf should see all of it. That makes the confirm step the only thing
standing between an unpriced material and an order line that charges nothing,
so these tests pin it from both sides: it must refuse the unpriced order, and it
must not refuse the orders that are legitimately free of charge.
"""

import uuid
from decimal import Decimal

from app.models.enums import DekorType, MaterialStatus
from app.modules.catalog.contracts import BranchMaterial, Dekor
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


async def _panel_material_id(db: AsyncSession, order_id: object) -> uuid.UUID:
    """The branch material behind a shop-supplied panel line on this order."""
    row = await db.scalar(
        select(OrderItem)
        .join(BranchMaterial, BranchMaterial.id == OrderItem.branch_material_id)
        .join(Dekor, Dekor.id == BranchMaterial.dekor_id)
        .where(
            OrderItem.order_id == uuid.UUID(str(order_id)),
            Dekor.tur != DekorType.KROMKA,
        )
    )
    assert row is not None, "the placed order should have a panel line"
    return row.branch_material_id


async def test_confirm_is_refused_while_a_sold_material_has_no_price(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, _, _, _ = await _placed_order(client, db_session)
    material_id = await _panel_material_id(db_session, order["id"])
    await _unprice(db_session, material_id)

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


async def test_an_order_level_price_unblocks_confirm(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Pricing the material for THIS order is how staff resolve it.

    The branch row stays at zero — the workshop agreed a price for one order,
    not for its catalog — so the guard has to read the resolved price, not the
    stored one.
    """
    order, _, owner_access, _, _, _ = await _placed_order(client, db_session)
    material_id = await _panel_material_id(db_session, order["id"])
    await _unprice(db_session, material_id)

    priced = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/prices",
        headers=_auth(owner_access),
        json={"version": order["version"], "material_prices": {str(material_id): 250_000}},
    )
    assert priced.status_code == 200, priced.text

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
    unpriced = BranchMaterial(
        id=material_id,
        branch_id=uuid.uuid4(),
        dekor_id=uuid.uuid4(),
        qalinlik_mm=Decimal("18"),
        price_tiyin=0,
    )

    assert (
        _unpriced_material_ids(
            panel_demands={material_id: 0},
            edge_demands={},
            branch_materials={material_id: unpriced},
            overrides=PriceOverrides(),
        )
        == []
    )
    assert _unpriced_material_ids(
        panel_demands={material_id: 1},
        edge_demands={},
        branch_materials={material_id: unpriced},
        overrides=PriceOverrides(),
    ) == [material_id]


def test_an_override_prices_a_material_whose_branch_row_is_zero() -> None:
    material_id = uuid.uuid4()
    unpriced = BranchMaterial(
        id=material_id,
        branch_id=uuid.uuid4(),
        dekor_id=uuid.uuid4(),
        qalinlik_mm=Decimal("18"),
        price_tiyin=0,
    )

    assert (
        _unpriced_material_ids(
            panel_demands={material_id: 3},
            edge_demands={},
            branch_materials={material_id: unpriced},
            overrides=PriceOverrides(material_prices={material_id: 120_000}),
        )
        == []
    )
