"""Order pricing, placement, and production workflow use cases."""

from __future__ import annotations

import copy
import math
import re
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from fastapi import status
from sqlalchemy import Select, and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import APIError
from app.core.material_label import edge_label, material_label
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
from app.modules.access.api import can_access_branch, seed_preferred_branch_if_missing
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import (
    BranchMaterial,
    BranchPricing,
    Dekor,
    Manufacturer,
    is_tape,
)
from app.modules.cutting.api import cutting_result_response, get_workshop_draft
from app.modules.cutting.contracts import (
    CuttingDraft,
    CuttingPanel,
    CuttingPlacement,
    CuttingResult,
)
from app.modules.cutting.schemas import CuttingDraftResponse
from app.modules.finance.contracts import Income
from app.modules.inventory.api import consume_order_stock, restore_order_stock
from app.modules.inventory.contracts import StockItem
from app.modules.sales.contracts import Order, OrderCancellation, OrderItem, OrderStatusEvent
from app.modules.sales.schemas import (
    BatchOrderQuoteResponse,
    ClientOrderCreateRequest,
    EdgePriceLine,
    MaterialPriceLine,
    NewOrderCountResponse,
    OrderDetailResponse,
    OrderEdgeMaterialDemand,
    OrderItemResponse,
    OrderPriceLine,
    OrderQuoteResponse,
    OrderSettlementResponse,
    OrderStatusEventResponse,
    OrderStockWarning,
    OrderSummaryResponse,
    ProductionEdgeSide,
    ProductionJobCard,
    ProductionJobDetail,
    ProductionJobItem,
    ProductionQueueResponse,
    ProductionWorkerRef,
    ReasonedVersionedRequest,
    VersionedRequest,
    WorkshopOrderAssignRequest,
    WorkshopOrderCompleteRequest,
    WorkshopOrderCreateRequest,
    WorkshopOrderDiscountRequest,
    WorkshopOrderEditApplyRequest,
    WorkshopOrderNoteRequest,
    WorkshopOrderSurchargeRequest,
    WorkshopWorkerOption,
)
from app.modules.support.api import record_action, record_status_change
from app.modules.support.contracts import Notification
from app.modules.workshop.contracts import Branch, Workshop

