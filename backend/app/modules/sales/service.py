"""Order pricing, placement, and production workflow use cases."""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast

from fastapi import status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    ActorType,
    AuthenticatedPrincipalType,
    BranchStatus,
    Currency,
    CuttingResultStatus,
    LedgerStatus,
    MaterialSource,
    MaterialStatus,
    OrderStatus,
    Permission,
    UserStatus,
    WorkshopStatus,
)
from app.modules.access.api import can_access_branch
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, BranchPricing, Material
from app.modules.cutting.api import cutting_result_response
from app.modules.cutting.contracts import (
    CuttingDraft,
    CuttingPanel,
    CuttingPlacement,
    CuttingResult,
)
from app.modules.finance.contracts import Income
from app.modules.inventory.api import consume_order_stock, restore_order_stock
from app.modules.inventory.contracts import StockItem
from app.modules.sales.contracts import Order, OrderCancellation, OrderItem, OrderStatusEvent
from app.modules.sales.schemas import (
    BatchOrderQuoteResponse,
    ClientOrderCreateRequest,
    EdgePriceLine,
    MaterialPriceLine,
    OrderDetailResponse,
    OrderItemResponse,
    OrderQuoteResponse,
    OrderSettlementResponse,
    OrderStatusEventResponse,
    OrderStockWarning,
    OrderSummaryResponse,
    ReasonedVersionedRequest,
    VersionedRequest,
    WorkshopOrderAssignRequest,
    WorkshopOrderCompleteRequest,
    WorkshopOrderDiscountRequest,
    WorkshopOrderNoteRequest,
    WorkshopWorkerOption,
)
from app.modules.support.api import record_action, record_status_change
from app.modules.support.contracts import Notification
from app.modules.workshop.contracts import Branch, Workshop

PHONE_RE = re.compile(r"^\+998\d{9}$")
WORKSHOP_ORDER_VIEW_PERMISSIONS = frozenset(
    {
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_ORDERS,
        Permission.PROCESS_PRODUCTION,
    }
)

# Client inbox event per destination status (notifications.md: "for the client, an
# order status change"). The client SPA renders these codes into localized titles
# (web clientUi NOTIFICATION_TITLES); the payload carries denormalized order data.
# NEW is absent — that is the client placing their own order, not a notifiable change.
_CLIENT_ORDER_EVENT_CODE: dict[OrderStatus, str] = {
    OrderStatus.CONFIRMED: "order.confirmed",
    OrderStatus.CUTTING: "order.status_changed",
    OrderStatus.EDGE_BANDING: "order.status_changed",
    OrderStatus.READY: "order.ready",
    OrderStatus.COMPLETED: "order.completed",
    OrderStatus.CANCELLED: "order.cancelled",
}


@dataclass(frozen=True)
class PricedPart:
    part: dict[str, Any]
    panel_price_tiyin: int
    edge_cost_tiyin: int
    material_snapshot: dict[str, Any]
    edge_snapshots: dict[str, dict[str, Any] | None]


@dataclass(frozen=True)
class PricingSnapshot:
    subtotal_cutting_tiyin: int
    subtotal_materials_tiyin: int
    subtotal_edge_banding_tiyin: int
    total_tiyin: int
    priced_parts: list[PricedPart]
    # Itemized quote breakdown (CB-117) — only consumed by the quote response.
    panels_used: int
    cutting_rate_tiyin: int
    material_lines: list[MaterialPriceLine]
    edge_lines: list[EdgePriceLine]


@dataclass(frozen=True)
class FinanceOrderTarget:
    order_id: uuid.UUID
    workshop_id: uuid.UUID
    branch_id: uuid.UUID
    total_tiyin: int


@dataclass(frozen=True)
class WorkerProductionRecord:
    user_id: uuid.UUID
    full_name: str
    panels_cut: int
    cut_count: int
    orders_banded: int
    edge_length_by_material: dict[str, int]


async def place_client_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: ClientOrderCreateRequest,
) -> OrderDetailResponse:
    client = await _client(db, principal)
    branch, workshop = await _active_branch_for_order(db, payload.branch_id)
    draft, result = await _client_orderable_draft_result(
        db,
        client_id=client.id,
        draft_id=payload.draft_id,
    )
    pricing = await _price_result(db, branch_id=branch.id, result=result)
    now = datetime.now(UTC)
    order = Order(
        order_number=await _next_order_number(db, now),
        client_id=client.id,
        workshop_id=workshop.id,
        branch_id=branch.id,
        cutting_result_id=result.id,
        status=OrderStatus.NEW,
        version=1,
        contact_name=_contact_name(payload.contact_name),
        contact_phone=_contact_phone(payload.contact_phone),
        note_client=_optional_text(payload.note_client),
        subtotal_cutting_tiyin=pricing.subtotal_cutting_tiyin,
        subtotal_materials_tiyin=pricing.subtotal_materials_tiyin,
        subtotal_edge_banding_tiyin=pricing.subtotal_edge_banding_tiyin,
        discount_tiyin=0,
        total_tiyin=pricing.total_tiyin,
        currency=Currency.UZS,
    )
    db.add(order)
    await db.flush()

    for priced in pricing.priced_parts:
        db.add(
            OrderItem(
                order_id=order.id,
                material_id=uuid.UUID(str(priced.part["material_id"])),
                material_source=MaterialSource(str(priced.part["material_source"])),
                material_snapshot=priced.material_snapshot,
                part_ref=str(priced.part["part_ref"]),
                length_mm=int(priced.part["length_mm"]),
                width_mm=int(priced.part["width_mm"]),
                quantity=int(priced.part["quantity"]),
                edge_top=priced.edge_snapshots["edge_top"],
                edge_bottom=priced.edge_snapshots["edge_bottom"],
                edge_left=priced.edge_snapshots["edge_left"],
                edge_right=priced.edge_snapshots["edge_right"],
                unit_cutting_price_tiyin=0,
                unit_material_price_tiyin=priced.panel_price_tiyin // int(priced.part["quantity"]),
                edge_cost_tiyin=priced.edge_cost_tiyin,
                line_total_tiyin=priced.panel_price_tiyin + priced.edge_cost_tiyin,
            )
        )

    result.status = CuttingResultStatus.CONFIRMED
    result.order_id = order.id
    result.draft_id = None
    result.confirmed_at = now
    draft.chosen_result_id = None
    await db.flush()
    await _delete_other_candidate_results(db, draft_id=draft.id, keep_result_id=result.id)
    await db.delete(draft)
    await _append_order_event(
        db,
        order=order,
        from_status=None,
        to_status=OrderStatus.NEW,
        actor_type=ActorType.CLIENT,
        actor_client_id=client.id,
        reason=None,
        metadata={"cutting_result_id": str(result.id)},
    )
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="orders.create",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=f"Created order {order.order_number}",
        details={"cutting_result_id": str(result.id)},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="order",
        entity_id=order.id,
        to_status=OrderStatus.NEW.value,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        action_log_id=action.id,
    )
    await db.flush()
    return cast(
        OrderDetailResponse,
        await _order_response(db, order, include_detail=True, settlement_visible=False),
    )


