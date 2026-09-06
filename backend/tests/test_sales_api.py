# ruff: noqa: RUF001 -- expected material/edge labels reuse the canonical display
# format's multiplication sign in dimensions.

import re
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    CuttingResultStatus,
    IncomeType,
    LedgerStatus,
    MaterialStatus,
    MoneyMethod,
    Permission,
    StockTransactionType,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, BranchPricing, DecorFormat, DecorType
from app.modules.cutting.contracts import CuttingDraft, CuttingResult
from app.modules.finance.contracts import Income
from app.modules.inventory.contracts import StockItem, StockTransaction
from app.modules.sales.api import order_pdf_pricing
from app.modules.sales.contracts import Order, OrderItem
from app.modules.sales.schemas import OrderDetailResponse
from app.modules.support.contracts import Notification
from app.modules.workshop.api import next_branch_no
from app.modules.workshop.contracts import Branch
from httpx import AsyncClient
from sqlalchemy import func, select
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


async def _client_access(db: AsyncSession, *, phone: str = "+998901555000") -> tuple[str, Client]:
    client = Client(phone=phone, name="Order Client")
    db.add(client)
    await db.flush()
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client.id,
    )
    return tokens.access_token, client


async def _workshop_setup(
    db: AsyncSession,
    *,
    login: str = "owner",
) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
    workshop, branch, owner = await seed_workshop_with_owner(db, login=login)
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


async def _staff(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    permission: Permission = Permission.PROCESS_PRODUCTION,
) -> WorkshopUser:
    staff = WorkshopUser(
        workshop_id=workshop_id,
        login=f"worker-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("Worker123"),
        full_name="Production Worker",
        phone="+998901555111",
        is_owner=False,
        home_branch_id=branch_id,
        status=UserStatus.ACTIVE,
        password_reset_required=False,
    )
    db.add(staff)
    await db.flush()
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
    return staff


