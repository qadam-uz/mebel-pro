"""Workshop staff revising a placed order (orders.md: "Revising a placed order")."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    CuttingResultStatus,
    OrderStatus,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchPricing
from app.modules.cutting.contracts import CuttingDraft, CuttingResult
from app.modules.inventory.contracts import StockItem
from app.modules.sales.contracts import Order, OrderItem
from app.modules.support.contracts import Notification
from httpx import AsyncClient
from sqlalchemy import select
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


async def _priced_workshop(db: AsyncSession) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
    workshop, branch, owner = await seed_workshop_with_owner(db)
    owner.password_reset_required = False
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
    return tokens.access_token, workshop.id, branch.id, owner.id


async def _materials(
    db: AsyncSession, *, branch_id: uuid.UUID
) -> tuple[MaterialFixture, MaterialFixture]:
    """The branch's carried panel and kromka, each stocked.

    `.id` is the BRANCH material id — what an order item, a cutting panel and a
    stock row all point at since the reshape.
    """
    manufacturer = await seed_manufacturer(db, name=f"Maker {uuid.uuid4().hex[:6]}", country="UZ")
    panel = await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        code=f"R-P-{uuid.uuid4().hex[:4]}",
        name="White",
        has_grain=False,
        thickness_mm=Decimal("18"),
        length_mm=900,
        width_mm=600,
        price_tiyin=250_000,
        min_stock=1,
    )
    edge = await seed_kromka_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        code=f"R-E-{uuid.uuid4().hex[:4]}",
        name="White",
        thickness_mm=Decimal("2"),
        tape_width_mm=19,
        price_tiyin=10_000,
        min_stock=1,
    )
    db.add_all(
        [
            StockItem(
                branch_id=branch_id,
                branch_material_id=panel.id,
                on_hand=10,
                updated_at=datetime.now(UTC),
            ),
            StockItem(
                branch_id=branch_id,
                branch_material_id=edge.id,
                on_hand=10_000,
                updated_at=datetime.now(UTC),
            ),
        ]
    )
    await db.flush()
    return panel, edge


def _part(
    panel: MaterialFixture,
    edge: MaterialFixture | None,
    *,
    quantity: int = 2,
) -> dict[str, object]:
    return {
        "part_ref": "rev-part",
        "material_id": str(panel.id),
        "material_source": "shop",
        "length_mm": 260,
        "width_mm": 180,
        "quantity": quantity,
        "edge_top": {"material_id": str(edge.id), "source": "shop"} if edge else None,
        "edge_bottom": None,
        "edge_left": None,
        "edge_right": None,
    }


async def _placed_order(
    client: AsyncClient,
    access: str,
    *,
    branch_id: uuid.UUID,
    panel: MaterialFixture,
    edge: MaterialFixture | None,
    phone: str,
) -> dict[str, object]:
    resolved = await client.post(
        "/api/v1/workshop/clients/resolve",
        headers=_auth(access),
        json={"phone": phone, "name": "Revision Client"},
    )
    assert resolved.status_code == 200, resolved.text
    client_id = str(resolved.json()["id"])
    created = await client.post(
        "/api/v1/workshop/cutting-drafts",
        headers=_auth(access),
        json={"client_id": client_id, "branch_id": str(branch_id)},
    )
    assert created.status_code == 201, created.text
    draft_id = created.json()["id"]
    patched = await client.patch(
        f"/api/v1/workshop/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": [_part(panel, edge)]},
    )
    assert patched.status_code == 200, patched.text
    optimized = await client.post(
        f"/api/v1/workshop/cutting-drafts/{draft_id}/optimize",
        headers=_auth(access),
    )
    assert optimized.status_code == 200, optimized.text
    placed = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "Revision Client",
            "contact_phone": phone,
        },
    )
    assert placed.status_code == 201, placed.text
    return dict(placed.json())


async def _revised_draft(
    client: AsyncClient,
    access: str,
    *,
    order_id: str,
    parts: list[dict[str, object]],
) -> str:
    begun = await client.post(
        f"/api/v1/workshop/orders/{order_id}/revision",
        headers=_auth(access),
    )
    assert begun.status_code == 200, begun.text
    draft_id = str(begun.json()["id"])
    patched = await client.patch(
        f"/api/v1/workshop/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"parts_snapshot": parts},
    )
    assert patched.status_code == 200, patched.text
    optimized = await client.post(
        f"/api/v1/workshop/cutting-drafts/{draft_id}/optimize",
        headers=_auth(access),
    )
    assert optimized.status_code == 200, optimized.text
    return draft_id


async def test_revision_begin_is_seeded_and_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, _ = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    order = await _placed_order(
        client, access, branch_id=branch_id, panel=panel, edge=edge, phone="+998902110011"
    )

    begun = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision", headers=_auth(access)
    )
    assert begun.status_code == 200, begun.text
    draft = begun.json()
    assert draft["revision_of_order_id"] == order["id"]
    assert draft["preferred_branch_id"] == order["branch_id"]
    # Seeded from the confirmed result's parts, ready to edit.
    assert [part["quantity"] for part in draft["parts_snapshot"]] == [2]

    again = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision", headers=_auth(access)
    )
    assert again.status_code == 200
    assert again.json()["id"] == draft["id"]

    # The open revision is surfaced on the workshop order detail.
    detail = await client.get(f"/api/v1/workshop/orders/{order['id']}", headers=_auth(access))
    assert detail.status_code == 200
    assert detail.json()["revision_draft_id"] == draft["id"]


async def test_revision_apply_rebinds_result_items_and_price(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, owner_id = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    order = await _placed_order(
        client, access, branch_id=branch_id, panel=panel, edge=edge, phone="+998902220022"
    )
    order_id = uuid.UUID(str(order["id"]))
    old_result_id = uuid.UUID(str(order["cutting_result_id"]))
    old_total = int(str(order["total_tiyin"]))

    # A discount and a surcharge that must NOT survive the revision.
    discounted = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/discount",
        headers=_auth(access),
        json={"version": order["version"], "kind": "fixed", "value": 10_000, "reason": "loyal"},
    )
    assert discounted.status_code == 200, discounted.text
    surcharged = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/surcharge",
        headers=_auth(access),
        json={
            "version": discounted.json()["version"],
            "kind": "fixed",
            "value": 6_000,
            "reason": "rush",
        },
    )
    assert surcharged.status_code == 200, surcharged.text
    version = surcharged.json()["version"]

    await _revised_draft(
        client,
        access,
        order_id=str(order["id"]),
        parts=[_part(panel, edge, quantity=3)],
    )
    applied = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision/apply",
        headers=_auth(access),
        json={"version": version, "reason": "client asked for one more"},
    )
    assert applied.status_code == 200, applied.text
    updated = applied.json()

    assert updated["status"] == "confirmed"
    assert updated["version"] == version + 1
    assert updated["cutting_result_id"] != str(old_result_id)
    assert updated["discount_tiyin"] == 0
    assert updated["discount_reason"] is None
    assert updated["surcharge_tiyin"] == 0
    assert updated["surcharge_reason"] is None
    assert updated["total_tiyin"] > old_total
    assert [item["quantity"] for item in updated["items"]] == [3]

    # Same-status edited event on the append-only spine, with the old/new totals.
    edited_events = [
        event
        for event in updated["events"]
        if event["metadata"] and event["metadata"].get("edited")
    ]
    assert len(edited_events) == 1
    event = edited_events[0]
    assert event["from_status"] == "confirmed"
    assert event["to_status"] == "confirmed"
    assert event["actor_user_id"] == str(owner_id)
    assert event["reason"] == "client asked for one more"
    # The captured previous total is the adjusted one the client last saw
    # (old_total - 10_000 discount + 6_000 surcharge).
    assert event["metadata"]["previous_total_tiyin"] == old_total - 10_000 + 6_000
    assert event["metadata"]["discount_cleared_tiyin"] == 10_000
    assert event["metadata"]["surcharge_cleared_tiyin"] == 6_000

    # The superseded result and the revision draft are gone; the new result is
    # confirmed and bound.
    assert await db_session.get(CuttingResult, old_result_id) is None
    new_result = await db_session.get(CuttingResult, uuid.UUID(updated["cutting_result_id"]))
    assert new_result is not None
    assert new_result.status is CuttingResultStatus.CONFIRMED
    assert new_result.order_id == order_id
    assert (
        await db_session.scalar(
            select(CuttingDraft.id).where(CuttingDraft.revision_of_order_id == order_id)
        )
        is None
    )
    items = (
        await db_session.scalars(select(OrderItem).where(OrderItem.order_id == order_id))
    ).all()
    assert [item.quantity for item in items] == [3]

    # The client is told their order changed.
    notification = await db_session.scalar(
        select(Notification).where(
            Notification.event_code == "order.updated",
            Notification.entity_id == order_id,
        )
    )
    assert notification is not None
    assert notification.payload["previous_total_tiyin"] == old_total - 10_000 + 6_000

    detail = await client.get(f"/api/v1/workshop/orders/{order['id']}", headers=_auth(access))
    assert detail.json()["revision_draft_id"] is None


async def test_revision_apply_clears_edger_when_banding_removed(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, owner_id = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    order = await _placed_order(
        client, access, branch_id=branch_id, panel=panel, edge=edge, phone="+998902330033"
    )
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/assign",
        headers=_auth(access),
        json={
            "version": order["version"],
            "cutter_user_id": str(owner_id),
            "edger_user_id": str(owner_id),
        },
    )
    assert assigned.status_code == 200, assigned.text
    version = assigned.json()["version"]

    await _revised_draft(
        client,
        access,
        order_id=str(order["id"]),
        parts=[_part(panel, None)],
    )
    applied = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision/apply",
        headers=_auth(access),
        json={"version": version},
    )
    assert applied.status_code == 200, applied.text
    updated = applied.json()
    assert updated["has_banding"] is False
    assert updated["assigned_edger_user_id"] is None
    assert updated["edger_assigned_at"] is None
    # The cutter keeps their assignment — only the moot edger is cleared.
    assert updated["assigned_cutter_user_id"] == str(owner_id)


async def test_revision_guards(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, _, branch_id, owner_id = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    order = await _placed_order(
        client, access, branch_id=branch_id, panel=panel, edge=edge, phone="+998902440044"
    )

    # Apply without an open revision → 404.
    missing = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision/apply",
        headers=_auth(access),
        json={"version": order["version"]},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "order_revision_not_found"

    draft_id = await _revised_draft(
        client,
        access,
        order_id=str(order["id"]),
        parts=[_part(panel, edge, quantity=4)],
    )

    # A revision draft never places a NEW order.
    placed = await client.post(
        "/api/v1/workshop/orders",
        headers=_auth(access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "X",
            "contact_phone": "+998902440044",
        },
    )
    assert placed.status_code == 400
    assert placed.json()["code"] == "cutting_result_not_usable"

    # …and its branch is locked to the order's branch.
    moved = await client.patch(
        f"/api/v1/workshop/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={"preferred_branch_id": str(uuid.uuid4())},
    )
    assert moved.status_code == 400
    assert moved.json()["code"] == "order_revision_branch_locked"

    # Stale version → optimistic-lock conflict.
    stale = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision/apply",
        headers=_auth(access),
        json={"version": 99},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "order_version_conflict"

    # Once production starts, begin and apply are both rejected.
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/assign",
        headers=_auth(access),
        json={
            "version": order["version"],
            "cutter_user_id": str(owner_id),
            "edger_user_id": str(owner_id),
        },
    )
    assert assigned.status_code == 200, assigned.text
    started = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/start-cutting",
        headers=_auth(access),
        json={"version": assigned.json()["version"]},
    )
    assert started.status_code == 200, started.text
    begun = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision", headers=_auth(access)
    )
    assert begun.status_code == 400
    assert begun.json()["code"] == "order_edit_not_allowed"
    applied = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision/apply",
        headers=_auth(access),
        json={"version": started.json()["version"]},
    )
    assert applied.status_code == 400
    assert applied.json()["code"] == "order_edit_not_allowed"

    # The leftover revision can still be discarded.
    discarded = await client.delete(
        f"/api/v1/workshop/cutting-drafts/{draft_id}", headers=_auth(access)
    )
    assert discarded.status_code == 204
    assert await db_session.get(CuttingDraft, uuid.UUID(draft_id)) is None


async def test_revision_requires_manage_orders(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access, workshop_id, branch_id, _ = await _priced_workshop(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    order = await _placed_order(
        client, access, branch_id=branch_id, panel=panel, edge=edge, phone="+998902550055"
    )
    worker = WorkshopUser(
        workshop_id=workshop_id,
        login=f"worker-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("WorkerTemp123"),
        full_name="Production Only",
        phone=f"+99890{uuid.uuid4().int % 10**7:07d}",
        is_owner=False,
        home_branch_id=branch_id,
        status=UserStatus.ACTIVE,
        password_reset_required=False,
    )
    db_session.add(worker)
    await db_session.flush()
    db_session.add(
        PermissionGrant(
            workshop_user_id=worker.id,
            permission=Permission.PROCESS_PRODUCTION,
            branch_id=branch_id,
            granted_by_user_id=worker.id,
            granted_at=datetime.now(UTC),
        )
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=worker.id,
    )

    # Unassigned production worker: the order isn't even visible → 404.
    begun = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision",
        headers=_auth(tokens.access_token),
    )
    assert begun.status_code == 404

    # Assigned as cutter they can SEE the order, but manage_orders still gates
    # the revision → 403.
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/assign",
        headers=_auth(access),
        json={
            "version": order["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )
    assert assigned.status_code == 200, assigned.text
    begun = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/revision",
        headers=_auth(tokens.access_token),
    )
    assert begun.status_code == 403

    order_row = await db_session.get(Order, uuid.UUID(str(order["id"])))
    assert order_row is not None
    assert order_row.status is OrderStatus.CONFIRMED
