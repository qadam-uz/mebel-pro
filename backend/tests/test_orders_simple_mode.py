"""Simple production mode — the two-tap order (orders.md).

A simple-mode branch collapses production to one composite **Tayyor** and one
**Orqaga**, without forking the state machine: the same spine events, the same
stock seam, the same stamps — written in one transaction instead of five taps.
The tests that matter most here are the *leftover* ones: a branch switched from
full to simple mid-job must finish only what the order still owes, so nothing
decrements twice.
"""

import uuid

from app.models.enums import ProductionMode, StockTransactionType
from app.modules.inventory.contracts import StockItem, StockTransaction
from app.modules.sales.service import _CLIENT_ORDER_EVENT_CODE
from app.modules.workshop.contracts import Branch
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_sales_api import (
    _auth,
    _client_access,
    _client_order_notifications,
    _materials,
    _placed_order,
    _staff,
    _workshop_setup,
)


async def _set_mode(db: AsyncSession, branch_id: uuid.UUID, mode: ProductionMode) -> None:
    branch = await db.get(Branch, branch_id)
    assert branch is not None
    branch.production_mode = mode
    await db.flush()


async def _on_hand(db: AsyncSession, branch_id: uuid.UUID, material_id: uuid.UUID) -> int:
    balance = await db.scalar(
        select(StockItem.on_hand).where(
            StockItem.branch_id == branch_id,
            StockItem.branch_material_id == material_id,
        )
    )
    assert balance is not None
    return int(balance)


async def _consume_count(db: AsyncSession, material_id: uuid.UUID) -> int:
    """How many consume movements this material has ever recorded."""
    count = await db.scalar(
        select(func.count(StockTransaction.id))
        .join(StockItem, StockItem.id == StockTransaction.stock_item_id)
        .where(
            StockItem.branch_material_id == material_id,
            StockTransaction.type == StockTransactionType.CONSUME,
        )
    )
    return int(count or 0)


def _instant(value: object) -> str:
    """One timestamp, comparable across responses.

    A stamp read back through SQLite loses its `+00:00` marker, so the same
    instant serializes with and without the trailing `Z` depending on whether the
    response was built before or after the row round-tripped.
    """
    assert isinstance(value, str)
    return value.removesuffix("Z")


def _spine(body: dict[str, object]) -> list[tuple[str | None, str]]:
    events = body["events"]
    assert isinstance(events, list)
    return [(event["from_status"], event["to_status"]) for event in events]


async def _approve(client: AsyncClient, owner_access: str, order: dict[str, object]) -> dict:
    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