async def _materials(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
) -> tuple[MaterialFixture, MaterialFixture]:
    """The branch's carried panel and kromka, each stocked.

    Both share one manufacturer, as they do in real catalogs. `.id` is the
    BRANCH material id — the id order items, cutting panels and stock all point
    at since the reshape.
    """
    manufacturer = await seed_manufacturer(
        db, name=f"Phase 5 Maker {uuid.uuid4().hex[:6]}", country="UZ"
    )
    panel = await seed_panel_material(
        db,
        branch_id=branch_id,
        manufacturer=manufacturer,
        code="P5-P",
        name="White",
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
        code="P5-E",
        name="White",
        thickness_mm=Decimal("2"),
        tape_width_mm=19,
        price_tiyin=10_000,
        min_stock=1_000,
    )
    db.add_all(
        [
            StockItem(
                branch_id=branch_id,
                branch_material_id=panel.id,
                on_hand=3,
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


async def _optimized_draft(
    client: AsyncClient,
    access: str,
    *,
    branch_id: uuid.UUID,
    panel: MaterialFixture,
    edge: MaterialFixture,
) -> dict[str, object]:
    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(access))
    assert created.status_code == 201
    draft_id = created.json()["id"]
    patched = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(access),
        json={
            "preferred_branch_id": str(branch_id),
            "parts_snapshot": [
                {
                    "part_ref": "phase5-part",
                    "material_id": str(panel.id),
                    "material_source": "shop",
                    "length_mm": 260,
                    "width_mm": 180,
                    "quantity": 2,
                    "edge_top": {"material_id": str(edge.id), "source": "shop"},
                    "edge_bottom": None,
                    "edge_left": {"material_id": str(edge.id), "source": "shop"},
                    "edge_right": None,
                }
            ],
        },
    )
    assert patched.status_code == 200
    optimized = await client.post(
        f"/api/v1/client/cutting-drafts/{draft_id}/optimize",
        headers=_auth(access),
    )
    assert optimized.status_code == 200
    return optimized.json()


async def _placed_order(
    client: AsyncClient,
    db: AsyncSession,
    *,
    login: str = "owner",
) -> tuple[dict[str, object], str, str, uuid.UUID, uuid.UUID, uuid.UUID]:
    owner_access, workshop_id, branch_id, _ = await _workshop_setup(db, login=login)
    panel, edge = await _materials(db, branch_id=branch_id)
    client_access, _ = await _client_access(db, phone=f"+99890{uuid.uuid4().int % 10**7:07d}")
    draft = await _optimized_draft(
        client,
        client_access,
        branch_id=branch_id,
        panel=panel,
        edge=edge,
    )
    placed = await client.post(
        "/api/v1/client/orders",
        headers=_auth(client_access),
        json={
            "draft_id": draft["id"],
            "branch_id": str(branch_id),
            "contact_name": "Checkout Name",
            "contact_phone": "+998901555222",
            "note_client": "Call before cutting",
        },
    )
    assert placed.status_code == 201
    # The client path mints the same global handle the walk-in path does.
    assert re.fullmatch(r"[1-9]\d{5}", str(placed.json()["order_number"]))
    return placed.json(), client_access, owner_access, workshop_id, branch_id, edge.id


async def test_client_places_order_and_confirms_cutting_snapshot(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, client_access, owner_access, _, _, edge_id = await _placed_order(client, db_session)
    order_id = uuid.UUID(str(order["id"]))
    result_id = uuid.UUID(str(order["cutting_result_id"]))
    draft_count = await db_session.scalar(select(func.count(CuttingDraft.id)))
    result = await db_session.get(CuttingResult, result_id)
    item_count = await db_session.scalar(
        select(func.count(OrderItem.id)).where(OrderItem.order_id == order_id)
    )
    client_list = await client.get("/api/v1/client/orders", headers=_auth(client_access))
    workshop_list = await client.get(
        "/api/v1/workshop/orders?status=active",
        headers=_auth(owner_access),
    )
    workshop_page_one = await client.get(
        "/api/v1/workshop/orders?status=active&limit=1&offset=0",
        headers=_auth(owner_access),
    )
    workshop_page_two = await client.get(
        "/api/v1/workshop/orders?status=active&limit=1&offset=1",
        headers=_auth(owner_access),
    )

    assert order["status"] == "new"
    assert order["contact_name"] == "Checkout Name"
    assert order["contact_phone"] == "+998901555222"
    assert order["subtotal_cutting_tiyin"] == 50_000
    assert order["subtotal_materials_tiyin"] == 250_000
    assert order["subtotal_edge_banding_tiyin"] == 30_000
    assert order["total_tiyin"] == 330_000
    assert order["items"][0]["unit_material_price_tiyin"] == 125_000
    assert order["items"][0]["edge_cost_tiyin"] == 10_000
    assert order["items"][0]["line_total_tiyin"] == 260_000
    assert order["cutting_result"]["status"] == "confirmed"
    assert order["planned_panels"] == 1
    planned_edge_line = order["planned_edge_lines"][0]
    assert planned_edge_line["material_id"] == str(edge_id)
    # Canonical edge shape: `{manufacturer} {decor}` · `{color}` · `{thickness}x{width} mm`.
    assert planned_edge_line["material_label"].startswith("Phase 5 Maker ")
    assert planned_edge_line["material_label"].endswith(" P5-E · White · 2×19 mm")
    assert planned_edge_line["thickness_mm"] == "2"
    assert planned_edge_line["color"] == "White"
    assert planned_edge_line["consumed_mm"] == 1000
    # Itemized money lines rebuilt from order-time snapshots: the panel line
    # reconciles with subtotal_materials, the edge line carries only the
    # material share of subtotal_edge_banding (labor stays an aggregate).
    panel_line, edge_line = order["price_lines"]
    assert panel_line["kind"] == "panel"
    assert panel_line["panels_used"] == 1
    assert panel_line["line_total_tiyin"] == 250_000
    # Canonical panel shape: `{type} {manufacturer} {decor}` · `{color}` · `LxWxT mm`.
    assert panel_line["material_name"].startswith("LDSP Phase 5 Maker ")
    assert panel_line["material_name"].endswith(" P5-P · White · 900×600×18 mm")
    assert edge_line["kind"] == "edge"
    assert edge_line["material_id"] == str(edge_id)
    assert edge_line["consumed_mm"] == 1000
    assert edge_line["line_total_tiyin"] == 10_000
    assert result is not None
    assert result.status is CuttingResultStatus.CONFIRMED
    assert result.order_id == order_id
    assert result.draft_id is None
    assert draft_count == 0
    assert item_count == 1
    assert client_list.status_code == 200
    assert client_list.json()[0]["id"] == str(order_id)
    assert workshop_list.status_code == 200
    assert workshop_list.json()[0]["planned_panels"] == 1
    assert workshop_list.json()[0]["planned_edge_lines"][0]["consumed_mm"] == 1000
    assert workshop_page_one.status_code == 200
    assert [row["id"] for row in workshop_page_one.json()] == [str(order_id)]
    assert workshop_page_two.status_code == 200
    assert workshop_page_two.json() == []


async def test_placing_an_order_pins_its_branch_and_a_later_order_moves_the_pin(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Decision 25: the order's branch becomes «Ustaxonangiz», latest wins.

    Opening the editor from a branch row no longer pins anything, so this is
    the path that has to carry the move — including away from a branch the
    client was already pinned to.
    """
    _, _, first_branch_id, _ = await _workshop_setup(db_session, login="pin_first")
    first_panel, first_edge = await _materials(db_session, branch_id=first_branch_id)
    client_access, client_row = await _client_access(db_session, phone="+998901555777")
    assert client_row.preferred_branch_id is None

    first_draft = await _optimized_draft(
        client,
        client_access,
        branch_id=first_branch_id,
        panel=first_panel,
        edge=first_edge,
    )
    first_order = await client.post(
        "/api/v1/client/orders",
        headers=_auth(client_access),
        json={
            "draft_id": first_draft["id"],
            "branch_id": str(first_branch_id),
            "contact_name": "Pin Client",
            "contact_phone": "+998901555777",
        },
    )
    assert first_order.status_code == 201, first_order.text
    # Nothing was pinned: the first order settles it.
    assert client_row.preferred_branch_id == first_branch_id

    _, _, second_branch_id, _ = await _workshop_setup(db_session, login="pin_second")
    second_panel, second_edge = await _materials(db_session, branch_id=second_branch_id)
    second_draft = await _optimized_draft(
        client,
        client_access,
        branch_id=second_branch_id,
        panel=second_panel,
        edge=second_edge,
    )
    second_order = await client.post(
        "/api/v1/client/orders",
        headers=_auth(client_access),
        json={
            "draft_id": second_draft["id"],
            "branch_id": str(second_branch_id),
            "contact_name": "Pin Client",
            "contact_phone": "+998901555777",
        },
    )
    assert second_order.status_code == 201, second_order.text
    # And the second order moves it, rather than leaving the first one standing.
    assert client_row.preferred_branch_id == second_branch_id


async def test_client_order_payloads_carry_the_workshop_branch_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The naming rule needs a number, not a guess.

    A workshop with one visible branch is shown by its own name and the branch
    name never appears; several and it is «{Workshop} · {Branch}». The web has
    two names and no way to tell the two cases apart, so the count travels —
    counted with the same visibility predicate Ustaxonalarim uses, which is why
    an `inactive` branch does not move it.
    """

    order, client_access, _, workshop_id, _, _ = await _placed_order(
        client, db_session, login="count_owner"
    )
    order_id = str(order["id"])

    listed = await client.get("/api/v1/client/orders", headers=_auth(client_access))
    detail = await client.get(f"/api/v1/client/orders/{order_id}", headers=_auth(client_access))

    assert listed.status_code == 200
    assert detail.status_code == 200
    assert [row["workshop_branch_count"] for row in listed.json()] == [1]
    assert detail.json()["workshop_branch_count"] == 1

    for name, status in (("Chilonzor", "active"), ("Sergeli", "inactive")):
        db_session.add(
            Branch(
                workshop_id=workshop_id,
                branch_no=await next_branch_no(db_session),
                name=name,
                address=f"Tashkent, {name}",
                phone="+998901111111",
                status=status,
            )
        )
    await db_session.flush()

    listed = await client.get("/api/v1/client/orders", headers=_auth(client_access))
    detail = await client.get(f"/api/v1/client/orders/{order_id}", headers=_auth(client_access))

    # Two visible counters, not three: the inactive one is invisible to the
    # client everywhere else too, so it cannot be what makes their order card
    # start naming a branch.
    assert [row["workshop_branch_count"] for row in listed.json()] == [2]
    assert detail.json()["workshop_branch_count"] == 2


async def test_client_order_detail_gates_settlement_until_ready(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, client_access, owner_access, workshop_id, branch_id, _ = await _placed_order(
        client,
        db_session,
    )
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]

    new_detail = await client.get(f"/api/v1/client/orders/{order_id}", headers=_auth(client_access))
    assert new_detail.status_code == 200
    assert new_detail.json()["settlement"] is None

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )
    cutter_queue = await client.get(
        f"/api/v1/workshop/orders?status=active&assigned_cutter_user_id={worker.id}",
        headers=_auth(owner_access),
    )
    unrelated_cutter_queue = await client.get(
        f"/api/v1/workshop/orders?status=active&assigned_cutter_user_id={uuid.uuid4()}",
        headers=_auth(owner_access),
    )
    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    edger_queue = await client.get(
        f"/api/v1/workshop/orders?status=edge_banding&assigned_edger_user_id={worker.id}",
        headers=_auth(owner_access),
    )
    ready = await client.post(
        f"/api/v1/workshop/orders/{order_id}/banding-done",
        headers=_auth(owner_access),
        json={"version": cut_done.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    assert cutter_queue.status_code == 200
    assert [row["id"] for row in cutter_queue.json()] == [order_id]
    assert unrelated_cutter_queue.status_code == 200
    assert unrelated_cutter_queue.json() == []
    assert edger_queue.status_code == 200
    assert [row["id"] for row in edger_queue.json()] == [order_id]
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    owner_id = await db_session.scalar(
        select(WorkshopUser.id).where(
            WorkshopUser.workshop_id == workshop_id,
            WorkshopUser.is_owner.is_(True),
        )
    )
    assert owner_id is not None
    db_session.add_all(
        [
            Income(
                workshop_id=workshop_id,
                branch_id=branch_id,
                type=IncomeType.ORDER_PAYMENT,
                order_id=uuid.UUID(order_id),
                amount_tiyin=120_000,
                method=MoneyMethod.CASH,
                received_on=date(2026, 6, 8),
                note="Client deposit",
                status=LedgerStatus.RECORDED,
                recorded_by_user_id=owner_id,
            ),
            Income(
                workshop_id=workshop_id,
                branch_id=branch_id,
                type=IncomeType.ORDER_PAYMENT,
                order_id=uuid.UUID(order_id),
                amount_tiyin=50_000,
                method=MoneyMethod.CASH,
                received_on=date(2026, 6, 8),
                note="Voided duplicate",
                status=LedgerStatus.VOIDED,
                recorded_by_user_id=owner_id,
                voided_by_user_id=owner_id,
                voided_at=datetime.now(UTC),
                voided_reason="Duplicate",
            ),
        ]
    )
    await db_session.flush()

    ready_detail = await client.get(
        f"/api/v1/client/orders/{order_id}", headers=_auth(client_access)
    )

    assert ready_detail.status_code == 200
    assert ready_detail.json()["settlement"] == {
        "total_tiyin": 330_000,
        "recorded_tiyin": 120_000,
        "balance_tiyin": 210_000,
    }


async def test_production_staff_sees_and_updates_only_assigned_orders(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    other_worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    worker_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=worker.id,
    )
    other_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=other_worker.id,
    )
    worker_access = worker_tokens.access_token
    other_access = other_tokens.access_token
    order_id = order["id"]

    before_assignment = await client.get(
        "/api/v1/workshop/orders?status=active",
        headers=_auth(worker_access),
    )
    invisible_detail = await client.get(
        f"/api/v1/workshop/orders/{order_id}",
        headers=_auth(worker_access),
    )

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )

    worker_list = await client.get(
        "/api/v1/workshop/orders?status=active",
        headers=_auth(worker_access),
    )
    worker_detail = await client.get(
        f"/api/v1/workshop/orders/{order_id}",
        headers=_auth(worker_access),
    )
    other_list = await client.get(
        "/api/v1/workshop/orders?status=active",
        headers=_auth(other_access),
    )
    other_detail = await client.get(
        f"/api/v1/workshop/orders/{order_id}",
        headers=_auth(other_access),
    )
    other_start = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(other_access),
        json={"version": assigned.json()["version"]},
    )
    worker_start = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(worker_access),
        json={"version": assigned.json()["version"]},
    )
    other_cut = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(other_access),
        json={"version": worker_start.json()["version"]},
    )
    worker_cut = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(worker_access),
        json={"version": worker_start.json()["version"]},
    )

    assert before_assignment.status_code == 200
    assert before_assignment.json() == []
    assert invisible_detail.status_code == 404
    assert worker_list.status_code == 200
    assert [row["id"] for row in worker_list.json()] == [order_id]
    assert worker_detail.status_code == 200
    assert worker_detail.json()["id"] == order_id
    assert other_list.status_code == 200
    assert other_list.json() == []
    assert other_detail.status_code == 404
    assert other_start.status_code == 404
    assert worker_start.status_code == 200
    assert worker_start.json()["status"] == "cutting"
    assert worker_start.json()["cutting_started_at"] is not None
    assert other_cut.status_code == 404
    assert worker_cut.status_code == 200
    assert worker_cut.json()["status"] == "edge_banding"