async def quote_client_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> OrderQuoteResponse:
    client = await _client(db, principal)
    branch, _ = await _active_branch_for_order(db, branch_id)
    _, result = await _client_orderable_draft_result(
        db,
        client_id=client.id,
        draft_id=draft_id,
    )
    pricing = await _price_result(db, branch_id=branch.id, result=result)
    return _build_quote_response(draft_id, branch, pricing)


def _build_quote_response(
    draft_id: uuid.UUID,
    branch: Branch,
    pricing: PricingSnapshot,
) -> OrderQuoteResponse:
    return OrderQuoteResponse(
        draft_id=draft_id,
        branch_id=branch.id,
        branch_name=branch.name,
        branch_address=branch.address,
        branch_phone=branch.phone,
        today_hours=branch.today_hours(),
        subtotal_cutting_tiyin=pricing.subtotal_cutting_tiyin,
        subtotal_materials_tiyin=pricing.subtotal_materials_tiyin,
        subtotal_edge_banding_tiyin=pricing.subtotal_edge_banding_tiyin,
        total_tiyin=pricing.total_tiyin,
        panels_used=pricing.panels_used,
        cutting_rate_tiyin=pricing.cutting_rate_tiyin,
        material_lines=pricing.material_lines,
        edge_lines=pricing.edge_lines,
    )


async def quote_client_order_batch(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
    branch_ids: list[uuid.UUID],
) -> BatchOrderQuoteResponse:
    """Quote one draft against many branches in a single request (CB-12), pricing
    the validated result once and capturing each branch's own error code so the
    client no longer fans out N requests."""
    client = await _client(db, principal)
    _, result = await _client_orderable_draft_result(
        db,
        client_id=client.id,
        draft_id=draft_id,
    )
    quotes: dict[str, OrderQuoteResponse] = {}
    errors: dict[str, str | None] = {}
    for branch_id in branch_ids:
        key = str(branch_id)
        try:
            branch, _ = await _active_branch_for_order(db, branch_id)
            pricing = await _price_result(db, branch_id=branch.id, result=result)
            quotes[key] = _build_quote_response(draft_id, branch, pricing)
        except APIError as exc:
            errors[key] = exc.code
    return BatchOrderQuoteResponse(quotes=quotes, errors=errors)


async def list_client_orders(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    status_filter: str | None = None,
    search: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> list[OrderSummaryResponse]:
    client = await _client(db, principal)
    query = (
        select(Order)
        .where(Order.client_id == client.id)
        .order_by(Order.created_at.desc(), Order.order_number.desc())
    )
    query = _apply_order_filters(query, status_filter=status_filter, search=search)
    # Paginate so a long history isn't re-downloaded whole (CB-38). Clamp to a sane
    # window; the client appends pages via offset.
    query = query.limit(max(1, min(limit, 100))).offset(max(0, offset))
    rows = (await db.scalars(query)).all()
    return [await _order_response(db, order, include_detail=False) for order in rows]


async def get_client_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> OrderDetailResponse:
    client = await _client(db, principal)
    order = await db.get(Order, order_id)
    if order is None or order.client_id != client.id:
        raise APIError("order_not_found", "Order not found", status_code=404)
    return cast(
        OrderDetailResponse,
        await _order_response(
            db,
            order,
            include_detail=True,
            settlement_visible=_client_settlement_visible(order.status),
        ),
    )


async def cancel_client_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: ReasonedVersionedRequest,
) -> OrderDetailResponse:
    client = await _client(db, principal)
    order = await _locked_order(db, order_id)
    if order.client_id != client.id:
        raise APIError("order_not_found", "Order not found", status_code=404)
    if order.status is not OrderStatus.NEW:
        raise APIError("order_cancel_not_allowed", "Client can cancel only new orders")
    await _cancel_order(
        db,
        principal=principal,
        order=order,
        version=payload.version,
        reason=payload.reason,
        cancelled_by_type=ActorType.CLIENT,
        cancelled_by_client_id=client.id,
        cancelled_by_user_id=None,
    )
    return cast(
        OrderDetailResponse,
        await _order_response(db, order, include_detail=True, settlement_visible=False),
    )