async def _simple_order(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    login: str = "owner",
) -> tuple[dict, str, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """An approved, banded order on a simple-mode branch, ready for its one tap.

    Returns the approved order body, the owner's token, workshop/branch ids and
    the panel + edge material ids the stock assertions read.
    """
    order, _, owner_access, workshop_id, branch_id, edge_id = await _placed_order(
        client, db_session, login=login
    )
    await _set_mode(db_session, branch_id, ProductionMode.SIMPLE)
    panel_id = uuid.UUID(str(order["items"][0]["material_id"]))
    return (
        await _approve(client, owner_access, order),
        owner_access,
        workshop_id,
        branch_id,
        panel_id,
        edge_id,
    )


async def test_tayyor_walks_the_remaining_spine_and_decrements_both_materials(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, workshop_id, branch_id, panel_id, edge_id = await _simple_order(
        client, db_session
    )
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={
            "version": order["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "ready"
    # The spine is unchanged — the tap writes the three events the five taps
    # would have written, in order, with the acting staffer as actor.
    assert _spine(body)[-3:] == [
        ("confirmed", "cutting"),
        ("cutting", "edge_banding"),
        ("edge_banding", "ready"),
    ]
    assert {event["actor_type"] for event in body["events"][-3:]} == {"workshop_user"}
    assert {event["reason"] for event in body["events"][-3:]} == {None}
    # One action time: every stamp the composite wrote is the same instant, so
    # both durations are zero rather than invented.
    assert body["cutting_started_at"] == body["cut_completed_at"]
    assert body["banding_started_at"] == body["edge_completed_at"]
    assert body["cut_completed_at"] == body["edge_completed_at"]
    assert body["cutter_assigned_at"] == body["cut_completed_at"]
    assert body["cutter_user_id"] == str(worker.id)
    assert body["edger_user_id"] == str(worker.id)
    assert body["panels_used_snapshot"] == 1
    assert body["edge_length_snapshot"] == {str(edge_id): 1000}
    # Panels and edges decrement together at Tayyor — the moved moment, not a
    # moved contract.
    assert await _on_hand(db_session, branch_id, panel_id) == 2
    assert await _on_hand(db_session, branch_id, edge_id) == 9_000


async def test_tayyor_notifies_the_client_exactly_once(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The client tracks four phases, so the whole tap is one inbox row."""
    order, owner_access, _, _, _, _ = await _simple_order(client, db_session)

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert done.status_code == 200
    codes = [row.event_code for row in await _client_order_notifications(db_session, order["id"])]
    assert codes == ["order.confirmed", "order.ready"]


def test_the_notification_map_carries_no_intermediate_statuses() -> None:
    """Both modes: `cutting` and `edge_banding` are one client phase, and a phase
    the client cannot see is not a notification."""
    assert set(_CLIENT_ORDER_EVENT_CODE) == {
        "confirmed",
        "ready",
        "completed",
        "cancelled",
    }
    assert "order.status_changed" not in set(_CLIENT_ORDER_EVENT_CODE.values())


async def _unbanded_order(
    client: AsyncClient,
    db_session: AsyncSession,
) -> tuple[dict, str, uuid.UUID, uuid.UUID, uuid.UUID]:
    """An approved order with no banded side, on a simple-mode branch."""
    owner_access, _, branch_id, _ = await _workshop_setup(db_session)
    await _set_mode(db_session, branch_id, ProductionMode.SIMPLE)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    client_access, _ = await _client_access(
        db_session, phone=f"+99890{uuid.uuid4().int % 10**7:07d}"
    )
    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(client_access))
    draft_id = created.json()["id"]
    patched = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(client_access),
        json={
            "preferred_branch_id": str(branch_id),
            "parts_snapshot": [
                {
                    "part_ref": "plain-part",
                    "material_id": str(panel.id),
                    "material_source": "shop",
                    "length_mm": 260,
                    "width_mm": 180,
                    "quantity": 2,
                    "edge_top": None,
                    "edge_bottom": None,
                    "edge_left": None,
                    "edge_right": None,
                }
            ],
        },
    )
    assert patched.status_code == 200
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft_id}/optimize", headers=_auth(client_access)
    )
    assert optimized.status_code == 200
    placed = await client.post(
        "/api/v1/client/orders",
        headers=_auth(client_access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "No Banding",
            "contact_phone": "+998901555333",
        },
    )
    assert placed.status_code == 201, placed.text
    return (
        await _approve(client, owner_access, placed.json()),
        owner_access,
        branch_id,
        panel.id,
        edge.id,
    )


async def test_tayyor_on_an_unbanded_order_takes_the_gateway_to_ready(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, branch_id, panel_id, edge_id = await _unbanded_order(client, db_session)

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "ready"
    assert _spine(body)[-2:] == [("confirmed", "cutting"), ("cutting", "ready")]
    assert body["edge_completed_at"] is None
    assert await _on_hand(db_session, branch_id, panel_id) == 2
    assert await _on_hand(db_session, branch_id, edge_id) == 10_000


async def test_an_edger_pick_is_refused_when_nothing_is_banded(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, _, _, _ = await _unbanded_order(client, db_session)
    workshop_id = uuid.UUID(str(order["workshop_id"]))
    branch_id = uuid.UUID(str(order["branch_id"]))
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)

    refused = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"], "edger_user_id": str(worker.id)},
    )

    assert refused.status_code == 400
    assert refused.json()["code"] == "edger_not_required"


async def test_tayyor_on_a_fully_own_order_writes_the_spine_and_skips_the_seam(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Zero `shop` demand is not a movement — but the banded order still walks
    `edge_banding`, because the spine is the same in both modes."""
    owner_access, _, branch_id, _ = await _workshop_setup(db_session)
    branch = await db_session.get(Branch, branch_id)
    assert branch is not None
    branch.own_material_allowed = True
    branch.production_mode = ProductionMode.SIMPLE
    await db_session.flush()
    panel, edge = await _materials(db_session, branch_id=branch_id)
    client_access, _ = await _client_access(
        db_session, phone=f"+99890{uuid.uuid4().int % 10**7:07d}"
    )
    # Every sheet and every metre is the client's: the sources go in before the
    # optimiser runs, because the shop/own split of each banded millimetre is
    # part of the result it produces.
    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(client_access))
    draft_id = created.json()["id"]
    claimed = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(client_access),
        json={
            "preferred_branch_id": str(branch_id),
            "parts_snapshot": [
                {
                    "part_ref": "own-part",
                    "material_id": str(panel.id),
                    "material_source": "own",
                    "length_mm": 260,
                    "width_mm": 180,
                    "quantity": 2,
                    "edge_top": {"material_id": str(edge.id), "source": "own"},
                    "edge_bottom": None,
                    "edge_left": {"material_id": str(edge.id), "source": "own"},
                    "edge_right": None,
                }
            ],
        },
    )
    assert claimed.status_code == 200, claimed.text
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft_id}/optimize", headers=_auth(client_access)
    )
    assert optimized.status_code == 200
    placed = await client.post(
        "/api/v1/client/orders",
        headers=_auth(client_access),
        json={
            "draft_id": draft_id,
            "branch_id": str(branch_id),
            "contact_name": "Own Everything",
            "contact_phone": "+998901555444",
        },
    )
    assert placed.status_code == 201, placed.text
    order = await _approve(client, owner_access, placed.json())

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "ready"
    assert _spine(body)[-3:] == [
        ("confirmed", "cutting"),
        ("cutting", "edge_banding"),
        ("edge_banding", "ready"),
    ]
    assert body["edge_length_snapshot"] == {}
    assert await _on_hand(db_session, branch_id, panel.id) == 3
    assert await _on_hand(db_session, branch_id, edge.id) == 10_000


async def test_tayyor_finishes_a_leftover_caught_at_cutting(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """full → simple with the saw already running: the order owes both stock
    steps, and gets exactly one of each."""
    order, _, owner_access, workshop_id, branch_id, edge_id = await _placed_order(
        client, db_session
    )
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    panel_id = uuid.UUID(str(order["items"][0]["material_id"]))
    approved = await _approve(client, owner_access, order)
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/assign",
        headers=_auth(owner_access),
        json={"version": approved["version"], "cutter_user_id": str(worker.id)},
    )
    started = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    assert started.json()["status"] == "cutting"
    await _set_mode(db_session, branch_id, ProductionMode.SIMPLE)

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": started.json()["version"]},
    )

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "ready"
    # Only what was left: no second `confirmed → cutting`.
    assert _spine(body)[-2:] == [("cutting", "edge_banding"), ("edge_banding", "ready")]
    # The real start stamp survives — that duration actually happened.
    assert _instant(body["cutting_started_at"]) == _instant(started.json()["cutting_started_at"])
    assert body["cutting_started_at"] != body["cut_completed_at"]
    # Credit falls back to who was already assigned when the tap names nobody.
    assert body["cutter_user_id"] == str(worker.id)
    assert body["edger_user_id"] is None
    assert await _on_hand(db_session, branch_id, panel_id) == 2
    assert await _on_hand(db_session, branch_id, edge_id) == 9_000
    assert await _consume_count(db_session, panel_id) == 1