async def test_workshop_transitions_consume_restore_stock_and_lock_versions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, workshop_id, branch_id, edge_id = await _placed_order(
        client,
        db_session,
    )
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assert approved.status_code == 200

    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )
    assert assigned.status_code == 200
    # Assignment is metadata: the order stays confirmed until the cutter starts.
    assert assigned.json()["status"] == "confirmed"
    assert assigned.json()["cutter_assigned_at"] is not None
    assert assigned.json()["edger_assigned_at"] is not None

    stale = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={"version": approved.json()["version"], "cutter_user_id": str(worker.id)},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "order_version_conflict"

    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "cutting"
    assert started.json()["cutting_started_at"] is not None

    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    assert cut_done.status_code == 200
    assert cut_done.json()["status"] == "edge_banding"
    assert cut_done.json()["cutter_user_id"] == str(worker.id)

    panel_tx = (
        await db_session.scalars(
            select(StockTransaction).where(StockTransaction.type == StockTransactionType.CONSUME)
        )
    ).all()
    assert [(tx.quantity, tx.order_id) for tx in panel_tx] == [(-1, uuid.UUID(order_id))]

    reverted_cut = await client.post(
        f"/api/v1/workshop/orders/{order_id}/revert",
        headers=_auth(owner_access),
        json={"version": cut_done.json()["version"], "reason": "Saw mistake"},
    )
    assert reverted_cut.status_code == 200
    assert reverted_cut.json()["status"] == "cutting"
    assert reverted_cut.json()["cutter_user_id"] is None

    restored_panel = await db_session.scalar(
        select(StockItem.on_hand).where(StockItem.branch_id == branch_id, StockItem.on_hand == 3)
    )
    assert restored_panel == 3

    cut_done_again = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={
            "version": reverted_cut.json()["version"],
            "completed_by_user_id": str(worker.id),
        },
    )
    band_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/banding-done",
        headers=_auth(owner_access),
        json={
            "version": cut_done_again.json()["version"],
            "completed_by_user_id": str(worker.id),
        },
    )
    assert band_done.status_code == 200
    assert band_done.json()["status"] == "ready"
    assert band_done.json()["edge_length_snapshot"] == {str(edge_id): 1000}

    production = await client.get(
        "/api/v1/workshop/finance/production?date_from=2020-01-01&date_to=2100-01-01",
        headers=_auth(owner_access),
    )
    assert production.status_code == 200
    production_row = production.json()["rows"][0]
    assert production_row["user_id"] == str(worker.id)
    assert production_row["full_name"] == "Production Worker"
    assert production_row["panels_cut"] == 1
    assert production_row["cut_count"] == 2
    assert production_row["orders_banded"] == 1
    assert production_row["edge_length_by_material"] == {str(edge_id): 1000}
    assert production_row["edge_lines"][0]["material_id"] == str(edge_id)
    # Canonical edge shape: `{manufacturer} {decor}` · `{color}` · `{thickness}x{width} mm`.
    assert production_row["edge_lines"][0]["material_label"].startswith("Phase 5 Maker ")
    assert production_row["edge_lines"][0]["material_label"].endswith(" P5-E · White · 2×19 mm")
    assert production_row["edge_lines"][0]["thickness_mm"] == "2"
    assert production_row["edge_lines"][0]["color"] == "White"
    assert production_row["edge_lines"][0]["length_mm"] == 1000
    assert production_row["edge_length_by_thickness"] == [{"thickness_mm": "2", "length_mm": 1000}]

    edge_on_hand = await db_session.scalar(
        select(StockItem.on_hand).where(
            StockItem.branch_id == branch_id,
            StockItem.branch_material_id == edge_id,
        )
    )
    assert edge_on_hand == 9000

    reverted_edge = await client.post(
        f"/api/v1/workshop/orders/{order_id}/revert",
        headers=_auth(owner_access),
        json={"version": band_done.json()["version"], "reason": "Banding correction"},
    )
    assert reverted_edge.status_code == 200
    assert reverted_edge.json()["status"] == "edge_banding"
    edge_restored = await db_session.scalar(
        select(StockItem.on_hand).where(
            StockItem.branch_id == branch_id,
            StockItem.branch_material_id == edge_id,
        )
    )
    assert edge_restored == 10000