PHONE_RE = re.compile(r"^\+998\d{9}$")
WORKSHOP_ORDER_VIEW_PERMISSIONS = frozenset(
    {
        Permission.VIEW_ORDERS,
        Permission.MANAGE_ORDERS,
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
    edge_banding_rate_tiyin: int
    material_lines: list[MaterialPriceLine]
    edge_lines: list[EdgePriceLine]


@dataclass(frozen=True)
class FinanceOrderTarget:
    order_id: uuid.UUID
    workshop_id: uuid.UUID
    branch_id: uuid.UUID
    total_tiyin: int


@dataclass(frozen=True)
class PayableOrder:
    """An order that still owes money, with its settlement already folded in."""

    order_id: uuid.UUID
    order_number: str
    contact_name: str
    contact_phone: str
    status: OrderStatus
    created_at: datetime
    total_tiyin: int
    recorded_tiyin: int
    balance_tiyin: int


@dataclass(frozen=True)
class OrderSettlementRef:
    """One order's identity and settlement, for a caller that already has its id.

    Same three money figures as `PayableOrder`, but no candidacy rules: an
    income keeps pointing at its order long after that order stops being a
    payment candidate (settled, or cancelled), and the ledger still has to name
    it.
    """

    order_id: uuid.UUID
    order_number: str
    contact_name: str
    total_tiyin: int
    recorded_tiyin: int
    balance_tiyin: int


@dataclass(frozen=True)
class EdgeMaterialProductionLine:
    material_id: uuid.UUID
    material_label: str
    thickness_mm: Decimal | None
    color: str | None
    length_mm: int


@dataclass(frozen=True)
class WorkerProductionRecord:
    user_id: uuid.UUID
    full_name: str
    panels_cut: int
    cut_count: int
    orders_banded: int
    edge_length_by_material: dict[str, int]
    edge_lines: tuple[EdgeMaterialProductionLine, ...] = ()
    edge_length_by_thickness: dict[str, int] = dataclass_field(default_factory=dict)


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
        order_number=await _next_order_number(db, now, branch.branch_no),
        client_id=client.id,
        workshop_id=workshop.id,
        branch_id=branch.id,
        cutting_result_id=result.id,
        status=OrderStatus.NEW,
        version=1,
        contact_name=_contact_name(payload.contact_name),
        contact_phone=_contact_phone(payload.contact_phone),
        note_client=_optional_text(payload.note_client),
        # Copied now, while the drawing still exists — placing an order deletes
        # it further down, so this is the only moment the name is readable.
        draft_name=draft.name,
        created_via_workshop=draft.created_via_workshop_id is not None,
        subtotal_cutting_tiyin=pricing.subtotal_cutting_tiyin,
        subtotal_materials_tiyin=pricing.subtotal_materials_tiyin,
        subtotal_edge_banding_tiyin=pricing.subtotal_edge_banding_tiyin,
        discount_tiyin=0,
        surcharge_tiyin=0,
        total_tiyin=pricing.total_tiyin,
        currency=Currency.UZS,
    )
    db.add(order)
    await db.flush()

    await seed_preferred_branch_if_missing(db, client=client, branch_id=branch.id)

    _add_order_items(db, order=order, pricing=pricing)

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


def _add_order_items(
    db: AsyncSession,
    *,
    order: Order,
    pricing: PricingSnapshot,
) -> None:
    """Append one OrderItem per priced part. Shared by the client and workshop
    create paths so the line-total formula (ck_order_items_line_total_formula)
    stays in one place."""
    for priced in pricing.priced_parts:
        quantity = int(priced.part["quantity"])
        # The per-part panel cost is divided into an integer per-unit price; the line
        # total must be derived from that same (floored) unit price, not the raw
        # panel_price_tiyin, or it breaks ck_order_items_line_total_formula
        # (line_total = (unit_cutting + unit_material) * quantity + edge_cost) whenever
        # panel_price_tiyin isn't divisible by quantity. The order's authoritative
        # subtotals/total stay exact (computed in _price_result); only the per-line
        # material display rounds down by up to quantity-1 tiyin.
        unit_material_price = priced.panel_price_tiyin // quantity
        db.add(
            OrderItem(
                order_id=order.id,
                # parts_snapshot keeps the JSON key `material_id`; what it holds
                # is a branch_material id (the migration rewrote the values).
                branch_material_id=uuid.UUID(str(priced.part["material_id"])),
                material_source=MaterialSource(str(priced.part["material_source"])),
                material_snapshot=priced.material_snapshot,
                part_ref=str(priced.part["part_ref"]),
                length_mm=int(priced.part["length_mm"]),
                width_mm=int(priced.part["width_mm"]),
                quantity=quantity,
                edge_top=priced.edge_snapshots["edge_top"],
                edge_bottom=priced.edge_snapshots["edge_bottom"],
                edge_left=priced.edge_snapshots["edge_left"],
                edge_right=priced.edge_snapshots["edge_right"],
                unit_cutting_price_tiyin=0,
                unit_material_price_tiyin=unit_material_price,
                edge_cost_tiyin=priced.edge_cost_tiyin,
                line_total_tiyin=unit_material_price * quantity + priced.edge_cost_tiyin,
            )
        )


async def quote_client_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> OrderQuoteResponse:
    client = await _client(db, principal)
    branch, workshop = await _active_branch_for_order(db, branch_id)
    _, result = await _client_orderable_draft_result(
        db,
        client_id=client.id,
        draft_id=draft_id,
    )
    pricing = await _price_result(db, branch_id=branch.id, result=result)
    return _build_quote_response(draft_id, branch, pricing, workshop)


async def _workshop_order_branch(
    db: AsyncSession,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> tuple[Branch, Workshop]:
    """Active branch of the principal's OWN workshop that they may place orders
    on (manage_orders on that branch; owner bypass via can_access_branch)."""
    _require_workshop(principal)
    branch, workshop = await _active_branch_for_order(db, branch_id)
    if workshop.id != principal.workshop_id or not can_access_branch(
        principal,
        workshop_id=workshop.id,
        branch_id=branch.id,
        permission=Permission.MANAGE_ORDERS,
    ):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return branch, workshop


async def _workshop_orderable_draft_result(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    draft_id: uuid.UUID,
    allow_revision: bool = False,
) -> tuple[CuttingDraft, CuttingResult]:
    """Draft-scope guard for the workshop path: the draft must have been minted
    via THIS workshop (created_via_workshop_id), else 404 — mirrors the client
    path's ownership check, which lives here (not the route) for both surfaces.
    A revision draft never places a NEW order (its only exit is applying back
    onto its order), so placement keeps `allow_revision` False; the quote path
    allows it — the revision review screen prices through the same endpoint."""
    draft = await db.get(CuttingDraft, draft_id)
    if draft is None or draft.created_via_workshop_id != workshop_id:
        raise APIError("cutting_result_not_usable", "Cutting result is not usable", status_code=404)
    if draft.revision_of_order_id is not None and not allow_revision:
        raise APIError("cutting_result_not_usable", "Cutting result is not usable")
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


async def quote_workshop_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> OrderQuoteResponse:
    branch, workshop = await _workshop_order_branch(db, principal, branch_id)
    _, result = await _workshop_orderable_draft_result(
        db,
        workshop_id=workshop.id,
        draft_id=draft_id,
        allow_revision=True,
    )
    pricing = await _price_result(db, branch_id=branch.id, result=result)
    return _build_quote_response(draft_id, branch, pricing, workshop)


async def place_workshop_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: WorkshopOrderCreateRequest,
) -> OrderDetailResponse:
    """Staff create + auto-confirm an order for a walk-in client. The client is
    the draft owner (resolved earlier by phone); the order arrives `confirmed`
    with both the ∅→new and new→confirmed events authored by the staff user."""
    branch, workshop = await _workshop_order_branch(db, principal, payload.branch_id)
    draft, result = await _workshop_orderable_draft_result(
        db,
        workshop_id=workshop.id,
        draft_id=payload.draft_id,
    )
    pricing = await _price_result(db, branch_id=branch.id, result=result)
    now = datetime.now(UTC)
    order = Order(
        order_number=await _next_order_number(db, now, branch.branch_no),
        client_id=draft.client_id,
        workshop_id=workshop.id,
        branch_id=branch.id,
        cutting_result_id=result.id,
        status=OrderStatus.NEW,
        version=1,
        contact_name=_contact_name(payload.contact_name),
        contact_phone=_contact_phone(payload.contact_phone),
        note_client=_optional_text(payload.note_client),
        # Copied now, while the drawing still exists — placing an order deletes
        # it further down, so this is the only moment the name is readable.
        draft_name=draft.name,
        created_via_workshop=draft.created_via_workshop_id is not None,
        subtotal_cutting_tiyin=pricing.subtotal_cutting_tiyin,
        subtotal_materials_tiyin=pricing.subtotal_materials_tiyin,
        subtotal_edge_banding_tiyin=pricing.subtotal_edge_banding_tiyin,
        discount_tiyin=0,
        surcharge_tiyin=0,
        total_tiyin=pricing.total_tiyin,
        currency=Currency.UZS,
    )
    db.add(order)
    await db.flush()

    _add_order_items(db, order=order, pricing=pricing)

    result.status = CuttingResultStatus.CONFIRMED
    result.order_id = order.id
    result.draft_id = None
    result.confirmed_at = now
    draft.chosen_result_id = None
    await db.flush()
    await _delete_other_candidate_results(db, draft_id=draft.id, keep_result_id=result.id)
    await db.delete(draft)

    # ∅→new authored by the staff user (actor shape: workshop_user + user id).
    await _append_order_event(
        db,
        order=order,
        from_status=None,
        to_status=OrderStatus.NEW,
        actor_type=ActorType.WORKSHOP_USER,
        actor_user_id=principal.principal_id,
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
        details={"cutting_result_id": str(result.id), "on_behalf": True},
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
    # Auto-confirm in the same call — the creator is the approver. _transition
    # writes the new→confirmed event (staff actor) + the standard order.confirmed
    # client notification; set confirmed_at like approve_order does.
    order.confirmed_at = now
    await _transition(
        db,
        principal=principal,
        order=order,
        to_status=OrderStatus.CONFIRMED,
        reason=None,
        metadata={},
    )
    await db.flush()
    return cast(
        OrderDetailResponse,
        await _order_response(db, order, include_detail=True),
    )


async def begin_order_edit(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> CuttingDraftResponse:
    """Create — or resume — the order's revision draft (orders.md: "Revising a
    placed order"): a staff-scoped scratchpad seeded from the confirmed result's
    parts, branch-locked to the order's branch. Idempotent; the order itself is
    untouched until the revision is applied."""
    order = await _locked_workshop_order_for_action(
        db, principal=principal, order_id=order_id, permission=Permission.MANAGE_ORDERS
    )
    _expect_editable_status(order)
    existing_id = await db.scalar(
        select(CuttingDraft.id).where(CuttingDraft.revision_of_order_id == order.id)
    )
    if existing_id is not None:
        return await get_workshop_draft(db, principal=principal, draft_id=existing_id)
    result = await _order_result(db, order)
    draft = CuttingDraft(
        client_id=order.client_id,
        preferred_branch_id=order.branch_id,
        created_via_workshop_id=order.workshop_id,
        revision_of_order_id=order.id,
        parts_snapshot=copy.deepcopy(result.parts_snapshot),
    )
    db.add(draft)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="orders.edit.begin",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=f"Started a revision of {order.order_number}",
        details={"revision_draft_id": str(draft.id)},
    )
    return await get_workshop_draft(db, principal=principal, draft_id=draft.id)


async def apply_order_edit(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: WorkshopOrderEditApplyRequest,
) -> OrderDetailResponse:
    """Apply the order's revision draft atomically (orders.md: "Revising a
    placed order"): rebind the cutting result, replace the item snapshots,
    re-freeze pricing at the branch's current rates, clear the discount, and
    record the edit on the append-only event spine. Status never changes."""
    order = await _locked_workshop_order_for_action(
        db, principal=principal, order_id=order_id, permission=Permission.MANAGE_ORDERS
    )
    _expect_version(order, payload.version)
    _expect_editable_status(order)
    draft = await db.scalar(
        select(CuttingDraft).where(CuttingDraft.revision_of_order_id == order.id)
    )
    if draft is None:
        raise APIError("order_revision_not_found", "Order has no open revision", status_code=404)
    _, result = await _workshop_orderable_draft_result(
        db, workshop_id=order.workshop_id, draft_id=draft.id, allow_revision=True
    )
    pricing = await _price_result(db, branch_id=order.branch_id, result=result)
    reason = _optional_text(payload.reason)
    now = datetime.now(UTC)

    old_result = await _order_result(db, order)
    previous_total = order.total_tiyin
    previous_discount = order.discount_tiyin
    previous_surcharge = order.surcharge_tiyin
    previous_result_id = str(old_result.id)
    # The superseded result must release the unique order binding
    # (uq_cutting_results_order is immediate) before the new one takes it.
    old_result.order_id = None
    await db.flush()

    result.status = CuttingResultStatus.CONFIRMED
    result.order_id = order.id
    result.draft_id = None
    result.confirmed_at = now
    order.cutting_result_id = result.id
    draft.chosen_result_id = None
    await db.flush()
    await _delete_other_candidate_results(db, draft_id=draft.id, keep_result_id=result.id)
    await _delete_cutting_result(db, old_result)
    await db.delete(draft)

    await db.execute(delete(OrderItem).where(OrderItem.order_id == order.id))
    _add_order_items(db, order=order, pricing=pricing)

    discount_cleared = previous_discount > 0
    surcharge_cleared = previous_surcharge > 0
    order.discount_tiyin = 0
    order.discount_reason = None
    order.discount_applied_by_user_id = None
    order.surcharge_tiyin = 0
    order.surcharge_reason = None
    order.surcharge_applied_by_user_id = None
    order.subtotal_cutting_tiyin = pricing.subtotal_cutting_tiyin
    order.subtotal_materials_tiyin = pricing.subtotal_materials_tiyin
    order.subtotal_edge_banding_tiyin = pricing.subtotal_edge_banding_tiyin
    order.total_tiyin = pricing.total_tiyin

    edger_cleared = False
    if order.assigned_edger_user_id is not None and not _parts_have_banding(result.parts_snapshot):
        order.assigned_edger_user_id = None
        order.edger_assigned_at = None
        edger_cleared = True

    _bump_order(order)
    metadata: dict[str, Any] = {
        "edited": True,
        "previous_total_tiyin": previous_total,
        "total_tiyin": order.total_tiyin,
        "previous_cutting_result_id": previous_result_id,
        "cutting_result_id": str(result.id),
    }
    if discount_cleared:
        metadata["discount_cleared_tiyin"] = previous_discount
    if surcharge_cleared:
        metadata["surcharge_cleared_tiyin"] = previous_surcharge
    if edger_cleared:
        metadata["edger_assignment_cleared"] = True
    await _append_order_event(
        db,
        order=order,
        from_status=order.status,
        to_status=order.status,
        actor_type=ActorType.WORKSHOP_USER,
        actor_user_id=principal.principal_id,
        reason=reason,
        metadata=metadata,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="orders.edit",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=f"Edited order {order.order_number}",
        details=metadata,
    )
    db.add(
        Notification(
            recipient_type=AuthenticatedPrincipalType.CLIENT,
            recipient_id=order.client_id,
            event_code="order.updated",
            entity_type="order",
            entity_id=order.id,
            payload={
                "order_number": order.order_number,
                "previous_total_tiyin": previous_total,
                "total_tiyin": order.total_tiyin,
            },
            created_at=now,
        )
    )
    await db.flush()
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


def _build_quote_response(
    draft_id: uuid.UUID,
    branch: Branch,
    pricing: PricingSnapshot,
    workshop: Workshop | None = None,
) -> OrderQuoteResponse:
    return OrderQuoteResponse(
        draft_id=draft_id,
        branch_id=branch.id,
        branch_name=branch.name,
        branch_address=branch.address,
        branch_phone=branch.phone,
        workshop_name=workshop.name if workshop is not None else "",
        branch_additional_phones=list(branch.additional_phones or []),
        branch_latitude=branch.latitude,
        branch_longitude=branch.longitude,
        subtotal_cutting_tiyin=pricing.subtotal_cutting_tiyin,
        subtotal_materials_tiyin=pricing.subtotal_materials_tiyin,
        subtotal_edge_banding_tiyin=pricing.subtotal_edge_banding_tiyin,
        total_tiyin=pricing.total_tiyin,
        panels_used=pricing.panels_used,
        cutting_rate_tiyin=pricing.cutting_rate_tiyin,
        edge_banding_rate_tiyin=pricing.edge_banding_rate_tiyin,
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
    return await _order_summary_responses(db, rows)


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
    date_from: date | None = None,
    date_to: date | None = None,
    contact_phone: str | None = None,
    assigned_cutter_user_id: uuid.UUID | None = None,
    assigned_edger_user_id: uuid.UUID | None = None,
    limit: int = 30,
    offset: int = 0,
) -> list[OrderSummaryResponse]:
    _require_workshop(principal)
    query = select(Order).order_by(Order.created_at.desc(), Order.order_number.desc())
    query = _apply_workshop_order_scope(query, principal, branch_id=branch_id)
    query = _apply_order_filters(
        query,
        status_filter=status_filter,
        search=search,
        date_from=date_from,
        date_to=date_to,
        contact_phone=contact_phone,
    )
    if assigned_cutter_user_id is not None:
        query = query.where(Order.assigned_cutter_user_id == assigned_cutter_user_id)
    if assigned_edger_user_id is not None:
        query = query.where(Order.assigned_edger_user_id == assigned_edger_user_id)
    # Keep the summary builder's per-order enrichment bounded. A fuller batch
    # summary path can still replace this later, but the API no longer downloads
    # or enriches an unbounded order history.
    query = query.limit(max(1, min(limit, 100))).offset(max(0, offset))
    rows = (await db.scalars(query)).all()
    return await _order_summary_responses(db, rows)


async def count_new_workshop_orders(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID | None = None,
) -> NewOrderCountResponse:
    """Backs the sidebar's `+N` badge (QAD-156): how many orders still sit in
    NEW and are waiting for someone to confirm them. Scoped to the branches the
    caller may manage orders in, so the number always agrees with the list the
    badge links to. Omitting `branch_id` counts the whole workshop."""
    _require_workshop(principal)
    query = select(func.count())
    query = query.select_from(Order).where(
        Order.workshop_id == principal.workshop_id,
        Order.status == OrderStatus.NEW,
    )
    if principal.is_owner:
        if branch_id is not None:
            query = query.where(Order.branch_id == branch_id)
    else:
        managed_branch_ids = {
            grant.branch_id
            for grant in principal.grants
            if grant.permission is Permission.MANAGE_ORDERS
        }
        if branch_id is not None:
            managed_branch_ids &= {branch_id}
        if not managed_branch_ids:
            return NewOrderCountResponse(count=0)
        query = query.where(Order.branch_id.in_(managed_branch_ids))
    return NewOrderCountResponse(count=await db.scalar(query) or 0)


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


async def list_payable_orders(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_ids: frozenset[uuid.UUID] | None,
    search: str | None = None,
    limit: int = 20,
) -> list[PayableOrder]:
    """Orders that still owe money, newest first — the finance order picker.

    Deliberately unfiltered by status apart from `cancelled`: money is most
    often taken at pickup, so a `completed` order is the single most likely
    payment target and hiding it is what made operators say "my order isn't
    there". A cancelled order stays out because v1 has no refund flow
    (`docs/scope.md`) — its recorded advance is settled off-system.

    The unpaid predicate runs in SQL, before LIMIT. Trimming a page in Python
    would silently return fewer rows than asked for whenever the newest orders
    happen to be settled, which reads to the operator as "not found".
    """
    if branch_ids is not None and not branch_ids:
        return []
    recorded = _recorded_income_total(Order.id).correlate(Order).scalar_subquery()
    query = (
        select(Order, recorded.label("recorded_tiyin"))
        .where(
            Order.workshop_id == workshop_id,
            Order.status != OrderStatus.CANCELLED,
            Order.total_tiyin > recorded,
        )
        .order_by(Order.created_at.desc(), Order.order_number.desc())
        .limit(max(1, min(limit, 100)))
    )
    if branch_ids is not None:
        query = query.where(Order.branch_id.in_(branch_ids))
    search_condition = _order_search_condition(search)
    if search_condition is not None:
        query = query.where(search_condition)
    rows = (await db.execute(query)).all()
    return [
        PayableOrder(
            order_id=order.id,
            order_number=order.order_number,
            contact_name=order.contact_name,
            contact_phone=order.contact_phone,
            status=order.status,
            created_at=order.created_at,
            total_tiyin=order.total_tiyin,
            recorded_tiyin=int(recorded_tiyin),
            balance_tiyin=_settlement_balance(order.total_tiyin, int(recorded_tiyin)),
        )
        for order, recorded_tiyin in rows
    ]


async def list_order_settlements(
    db: AsyncSession,
    *,
    workshop_ids: frozenset[uuid.UUID],
    order_ids: frozenset[uuid.UUID],
) -> list[OrderSettlementRef]:
    """Identity + settlement for a whole set of orders, in one round trip.

    The finance ledger resolves every order-linked row of a listed page through
    this — one aggregate over the set, never a query per row. Unlike
    `list_payable_orders` it applies no candidacy filter: the caller names the
    orders it already holds, and a settled or cancelled one still needs a label.

    Tenant-scoped by `workshop_ids` rather than permission-gated: the caller
    resolves rows it has already been authorized to read, and the ids come from
    those rows, not from user input.
    """
    if not order_ids or not workshop_ids:
        return []
    recorded = _recorded_income_total(Order.id).correlate(Order).scalar_subquery()
    query = select(Order, recorded.label("recorded_tiyin")).where(
        Order.workshop_id.in_(workshop_ids),
        Order.id.in_(order_ids),
    )
    rows = (await db.execute(query)).all()
    return [
        OrderSettlementRef(
            order_id=order.id,
            order_number=order.order_number,
            contact_name=order.contact_name,
            total_tiyin=order.total_tiyin,
            recorded_tiyin=int(recorded_tiyin),
            balance_tiyin=_settlement_balance(order.total_tiyin, int(recorded_tiyin)),
        )
        for order, recorded_tiyin in rows
    ]


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
    material_meta = await _edge_material_meta(db, rows.values())
    for row in list(rows.values()):
        edge_lines = _production_edge_lines(row.edge_length_by_material, material_meta)
        replace(
            WorkerProductionRecord(
                user_id=row.user_id,
                full_name=row.full_name,
                panels_cut=row.panels_cut,
                cut_count=row.cut_count,
                orders_banded=row.orders_banded,
                edge_length_by_material=dict(row.edge_length_by_material),
                edge_lines=tuple(edge_lines),
                edge_length_by_thickness=_edge_length_by_thickness(edge_lines),
            )
        )
    return sorted(rows.values(), key=lambda row: row.full_name)


async def _edge_material_meta(
    db: AsyncSession,
    rows: Iterable[WorkerProductionRecord],
) -> dict[str, tuple[str, Decimal | None, str | None]]:
    branch_material_ids = {
        uuid.UUID(material_id)
        for row in rows
        for material_id in row.edge_length_by_material
        if material_id
    }
    if not branch_material_ids:
        return {}
    # No status filter, deliberately: this labels *historical* production, and a
    # deactivated dekor or format must still render its name rather than an id.
    result = await db.execute(
        select(BranchMaterial, Dekor, Manufacturer)
        .join(Dekor, Dekor.id == BranchMaterial.dekor_id)
        .join(Manufacturer, Manufacturer.id == Dekor.manufacturer_id)
        .where(BranchMaterial.id.in_(branch_material_ids))
    )
    return {
        str(branch_material.id): (
            edge_label(
                {
                    "manufacturer_name": manufacturer.name,
                    "tur": dekor.tur.value,
                    "kod": dekor.kod,
                    "nomi": dekor.nomi,
                    "qalinlik_mm": str(branch_material.qalinlik_mm),
                    "kromka_eni_mm": branch_material.kromka_eni_mm,
                },
                branch_material.id,
            ),
            _normalized_decimal(branch_material.qalinlik_mm),
            dekor.nomi,
        )
        for branch_material, dekor, manufacturer in result.all()
    }


def _production_edge_lines(
    edge_length_by_material: dict[str, int],
    material_meta: dict[str, tuple[str, Decimal | None, str | None]],
) -> list[EdgeMaterialProductionLine]:
    lines: list[EdgeMaterialProductionLine] = []
    for material_id, length in sorted(edge_length_by_material.items()):
        meta = material_meta.get(material_id)
        label, thickness_mm, color = (
            meta if meta is not None else (f"Material {material_id[:8]}", None, None)
        )
        lines.append(
            EdgeMaterialProductionLine(
                material_id=uuid.UUID(material_id),
                material_label=label,
                thickness_mm=thickness_mm,
                color=color,
                length_mm=int(length),
            )
        )
    return lines


def _edge_length_by_thickness(lines: Sequence[EdgeMaterialProductionLine]) -> dict[str, int]:
    by_thickness: dict[str, int] = {}
    for line in lines:
        key = str(line.thickness_mm) if line.thickness_mm is not None else "unknown"
        by_thickness[key] = by_thickness.get(key, 0) + line.length_mm
    return by_thickness


async def get_workshop_order(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> OrderDetailResponse:
    order = await _workshop_order_in_scope(db, principal=principal, order_id=order_id)
    return cast(
        OrderDetailResponse,
        await _order_response(db, order, include_detail=True, include_revision=True),
    )


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
        # The cutter locks the moment cutting starts — after that the fix path is
        # revert (which clears the start stamp), not a silent swap mid-job.
        if order.status is not OrderStatus.CONFIRMED:
            raise APIError("cutting_already_started", "Cutting has already started")
        await _validate_production_worker(
            db,
            workshop_id=order.workshop_id,
            branch_id=order.branch_id,
            user_id=payload.cutter_user_id,
        )
        if order.assigned_cutter_user_id != payload.cutter_user_id:
            order.cutter_assigned_at = datetime.now(UTC)
        order.assigned_cutter_user_id = payload.cutter_user_id
    if payload.edger_user_id is not None:
        if not await _order_has_banding(db, order.id):
            raise APIError("edger_not_required", "This order has no edge banding")
        # The edger locks once banding starts; until then (queued, or still at
        # the saw) the office may still swap the assignee.
        if order.banding_started_at is not None:
            raise APIError("banding_already_started", "Banding has already started")
        await _validate_production_worker(
            db,
            workshop_id=order.workshop_id,
            branch_id=order.branch_id,
            user_id=payload.edger_user_id,
        )
        if order.assigned_edger_user_id != payload.edger_user_id:
            order.edger_assigned_at = datetime.now(UTC)
        order.assigned_edger_user_id = payload.edger_user_id

    # Assignment is pure metadata — the status moves when the assigned cutter starts.
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


async def start_cutting(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: VersionedRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_visible(db, principal=principal, order_id=order_id)
    _expect_version(order, payload.version)
    _expect_status(order, {OrderStatus.CONFIRMED})
    if order.assigned_cutter_user_id is None:
        raise APIError("cutter_required", "Assign a cutter first")
    _require_production_actor(
        principal, order, assigned_user_id=order.assigned_cutter_user_id, job="cutting"
    )
    order.cutting_started_at = datetime.now(UTC)
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
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def start_banding(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: VersionedRequest,
) -> OrderDetailResponse:
    order = await _locked_workshop_order_visible(db, principal=principal, order_id=order_id)
    _expect_version(order, payload.version)
    _expect_status(order, {OrderStatus.EDGE_BANDING})
    if order.banding_started_at is not None:
        raise APIError("banding_already_started", "Banding is already started")
    # Each stage gates on its own worker at its own start — cutting is never
    # held up by the edger slot; the edger becomes mandatory here.
    if order.assigned_edger_user_id is None:
        raise APIError("edger_required", "Choose an edge bander for this order")
    _require_production_actor(
        principal, order, assigned_user_id=order.assigned_edger_user_id, job="banding"
    )
    order.banding_started_at = datetime.now(UTC)
    _bump_order(order)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="orders.start_banding",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=f"Started banding for {order.order_number}",
        details={},
    )
    return cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))


async def list_production_queue(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    station: str,
    branch_id: uuid.UUID | None = None,
) -> ProductionQueueResponse:
    _require_workshop(principal)
    if station not in {"cutting", "banding"}:
        raise APIError("invalid_station", "Invalid station")
    if station == "cutting":
        assigned_column = Order.assigned_cutter_user_id
        credited_column = Order.cutter_user_id
        completed_column = Order.cut_completed_at
        active_statuses = [OrderStatus.CONFIRMED, OrderStatus.CUTTING]
    else:
        assigned_column = Order.assigned_edger_user_id
        credited_column = Order.edger_user_id
        completed_column = Order.edge_completed_at
        active_statuses = [OrderStatus.EDGE_BANDING]

    base_query = select(Order).where(Order.workshop_id == principal.workshop_id)
    if branch_id is not None:
        base_query = base_query.where(Order.branch_id == branch_id)
    # The station queue is personal for everyone — owner included: only jobs
    # assigned to the caller, only the caller's own completions. On-behalf
    # management lives on the office order page, not at the station terminal.
    _require_station_access(principal)
    active_query = base_query.where(
        assigned_column == principal.principal_id,
        Order.status.in_(active_statuses),
    )
    completed_since = datetime.now(UTC) - timedelta(hours=24)
    completed_query = base_query.where(
        credited_column == principal.principal_id,
        completed_column >= completed_since,
    )

    active_orders = list((await db.scalars(active_query)).all())
    completed_orders = list((await db.scalars(completed_query)).all())
    if station == "cutting":
        active_orders.sort(key=lambda o: (o.cutter_assigned_at or o.created_at, o.created_at))
        completed_orders.sort(key=lambda o: o.cut_completed_at or o.created_at, reverse=True)
    else:
        active_orders.sort(key=lambda o: (o.edger_assigned_at or o.created_at, o.created_at))
        completed_orders.sort(key=lambda o: o.edge_completed_at or o.created_at, reverse=True)

    cards = await _production_job_cards(db, [*active_orders, *completed_orders])
    return ProductionQueueResponse(
        station=station,
        jobs=cards[: len(active_orders)],
        completed_today=cards[len(active_orders) :],
    )


async def get_production_job(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
) -> ProductionJobDetail:
    order = await _workshop_order_in_scope(db, principal=principal, order_id=order_id)
    if not (
        _has_order_permission(principal, order, Permission.MANAGE_ORDERS)
        or _can_view_assigned_production_order(principal, order)
    ):
        raise APIError("order_not_found", "Order not found", status_code=404)
    cards = await _production_job_cards(db, [order])
    items = (
        await db.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
        )
    ).all()
    result = await db.get(CuttingResult, order.cutting_result_id)
    return ProductionJobDetail(
        **cards[0].model_dump(),
        items=[_production_job_item(item) for item in items],
        cutting_result=await cutting_result_response(db, result) if result is not None else None,
    )


