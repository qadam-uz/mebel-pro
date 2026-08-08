"""TEMPORARY probe — deleted after the run. Not part of the repo."""

import uuid

from app.modules.catalog.contracts import BranchMaterial
from app.modules.sales.contracts import Order, OrderItem
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_sales_api import (
    _auth,
    _client_access,
    _materials,
    _optimized_draft,
    _workshop_setup,
)


async def _place_with_unpriced_panel(client: AsyncClient, db: AsyncSession):
    owner_access, _wid, branch_id, _ = await _workshop_setup(db, login="owner")
    panel, edge = await _materials(db, branch_id=branch_id)
    # Unprice BEFORE anything is drafted or placed — the branch registered the
    # format but has not priced it yet. This is the case no test covers.
    row = await db.get(BranchMaterial, panel.id)
    row.price_tiyin = 0
    await db.flush()
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
            "contact_name": "Probe",
            "contact_phone": "+998901555222",
            "note_client": None,
        },
    )
    assert placed.status_code == 201, placed.text
    return placed.json(), owner_access, panel, branch_id


async def test_probe_frozen_snapshot(client: AsyncClient, db_session: AsyncSession) -> None:
    order, owner_access, panel, _ = await _place_with_unpriced_panel(client, db_session)
    print("\n[A] PLACED  total:", order["total_tiyin"], "materials:", order["subtotal_materials_tiyin"])
    print("[A] unpriced_materials on detail:", order.get("unpriced_materials"))

    # The branch admin now does the obvious thing: prices the format in the
    # CATALOG. No order-level override is set.
    row = await db_session.get(BranchMaterial, panel.id)
    row.price_tiyin = 250_000
    await db_session.flush()

    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    print("[A] approve status:", approved.status_code)
    if approved.status_code == 200:
        body = approved.json()
        print("[A] AFTER CONFIRM -> status:", body["status"],
              "total:", body["total_tiyin"],
              "materials:", body["subtotal_materials_tiyin"])
        items = (await db_session.scalars(
            select(OrderItem).where(OrderItem.order_id == uuid.UUID(str(order["id"])))
        )).all()
        for it in items:
            print("[A] item unit_material_price:", it.unit_material_price_tiyin,
                  "line_total:", it.line_total_tiyin)
        db_order = await db_session.get(Order, uuid.UUID(str(order["id"])))
        print("[A] DB row -> status:", db_order.status, "total:", db_order.total_tiyin,
              "materials:", db_order.subtotal_materials_tiyin)


async def test_probe_own_material_unclaim(client: AsyncClient, db_session: AsyncSession) -> None:
    order, owner_access, panel, _ = await _place_with_unpriced_panel(client, db_session)
    oid = order["id"]

    # Client says: I bring every sheet myself.
    claimed = await client.post(
        f"/api/v1/workshop/orders/{oid}/own-material",
        headers=_auth(owner_access),
        json={"version": order["version"], "own_panel_counts": {str(panel.id): 99}},
    )
    print("\n[B] own-material claim-all:", claimed.status_code)
    body = claimed.json()
    print("[B] unpriced_materials after claim:", body.get("unpriced_materials"))

    approved = await client.post(
        f"/api/v1/workshop/orders/{oid}/approve",
        headers=_auth(owner_access),
        json={"version": body["version"]},
    )
    print("[B] approve:", approved.status_code)
    assert approved.status_code == 200, approved.text
    ver = approved.json()["version"]

    # Client turns up with nothing. Staff clear the claim on the CONFIRMED order.
    unclaimed = await client.post(
        f"/api/v1/workshop/orders/{oid}/own-material",
        headers=_auth(owner_access),
        json={"version": ver, "own_panel_counts": {}},
    )
    print("[B] own-material UNCLAIM on confirmed order:", unclaimed.status_code)
    if unclaimed.status_code == 200:
        b = unclaimed.json()
        print("[B] AFTER UNCLAIM -> status:", b["status"], "total:", b["total_tiyin"],
              "materials:", b["subtotal_materials_tiyin"])
        print("[B] unpriced_materials:", b.get("unpriced_materials"))
        db_order = await db_session.get(Order, uuid.UUID(str(oid)))
        print("[B] DB row -> status:", db_order.status, "total:", db_order.total_tiyin)