async def test_tayyor_finishes_a_leftover_caught_at_edge_banding_without_recutting_stock(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The panels are already spent — the composite must not spend them twice."""
    order, _, owner_access, workshop_id, branch_id, edge_id = await _placed_order(
        client, db_session
    )
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    panel_id = uuid.UUID(str(order["items"][0]["material_id"]))
    approved = await _approve(client, owner_access, order)
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/assign",
        headers=_auth(owner_access),
        json={"version": approved["version"], "cutter_user_id": str(worker.id)},
    )
    started = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/cutting-done",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    assert cut_done.json()["status"] == "edge_banding"
    assert await _on_hand(db_session, branch_id, panel_id) == 2
    await _set_mode(db_session, branch_id, ProductionMode.SIMPLE)

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": cut_done.json()["version"]},
    )

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "ready"
    assert _spine(body)[-1:] == [("edge_banding", "ready")]
    # Panels: one movement, one sheet, from the completion that actually cut them.
    assert await _on_hand(db_session, branch_id, panel_id) == 2
    assert await _consume_count(db_session, panel_id) == 1
    assert await _on_hand(db_session, branch_id, edge_id) == 9_000
    # The cutter it credited then is not the composite's to rewrite.
    assert body["cutter_user_id"] == str(worker.id)
    assert _instant(body["cut_completed_at"]) == _instant(cut_done.json()["cut_completed_at"])
    # The banding stage never started, so its start stamp is this tap's.
    assert body["banding_started_at"] == body["edge_completed_at"]


async def test_the_composite_belongs_to_the_office_not_the_floor(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Both taps are `manage_orders` actions. A production worker has no standing
    on a simple-mode order at all — nothing was ever assigned to them."""
    from app.models.enums import AuthenticatedPrincipalType
    from app.modules.access.api import create_session

    order, _, workshop_id, branch_id, _, _ = await _simple_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=worker.id,
    )

    refused = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(tokens.access_token),
        json={"version": order["version"]},
    )

    assert refused.status_code == 404
    assert refused.json()["code"] == "order_not_found"