def _require_station_access(principal: AuthenticatedPrincipal) -> None:
    """The station pages need some production standing — the owner, or any
    process_production / manage_orders grant. Assignment does the real scoping."""
    if principal.is_owner:
        return
    if any(
        grant.permission in {Permission.PROCESS_PRODUCTION, Permission.MANAGE_ORDERS}
        for grant in principal.grants
    ):
        return
    raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


async def _production_job_cards(
    db: AsyncSession, orders: Sequence[Order]
) -> list[ProductionJobCard]:
    if not orders:
        return []
    branch_ids = {order.branch_id for order in orders}
    result_ids = {order.cutting_result_id for order in orders}
    order_ids = [order.id for order in orders]
    worker_ids = {
        user_id
        for order in orders
        for user_id in (order.assigned_cutter_user_id, order.assigned_edger_user_id)
        if user_id is not None
    }
    branches = {
        row.id: row
        for row in (await db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))).all()
    }
    results = {
        row.id: row
        for row in (
            await db.scalars(select(CuttingResult).where(CuttingResult.id.in_(result_ids)))
        ).all()
    }
    workers: dict[uuid.UUID, ProductionWorkerRef] = {}
    if worker_ids:
        workers = {
            row.id: ProductionWorkerRef(id=row.id, full_name=row.full_name)
            for row in (
                await db.scalars(select(WorkshopUser).where(WorkshopUser.id.in_(worker_ids)))
            ).all()
        }
    items_by_order: dict[uuid.UUID, list[OrderItem]] = defaultdict(list)
    item_rows = (
        await db.scalars(
            select(OrderItem).where(OrderItem.order_id.in_(order_ids)).order_by(OrderItem.id)
        )
    ).all()
    for item in item_rows:
        items_by_order[item.order_id].append(item)

    cards: list[ProductionJobCard] = []
    for order in orders:
        branch = branches.get(order.branch_id)
        items = items_by_order.get(order.id, [])
        result = results.get(order.cutting_result_id)
        cards.append(
            ProductionJobCard(
                id=order.id,
                order_number=order.order_number,
                status=order.status,
                version=order.version,
                client_first_name=_first_name(order.contact_name),
                branch_id=order.branch_id,
                branch_name=branch.name if branch is not None else "",
                item_count=sum(item.quantity for item in items),
                has_banding=_items_have_banding(items),
                planned_panels=_planned_panels(result),
                planned_edge_lines=_planned_edge_lines(result),
                material_labels=_panel_material_labels(items),
                assigned_cutter=workers.get(order.assigned_cutter_user_id)
                if order.assigned_cutter_user_id
                else None,
                assigned_edger=workers.get(order.assigned_edger_user_id)
                if order.assigned_edger_user_id
                else None,
                cutter_assigned_at=order.cutter_assigned_at,
                edger_assigned_at=order.edger_assigned_at,
                cutting_started_at=order.cutting_started_at,
                banding_started_at=order.banding_started_at,
                cut_completed_at=order.cut_completed_at,
                edge_completed_at=order.edge_completed_at,
                created_at=order.created_at,
            )
        )
    return cards