async def test_assignment_locks_per_role_once_the_stage_starts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The cutter locks when cutting starts and the edger when banding is
    stamped started; revert clears the start stamp and unlocks again."""
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    cutter = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    edger = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    substitute = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(cutter.id),
            "edger_user_id": str(edger.id),
        },
    )
    assert assigned.status_code == 200
    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    assert started.status_code == 200

    cutter_swap = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "cutter_user_id": str(substitute.id)},
    )
    assert cutter_swap.status_code == 400
    assert cutter_swap.json()["code"] == "cutting_already_started"

    # The edger's work hasn't started — swapping them mid-cut is still allowed.
    edger_swap = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "edger_user_id": str(substitute.id)},
    )
    assert edger_swap.status_code == 200
    assert edger_swap.json()["assigned_edger_user_id"] == str(substitute.id)

    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={"version": edger_swap.json()["version"], "completed_by_user_id": str(cutter.id)},
    )
    assert cut_done.status_code == 200
    assert cut_done.json()["status"] == "edge_banding"

    # Queued at the banding station the edger is still swappable...
    edger_back = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={"version": cut_done.json()["version"], "edger_user_id": str(edger.id)},
    )
    assert edger_back.status_code == 200

    banding_started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-banding",
        headers=_auth(owner_access),
        json={"version": edger_back.json()["version"]},
    )
    assert banding_started.status_code == 200

    # ...but not once banding is stamped started.
    edger_late = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={"version": banding_started.json()["version"], "edger_user_id": str(substitute.id)},
    )
    assert edger_late.status_code == 400
    assert edger_late.json()["code"] == "banding_already_started"

    # Revert clears the start stamp — the deliberate unlock path.
    reverted = await client.post(
        f"/api/v1/workshop/orders/{order_id}/revert",
        headers=_auth(owner_access),
        json={"version": banding_started.json()["version"], "reason": "Swap the edger"},
    )
    assert reverted.status_code == 200
    assert reverted.json()["status"] == "cutting"
    edger_after_revert = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={"version": reverted.json()["version"], "edger_user_id": str(substitute.id)},
    )
    assert edger_after_revert.status_code == 200
    assert edger_after_revert.json()["assigned_edger_user_id"] == str(substitute.id)


async def test_discount_requires_version_and_client_cancel_only_new(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, client_access, owner_access, _, _, _ = await _placed_order(client, db_session)
    order_id = order["id"]

    discounted = await client.post(
        f"/api/v1/workshop/orders/{order_id}/discount",
        headers=_auth(owner_access),
        json={"version": order["version"], "kind": "fixed", "value": 30_000, "reason": "Promo"},
    )
    assert discounted.status_code == 200
    assert discounted.json()["discount_tiyin"] == 30_000
    assert discounted.json()["total_tiyin"] == 300_000

    removed_discount = await client.post(
        f"/api/v1/workshop/orders/{order_id}/discount",
        headers=_auth(owner_access),
        json={
            "version": discounted.json()["version"],
            "kind": "fixed",
            "value": 0,
            "reason": "Remove discount",
        },
    )
    assert removed_discount.status_code == 200
    assert removed_discount.json()["discount_tiyin"] == 0
    assert removed_discount.json()["discount_reason"] is None
    assert removed_discount.json()["discount_applied_by_user_id"] is None
    assert removed_discount.json()["total_tiyin"] == 330_000

    stale_cancel = await client.post(
        f"/api/v1/client/orders/{order_id}/cancel",
        headers=_auth(client_access),
        json={"version": order["version"], "reason": "Changed plans"},
    )
    assert stale_cancel.status_code == 409

    cancelled = await client.post(
        f"/api/v1/client/orders/{order_id}/cancel",
        headers=_auth(client_access),
        json={"version": removed_discount.json()["version"], "reason": "Changed plans"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    stored = await db_session.get(Order, uuid.UUID(order_id))
    stock_tx_count = await db_session.scalar(select(func.count(StockTransaction.id)))
    assert stored is not None
    assert stored.cancelled_at is not None
    assert stock_tx_count == 0


async def test_surcharge_adds_to_total_and_coexists_with_discount(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, _, _, _ = await _placed_order(client, db_session)
    order_id = order["id"]  # pre-adjustment total is 330_000

    surcharged = await client.post(
        f"/api/v1/workshop/orders/{order_id}/surcharge",
        headers=_auth(owner_access),
        json={"version": order["version"], "kind": "fixed", "value": 20_000, "reason": "Rush job"},
    )
    assert surcharged.status_code == 200
    assert surcharged.json()["surcharge_tiyin"] == 20_000
    assert surcharged.json()["surcharge_reason"] == "Rush job"
    assert surcharged.json()["surcharge_applied_by_user_id"] is not None
    assert surcharged.json()["total_tiyin"] == 350_000  # 330_000 + 20_000

    # A discount stacks with the surcharge: 330_000 - 30_000 + 20_000 = 320_000.
    discounted = await client.post(
        f"/api/v1/workshop/orders/{order_id}/discount",
        headers=_auth(owner_access),
        json={
            "version": surcharged.json()["version"],
            "kind": "fixed",
            "value": 30_000,
            "reason": "Loyalty",
        },
    )
    assert discounted.status_code == 200
    assert discounted.json()["discount_tiyin"] == 30_000
    assert discounted.json()["surcharge_tiyin"] == 20_000
    assert discounted.json()["total_tiyin"] == 320_000

    # Percent surcharge resolves against the subtotal (330_000), not the discounted
    # total: 10% → 33_000, so total = 330_000 - 30_000 + 33_000 = 333_000.
    percent = await client.post(
        f"/api/v1/workshop/orders/{order_id}/surcharge",
        headers=_auth(owner_access),
        json={
            "version": discounted.json()["version"],
            "kind": "percent",
            "value": 10,
            "reason": "10% custom work",
        },
    )
    assert percent.status_code == 200
    assert percent.json()["surcharge_tiyin"] == 33_000
    assert percent.json()["total_tiyin"] == 333_000

    # Removing the surcharge clears its metadata and returns the total to the
    # discounted figure (330_000 - 30_000 = 300_000).
    removed = await client.post(
        f"/api/v1/workshop/orders/{order_id}/surcharge",
        headers=_auth(owner_access),
        json={
            "version": percent.json()["version"],
            "kind": "fixed",
            "value": 0,
            "reason": "Remove surcharge",
        },
    )
    assert removed.status_code == 200
    assert removed.json()["surcharge_tiyin"] == 0
    assert removed.json()["surcharge_reason"] is None
    assert removed.json()["surcharge_applied_by_user_id"] is None
    assert removed.json()["total_tiyin"] == 300_000

    stale = await client.post(
        f"/api/v1/workshop/orders/{order_id}/surcharge",
        headers=_auth(owner_access),
        json={"version": order["version"], "kind": "fixed", "value": 5_000, "reason": "Stale"},
    )
    assert stale.status_code == 409


async def test_surcharge_rejects_bad_percent_terminal_status_and_unprivileged(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, client_access, owner_access, workshop_id, branch_id, _ = await _placed_order(
        client, db_session
    )
    order_id = order["id"]

    # A percent above 100 is rejected outright (not silently resolved to >100%).
    bad_percent = await client.post(
        f"/api/v1/workshop/orders/{order_id}/surcharge",
        headers=_auth(owner_access),
        json={"version": order["version"], "kind": "percent", "value": 150, "reason": "Too much"},
    )
    assert bad_percent.status_code == 400
    assert bad_percent.json()["code"] == "invalid_surcharge"

    # A production-scoped staffer without manage_orders can't set a surcharge.
    staff = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    staff_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )
    forbidden = await client.post(
        f"/api/v1/workshop/orders/{order_id}/surcharge",
        headers=_auth(staff_tokens.access_token),
        json={"version": order["version"], "kind": "fixed", "value": 5_000, "reason": "Nope"},
    )
    # Denied for lack of manage_orders — the scoped lookup declines the order
    # (403 forbidden, or 404 to avoid an existence oracle) — never applies it.
    assert forbidden.status_code in (403, 404)

    # Once the order is terminal (cancelled), a surcharge is not allowed.
    cancelled = await client.post(
        f"/api/v1/client/orders/{order_id}/cancel",
        headers=_auth(client_access),
        json={"version": order["version"], "reason": "Changed plans"},
    )
    assert cancelled.status_code == 200
    surcharge_after = await client.post(
        f"/api/v1/workshop/orders/{order_id}/surcharge",
        headers=_auth(owner_access),
        json={
            "version": cancelled.json()["version"],
            "kind": "fixed",
            "value": 5_000,
            "reason": "Late",
        },
    )
    assert surcharge_after.status_code == 400
    assert surcharge_after.json()["code"] == "surcharge_not_allowed"


async def test_order_carries_the_drawing_name_it_was_placed_from(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The order card is identified by the drawing the client named, not by the
    branch. An unnamed drawing yields `None` — the surface falls back, the API
    does not invent a label."""
    owner_access, _, branch_id, _ = await _workshop_setup(db_session)
    del owner_access
    panel, edge = await _materials(db_session, branch_id=branch_id)
    client_access, _ = await _client_access(db_session, phone="+998901555991")
    draft = await _optimized_draft(
        client, client_access, branch_id=branch_id, panel=panel, edge=edge
    )
    named = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft['id']}",
        headers=_auth(client_access),
        json={"name": "Oshxona shkafi"},
    )
    assert named.status_code == 200

    placed = await client.post(
        "/api/v1/client/orders",
        headers=_auth(client_access),
        json={
            "draft_id": draft["id"],
            "branch_id": str(branch_id),
            "contact_name": "Named Draft",
            "contact_phone": "+998901555222",
        },
    )
    assert placed.status_code == 201, placed.text
    order_id = placed.json()["id"]
    assert placed.json()["draft_name"] == "Oshxona shkafi"

    listed = await client.get("/api/v1/client/orders", headers=_auth(client_access))
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == order_id)
    assert row["draft_name"] == "Oshxona shkafi"
    # Placed by the client themselves — no staff badge.
    assert row["created_via_workshop"] is False

    detail = await client.get(f"/api/v1/client/orders/{order_id}", headers=_auth(client_access))
    assert detail.status_code == 200
    assert detail.json()["draft_name"] == "Oshxona shkafi"