async def test_a_cutter_pick_is_refused_once_the_saw_is_behind_the_order(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    approved = await _approve(client, owner_access, order)
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/assign",
        headers=_auth(owner_access),
        json={"version": approved["version"], "cutter_user_id": str(worker.id)},
    )
    started = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/cutting-done",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    await _set_mode(db_session, branch_id, ProductionMode.SIMPLE)
    other = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)

    refused = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": cut_done.json()["version"], "cutter_user_id": str(other.id)},
    )

    assert refused.status_code == 400
    assert refused.json()["code"] == "cutting_already_started"


async def test_tayyor_completes_with_no_worker_and_the_report_still_counts_it(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Worker accounts are a reporting dimension in simple mode, not a gate —
    but the accountant still has to see the volume, under its own bucket."""
    order, owner_access, _, _, _, edge_id = await _simple_order(client, db_session)

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "ready"
    assert body["cutter_user_id"] is None
    assert body["edger_user_id"] is None
    assert body["assigned_cutter_user_id"] is None
    assert body["assigned_edger_user_id"] is None

    production = await client.get(
        "/api/v1/workshop/finance/production?date_from=2020-01-01&date_to=2100-01-01",
        headers=_auth(owner_access),
    )
    assert production.status_code == 200
    rows = production.json()["rows"]
    assert [row["user_id"] for row in rows] == [None]
    assert rows[0]["panels_cut"] == 1
    assert rows[0]["cut_count"] == 2
    assert rows[0]["orders_banded"] == 1
    assert rows[0]["edge_length_by_material"] == {str(edge_id): 1000}


async def test_a_worker_id_from_another_branch_is_refused_and_writes_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, _, branch_id, panel_id, _ = await _simple_order(client, db_session)
    _, other_workshop_id, other_branch_id, _ = await _workshop_setup(db_session, login="owner_b")
    outsider = await _staff(db_session, workshop_id=other_workshop_id, branch_id=other_branch_id)

    refused = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"], "cutter_user_id": str(outsider.id)},
    )

    assert refused.status_code == 404
    assert refused.json()["code"] == "worker_not_found"
    current = await client.get(
        f"/api/v1/workshop/orders/{order['id']}", headers=_auth(owner_access)
    )
    assert current.json()["status"] == "confirmed"
    assert await _on_hand(db_session, branch_id, panel_id) == 3


async def test_orqaga_restores_stock_stamps_and_worker_ids_in_one_step(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, workshop_id, branch_id, panel_id, edge_id = await _simple_order(
        client, db_session
    )
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={
            "version": order["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )
    assert done.status_code == 200

    undone = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/undo-production",
        headers=_auth(owner_access),
        json={"version": done.json()["version"], "reason": "Wrong sizes on the map"},
    )

    assert undone.status_code == 200, undone.text
    body = undone.json()
    assert body["status"] == "confirmed"
    # One revert event per step, all carrying the one reason the dialog asked for.
    assert _spine(body)[-3:] == [
        ("ready", "edge_banding"),
        ("edge_banding", "cutting"),
        ("cutting", "confirmed"),
    ]
    assert [event["reason"] for event in body["events"][-3:]] == ["Wrong sizes on the map"] * 3
    # Everything the composite wrote is taken back out.
    assert body["cutter_user_id"] is None
    assert body["edger_user_id"] is None
    assert body["assigned_cutter_user_id"] is None
    assert body["assigned_edger_user_id"] is None
    assert body["cutter_assigned_at"] is None
    assert body["edger_assigned_at"] is None
    assert body["cutting_started_at"] is None
    assert body["banding_started_at"] is None
    assert body["cut_completed_at"] is None
    assert body["edge_completed_at"] is None
    assert body["panels_used_snapshot"] is None
    assert body["cut_count_snapshot"] is None
    assert body["edge_length_snapshot"] is None
    assert await _on_hand(db_session, branch_id, panel_id) == 3
    assert await _on_hand(db_session, branch_id, edge_id) == 10_000


async def test_the_order_can_be_taped_again_after_an_undo(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Undo then re-Tayyor is a supported story, and the spine records all of it."""
    order, owner_access, _, branch_id, panel_id, edge_id = await _simple_order(client, db_session)
    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    undone = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/undo-production",
        headers=_auth(owner_access),
        json={"version": done.json()["version"], "reason": "Client changed the colour"},
    )

    again = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": undone.json()["version"]},
    )

    assert again.status_code == 200, again.text
    assert again.json()["status"] == "ready"
    assert _spine(again.json())[-3:] == [
        ("confirmed", "cutting"),
        ("cutting", "edge_banding"),
        ("edge_banding", "ready"),
    ]
    assert await _on_hand(db_session, branch_id, panel_id) == 2
    assert await _on_hand(db_session, branch_id, edge_id) == 9_000
    assert await _consume_count(db_session, panel_id) == 2