def _first_name(value: str) -> str:
    stripped = value.strip()
    return stripped.split()[0] if stripped else stripped


def _panel_material_labels(items: Sequence[OrderItem]) -> list[str]:
    labels = [material_label(item.material_snapshot, item.branch_material_id) for item in items]
    return list(dict.fromkeys(labels))


def _production_job_item(item: OrderItem) -> ProductionJobItem:
    return ProductionJobItem(
        id=item.id,
        part_ref=item.part_ref,
        length_mm=item.length_mm,
        width_mm=item.width_mm,
        quantity=item.quantity,
        material_label=material_label(item.material_snapshot, item.branch_material_id),
        edge_top=_production_edge_side(item.edge_top),
        edge_bottom=_production_edge_side(item.edge_bottom),
        edge_left=_production_edge_side(item.edge_left),
        edge_right=_production_edge_side(item.edge_right),
    )


def _production_edge_side(edge: dict[str, Any] | None) -> ProductionEdgeSide | None:
    if edge is None:
        return None
    snapshot = edge.get("snapshot") or {}
    return ProductionEdgeSide(
        material_label=edge_label(snapshot, edge["material_id"]),
        thickness_mm=_snapshot_decimal(_snapshot_first(snapshot, "qalinlik_mm", "thickness_mm")),
        color=_snapshot_text(_snapshot_first(snapshot, "nomi", "color")),
        source=MaterialSource(str(edge["source"])),
    )


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
    shortfall = False
    for branch_material_id, quantity in panel_demands.items():
        transaction = await consume_order_stock(
            db,
            branch_id=order.branch_id,
            branch_material_id=branch_material_id,
            order_id=order.id,
            quantity=quantity,
        )
        shortfall = shortfall or transaction.balance_after < 0
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
    response = cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))
    response.stock_shortfall = shortfall
    return response


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
    shortfall = False
    for branch_material_id, quantity in edge_demands.items():
        transaction = await consume_order_stock(
            db,
            branch_id=order.branch_id,
            branch_material_id=branch_material_id,
            order_id=order.id,
            quantity=quantity,
        )
        shortfall = shortfall or transaction.balance_after < 0
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
    response = cast(OrderDetailResponse, await _order_response(db, order, include_detail=True))
    response.stock_shortfall = shortfall
    return response


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
        # Assignment persists — the order returns to the cutter's queue, unstarted.
        order.cutting_started_at = None
        to_status = OrderStatus.CONFIRMED
    elif order.status is OrderStatus.EDGE_BANDING:
        restored = await _restore_cutting_step(db, order)
        metadata["restored_panels"] = {str(key): value for key, value in restored.items()}
        order.banding_started_at = None
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
    if payload.kind == "percent" and payload.value > 100:
        raise APIError("invalid_discount", "Percent must be between 0 and 100")
    discount = payload.value if payload.kind == "fixed" else subtotal * payload.value // 100
    if discount > subtotal:
        raise APIError("invalid_discount", "Discount cannot exceed subtotal")
    order.discount_tiyin = discount
    if discount == 0:
        order.discount_reason = None
        order.discount_applied_by_user_id = None
    else:
        order.discount_reason = reason
        order.discount_applied_by_user_id = principal.principal_id
    order.total_tiyin = subtotal - discount + order.surcharge_tiyin
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