async def test_order_search_matches_the_drawing_name(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The card's headline is the drawing name, so the search box has to reach
    it — and an unnamed order must not be swept in by a name query."""
    owner_access, _, branch_id, _ = await _workshop_setup(db_session)
    del owner_access
    panel, edge = await _materials(db_session, branch_id=branch_id)
    client_access, _ = await _client_access(db_session, phone="+998901555992")

    async def _place(name: str | None, contact: str) -> str:
        draft = await _optimized_draft(
            client, client_access, branch_id=branch_id, panel=panel, edge=edge
        )
        if name is not None:
            patched = await client.patch(
                f"/api/v1/client/cutting-drafts/{draft['id']}",
                headers=_auth(client_access),
                json={"name": name},
            )
            assert patched.status_code == 200
        placed = await client.post(
            "/api/v1/client/orders",
            headers=_auth(client_access),
            json={
                "draft_id": draft["id"],
                "branch_id": str(branch_id),
                "contact_name": contact,
                "contact_phone": "+998901555222",
            },
        )
        assert placed.status_code == 201, placed.text
        return str(placed.json()["id"])

    named_id = await _place("Oshxona shkafi", "Named")
    unnamed_id = await _place(None, "Unnamed")

    async def _search(term: str) -> set[str]:
        response = await client.get(
            "/api/v1/client/orders",
            params={"search": term},
            headers=_auth(client_access),
        )
        assert response.status_code == 200
        return {str(row["id"]) for row in response.json()}

    # Whole name, a fragment, and a different case all find it.
    assert await _search("Oshxona shkafi") == {named_id}
    assert await _search("shkaf") == {named_id}
    assert await _search("OSHXONA") == {named_id}
    # The unnamed order is reachable by its own fields, never by a name query.
    assert unnamed_id not in await _search("shkaf")
    assert unnamed_id in await _search("Unnamed")


async def test_order_from_an_unnamed_drawing_reports_no_draft_name(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, client_access, _, _, _, _ = await _placed_order(client, db_session)

    listed = await client.get("/api/v1/client/orders", headers=_auth(client_access))
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == order["id"])
    assert row["draft_name"] is None
    assert row["created_via_workshop"] is False


async def test_client_orders_active_filter_expands_to_status_union(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Pin the synthetic ?status=active filter (CB-119): it must expand to the
    new/confirmed/cutting/edge_banding/ready union, not be a no-op passthrough."""
    order, client_access, _, _, _, _ = await _placed_order(client, db_session)
    order_id = order["id"]

    def _ids(rows: list[dict[str, object]]) -> set[str]:
        return {str(row["id"]) for row in rows}

    async def _list(status_filter: str) -> list[dict[str, object]]:
        response = await client.get(
            "/api/v1/client/orders",
            params={"status": status_filter},
            headers=_auth(client_access),
        )
        assert response.status_code == 200
        return list(response.json())

    # A fresh order is "new" → in the active union, and excluded from the terminal tabs.
    assert order_id in _ids(await _list("active"))
    assert order_id not in _ids(await _list("completed"))
    assert order_id not in _ids(await _list("cancelled"))

    cancel = await client.post(
        f"/api/v1/client/orders/{order_id}/cancel",
        headers=_auth(client_access),
        json={"version": order["version"], "reason": "Changed plans"},
    )
    assert cancel.status_code == 200

    # Once cancelled it drops out of active and appears under the cancelled tab.
    assert order_id not in _ids(await _list("active"))
    assert order_id in _ids(await _list("cancelled"))


async def test_view_orders_grant_reads_the_branch_orders_but_cannot_act(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """QAD-166: `view_orders` is exactly what its name says — read access to the
    branch's orders, including the client contact and the money on them, and no
    office action. The grant was called `view_dashboard` while doing this, so an
    owner ticking it thought they were unlocking a KPI page.
    """
    order, _, _, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    reader = await _staff(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.VIEW_ORDERS,
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=reader.id,
    )
    reader_access = tokens.access_token

    listed = await client.get("/api/v1/workshop/orders", headers=_auth(reader_access))
    detail = await client.get(
        f"/api/v1/workshop/orders/{order['id']}",
        headers=_auth(reader_access),
    )
    approve = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(reader_access),
        json={"version": order["version"]},
    )

    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [order["id"]]
    assert detail.status_code == 200
    assert detail.json()["contact_phone"] == "+998901555222"
    assert approve.status_code == 403


async def test_workshop_orders_date_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, _, branch_id, _ = await _placed_order(client, db_session)
    today = datetime.now(UTC).date()
    tomorrow = today + timedelta(days=1)

    today_rows = await client.get(
        "/api/v1/workshop/orders",
        headers=_auth(owner_access),
        params={
            "branch_id": str(branch_id),
            "date_from": today.isoformat(),
            "date_to": today.isoformat(),
        },
    )
    future_rows = await client.get(
        "/api/v1/workshop/orders",
        headers=_auth(owner_access),
        params={
            "branch_id": str(branch_id),
            "date_from": tomorrow.isoformat(),
            "date_to": tomorrow.isoformat(),
        },
    )
    assert today_rows.status_code == 200
    assert [row["id"] for row in today_rows.json()] == [order["id"]]
    assert future_rows.status_code == 200
    assert future_rows.json() == []


async def test_workshop_orders_contact_phone_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The operator types whatever the client dictates — partial digits, spaced
    formatting, or the full number — and only digits count as signal."""
    order, _, owner_access, _, branch_id, _ = await _placed_order(client, db_session)

    async def rows(phone: str) -> list[str]:
        response = await client.get(
            "/api/v1/workshop/orders",
            headers=_auth(owner_access),
            params={"branch_id": str(branch_id), "contact_phone": phone},
        )
        assert response.status_code == 200, response.text
        return [row["id"] for row in response.json()]

    # Partial digits (the tail the operator remembers) and formatted input both hit.
    assert await rows("1555222") == [order["id"]]
    assert await rows("+998 90 155 52 22") == [order["id"]]
    # A non-matching number filters everything out.
    assert await rows("998977777777") == []
    # An input with no digits is formatting-only — it must not filter at all.
    assert await rows("++--") == [order["id"]]


async def _client_order_notifications(db: AsyncSession, order_id: str) -> list[Notification]:
    rows = await db.scalars(
        select(Notification)
        .where(
            Notification.recipient_type == AuthenticatedPrincipalType.CLIENT,
            Notification.entity_type == "order",
            Notification.entity_id == uuid.UUID(order_id),
        )
        .order_by(Notification.created_at)
    )
    return list(rows.all())


async def test_workshop_status_changes_notify_the_client(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """CB-02: workshop-driven status changes fan inbox rows to the order's client,
    carrying the status + denormalized order number. Placing the order (client's
    own action) emits nothing, and the two cutting-floor stages emit nothing
    either — they are one client phase, so the client hears about the order being
    confirmed and about it being ready, not about which machine it is at."""
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]

    # The client placing their own order is not a notifiable change.
    assert await _client_order_notifications(db_session, order_id) == []

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assert approved.status_code == 200

    after_approve = await _client_order_notifications(db_session, order_id)
    assert [n.event_code for n in after_approve] == ["order.confirmed"]
    assert after_approve[0].payload["order_number"] == order["order_number"]
    assert after_approve[0].payload["to_status"] == "confirmed"

    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )
    # Assignment is metadata — it emits no status change and no client notification.
    after_assign = await _client_order_notifications(db_session, order_id)
    assert [n.event_code for n in after_assign] == ["order.confirmed"]
    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    band_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/banding-done",
        headers=_auth(owner_access),
        json={"version": cut_done.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    assert band_done.json()["status"] == "ready"

    codes = [n.event_code for n in await _client_order_notifications(db_session, order_id)]
    assert codes == [
        "order.confirmed",  # approve
        # start-cutting → cutting and cutting-done → edge_banding are silent:
        # the client track has no intermediate phase to move to.
        "order.ready",  # banding-done → ready
    ]


async def test_client_self_cancel_does_not_notify_self_but_workshop_cancel_does(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """CB-02: a client cancelling their own order is their own action — no inbox row
    for them. A workshop cancelling the client's order does notify the client."""
    self_cancel, self_client_access, _, _, _, _ = await _placed_order(client, db_session)
    self_id = self_cancel["id"]
    cancelled = await client.post(
        f"/api/v1/client/orders/{self_id}/cancel",
        headers=_auth(self_client_access),
        json={"version": self_cancel["version"], "reason": "Changed plans"},
    )
    assert cancelled.status_code == 200
    assert await _client_order_notifications(db_session, self_id) == []

    shop_cancel, _, owner_access, _, _, _ = await _placed_order(
        client,
        db_session,
        login="owner_b",
    )
    shop_id = shop_cancel["id"]
    shop_cancelled = await client.post(
        f"/api/v1/workshop/orders/{shop_id}/cancel",
        headers=_auth(owner_access),
        json={"version": shop_cancel["version"], "reason": "Out of stock"},
    )
    assert shop_cancelled.status_code == 200
    notifications = await _client_order_notifications(db_session, shop_id)
    assert [n.event_code for n in notifications] == ["order.cancelled"]
    assert notifications[0].payload["to_status"] == "cancelled"


async def test_client_order_with_indivisible_panel_price_and_quantity(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Regression: a part quantity that doesn't evenly divide its per-part panel price
    # used to violate ck_order_items_line_total_formula (line_total kept the raw
    # panel_price while unit_material was floored), 500ing order placement. A panel
    # price of 250_000 tiyin with quantity 3 leaves a remainder — a failing case the
    # existing tests (quantity 2, even price) never reach.
    _, _, branch_id, _ = await _workshop_setup(db_session)
    panel, _ = await _materials(db_session, branch_id=branch_id)
    client_access, _ = await _client_access(
        db_session, phone=f"+99890{uuid.uuid4().int % 10**7:07d}"
    )
    created = await client.post("/api/v1/client/cutting-drafts", headers=_auth(client_access))
    assert created.status_code == 201
    draft_id = created.json()["id"]
    patched = await client.patch(
        f"/api/v1/client/cutting-drafts/{draft_id}",
        headers=_auth(client_access),
        json={
            "preferred_branch_id": str(branch_id),
            "parts_snapshot": [
                {
                    "part_ref": "indivisible",
                    "material_id": str(panel.id),
                    "material_source": "shop",
                    "length_mm": 260,
                    "width_mm": 180,
                    "quantity": 3,
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
        f"/api/v1/client/cutting-drafts/{draft_id}/optimize",
        headers=_auth(client_access),
    )
    assert optimized.status_code == 200

    placed = await client.post(
        "/api/v1/client/orders",
        headers=_auth(client_access),
        json={
            "draft_id": optimized.json()["id"],
            "branch_id": str(branch_id),
            "contact_name": "Rounding Check",
            "contact_phone": "+998901555333",
        },
    )
    assert placed.status_code == 201, placed.text

    order_id = uuid.UUID(str(placed.json()["id"]))
    item = (
        await db_session.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    ).scalar_one()
    assert item.quantity == 3
    # The stored row must satisfy the DB check-constraint identity exactly.
    assert (
        item.line_total_tiyin
        == (item.unit_cutting_price_tiyin + item.unit_material_price_tiyin) * item.quantity
        + item.edge_cost_tiyin
    )
    order = await db_session.get(Order, order_id)
    assert order is not None
    # The regression scenario is genuinely exercised (price not divisible by quantity),
    # and the order's authoritative material subtotal stays the exact, un-floored cost.
    assert order.subtotal_materials_tiyin % 3 != 0
    assert item.unit_material_price_tiyin == order.subtotal_materials_tiyin // 3


async def test_workshop_new_order_count_is_branch_scoped_and_tenant_isolated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The sidebar badge (QAD-156) counts only NEW orders the caller may manage,
    in the branch they are looking at — and never another workshop's orders."""
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)

    async def count(access: str, **params: str) -> int:
        response = await client.get(
            "/api/v1/workshop/orders/new-count",
            headers=_auth(access),
            params=params,
        )
        assert response.status_code == 200, response.text
        return int(response.json()["count"])

    # The fresh order is NEW, so the owner sees it workshop-wide and in its branch.
    assert await count(owner_access) == 1
    assert await count(owner_access, branch_id=str(branch_id)) == 1
    # A branch with no orders of its own reports zero, not the workshop total.
    other_branch = Branch(
        workshop_id=workshop_id,
        branch_no=await next_branch_no(db_session),
        name="Chilonzor",
        address="Tashkent, Chilonzor",
        phone="+998902222333",
        latitude=Decimal("41.28"),
        longitude=Decimal("69.20"),
    )
    db_session.add(other_branch)
    await db_session.flush()
    assert await count(owner_access, branch_id=str(other_branch.id)) == 0

    # Production-only staff can't manage orders, so they get no badge at all.
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    worker_tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=worker.id,
    )
    assert await count(worker_tokens.access_token) == 0

    # A different workshop never sees these orders in its own count.
    outsider_access, _, _, _ = await _workshop_setup(db_session, login="outsider-owner")
    assert await count(outsider_access) == 0

    # Confirming the order takes it out of NEW, and the count falls on its own.
    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assert approved.status_code == 200, approved.text
    assert await count(owner_access, branch_id=str(branch_id)) == 0


async def test_cutting_done_is_not_blocked_by_missing_or_unrecorded_stock(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """QAD-150: the panels are cut; a bookkeeping gap must not refuse to record it."""

    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]

    # The two blocking states at once: nothing on the shelf, and the material was
    # dropped from the branch catalog after the order was placed. Post-reshape
    # "dropped" means DEACTIVATED — the order item FKs the branch material, so
    # the row cannot be deleted out from under a live order any more.
    panel_item = await db_session.scalar(
        select(StockItem)
        .join(BranchMaterial, BranchMaterial.id == StockItem.branch_material_id)
        # The substrate lives on the format now, one join further out.
        .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
        .where(StockItem.branch_id == branch_id, DecorFormat.type != DecorType.KROMKA)
    )
    assert panel_item is not None
    panel_item.on_hand = 0
    panel_branch_material = await db_session.get(BranchMaterial, panel_item.branch_material_id)
    assert panel_branch_material is not None
    panel_branch_material.status = MaterialStatus.INACTIVE
    await db_session.flush()

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )
    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "completed_by_user_id": str(worker.id)},
    )

    assert cut_done.status_code == 200
    assert cut_done.json()["status"] == "edge_banding"
    # Informational, not a failure — the worker gets a warning toast, not an error.
    assert cut_done.json()["stock_shortfall"] is True
    await db_session.refresh(panel_item)
    assert panel_item.on_hand == -1
    # The material is NOT silently re-listed for clients: what physically moved
    # and what is offerable are different questions.
    await db_session.refresh(panel_branch_material)
    assert panel_branch_material.status is MaterialStatus.INACTIVE

    # Recording the arrival afterwards lands the balance on the right number with
    # no manual adjustment: 1 was consumed, 4 arrive, 3 remain.
    supplier = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Late Arrival Supplier"},
    )
    assert supplier.status_code == 201
    # Re-list it the way a human would — deliberately, through the catalog.
    panel_branch_material.status = MaterialStatus.ACTIVE
    await db_session.flush()
    stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "branch_material_id": str(panel_item.branch_material_id),
            "quantity": 4,
            "unit_price_tiyin": 100_000,
            "supplier_id": supplier.json()["id"],
        },
    )
    assert stock_in.status_code == 201
    assert stock_in.json()["balance_after"] == 3