async def test_orqaga_is_ready_only_and_needs_a_reason(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, _, _, _, _ = await _simple_order(client, db_session)

    too_early = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/undo-production",
        headers=_auth(owner_access),
        json={"version": order["version"], "reason": "Nothing to undo yet"},
    )
    assert too_early.status_code == 400
    assert too_early.json()["code"] == "invalid_order_status"

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    blank_reason = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/undo-production",
        headers=_auth(owner_access),
        json={"version": done.json()["version"], "reason": "   "},
    )
    assert blank_reason.status_code == 400
    assert blank_reason.json()["code"] == "reason_required"

    collected = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/mark-collected",
        headers=_auth(owner_access),
        json={"version": done.json()["version"]},
    )
    assert collected.status_code == 200
    after_pickup = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/undo-production",
        headers=_auth(owner_access),
        json={"version": collected.json()["version"], "reason": "Too late"},
    )
    assert after_pickup.status_code == 400
    assert after_pickup.json()["code"] == "invalid_order_status"


async def test_a_second_tayyor_from_the_same_screen_conflicts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Double tap, or two admins: the loser is told the order moved."""
    order, owner_access, _, branch_id, panel_id, _ = await _simple_order(client, db_session)
    first = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert second.status_code == 409
    assert second.json()["code"] == "order_version_conflict"
    # And a caller that refreshed first still finds the order past its from-status.
    refreshed = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": first.json()["version"]},
    )
    assert refreshed.status_code == 400
    assert refreshed.json()["code"] == "invalid_order_status"
    # One tap, one decrement — the refused calls wrote nothing.
    assert await _on_hand(db_session, branch_id, panel_id) == 2
    assert await _consume_count(db_session, panel_id) == 1


async def test_a_stale_version_loses_the_race_against_a_discount(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, _, _, _, _ = await _simple_order(client, db_session)
    discounted = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/discount",
        headers=_auth(owner_access),
        json={"version": order["version"], "kind": "fixed", "value": 1_000, "reason": "Regular"},
    )
    assert discounted.status_code == 200

    stale = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert stale.status_code == 409
    assert stale.json()["code"] == "order_version_conflict"
    retried = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": discounted.json()["version"]},
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "ready"


async def test_a_simple_branch_refuses_every_per_step_production_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, owner_access, workshop_id, branch_id, _, _ = await _simple_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]
    version = order["version"]

    calls = {
        "assign": {"version": version, "cutter_user_id": str(worker.id)},
        "start-cutting": {"version": version},
        "start-banding": {"version": version},
        "cutting-done": {"version": version},
        "banding-done": {"version": version},
        "revert": {"version": version, "reason": "Mistake"},
    }
    for path, payload in calls.items():
        response = await client.post(
            f"/api/v1/workshop/orders/{order_id}/{path}",
            headers=_auth(owner_access),
            json=payload,
        )
        assert response.status_code == 409, f"{path}: {response.text}"
        assert response.json()["code"] == "simple_mode_active"
        assert response.json()["details"] == {"production_mode": "simple"}


async def test_a_full_branch_refuses_the_composite_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, _, _, _ = await _placed_order(client, db_session)
    approved = await _approve(client, owner_access, order)

    for path, payload in (
        ("complete-production", {"version": approved["version"]}),
        ("undo-production", {"version": approved["version"], "reason": "Mistake"}),
    ):
        response = await client.post(
            f"/api/v1/workshop/orders/{order['id']}/{path}",
            headers=_auth(owner_access),
            json=payload,
        )
        assert response.status_code == 409, f"{path}: {response.text}"
        assert response.json()["code"] == "full_mode_active"
        assert response.json()["details"] == {"production_mode": "full"}


async def test_mode_independent_actions_are_untouched_on_a_simple_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Approve, discount and mark-collected belong to the office in either mode."""
    order, owner_access, _, _, _, _ = await _simple_order(client, db_session)
    discounted = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/discount",
        headers=_auth(owner_access),
        json={"version": order["version"], "kind": "percent", "value": 10, "reason": "Regular"},
    )
    assert discounted.status_code == 200

    done = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": discounted.json()["version"]},
    )
    collected = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/mark-collected",
        headers=_auth(owner_access),
        json={"version": done.json()["version"]},
    )

    assert collected.status_code == 200
    assert collected.json()["status"] == "completed"
    assert collected.json()["picked_up_at"] is not None