async def apply_surcharge(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    order_id: uuid.UUID,
    payload: WorkshopOrderSurchargeRequest,
) -> OrderDetailResponse:
    """Set the order's surcharge (ustama) — symmetric to apply_discount but
    additive and uncapped (orders.md: "Pricing"). Allowed on new/confirmed
    orders by manage_orders; percent resolves against the computed subtotal."""
    order = await _locked_workshop_order_for_action(
        db,
        principal=principal,
        order_id=order_id,
        permission=Permission.MANAGE_ORDERS,
    )
    _expect_version(order, payload.version)
    if order.status not in {OrderStatus.NEW, OrderStatus.CONFIRMED}:
        raise APIError("surcharge_not_allowed", "Surcharge is not allowed at this status")
    reason = _required_reason(payload.reason)
    subtotal = _pre_discount_total(order)
    if payload.value < 0:
        raise APIError("invalid_surcharge", "Surcharge must be non-negative")
    if payload.kind == "percent" and payload.value > 100:
        raise APIError("invalid_surcharge", "Percent must be between 0 and 100")
    surcharge = payload.value if payload.kind == "fixed" else subtotal * payload.value // 100
    order.surcharge_tiyin = surcharge
    if surcharge == 0:
        order.surcharge_reason = None
        order.surcharge_applied_by_user_id = None
    else:
        order.surcharge_reason = reason
        order.surcharge_applied_by_user_id = principal.principal_id
    order.total_tiyin = subtotal - order.discount_tiyin + surcharge
    _bump_order(order)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="orders.surcharge",
        entity_type="order",
        entity_id=order.id,
        workshop_id=order.workshop_id,
        branch_id=order.branch_id,
        summary=f"Applied surcharge to {order.order_number}",
        details={"surcharge_tiyin": surcharge, "reason": reason},
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
    for branch_material_id, quantity in demands.items():
        await restore_order_stock(
            db,
            branch_id=order.branch_id,
            branch_material_id=branch_material_id,
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
    for branch_material_id, quantity in demands.items():
        await restore_order_stock(
            db,
            branch_id=order.branch_id,
            branch_material_id=branch_material_id,
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


async def _order_summary_responses(
    db: AsyncSession,
    orders: Sequence[Order],
) -> list[OrderSummaryResponse]:
    if not orders:
        return []

    client_ids = {order.client_id for order in orders}
    branch_ids = {order.branch_id for order in orders}
    workshop_ids = {order.workshop_id for order in orders}
    result_ids = {order.cutting_result_id for order in orders}
    order_ids = [order.id for order in orders]

    clients = {
        row.id: row
        for row in (await db.scalars(select(Client).where(Client.id.in_(client_ids)))).all()
    }
    branches = {
        row.id: row
        for row in (await db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))).all()
    }
    workshops = {
        row.id: row
        for row in (await db.scalars(select(Workshop).where(Workshop.id.in_(workshop_ids)))).all()
    }
    results = {
        row.id: row
        for row in (
            await db.scalars(select(CuttingResult).where(CuttingResult.id.in_(result_ids)))
        ).all()
    }
    items_by_order: dict[uuid.UUID, list[OrderItem]] = defaultdict(list)
    item_rows = (
        await db.scalars(
            select(OrderItem).where(OrderItem.order_id.in_(order_ids)).order_by(OrderItem.id)
        )
    ).all()
    for item in item_rows:
        items_by_order[item.order_id].append(item)

    demands_by_order: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    demanded_branch_material_ids: set[uuid.UUID] = set()
    for order in orders:
        demands = _stock_demands_for_order_summary(order, results.get(order.cutting_result_id))
        if not demands:
            continue
        demands_by_order[order.id] = demands
        demanded_branch_material_ids.update(demands)

    stock_by_branch_material: dict[uuid.UUID, StockItem] = {}
    materials: dict[uuid.UUID, tuple[BranchMaterial, Dekor, Manufacturer]] = {}
    if demanded_branch_material_ids:
        material_rows = (
            await db.execute(
                select(BranchMaterial, Dekor, Manufacturer)
                .join(Dekor, Dekor.id == BranchMaterial.dekor_id)
                .join(Manufacturer, Manufacturer.id == Dekor.manufacturer_id)
                .where(BranchMaterial.id.in_(demanded_branch_material_ids))
            )
        ).all()
        materials = {row[0].id: (row[0], row[1], row[2]) for row in material_rows}
        # A branch material is already branch-scoped, so `unique(branch_material_id)`
        # replaced the old (branch_id, material_id) pair — one key, no tuple.
        stock_rows = (
            await db.scalars(
                select(StockItem).where(
                    StockItem.branch_material_id.in_(demanded_branch_material_ids),
                )
            )
        ).all()
        stock_by_branch_material = {item.branch_material_id: item for item in stock_rows}

    responses: list[OrderSummaryResponse] = []
    for order in orders:
        client = clients.get(order.client_id)
        branch = branches.get(order.branch_id)
        workshop = workshops.get(order.workshop_id)
        if client is None or branch is None or workshop is None:
            raise APIError("order_scope_missing", "Order scope is incomplete", status_code=500)
        items = items_by_order.get(order.id, [])
        result = results.get(order.cutting_result_id)
        responses.append(
            OrderSummaryResponse(
                **_order_summary_base(
                    order=order,
                    client=client,
                    branch=branch,
                    workshop=workshop,
                    items=items,
                    result=result,
                    stock_warnings=_stock_warnings_from_demands(
                        demands=demands_by_order.get(order.id, {}),
                        stock_by_branch_material=stock_by_branch_material,
                        materials=materials,
                    ),
                )
            )
        )
    return responses


