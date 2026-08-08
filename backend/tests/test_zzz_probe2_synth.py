"""TEMPORARY probe 2 — deleted after the run."""

import uuid

from app.modules.catalog.contracts import BranchMaterial
from app.modules.sales.contracts import Order
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_zzz_probe_synth import _place_with_unpriced_panel
from tests.test_sales_api import _auth


async def test_probe_second_prices_call_drops_the_override(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, owner_access, panel, _ = await _place_with_unpriced_panel(client, db_session)
    oid = order["id"]

    # The sanctioned fix: price this material for THIS order.
    priced = await client.post(
        f"/api/v1/workshop/orders/{oid}/prices",
        headers=_auth(owner_access),
        json={"version": order["version"], "material_prices": {str(panel.id): 250_000}},
    )
    print("\n[C] /prices with override:", priced.status_code, priced.text[:200])
    assert priced.status_code == 200
    b = priced.json()
    print("[C] after override -> total:", b["total_tiyin"], "materials:", b["subtotal_materials_tiyin"])

    approved = await client.post(
        f"/api/v1/workshop/orders/{oid}/approve",
        headers=_auth(owner_access),
        json={"version": b["version"]},
    )
    print("[C] approve:", approved.status_code)
    assert approved.status_code == 200
    ab = approved.json()
    print("[C] CONFIRMED correctly -> total:", ab["total_tiyin"],
          "materials:", ab["subtotal_materials_tiyin"])

    # Staff reopen the prices modal to tweak the CUTTING rate and save. The
    # material_prices map is replaced wholesale.
    second = await client.post(
        f"/api/v1/workshop/orders/{oid}/prices",
        headers=_auth(owner_access),
        json={"version": ab["version"], "cutting_rate_tiyin": 30_000, "material_prices": {}},
    )
    print("[C] SECOND /prices on confirmed order:", second.status_code)
    if second.status_code == 200:
        s = second.json()
        print("[C] AFTER -> status:", s["status"], "total:", s["total_tiyin"],
              "materials:", s["subtotal_materials_tiyin"])
        print("[C] unpriced_materials:", s.get("unpriced_materials"))
        db_order = await db_session.get(Order, uuid.UUID(str(oid)))
        print("[C] DB -> status:", db_order.status, "materials:", db_order.subtotal_materials_tiyin)


async def test_probe_walkin_and_revision_fixes_hold(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Do the UNCOMMITTED working-tree fixes actually close their paths?"""
    order, owner_access, panel, _ = await _place_with_unpriced_panel(client, db_session)
    # Revision path: price it, confirm, then try to apply a revision.
    priced = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/prices",
        headers=_auth(owner_access),
        json={"version": order["version"], "material_prices": {str(panel.id): 250_000}},
    )
    v = priced.json()["version"]
    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": v},
    )
    assert approved.status_code == 200
    print("\n[D] confirmed via override, now open a revision")
    rev = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision",
        headers=_auth(owner_access),
        json={"version": approved.json()["version"]},
    )
    print("[D] begin revision:", rev.status_code, rev.text[:300])