async def test_order_cutting_pdf_carries_the_receipt_the_client_saw(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The document's first page states the money, itemized the way the client
    already read it under «Buyurtmangiz» — from the order's own frozen prices,
    so what is printed reconciles with the total the order was placed at."""
    order, client_access, owner_access, _, _, _ = await _placed_order(client, db_session)
    detail = await client.get(
        f"/api/v1/client/orders/{order['id']}",
        headers=_auth(client_access),
    )
    pricing = order_pdf_pricing(OrderDetailResponse.model_validate(detail.json()))
    client_pdf = await client.get(
        f"/api/v1/client/orders/{order['id']}/cutting/pdf",
        headers=_auth(client_access),
    )
    workshop_pdf = await client.get(
        f"/api/v1/workshop/orders/{order['id']}/cutting/pdf",
        headers=_auth(owner_access),
    )

    assert [
        (row.group, row.label, row.quantity, row.unit, row.unit_price_tiyin, row.amount_tiyin)
        for row in pricing.rows
    ] == [
        ("List", pricing.rows[0].label, "1", "list", 250_000, 250_000),
        ("Kromka", pricing.rows[1].label, "1.00", "m", 10_000, 10_000),
        ("Xizmat", "Kesish xizmati", "1", "list", 50_000, 50_000),
        # Banding labour is what the banding subtotal has left once the tape
        # material line is taken out of it.
        ("Xizmat", "Kromka yopishtirish", "1.00", "m", 20_000, 20_000),
    ]
    assert pricing.total_tiyin == 330_000
    assert sum(row.amount_tiyin or 0 for row in pricing.rows) == pricing.total_tiyin
    assert client_pdf.status_code == 200
    assert client_pdf.headers["content-type"] == "application/pdf"
    assert client_pdf.content.startswith(b"%PDF")
    assert workshop_pdf.status_code == 200
    assert workshop_pdf.content.startswith(b"%PDF")