def _order_summary_base(
    *,
    order: Order,
    client: Client,
    branch: Branch,
    workshop: Workshop,
    items: Sequence[OrderItem],
    result: CuttingResult | None,
    stock_warnings: list[OrderStockWarning],
) -> dict[str, Any]:
    return {
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
        "branch_additional_phones": list(branch.additional_phones or []),
        "branch_latitude": branch.latitude,
        "branch_longitude": branch.longitude,
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
        "surcharge_tiyin": order.surcharge_tiyin,
        "surcharge_reason": order.surcharge_reason,
        "surcharge_applied_by_user_id": order.surcharge_applied_by_user_id,
        "total_tiyin": order.total_tiyin,
        "currency": order.currency,
        "assigned_cutter_user_id": order.assigned_cutter_user_id,
        "assigned_edger_user_id": order.assigned_edger_user_id,
        "cutter_assigned_at": order.cutter_assigned_at,
        "edger_assigned_at": order.edger_assigned_at,
        "cutting_started_at": order.cutting_started_at,
        "banding_started_at": order.banding_started_at,
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
        "planned_panels": _planned_panels(result),
        "draft_name": order.draft_name,
        "created_via_workshop": order.created_via_workshop,
        "planned_edge_lines": _planned_edge_lines(result),
        "stock_warnings": stock_warnings,
    }