async def get_client_order_cutting_result(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> CuttingResult:
    client = await _client(db, principal)
    order = await db.get(Order, order_id)
    if order is None or order.client_id != client.id:
        raise APIError("order_not_found", "Order not found", status_code=404)
    result = await db.get(CuttingResult, order.cutting_result_id)
    if result is None:
        raise APIError("cutting_result_not_found", "Cutting result not found", status_code=404)
    return result


async def list_workshop_orders(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    search: str | None = None,
) -> list[OrderSummaryResponse]:
    _require_workshop(principal)
    query = select(Order).order_by(Order.created_at.desc(), Order.order_number.desc())
    query = _apply_workshop_order_scope(query, principal, branch_id=branch_id)
    query = _apply_order_filters(query, status_filter=status_filter, search=search)
    rows = (await db.scalars(query)).all()
    return [await _order_response(db, order, include_detail=False) for order in rows]


async def get_order_finance_target(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    permission: Permission,
) -> FinanceOrderTarget:
    order = await db.get(Order, order_id)
    if order is None:
        raise APIError("order_not_found", "Order not found", status_code=status.HTTP_404_NOT_FOUND)
    if not can_access_branch(
        principal,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        permission=permission,
    ):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return FinanceOrderTarget(
        order_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        total_tiyin=order.total_tiyin,
    )


async def list_worker_production_records(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_ids: frozenset[uuid.UUID] | None,
    date_from: date,
    date_to: date,
) -> list[WorkerProductionRecord]:
    query = select(Order).where(Order.workshop_id == workshop_id)
    if branch_ids is not None:
        if not branch_ids:
            return []
        query = query.where(Order.branch_id.in_(branch_ids))
    orders = (await db.scalars(query)).all()
    rows: dict[uuid.UUID, WorkerProductionRecord] = {}

    def current(user_id: uuid.UUID) -> WorkerProductionRecord:
        row = rows.get(user_id)
        if row is None:
            row = WorkerProductionRecord(
                user_id=user_id,
                full_name="Worker",
                panels_cut=0,
                cut_count=0,
                orders_banded=0,
                edge_length_by_material={},
            )
            rows[user_id] = row
        return row

    def replace(row: WorkerProductionRecord) -> None:
        rows[row.user_id] = row

    for order in orders:
        if (
            order.cutter_user_id is not None
            and order.cut_completed_at is not None
            and date_from <= order.cut_completed_at.date() <= date_to
        ):
            row = current(order.cutter_user_id)
            replace(
                WorkerProductionRecord(
                    user_id=row.user_id,
                    full_name=row.full_name,
                    panels_cut=row.panels_cut + (order.panels_used_snapshot or 0),
                    cut_count=row.cut_count + (order.cut_count_snapshot or 0),
                    orders_banded=row.orders_banded,
                    edge_length_by_material=dict(row.edge_length_by_material),
                )
            )
        if (
            order.edger_user_id is not None
            and order.edge_completed_at is not None
            and date_from <= order.edge_completed_at.date() <= date_to
        ):
            row = current(order.edger_user_id)
            edge_lengths = dict(row.edge_length_by_material)
            for material_id, length in (order.edge_length_snapshot or {}).items():
                edge_lengths[material_id] = edge_lengths.get(material_id, 0) + int(length)
            replace(
                WorkerProductionRecord(
                    user_id=row.user_id,
                    full_name=row.full_name,
                    panels_cut=row.panels_cut,
                    cut_count=row.cut_count,
                    orders_banded=row.orders_banded + 1,
                    edge_length_by_material=edge_lengths,
                )
            )

    if not rows:
        return []
    users = (await db.scalars(select(WorkshopUser).where(WorkshopUser.id.in_(rows.keys())))).all()
    for user in users:
        row = rows[user.id]
        replace(
            WorkerProductionRecord(
                user_id=row.user_id,
                full_name=user.full_name,
                panels_cut=row.panels_cut,
                cut_count=row.cut_count,
                orders_banded=row.orders_banded,
                edge_length_by_material=dict(row.edge_length_by_material),
            )
        )
    return sorted(rows.values(), key=lambda row: row.full_name)


async def get_workshop_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> OrderDetailResponse:
    order = await _workshop_order_in_scope(db, principal=principal, order_id=order_id)
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def get_workshop_order_cutting_result(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> CuttingResult:
    order = await _workshop_order_in_scope(db, principal=principal, order_id=order_id)
    result = await db.get(CuttingResult, order.cutting_result_id)
    if result is None:
        raise APIError("cutting_result_not_found", "Cutting result not found", status_code=404)
    return result


async def list_worker_options(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> list[WorkshopWorkerOption]:
    _require_workshop(principal)
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.workshop_id != principal.workshop_id:
        raise APIError("branch_not_found", "Branch not found", status_code=404)
    if not can_access_branch(
        principal,
        workshop_id=branch.workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_ORDERS,
    ):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    rows = await _eligible_workers(db, workshop_id=principal.workshop_id, branch_id=branch_id)
    return [
        WorkshopWorkerOption(
            id=row.id,
            full_name=row.full_name,
            is_owner=row.is_owner,
            home_branch_id=row.home_branch_id,
        )
        for row in rows
    ]


async def approve_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: VersionedRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_for_action(
        db,
        principal=principal,
        order_id=order_id,
        permission=Permission.MANAGE_ORDERS,
    )
    _expect_version(order, payload.version)
    _expect_status(order, {OrderStatus.NEW})
    order.confirmed_at = datetime.now(UTC)
    await _transition(
        db,
        principal=principal,
        order=order,
        to_status=OrderStatus.CONFIRMED,
        reason=None,
        metadata={},
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def assign_order_workers(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: WorkshopOrderAssignRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_for_action(
        db,
        principal=principal,
        order_id=order_id,
        permission=Permission.MANAGE_ORDERS,
    )
    _expect_version(order, payload.version)
    if order.status not in {OrderStatus.CONFIRMED, OrderStatus.CUTTING, OrderStatus.EDGE_BANDING}:
        raise APIError("order_assignment_not_allowed", "Assignment is not allowed")
    if payload.cutter_user_id is None and payload.edger_user_id is None:
        raise APIError("worker_required", "Choose a worker")

    if payload.cutter_user_id is not None:
        if order.cut_completed_at is not None:
            raise APIError("cutting_already_done", "Cutting is already complete")
        await _validate_production_worker(
            db,
            workshop_id=order.workshop_id,
            branch_id=order.branch_id,
            user_id=payload.cutter_user_id,
        )
        order.assigned_cutter_user_id = payload.cutter_user_id
    if payload.edger_user_id is not None:
        if not await _order_has_banding(db, order.id):
            raise APIError("edger_not_required", "This order has no edge banding")
        if order.edge_completed_at is not None:
            raise APIError("banding_already_done", "Banding is already complete")
        await _validate_production_worker(
            db,
            workshop_id=order.workshop_id,
            branch_id=order.branch_id,
            user_id=payload.edger_user_id,
        )
        order.assigned_edger_user_id = payload.edger_user_id

    if order.status is OrderStatus.CONFIRMED and payload.cutter_user_id is not None:
        if await _order_has_banding(db, order.id) and order.assigned_edger_user_id is None:
            raise APIError("edger_required", "Choose an edge bander for this order")
        await _transition(
            db,
            principal=principal,
            order=order,
            to_status=OrderStatus.CUTTING,
            reason=None,
            metadata={
                "assigned_cutter_user_id": str(order.assigned_cutter_user_id),
                "assigned_edger_user_id": str(order.assigned_edger_user_id)
                if order.assigned_edger_user_id
                else None,
            },
        )
    else:
        _bump_order(order)
        await record_action(
            db,
            actor=actor_from_principal(principal),
            action="orders.assign",
            entity_type="order",
            entity_id=order.id,
            workshop_id=order.workshop_id,
            branch_id=order.branch_id,
            summary=f"Assigned workers for {order.order_number}",
            details={
                "assigned_cutter_user_id": str(order.assigned_cutter_user_id)
                if order.assigned_cutter_user_id
                else None,
                "assigned_edger_user_id": str(order.assigned_edger_user_id)
                if order.assigned_edger_user_id
                else None,
            },
        )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def complete_cutting(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: WorkshopOrderCompleteRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_visible(db, principal=principal, order_id=order_id)
    _expect_version(order, payload.version)
    _expect_status(order, {OrderStatus.CUTTING})
    worker_id = await _credited_worker(
        db,
        principal=principal,
        order=order,
        requested_user_id=payload.completed_by_user_id,
        assigned_user_id=order.assigned_cutter_user_id,
        job="cutting",
    )
    result = await _order_result(db, order)
    panel_demands = _panel_stock_demands(result)
    for material_id, quantity in panel_demands.items():
        await consume_order_stock(
            db,
            branch_id=order.branch_id,
            material_id=material_id,
            order_id=order.id,
            quantity=quantity,
        )
    order.cutter_user_id = worker_id
    order.cut_completed_at = datetime.now(UTC)
    order.panels_used_snapshot = sum(
        int(value) for value in result.panels_used_by_material.values()
    )
    order.cut_count_snapshot = sum(int(part.get("quantity", 0)) for part in result.parts_snapshot)
    to_status = (
        OrderStatus.EDGE_BANDING if await _order_has_banding(db, order.id) else OrderStatus.READY
    )
    await _transition(
        db,
        principal=principal,
        order=order,
        to_status=to_status,
        reason=None,
        metadata={
            "credited_user_id": str(worker_id),
            "panel_demands": {str(key): value for key, value in panel_demands.items()},
        },
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def complete_banding(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: WorkshopOrderCompleteRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_visible(db, principal=principal, order_id=order_id)
    _expect_version(order, payload.version)
    _expect_status(order, {OrderStatus.EDGE_BANDING})
    worker_id = await _credited_worker(
        db,
        principal=principal,
        order=order,
        requested_user_id=payload.completed_by_user_id,
        assigned_user_id=order.assigned_edger_user_id,
        job="banding",
    )
    result = await _order_result(db, order)
    edge_demands = _edge_stock_demands(result)
    for material_id, quantity in edge_demands.items():
        await consume_order_stock(
            db,
            branch_id=order.branch_id,
            material_id=material_id,
            order_id=order.id,
            quantity=quantity,
        )
    order.edger_user_id = worker_id
    order.edge_completed_at = datetime.now(UTC)
    order.edge_length_snapshot = {str(key): value for key, value in edge_demands.items()}
    await _transition(
        db,
        principal=principal,
        order=order,
        to_status=OrderStatus.READY,
        reason=None,
        metadata={
            "credited_user_id": str(worker_id),
            "edge_demands": {str(key): value for key, value in edge_demands.items()},
        },
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def mark_collected(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: VersionedRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_for_action(
        db,
        principal=principal,
        order_id=order_id,
        permission=Permission.MANAGE_ORDERS,
    )
    _expect_version(order, payload.version)
    _expect_status(order, {OrderStatus.READY})
    now = datetime.now(UTC)
    order.picked_up_at = now
    order.completed_at = now
    await _transition(
        db,
        principal=principal,
        order=order,
        to_status=OrderStatus.COMPLETED,
        reason=None,
        metadata={},
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def revert_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: ReasonedVersionedRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_for_action(
        db,
        principal=principal,
        order_id=order_id,
        permission=Permission.MANAGE_ORDERS,
    )
    _expect_version(order, payload.version)
    reason = _required_reason(payload.reason)
    metadata: dict[str, Any] = {}
    if order.status is OrderStatus.CUTTING:
        order.assigned_cutter_user_id = None
        to_status = OrderStatus.CONFIRMED
    elif order.status is OrderStatus.EDGE_BANDING:
        restored = await _restore_cutting_step(db, order)
        metadata["restored_panels"] = {str(key): value for key, value in restored.items()}
        to_status = OrderStatus.CUTTING
    elif order.status is OrderStatus.READY:
        if await _order_has_banding(db, order.id):
            restored_edges = await _restore_banding_step(db, order)
            metadata["restored_edges"] = {str(key): value for key, value in restored_edges.items()}
            to_status = OrderStatus.EDGE_BANDING
        else:
            restored_panels = await _restore_cutting_step(db, order)
            metadata["restored_panels"] = {
                str(key): value for key, value in restored_panels.items()
            }
            to_status = OrderStatus.CUTTING
    else:
        raise APIError("order_revert_not_allowed", "Revert is not allowed")
    await _transition(
        db,
        principal=principal,
        order=order,
        to_status=to_status,
        reason=reason,
        metadata=metadata,
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def cancel_workshop_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: ReasonedVersionedRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_for_action(
        db,
        principal=principal,
        order_id=order_id,
        permission=Permission.MANAGE_ORDERS,
    )
    await _cancel_order(
        db,
        principal=principal,
        order=order,
        version=payload.version,
        reason=payload.reason,
        cancelled_by_type=ActorType.WORKSHOP_USER,
        cancelled_by_user_id=principal.principal_id,
        cancelled_by_client_id=None,
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def apply_discount(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: WorkshopOrderDiscountRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_for_action(
        db,
        principal=principal,
        order_id=order_id,
        permission=Permission.MANAGE_ORDERS,
    )
    _expect_version(order, payload.version)
    if order.status not in {OrderStatus.NEW, OrderStatus.CONFIRMED}:
        raise APIError("discount_not_allowed", "Discount is not allowed at this status")
    reason = _required_reason(payload.reason)
    subtotal = _pre_discount_total(order)
    if payload.value < 0:
        raise APIError("invalid_discount", "Discount must be non-negative")
    discount = payload.value if payload.kind == "fixed" else subtotal * payload.value // 100
    if discount > subtotal:
        raise APIError("invalid_discount", "Discount cannot exceed subtotal")
    order.discount_tiyin = discount
    order.discount_reason = reason
    order.discount_applied_by_user_id = principal.principal_id
    order.total_tiyin = subtotal - discount
    _bump_order(order)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="orders.discount",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=f"Applied discount to {order.order_number}",
        details={"discount_tiyin": discount, "reason": reason},
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def update_workshop_note(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: WorkshopOrderNoteRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_for_action(
        db,
        principal=principal,
        order_id=order_id,
        permission=Permission.MANAGE_ORDERS,
    )
    order.note_workshop = _optional_text(payload.note_workshop)
    _bump_order(order)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="orders.note.update",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=f"Updated note for {order.order_number}",
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def _cancel_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order: Order,
    version: int,
    reason: str,
    cancelled_by_type: ActorType,
    cancelled_by_user_id: uuid.UUID | None,
    cancelled_by_client_id: uuid.UUID | None,
) -> None:
    _expect_version(order, version)
    if order.status in {OrderStatus.COMPLETED, OrderStatus.CANCELLED}:
        raise APIError("order_cancel_not_allowed", "Order cannot be cancelled")
    normalized_reason = _required_reason(reason)
    now = datetime.now(UTC)
    order.cancelled_at = now
    db.add(
        OrderCancellation(
            order_id=order.id,
            cancelled_by_type=cancelled_by_type,
            cancelled_by_user_id=cancelled_by_user_id,
            cancelled_by_client_id=cancelled_by_client_id,
            reason=normalized_reason,
            cancelled_at=now,
        )
    )
    await _transition(
        db,
        principal=principal,
        order=order,
        to_status=OrderStatus.CANCELLED,
        reason=normalized_reason,
        metadata={"cancelled_by_type": cancelled_by_type.value},
    )


async def _restore_cutting_step(db: AsyncSession, order: Order) -> dict[uuid.UUID, int]:
    result = await _order_result(db, order)
    demands = _panel_stock_demands(result)
    for material_id, quantity in demands.items():
        await restore_order_stock(
            db,
            branch_id=order.branch_id,
            material_id=material_id,
            order_id=order.id,
            quantity=quantity,
        )
    order.cutter_user_id = None
    order.cut_completed_at = None
    order.panels_used_snapshot = None
    order.cut_count_snapshot = None
    return demands


async def _restore_banding_step(db: AsyncSession, order: Order) -> dict[uuid.UUID, int]:
    result = await _order_result(db, order)
    demands = _edge_stock_demands(result)
    for material_id, quantity in demands.items():
        await restore_order_stock(
            db,
            branch_id=order.branch_id,
            material_id=material_id,
            order_id=order.id,
            quantity=quantity,
        )
    order.edger_user_id = None
    order.edge_completed_at = None
    order.edge_length_snapshot = None
    return demands


async def _transition(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order: Order,
    to_status: OrderStatus,
    reason: str | None,
    metadata: dict[str, Any],
) -> None:
    from_status = order.status
    order.status = to_status
    _bump_order(order)
    await _append_order_event(
        db,
        order=order,
        from_status=from_status,
        to_status=to_status,
        actor_type=ActorType(principal.principal_type.value),
        actor_user_id=principal.principal_id
        if principal.principal_type is AuthenticatedPrincipalType.WORKSHOP_USER
        else None,
        actor_client_id=principal.principal_id
        if principal.principal_type is AuthenticatedPrincipalType.CLIENT
        else None,
        reason=reason,
        metadata=metadata,
    )
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"orders.status.{to_status.value}",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=f"Moved {order.order_number} to {to_status.value}",
        details={"from_status": from_status.value, "to_status": to_status.value, **metadata},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="order",
        entity_id=order.id,
        from_status=from_status.value,
        to_status=to_status.value,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        reason=reason,
        action_log_id=action.id,
    )
    _notify_client_of_status(
        db, principal=principal, order=order, from_status=from_status, to_status=to_status
    )


def _notify_client_of_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order: Order,
    from_status: OrderStatus,
    to_status: OrderStatus,
) -> None:
    """Fan one inbox row to the order's client on a status change (CB-02).

    Skipped when the client themselves drove the change (e.g. a self-cancel) — they
    don't need to be told about their own action — and for transitions with no
    client-facing event code. Recipient/payload follow the generic Notification
    model; the client SPA already maps these event codes to localized titles.
    """
    event_code = _CLIENT_ORDER_EVENT_CODE.get(to_status)
    if event_code is None:
        return
    actor_is_the_client = (
        principal.principal_type is AuthenticatedPrincipalType.CLIENT
        and principal.principal_id == order.client_id
    )
    if actor_is_the_client:
        return
    db.add(
        Notification(
            recipient_type=AuthenticatedPrincipalType.CLIENT,
            recipient_id=order.client_id,
            event_code=event_code,
            entity_type="order",
            entity_id=order.id,
            payload={
                "order_number": order.order_number,
                "from_status": from_status.value,
                "to_status": to_status.value,
            },
            created_at=datetime.now(UTC),
        )
    )


async def _append_order_event(
    db: AsyncSession,
    *,
    order: Order,
    from_status: OrderStatus | None,
    to_status: OrderStatus,
    actor_type: ActorType,
    actor_user_id: uuid.UUID | None = None,
    actor_client_id: uuid.UUID | None = None,
    reason: str | None,
    metadata: dict[str, Any],
) -> None:
    db.add(
        OrderStatusEvent(
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            actor_client_id=actor_client_id,
            reason=reason,
            metadata_json=metadata,
            changed_at=datetime.now(UTC),
        )
    )
    await db.flush()


async def _order_response(
    db: AsyncSession,
    order: Order,
    *,
    include_detail: bool,
    settlement_visible: bool = True,
) -> OrderDetailResponse | OrderSummaryResponse:
    client = await db.get(Client, order.client_id)
    branch = await db.get(Branch, order.branch_id)
    workshop = await db.get(Workshop, order.workshop_id)
    if client is None or branch is None or workshop is None:
        raise APIError("order_scope_missing", "Order scope is incomplete", status_code=500)
    items = (
        await db.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
        )
    ).all()
    warnings = await _stock_warnings(db, order)
    base = {
        "id": order.id,
        "order_number": order.order_number,
        "client_id": order.client_id,
        "client_name": client.name,
        "client_phone": client.phone,
        "contact_name": order.contact_name,
        "contact_phone": order.contact_phone,
        "workshop_id": order.workshop_id,
        "workshop_name": workshop.name,
        "branch_id": order.branch_id,
        "branch_name": branch.name,
        "branch_address": branch.address,
        "branch_phone": branch.phone,
        "today_hours": branch.today_hours(),
        "cutting_result_id": order.cutting_result_id,
        "status": order.status,
        "version": order.version,
        "note_client": order.note_client,
        "note_workshop": order.note_workshop,
        "subtotal_cutting_tiyin": order.subtotal_cutting_tiyin,
        "subtotal_materials_tiyin": order.subtotal_materials_tiyin,
        "subtotal_edge_banding_tiyin": order.subtotal_edge_banding_tiyin,
        "discount_tiyin": order.discount_tiyin,
        "discount_reason": order.discount_reason,
        "discount_applied_by_user_id": order.discount_applied_by_user_id,
        "total_tiyin": order.total_tiyin,
        "currency": order.currency,
        "assigned_cutter_user_id": order.assigned_cutter_user_id,
        "assigned_edger_user_id": order.assigned_edger_user_id,
        "cutter_user_id": order.cutter_user_id,
        "cut_completed_at": order.cut_completed_at,
        "panels_used_snapshot": order.panels_used_snapshot,
        "cut_count_snapshot": order.cut_count_snapshot,
        "edger_user_id": order.edger_user_id,
        "edge_completed_at": order.edge_completed_at,
        "edge_length_snapshot": order.edge_length_snapshot,
        "picked_up_at": order.picked_up_at,
        "confirmed_at": order.confirmed_at,
        "completed_at": order.completed_at,
        "cancelled_at": order.cancelled_at,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "item_count": sum(item.quantity for item in items),
        "has_banding": _items_have_banding(items),
        "stock_warnings": warnings,
    }
    if not include_detail:
        return OrderSummaryResponse(**base)
    events = (
        await db.scalars(
            select(OrderStatusEvent)
            .where(OrderStatusEvent.order_id == order.id)
            .order_by(OrderStatusEvent.changed_at.asc(), OrderStatusEvent.id.asc())
        )
    ).all()
    result = await db.get(CuttingResult, order.cutting_result_id)
    return OrderDetailResponse(
        **base,
        items=[OrderItemResponse.model_validate(item) for item in items],
        events=[
            OrderStatusEventResponse(
                id=event.id,
                from_status=event.from_status,
                to_status=event.to_status,
                actor_type=event.actor_type,
                actor_user_id=event.actor_user_id,
                actor_client_id=event.actor_client_id,
                reason=event.reason,
                metadata=event.metadata_json,
                changed_at=event.changed_at,
            )
            for event in events
        ],
        cutting_result=await cutting_result_response(db, result) if result is not None else None,
        settlement=await _order_settlement(db, order) if settlement_visible else None,
    )


def _client_settlement_visible(status_value: OrderStatus) -> bool:
    return status_value in {OrderStatus.READY, OrderStatus.COMPLETED}


async def _order_settlement(db: AsyncSession, order: Order) -> OrderSettlementResponse:
    recorded = int(
        await db.scalar(
            select(func.coalesce(func.sum(Income.amount_tiyin), 0)).where(
                Income.order_id == order.id,
                Income.status == LedgerStatus.RECORDED,
            )
        )
        or 0
    )
    return OrderSettlementResponse(
        total_tiyin=order.total_tiyin,
        recorded_tiyin=recorded,
        balance_tiyin=max(order.total_tiyin - recorded, 0),
    )


async def _stock_warnings(db: AsyncSession, order: Order) -> list[OrderStockWarning]:
    if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED, OrderStatus.READY}:
        return []
    result = await db.get(CuttingResult, order.cutting_result_id)
    if result is None:
        return []
    demands: dict[uuid.UUID, int] = {}
    if order.cut_completed_at is None:
        demands.update(_panel_stock_demands(result))
    if order.edge_completed_at is None:
        for material_id, quantity in _edge_stock_demands(result).items():
            demands[material_id] = demands.get(material_id, 0) + quantity
    if not demands:
        return []
    rows = (
        await db.execute(
            select(StockItem, Material)
            .join(Material, Material.id == StockItem.material_id)
            .where(
                StockItem.branch_id == order.branch_id,
                StockItem.material_id.in_(demands.keys()),
            )
        )
    ).all()
    by_material = {item.material_id: (item, material) for item, material in rows}
    warnings: list[OrderStockWarning] = []
    for material_id, required in demands.items():
        item, material = by_material.get(material_id, (None, None))
        on_hand = item.on_hand if item is not None else 0
        min_stock = item.min_stock if item is not None else 0
        projected = on_hand - required
        if projected >= 0 and projected > min_stock:
            continue
        warnings.append(
            OrderStockWarning(
                material_id=material_id,
                material_name=material.name if material is not None else str(material_id),
                kind=material.kind.value if material is not None else "unknown",
                on_hand=on_hand,
                required=required,
                projected_after=projected,
            )
        )
    return warnings


async def _price_result(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    result: CuttingResult,
) -> PricingSnapshot:
    pricing = await db.get(BranchPricing, branch_id)
    if pricing is None or pricing.cutting_rate_tiyin is None:
        raise APIError("missing_cutting_rate", "Branch cutting rate is not set")
    panel_demands = _panel_stock_demands(result)
    edge_demands = _edge_stock_demands(result)
    if edge_demands and pricing.edge_banding_rate_tiyin is None:
        raise APIError("missing_edge_banding_rate", "Branch edge banding rate is not set")
    branch_materials = await _active_branch_materials(
        db,
        branch_id=branch_id,
        material_ids=set(panel_demands) | set(edge_demands),
    )
    for material_id in panel_demands:
        if material_id not in branch_materials:
            raise APIError("branch_does_not_carry_panel", "Branch does not carry a panel material")
    for material_id in edge_demands:
        if material_id not in branch_materials:
            raise APIError("branch_does_not_carry_edge", "Branch does not carry an edge material")

    subtotal_cutting = sum(int(value) for value in result.panels_used_by_material.values()) * int(
        pricing.cutting_rate_tiyin
    )
    subtotal_materials = sum(
        branch_materials[material_id].price_tiyin * quantity
        for material_id, quantity in panel_demands.items()
    )
    edge_material_total = sum(
        _millimetre_price(edge_demands[material_id], branch_materials[material_id].price_tiyin)
        for material_id in edge_demands
    )
    # Sum per-material labor (not _millimetre_price of the global sum): integer
    # floor-division isn't distributive, so per-material must be summed for the
    # itemized edge_lines (CB-117) to reconcile exactly with this subtotal.
    edge_labor_total = sum(
        _millimetre_price(edge_demands[material_id], int(pricing.edge_banding_rate_tiyin or 0))
        for material_id in edge_demands
    )
    priced_parts = _priced_parts(result, branch_materials)
    subtotal_edge = edge_material_total + edge_labor_total
    total = subtotal_cutting + subtotal_materials + subtotal_edge
    edge_rate = int(pricing.edge_banding_rate_tiyin or 0)

    def _line_name(material_id: uuid.UUID) -> str:
        snapshot = result.material_snapshots.get(str(material_id), {})
        manufacturer = str(snapshot.get("manufacturer_name", "")).strip()
        name = str(snapshot.get("name", "")).strip()
        return f"{manufacturer} {name}".strip() or "Material"

    material_lines = [
        MaterialPriceLine(
            material_id=material_id,
            material_name=_line_name(material_id),
            panels_used=quantity,
            unit_price_tiyin=branch_materials[material_id].price_tiyin,
            line_total_tiyin=branch_materials[material_id].price_tiyin * quantity,
        )
        for material_id, quantity in panel_demands.items()
    ]
    edge_lines = []
    for material_id in edge_demands:
        mm = edge_demands[material_id]
        material_cost = _millimetre_price(mm, branch_materials[material_id].price_tiyin)
        service_cost = _millimetre_price(mm, edge_rate)
        edge_lines.append(
            EdgePriceLine(
                material_id=material_id,
                material_name=_line_name(material_id),
                consumed_mm=mm,
                material_cost_tiyin=material_cost,
                service_cost_tiyin=service_cost,
                line_total_tiyin=material_cost + service_cost,
            )
        )
    return PricingSnapshot(
        subtotal_cutting_tiyin=subtotal_cutting,
        subtotal_materials_tiyin=subtotal_materials,
        subtotal_edge_banding_tiyin=subtotal_edge,
        total_tiyin=total,
        priced_parts=priced_parts,
        panels_used=sum(int(value) for value in result.panels_used_by_material.values()),
        cutting_rate_tiyin=int(pricing.cutting_rate_tiyin),
        material_lines=material_lines,
        edge_lines=edge_lines,
    )


def _priced_parts(
    result: CuttingResult,
    branch_materials: dict[uuid.UUID, BranchMaterial],
) -> list[PricedPart]:
    priced: list[PricedPart] = []
    panel_line_prices = _panel_line_prices(result, branch_materials)
    for index, part in enumerate(result.parts_snapshot):
        material_id = uuid.UUID(str(part["material_id"]))
        material_source = MaterialSource(str(part["material_source"]))
        panel_price = (
            panel_line_prices[index]
            if material_source is MaterialSource.SHOP and material_id in branch_materials
            else 0
        )
        material_snapshot = dict(result.material_snapshots.get(str(material_id), {}))
        material_snapshot["price_tiyin"] = (
            branch_materials[material_id].price_tiyin if material_id in branch_materials else 0
        )
        edge_snapshots: dict[str, dict[str, Any] | None] = {}
        edge_cost = 0
        quantity = int(part["quantity"])
        for field in _edge_fields():
            edge = part.get(field)
            if edge is None:
                edge_snapshots[field] = None
                continue
            edge_material_id = uuid.UUID(str(edge["material_id"]))
            edge_source = MaterialSource(str(edge["source"]))
            side_mm = _side_length_mm(part, field) * quantity
            side_consumed_mm = side_mm + 30 * quantity if edge_source is MaterialSource.SHOP else 0
            price = (
                branch_materials[edge_material_id].price_tiyin
                if edge_source is MaterialSource.SHOP and edge_material_id in branch_materials
                else 0
            )
            edge_cost += _millimetre_price(side_consumed_mm, price)
            snapshot = dict(result.material_snapshots.get(str(edge_material_id), {}))
            snapshot["price_tiyin"] = price
            edge_snapshots[field] = {
                "material_id": str(edge_material_id),
                "source": edge_source.value,
                "snapshot": snapshot,
            }
        priced.append(
            PricedPart(
                part=part,
                panel_price_tiyin=panel_price,
                edge_cost_tiyin=edge_cost,
                material_snapshot=material_snapshot,
                edge_snapshots=edge_snapshots,
            )
        )
    return priced


def _panel_line_prices(
    result: CuttingResult,
    branch_materials: dict[uuid.UUID, BranchMaterial],
) -> list[int]:
    panel_demands = _panel_stock_demands(result)
    area_by_material: dict[uuid.UUID, int] = {}
    row_area: list[tuple[uuid.UUID, int]] = []
    for part in result.parts_snapshot:
        material_id = uuid.UUID(str(part["material_id"]))
        material_source = MaterialSource(str(part["material_source"]))
        area = (
            int(part["length_mm"]) * int(part["width_mm"]) * int(part["quantity"])
            if material_source is MaterialSource.SHOP and material_id in branch_materials
            else 0
        )
        row_area.append((material_id, area))
        area_by_material[material_id] = area_by_material.get(material_id, 0) + area

    allocations = [0 for _ in result.parts_snapshot]
    running_by_material: dict[uuid.UUID, int] = {}
    last_index_by_material = {
        material_id: index for index, (material_id, area) in enumerate(row_area) if area > 0
    }
    for index, (material_id, area) in enumerate(row_area):
        total_area = area_by_material.get(material_id, 0)
        if area == 0 or total_area == 0:
            continue
        material_total = branch_materials[material_id].price_tiyin * panel_demands.get(
            material_id,
            0,
        )
        allocated = material_total * area // total_area
        if index == last_index_by_material.get(material_id):
            allocated = material_total - running_by_material.get(material_id, 0)
        allocations[index] = allocated
        running_by_material[material_id] = running_by_material.get(material_id, 0) + allocated
    return allocations


def _panel_stock_demands(result: CuttingResult) -> dict[uuid.UUID, int]:
    area_by_material: dict[uuid.UUID, int] = {}
    shop_area_by_material: dict[uuid.UUID, int] = {}
    for part in result.parts_snapshot:
        material_id = uuid.UUID(str(part["material_id"]))
        area = int(part["length_mm"]) * int(part["width_mm"]) * int(part["quantity"])
        area_by_material[material_id] = area_by_material.get(material_id, 0) + area
        if MaterialSource(str(part["material_source"])) is MaterialSource.SHOP:
            shop_area_by_material[material_id] = shop_area_by_material.get(material_id, 0) + area
    demands: dict[uuid.UUID, int] = {}
    for material_id_text, panels_used in result.panels_used_by_material.items():
        material_id = uuid.UUID(material_id_text)
        shop_area = shop_area_by_material.get(material_id, 0)
        if shop_area == 0:
            continue
        total_area = area_by_material.get(material_id, shop_area)
        demands[material_id] = max(1, math.ceil(int(panels_used) * shop_area / total_area))
    return demands


def _edge_stock_demands(result: CuttingResult) -> dict[uuid.UUID, int]:
    return {
        uuid.UUID(material_id): int(quantity)
        for material_id, quantity in result.edge_consumed_shop_by_material.items()
        if int(quantity) > 0
    }


async def _active_branch_materials(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    material_ids: set[uuid.UUID],
) -> dict[uuid.UUID, BranchMaterial]:
    if not material_ids:
        return {}
    rows = (
        await db.scalars(
            select(BranchMaterial)
            .join(Material, Material.id == BranchMaterial.material_id)
            .where(
                BranchMaterial.branch_id == branch_id,
                BranchMaterial.material_id.in_(material_ids),
                BranchMaterial.status == MaterialStatus.ACTIVE,
                Material.status == MaterialStatus.ACTIVE,
            )
        )
    ).all()
    return {row.material_id: row for row in rows}


async def _client_orderable_draft_result(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    draft_id: uuid.UUID,
) -> tuple[CuttingDraft, CuttingResult]:
    draft = await db.get(CuttingDraft, draft_id)
    if draft is None or draft.client_id != client_id:
        raise APIError("cutting_result_not_usable", "Cutting result is not usable", status_code=404)
    if draft.chosen_result_id is None:
        raise APIError("cutting_result_not_usable", "Choose a cutting result first")
    result = await db.get(CuttingResult, draft.chosen_result_id)
    if (
        result is None
        or result.draft_id != draft.id
        or result.status is not CuttingResultStatus.CANDIDATE
    ):
        raise APIError("cutting_result_not_usable", "Cutting result is not usable")
    return draft, result


async def _active_branch_for_order(
    db: AsyncSession,
    branch_id: uuid.UUID,
) -> tuple[Branch, Workshop]:
    row = (
        await db.execute(
            select(Branch, Workshop)
            .join(Workshop, Workshop.id == Branch.workshop_id)
            .where(Branch.id == branch_id)
        )
    ).one_or_none()
    if row is None:
        raise APIError("branch_closed", "Branch is not accepting orders", status_code=404)
    branch, workshop = row
    if workshop.status is not WorkshopStatus.ACTIVE:
        raise APIError("workshop_blocked", "Workshop is blocked", status_code=403)
    if branch.status is not BranchStatus.ACTIVE:
        raise APIError("branch_closed", "Branch is not accepting orders")
    return branch, workshop


async def _delete_other_candidate_results(
    db: AsyncSession,
    *,
    draft_id: uuid.UUID,
    keep_result_id: uuid.UUID,
) -> None:
    result_ids = (
        await db.scalars(
            select(CuttingResult.id).where(
                CuttingResult.draft_id == draft_id,
                CuttingResult.status == CuttingResultStatus.CANDIDATE,
                CuttingResult.id != keep_result_id,
            )
        )
    ).all()
    if not result_ids:
        return
    panel_ids = (
        await db.scalars(
            select(CuttingPanel.id).where(CuttingPanel.cutting_result_id.in_(result_ids))
        )
    ).all()
    if panel_ids:
        await db.execute(
            delete(CuttingPlacement).where(CuttingPlacement.cutting_panel_id.in_(panel_ids))
        )
        await db.execute(delete(CuttingPanel).where(CuttingPanel.id.in_(panel_ids)))
    await db.execute(delete(CuttingResult).where(CuttingResult.id.in_(result_ids)))


async def _locked_order(db: AsyncSession, order_id: uuid.UUID) -> Order:
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise APIError("order_not_found", "Order not found", status_code=404)
    return order


async def _locked_workshop_order_visible(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> Order:
    order = await _locked_order(db, order_id)
    if not _can_view_workshop_order(principal, order):
        raise APIError("order_not_found", "Order not found", status_code=404)
    return order


async def _locked_workshop_order_for_action(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    permission: Permission,
) -> Order:
    order = await _locked_workshop_order_visible(db, principal=principal, order_id=order_id)
    if not _has_order_permission(principal, order, permission):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return order


async def _workshop_order_in_scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> Order:
    order = await db.get(Order, order_id)
    if order is None or not _can_view_workshop_order(principal, order):
        raise APIError("order_not_found", "Order not found", status_code=404)
    return order


def _apply_workshop_order_scope(
    query: Any,
    principal: AuthenticatedPrincipal,
    *,
    branch_id: uuid.UUID | None,
) -> Any:
    _require_workshop(principal)
    query = query.where(Order.workshop_id == principal.workshop_id)
    if principal.is_owner:
        return query.where(Order.branch_id == branch_id) if branch_id is not None else query
    branch_ids = {
        grant.branch_id
        for grant in principal.grants
        if grant.permission in WORKSHOP_ORDER_VIEW_PERMISSIONS
    }
    if branch_id is not None:
        branch_ids = {branch_id} if branch_id in branch_ids else set()
    return query.where(Order.branch_id.in_(branch_ids))


def _apply_order_filters(query: Any, *, status_filter: str | None, search: str | None) -> Any:
    if status_filter and status_filter != "all":
        if status_filter == "active":
            query = query.where(
                Order.status.in_(
                    [
                        OrderStatus.NEW,
                        OrderStatus.CONFIRMED,
                        OrderStatus.CUTTING,
                        OrderStatus.EDGE_BANDING,
                        OrderStatus.READY,
                    ]
                )
            )
        else:
            try:
                status_value = OrderStatus(status_filter)
            except ValueError as exc:
                raise APIError("invalid_order_status", "Invalid order status") from exc
            query = query.where(Order.status == status_value)
    normalized = search.strip() if search else ""
    if normalized:
        pattern = f"%{normalized.lower()}%"
        query = query.where(
            or_(Order.order_number.ilike(pattern), Order.contact_name.ilike(pattern))
        )
    return query


def _can_view_workshop_order(principal: AuthenticatedPrincipal, order: Order) -> bool:
    return any(
        _has_order_permission(principal, order, permission)
        for permission in WORKSHOP_ORDER_VIEW_PERMISSIONS
    )


def _has_order_permission(
    principal: AuthenticatedPrincipal,
    order: Order,
    permission: Permission,
) -> bool:
    return can_access_branch(
        principal,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        permission=permission,
    )


async def _credited_worker(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order: Order,
    requested_user_id: uuid.UUID | None,
    assigned_user_id: uuid.UUID | None,
    job: str,
) -> uuid.UUID:
    manage = _has_order_permission(principal, order, Permission.MANAGE_ORDERS)
    process = _has_order_permission(principal, order, Permission.PROCESS_PRODUCTION)
    if not manage and not process:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    if manage:
        worker_id = requested_user_id or assigned_user_id
        if worker_id is None:
            raise APIError("worker_required", "Choose who did this work")
        await _validate_production_worker(
            db,
            workshop_id=order.workshop_id,
            branch_id=order.branch_id,
            user_id=worker_id,
        )
        return worker_id
    if assigned_user_id != principal.principal_id:
        raise APIError(
            "not_assigned",
            f"This {job} job is assigned to another worker",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    await _validate_production_worker(
        db,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        user_id=principal.principal_id,
    )
    return principal.principal_id


async def _validate_production_worker(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkshopUser:
    user = await db.get(WorkshopUser, user_id)
    if user is None or user.workshop_id != workshop_id or user.status is not UserStatus.ACTIVE:
        raise APIError("worker_not_found", "Worker not found", status_code=404)
    if user.is_owner:
        return user
    if user.home_branch_id != branch_id:
        raise APIError("worker_wrong_branch", "Worker does not belong to this branch")
    grant = await db.scalar(
        select(PermissionGrant).where(
            PermissionGrant.workshop_user_id == user.id,
            PermissionGrant.branch_id == branch_id,
            PermissionGrant.permission == Permission.PROCESS_PRODUCTION,
        )
    )
    if grant is None:
        raise APIError("worker_missing_permission", "Worker cannot process production")
    return user


async def _eligible_workers(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID | None,
    branch_id: uuid.UUID,
) -> list[WorkshopUser]:
    if workshop_id is None:
        return []
    rows = (
        await db.scalars(
            select(WorkshopUser)
            .where(
                WorkshopUser.workshop_id == workshop_id,
                WorkshopUser.status == UserStatus.ACTIVE,
            )
            .order_by(WorkshopUser.is_owner.desc(), WorkshopUser.full_name)
        )
    ).all()
    eligible: list[WorkshopUser] = []
    for row in rows:
        if row.is_owner:
            eligible.append(row)
            continue
        if row.home_branch_id != branch_id:
            continue
        grant = await db.scalar(
            select(PermissionGrant).where(
                PermissionGrant.workshop_user_id == row.id,
                PermissionGrant.branch_id == branch_id,
                PermissionGrant.permission == Permission.PROCESS_PRODUCTION,
            )
        )
        if grant is not None:
            eligible.append(row)
    return eligible


async def _order_result(db: AsyncSession, order: Order) -> CuttingResult:
    result = await db.get(CuttingResult, order.cutting_result_id)
    if result is None:
        raise APIError("cutting_result_not_found", "Cutting result not found", status_code=404)
    return result


async def _order_has_banding(db: AsyncSession, order_id: uuid.UUID) -> bool:
    items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order_id))).all()
    return _items_have_banding(items)


def _items_have_banding(items: Sequence[OrderItem]) -> bool:
    return any(
        item.edge_top is not None
        or item.edge_bottom is not None
        or item.edge_left is not None
        or item.edge_right is not None
        for item in items
    )


async def _client(db: AsyncSession, principal: AuthenticatedPrincipal) -> Client:
    if principal.principal_type is not AuthenticatedPrincipalType.CLIENT:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    client = await db.get(Client, principal.principal_id)
    if client is None:
        raise APIError("invalid_access_token", "Authentication required", status_code=401)
    return client


def _require_workshop(principal: AuthenticatedPrincipal) -> None:
    if (
        principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER
        or principal.workshop_id is None
    ):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


def _expect_version(order: Order, version: int) -> None:
    if order.version != version:
        raise APIError(
            "order_version_conflict",
            "This order changed. Refresh and try again.",
            status_code=status.HTTP_409_CONFLICT,
            details={"current_version": order.version},
        )


def _expect_status(order: Order, allowed: set[OrderStatus]) -> None:
    if order.status not in allowed:
        raise APIError("invalid_order_status", "Order status does not allow this action")


def _bump_order(order: Order) -> None:
    order.version += 1
    order.updated_at = datetime.now(UTC)


async def _next_order_number(db: AsyncSession, now: datetime) -> str:
    prefix = f"ORD-{now.year}-"
    count = await db.scalar(
        select(func.count(Order.id)).where(Order.order_number.like(f"{prefix}%"))
    )
    return f"{prefix}{int(count or 0) + 1:06d}"


def _pre_discount_total(order: Order) -> int:
    return (
        order.subtotal_cutting_tiyin
        + order.subtotal_materials_tiyin
        + order.subtotal_edge_banding_tiyin
    )


def _contact_name(value: str) -> str:
    normalized = _required_text(value, "contact_name_required")
    if len(normalized) > 80:
        raise APIError("invalid_contact_name", "Contact name is too long")
    return normalized


def _contact_phone(value: str) -> str:
    normalized = value.strip().replace(" ", "")
    if not PHONE_RE.fullmatch(normalized):
        raise APIError("invalid_contact_phone", "Contact phone must be +998XXXXXXXXX")
    return normalized


def _required_reason(value: str) -> str:
    normalized = _required_text(value, "reason_required")
    if len(normalized) < 3:
        raise APIError("reason_required", "Reason is required")
    return normalized


def _required_text(value: str, code: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise APIError(code, "Required field is missing")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None


def _millimetre_price(length_mm: int, metre_price_tiyin: int) -> int:
    if length_mm <= 0 or metre_price_tiyin <= 0:
        return 0
    return length_mm * metre_price_tiyin // 1000


def _edge_fields() -> tuple[str, str, str, str]:
    return ("edge_top", "edge_bottom", "edge_left", "edge_right")


def _side_length_mm(part: dict[str, Any], field: str) -> int:
    return int(part["length_mm"]) if field in {"edge_top", "edge_bottom"} else int(part["width_mm"])