async def test_the_order_detail_names_its_own_branch_mode(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, _, branch_id, _ = await _placed_order(client, db_session)

    in_full = await client.get(
        f"/api/v1/workshop/orders/{order['id']}", headers=_auth(owner_access)
    )
    assert in_full.json()["branch_production_mode"] == "full"

    await _set_mode(db_session, branch_id, ProductionMode.SIMPLE)
    in_simple = await client.get(
        f"/api/v1/workshop/orders/{order['id']}", headers=_auth(owner_access)
    )
    assert in_simple.json()["branch_production_mode"] == "simple"


async def test_the_owner_switches_the_mode_and_a_mid_spine_order_never_blocks_it(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    approved = await _approve(client, owner_access, order)
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/assign",
        headers=_auth(owner_access),
        json={"version": approved["version"], "cutter_user_id": str(worker.id)},
    )
    started = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    assert started.json()["status"] == "cutting"

    switched = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}",
        headers=_auth(owner_access),
        json={"production_mode": "simple"},
    )

    assert switched.status_code == 200, switched.text
    assert switched.json()["production_mode"] == "simple"
    # The order caught mid-spine is finished by the composite, not migrated.
    finished = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/complete-production",
        headers=_auth(owner_access),
        json={"version": started.json()["version"]},
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "ready"


async def test_only_the_owner_switches_the_mode(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.models.enums import AuthenticatedPrincipalType, Permission
    from app.modules.access.api import create_session

    _, workshop_id, branch_id, _ = await _workshop_setup(db_session)
    manager = await _staff(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_ORDERS,
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=manager.id,
    )

    refused = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}",
        headers=_auth(tokens.access_token),
        json={"production_mode": "simple"},
    )

    assert refused.status_code == 403


async def test_a_new_branch_is_born_simple(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, _, _, _ = await _workshop_setup(db_session)

    created = await client.post(
        "/api/v1/workshop/branches",
        headers=_auth(owner_access),
        json={
            "name": "Chilonzor",
            "address": "Tashkent, Chilonzor",
            "phone": "+998905555555",
        },
    )

    assert created.status_code == 201, created.text
    assert created.json()["production_mode"] == "simple"