async def _order_response(
    db: AsyncSession,
    order: Order,
    *,
    include_detail: bool,
    settlement_visible: bool = True,
    include_revision: bool = False,
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
    result = await db.get(CuttingResult, order.cutting_result_id)
    base = _order_summary_base(
        order=order,
        client=client,
        branch=branch,
        workshop=workshop,
        items=items,
        result=result,
        stock_warnings=warnings,
    )
    if not include_detail:
        return OrderSummaryResponse(**base)
    events = (
        await db.scalars(
            select(OrderStatusEvent)
            .where(OrderStatusEvent.order_id == order.id)
            .order_by(OrderStatusEvent.changed_at.asc(), OrderStatusEvent.id.asc())
        )
    ).all()
    return OrderDetailResponse(
        **base,
        items=[OrderItemResponse.model_validate(item) for item in items],
        price_lines=_order_price_lines(items, result),
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
        revision_draft_id=(
            await db.scalar(
                select(CuttingDraft.id).where(CuttingDraft.revision_of_order_id == order.id)
            )
            if include_revision
            else None
        ),
    )


def _client_settlement_visible(status_value: OrderStatus) -> bool:
    return status_value in {OrderStatus.READY, OrderStatus.COMPLETED}


def _planned_panels(result: CuttingResult | None) -> int:
    if result is None:
        return 0
    return sum(int(value) for value in result.panels_used_by_material.values())


def _planned_edge_lines(result: CuttingResult | None) -> list[OrderEdgeMaterialDemand]:
    if result is None:
        return []
    lines: list[OrderEdgeMaterialDemand] = []
    for material_id, consumed_mm in sorted(result.edge_consumed_shop_by_material.items()):
        snapshot = result.material_snapshots.get(material_id, {})
        lines.append(
            OrderEdgeMaterialDemand(
                material_id=uuid.UUID(material_id),
                material_label=edge_label(snapshot, material_id),
                thickness_mm=_snapshot_decimal(
                    _snapshot_first(snapshot, "qalinlik_mm", "thickness_mm")
                ),
                color=_snapshot_text(_snapshot_first(snapshot, "nomi", "color")),
                consumed_mm=int(consumed_mm),
            )
        )
    return lines


def _order_price_lines(
    items: Sequence[OrderItem],
    result: CuttingResult | None,
) -> list[OrderPriceLine]:
    """Itemized material lines for the order money breakdown. Prices come from
    the snapshots frozen on the order items at placement — not live branch
    pricing — so panel lines sum exactly to subtotal_materials and edge lines
    to the material share of subtotal_edge_banding."""
    if result is None:
        return []
    panel_prices: dict[uuid.UUID, int] = {}
    edge_prices: dict[uuid.UUID, int] = {}
    for item in items:
        if item.material_source is MaterialSource.SHOP:
            panel_prices.setdefault(
                item.branch_material_id, int(item.material_snapshot.get("price_tiyin") or 0)
            )
        for edge in (item.edge_top, item.edge_bottom, item.edge_left, item.edge_right):
            if edge is None or MaterialSource(str(edge["source"])) is not MaterialSource.SHOP:
                continue
            snapshot = edge.get("snapshot") or {}
            edge_prices.setdefault(
                uuid.UUID(str(edge["material_id"])), int(snapshot.get("price_tiyin") or 0)
            )

    def _panel_line_label(material_id: uuid.UUID) -> str:
        return material_label(result.material_snapshots.get(str(material_id), {}), material_id)

    def _edge_line_label(material_id: uuid.UUID) -> str:
        return edge_label(result.material_snapshots.get(str(material_id), {}), material_id)

    panel_lines = [
        OrderPriceLine(
            material_id=material_id,
            material_name=_panel_line_label(material_id),
            kind="panel",
            panels_used=quantity,
            line_total_tiyin=panel_prices.get(material_id, 0) * quantity,
        )
        for material_id, quantity in _panel_stock_demands(result).items()
    ]
    edge_lines = [
        OrderPriceLine(
            material_id=material_id,
            material_name=_edge_line_label(material_id),
            kind="edge",
            consumed_mm=consumed_mm,
            line_total_tiyin=_millimetre_price(consumed_mm, edge_prices.get(material_id, 0)),
        )
        for material_id, consumed_mm in _edge_stock_demands(result).items()
    ]
    panel_lines.sort(key=lambda line: line.material_name)
    edge_lines.sort(key=lambda line: line.material_name)
    return panel_lines + edge_lines


def _snapshot_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return _normalized_decimal(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


def _normalized_decimal(value: Decimal) -> Decimal:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return normalized.quantize(Decimal(1))
    return normalized


def _snapshot_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _snapshot_first(snapshot: dict[str, Any], *keys: str) -> object:
    """First present key, new snapshot vocabulary before the legacy one.

    `order_items.material_snapshot` and `cutting_results.material_snapshots` are
    frozen history and were NOT rewritten by the reshape, so both vocabularies
    live in the database side by side — see app/core/material_label.py.
    """
    for key in keys:
        value = snapshot.get(key)
        if value is not None:
            return value
    return None


def _recorded_income_total(order_id: Any) -> Select[tuple[int]]:
    """Σ of an order's `recorded` income — the single definition of "paid".

    Takes a value or a column so the same statement serves a one-order lookup
    and a correlated subquery inside a list query; a voided row leaves the sum
    by itself, which is why no balance is ever stored.
    """
    return select(func.coalesce(func.sum(Income.amount_tiyin), 0)).where(
        Income.order_id == order_id,
        Income.status == LedgerStatus.RECORDED,
    )


def _settlement_balance(total_tiyin: int, recorded_tiyin: int) -> int:
    """What is still owed. Clamped at zero — an overpayment is not a debt."""

    return max(total_tiyin - recorded_tiyin, 0)


async def _order_settlement(db: AsyncSession, order: Order) -> OrderSettlementResponse:
    recorded = int(await db.scalar(_recorded_income_total(order.id)) or 0)
    return OrderSettlementResponse(
        total_tiyin=order.total_tiyin,
        recorded_tiyin=recorded,
        balance_tiyin=_settlement_balance(order.total_tiyin, recorded),
    )


async def _stock_warnings(db: AsyncSession, order: Order) -> list[OrderStockWarning]:
    result = await db.get(CuttingResult, order.cutting_result_id)
    demands = _stock_demands_for_order_summary(order, result)
    if not demands:
        return []
    rows = (
        await db.execute(
            select(StockItem, BranchMaterial, Dekor, Manufacturer)
            .join(BranchMaterial, BranchMaterial.id == StockItem.branch_material_id)
            .join(Dekor, Dekor.id == BranchMaterial.dekor_id)
            .join(Manufacturer, Manufacturer.id == Dekor.manufacturer_id)
            .where(
                StockItem.branch_id == order.branch_id,
                StockItem.branch_material_id.in_(demands.keys()),
            )
        )
    ).all()
    stock_by_branch_material = {item.branch_material_id: item for item, _, _, _ in rows}
    materials = {
        branch_material.id: (branch_material, dekor, manufacturer)
        for _, branch_material, dekor, manufacturer in rows
    }
    return _stock_warnings_from_demands(
        demands=demands,
        stock_by_branch_material=stock_by_branch_material,
        materials=materials,
    )


def _stock_demands_for_order_summary(
    order: Order,
    result: CuttingResult | None,
) -> dict[uuid.UUID, int]:
    if result is None:
        return {}
    if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED, OrderStatus.READY}:
        return {}
    demands: dict[uuid.UUID, int] = {}
    if order.cut_completed_at is None:
        demands.update(_panel_stock_demands(result))
    if order.edge_completed_at is None:
        for material_id, quantity in _edge_stock_demands(result).items():
            demands[material_id] = demands.get(material_id, 0) + quantity
    return demands


def _stock_warnings_from_demands(
    *,
    demands: dict[uuid.UUID, int],
    stock_by_branch_material: dict[uuid.UUID, StockItem],
    materials: dict[uuid.UUID, tuple[BranchMaterial, Dekor, Manufacturer]],
) -> list[OrderStockWarning]:
    warnings: list[OrderStockWarning] = []
    for branch_material_id, required in demands.items():
        item = stock_by_branch_material.get(branch_material_id)
        material = materials.get(branch_material_id)
        on_hand = item.on_hand if item is not None else 0
        # The threshold is the branch material's, not the balance row's — a
        # material the branch stopped carrying has no threshold to warn against.
        min_stock = material[0].min_stock if material is not None else 0
        projected = on_hand - required
        if projected >= 0 and projected > min_stock:
            continue
        warnings.append(
            OrderStockWarning(
                material_id=branch_material_id,
                material_name=(
                    _branch_material_label(*material)
                    if material is not None
                    else str(branch_material_id)
                ),
                # `kind` keeps its two-value wire domain (`panel` / `edge`) even
                # though `tur` now has seven values: the client SPA switches on
                # it, and leaking raw dekor types here would silently widen a
                # field nothing type-checks.
                kind=_stock_warning_kind(material),
                on_hand=on_hand,
                required=required,
                projected_after=projected,
            )
        )
    return warnings


def _stock_warning_kind(material: tuple[BranchMaterial, Dekor, Manufacturer] | None) -> str:
    if material is None:
        return "unknown"
    return "edge" if is_tape(material[1].tur) else "panel"


def _branch_material_label(
    branch_material: BranchMaterial,
    dekor: Dekor,
    manufacturer: Manufacturer,
) -> str:
    """Live label for a carried format — there is no stored name to read.

    Used where the row is loaded fresh (stock warnings, price quotes); anything
    describing a *placed* order reads its frozen snapshot instead.
    """
    snapshot: dict[str, Any] = {
        "manufacturer_name": manufacturer.name,
        "tur": dekor.tur.value,
        "kod": dekor.kod,
        "nomi": dekor.nomi,
        "qalinlik_mm": str(branch_material.qalinlik_mm),
        "uzunlik_mm": branch_material.uzunlik_mm,
        "eni_mm": branch_material.eni_mm,
        "kromka_eni_mm": branch_material.kromka_eni_mm,
        "tolali": dekor.tolali,
    }
    if is_tape(dekor.tur):
        return edge_label(snapshot, branch_material.id)
    return material_label(snapshot, branch_material.id)


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
        branch_material_ids=set(panel_demands) | set(edge_demands),
    )
    # The part now names a branch material directly, so "does the branch carry
    # it" is an id-in-this-branch + still-active test rather than a catalog
    # lookup. The error codes are unchanged: they are what the SPAs match on.
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
    # Labour is charged on every banded millimetre, the client's own tape
    # included: gluing someone else's tape is still the workshop's work. Only
    # the tape *material* is free, which is what `edge_demands` already scopes.
    # Sum per-material labor (not _millimetre_price of the global sum): integer
    # floor-division isn't distributive, so per-material must be summed for the
    # itemized edge_lines (CB-117) to reconcile exactly with this subtotal.
    edge_labour_mm = _edge_banded_millimetres(result)
    edge_labor_total = sum(
        _millimetre_price(mm, int(pricing.edge_banding_rate_tiyin or 0))
        for mm in edge_labour_mm.values()
    )
    priced_parts = _priced_parts(result, branch_materials)
    subtotal_edge = edge_material_total + edge_labor_total
    total = subtotal_cutting + subtotal_materials + subtotal_edge
    edge_rate = int(pricing.edge_banding_rate_tiyin or 0)

    # There is no stored material name left to concatenate, so quote lines use
    # the same canonical formatter as every other surface — panels and tapes
    # each with their own shape.
    def _panel_line_name(material_id: uuid.UUID) -> str:
        return material_label(result.material_snapshots.get(str(material_id), {}), material_id)

    def _edge_line_name(material_id: uuid.UUID) -> str:
        return edge_label(result.material_snapshots.get(str(material_id), {}), material_id)

    own_panels = _own_panels_used(result)
    material_lines = [
        MaterialPriceLine(
            material_id=material_id,
            material_name=_panel_line_name(material_id),
            # `panels_used` is what the layout needs; `own_panels` is how many of
            # those the client brings. The charged count is the difference, which
            # is exactly `quantity` — the demand this line was built from.
            panels_used=quantity + own_panels.get(material_id, 0),
            own_panels=own_panels.get(material_id, 0),
            unit_price_tiyin=branch_materials[material_id].price_tiyin,
            line_total_tiyin=branch_materials[material_id].price_tiyin * quantity,
        )
        for material_id, quantity in panel_demands.items()
    ]
    edge_lines = []
    for material_id, mm in edge_labour_mm.items():
        shop_mm = edge_demands.get(material_id, 0)
        material_cost = (
            _millimetre_price(shop_mm, branch_materials[material_id].price_tiyin)
            if shop_mm > 0
            else 0
        )
        service_cost = _millimetre_price(mm, edge_rate)
        edge_lines.append(
            EdgePriceLine(
                material_id=material_id,
                material_name=_edge_line_name(material_id),
                consumed_mm=mm,
                own=shop_mm == 0,
                metre_price_tiyin=branch_materials[material_id].price_tiyin,
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
        edge_banding_rate_tiyin=edge_rate,
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


def _own_panels_used(result: CuttingResult) -> dict[uuid.UUID, int]:
    """Sheets this layout actually draws from the client's own stack.

    The stored number is a claim, so it is clamped to what the layout uses: a
    client who owns seven sheets and needs five brings five, and the other two
    stay a claim for the edit that needs them.
    """
    own: dict[uuid.UUID, int] = {}
    for material_id_text, claimed in (result.own_panel_counts or {}).items():
        used = int(result.panels_used_by_material.get(material_id_text, 0))
        capped = min(int(claimed), used)
        if capped > 0:
            own[uuid.UUID(material_id_text)] = capped
    return own


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
    # Client-supplied sheets come off the top of the demand: the workshop buys
    # only what the client did not bring. The key survives at zero so the branch
    # still has to carry the material — the client picked it from that catalog,
    # and the cutting plan names it either way.
    for material_id, own in _own_panels_used(result).items():
        if material_id in demands:
            demands[material_id] = max(0, demands[material_id] - own)
    return demands


def _edge_banded_millimetres(result: CuttingResult) -> dict[uuid.UUID, int]:
    """Every banded millimetre per tape, whoever supplied the roll.

    Material cost follows `_edge_stock_demands` (shop only); labour follows this,
    because the gluing is the workshop's work either way.
    """
    totals: dict[uuid.UUID, int] = {}
    for source in (result.edge_consumed_shop_by_material, result.edge_consumed_own_by_material):
        for material_id, quantity in (source or {}).items():
            if int(quantity) <= 0:
                continue
            key = uuid.UUID(material_id)
            totals[key] = totals.get(key, 0) + int(quantity)
    return totals


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
    branch_material_ids: set[uuid.UUID],
) -> dict[uuid.UUID, BranchMaterial]:
    if not branch_material_ids:
        return {}
    rows = (
        await db.scalars(
            select(BranchMaterial)
            .join(Dekor, Dekor.id == BranchMaterial.dekor_id)
            .where(
                # branch_id is redundant with the id set for a well-formed
                # order, and load-bearing for a malformed one: it is what stops
                # another branch's format id from being priced here.
                BranchMaterial.branch_id == branch_id,
                BranchMaterial.id.in_(branch_material_ids),
                BranchMaterial.status == MaterialStatus.ACTIVE,
                Dekor.holat == MaterialStatus.ACTIVE,
            )
        )
    ).all()
    return {row.id: row for row in rows}


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


async def _delete_cutting_result(db: AsyncSession, result: CuttingResult) -> None:
    """Delete one loaded cutting result with its panels/placements — the
    superseded confirmed result after a revision apply."""
    panel_ids = (
        await db.scalars(select(CuttingPanel.id).where(CuttingPanel.cutting_result_id == result.id))
    ).all()
    if panel_ids:
        await db.execute(
            delete(CuttingPlacement).where(CuttingPlacement.cutting_panel_id.in_(panel_ids))
        )
        await db.execute(delete(CuttingPanel).where(CuttingPanel.id.in_(panel_ids)))
    await db.delete(result)


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
    view_branch_ids = {
        grant.branch_id
        for grant in principal.grants
        if grant.permission in WORKSHOP_ORDER_VIEW_PERMISSIONS
    }
    production_branch_ids = _production_branch_ids(principal)
    if branch_id is not None:
        view_branch_ids = {branch_id} if branch_id in view_branch_ids else set()
        production_branch_ids = {branch_id} if branch_id in production_branch_ids else set()
    conditions: list[ColumnElement[bool]] = []
    if view_branch_ids:
        conditions.append(Order.branch_id.in_(view_branch_ids))
    if production_branch_ids:
        conditions.append(
            and_(
                Order.branch_id.in_(production_branch_ids),
                or_(
                    Order.assigned_cutter_user_id == principal.principal_id,
                    Order.assigned_edger_user_id == principal.principal_id,
                ),
            )
        )
    if not conditions:
        return query.where(Order.branch_id.in_([]))
    return query.where(or_(*conditions))


def _apply_order_filters(
    query: Any,
    *,
    status_filter: str | None,
    search: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
    contact_phone: str | None = None,
) -> Any:
    if date_from and date_to and date_from > date_to:
        raise APIError("invalid_date_range", "date_from must be before date_to")
    if date_from:
        query = query.where(Order.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC))
    if date_to:
        end_exclusive = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
        query = query.where(Order.created_at < end_exclusive)
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
        # `draft_name` is what the client calls the order ("Oshxona shkafi") — it
        # is the card's headline, so the search box has to reach it. NULL names
        # simply never match, which is what an OR of ilike already gives.
        query = query.where(
            or_(
                Order.order_number.ilike(pattern),
                Order.contact_name.ilike(pattern),
                Order.draft_name.ilike(pattern),
            )
        )
    phone_condition = _phone_digits_condition(contact_phone)
    if phone_condition is not None:
        query = query.where(phone_condition)
    return query


def _phone_digits_condition(value: str | None) -> ColumnElement[bool] | None:
    """Digits-contains match against the stored normalized +998XXXXXXXXX.

    The operator types whatever the client dictates ("90 111 22 33",
    "+998901112233", the last four digits); non-digits in the input are
    formatting, never signal. An input with no digits matches nothing here and
    the caller drops the clause, so it filters nothing rather than everything.
    """
    digits = re.sub(r"\D", "", value) if value else ""
    if not digits:
        return None
    return Order.contact_phone.like(f"%{digits}%")


def _order_search_condition(search: str | None) -> ColumnElement[bool] | None:
    """One search box over order number, contact name, and contact phone.

    The finance order picker gets a single field rather than the list page's
    separate search + phone filters: at the counter the operator has one thing
    the client just said, and doesn't know which field it lands in.
    """
    normalized = search.strip() if search else ""
    if not normalized:
        return None
    pattern = f"%{normalized.lower()}%"
    conditions: list[ColumnElement[bool]] = [
        Order.order_number.ilike(pattern),
        Order.contact_name.ilike(pattern),
        # Same reason as the list filter: at the counter the client is as likely
        # to name the drawing as the order number.
        Order.draft_name.ilike(pattern),
    ]
    phone_condition = _phone_digits_condition(normalized)
    if phone_condition is not None:
        conditions.append(phone_condition)
    return or_(*conditions)


def _can_view_workshop_order(principal: AuthenticatedPrincipal, order: Order) -> bool:
    if any(
        _has_order_permission(principal, order, permission)
        for permission in WORKSHOP_ORDER_VIEW_PERMISSIONS
    ):
        return True
    return _can_view_assigned_production_order(principal, order)


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


def _production_branch_ids(principal: AuthenticatedPrincipal) -> set[uuid.UUID]:
    return {
        grant.branch_id
        for grant in principal.grants
        if grant.permission is Permission.PROCESS_PRODUCTION
    }


def _can_view_assigned_production_order(
    principal: AuthenticatedPrincipal,
    order: Order,
) -> bool:
    if principal.principal_id not in {
        order.assigned_cutter_user_id,
        order.assigned_edger_user_id,
    }:
        return False
    return _has_order_permission(principal, order, Permission.PROCESS_PRODUCTION)


def _require_production_actor(
    principal: AuthenticatedPrincipal,
    order: Order,
    *,
    assigned_user_id: uuid.UUID | None,
    job: str,
) -> None:
    if _has_order_permission(principal, order, Permission.MANAGE_ORDERS):
        return
    if not _has_order_permission(principal, order, Permission.PROCESS_PRODUCTION):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    if assigned_user_id != principal.principal_id:
        raise APIError(
            "not_assigned",
            f"This {job} job is assigned to another worker",
            status_code=status.HTTP_403_FORBIDDEN,
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


def _expect_editable_status(order: Order) -> None:
    if order.status not in {OrderStatus.NEW, OrderStatus.CONFIRMED}:
        raise APIError(
            "order_edit_not_allowed", "Order can be edited only before production starts"
        )


def _parts_have_banding(parts: list[dict[str, Any]]) -> bool:
    return any(part.get(field) is not None for part in parts for field in _edge_fields())


def _bump_order(order: Order) -> None:
    order.version += 1
    order.updated_at = datetime.now(UTC)


async def _next_order_number(db: AsyncSession, now: datetime, branch_no: int) -> str:
    """`#26-14-0003` — 2-digit year, branch number, per-branch/per-year sequence.

    The sequence is scoped to one branch so a workshop's numbers have no holes:
    branch 14's third order of 2026 is `#26-14-0003` no matter how busy the rest
    of the platform is. The trailing dash in the prefix is load-bearing — without
    it `#26-1-` would also match branch 14's numbers.

    Counting rows is only safe because orders are never deleted (architecture.md);
    the advisory lock is what makes concurrent creation in the same branch safe.
    Orders placed before this format keep their legacy `ORD-2026-000123` numbers
    and are excluded by the prefix (sales.md).
    """
    prefix = f"#{now.year % 100:02d}-{branch_no}-"
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"orders:{prefix}"))))
    count = await db.scalar(
        select(func.count(Order.id)).where(Order.order_number.like(f"{prefix}%"))
    )
    return f"{prefix}{int(count or 0) + 1:04d}"


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
