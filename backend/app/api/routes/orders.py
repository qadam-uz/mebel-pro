"""Order routes — client placement/reads and the workshop state machine.

Client app (`/c/orders`): place, list, detail, cancel-while-new.
Workshop app (`/workshop/orders`): board/table, detail, and the action
endpoints (approve, assign, cutting-done, banding-done, mark-collected, revert,
cancel, apply-discount). Cutter/edger workspaces at `/workshop/cutting` and
`/workshop/banding`. Routes stay thin — the state machine lives in
``app.services.orders``.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentClient, CurrentWorkshopUser, Session
from app.core.principal import Principal
from app.models.enums import OrderStatus, Permission
from app.models.sales import Order, OrderItem
from app.schemas.orders import (
    AssignIn,
    ClientOrderDetail,
    DiscountIn,
    OnBehalfIn,
    OrderCardOut,
    OrderItemOut,
    OrderListOut,
    PlaceOrderIn,
    PriceBreakdown,
    ProductionStamps,
    ReasonIn,
    SettlementOut,
    TimelineEvent,
    TransitionOut,
    VersionedIn,
    WorkshopBoardOut,
    WorkshopOrderDetail,
)
from app.services import finance
from app.services import orders as service

client_router = APIRouter()
workshop_router = APIRouter()
cutter_router = APIRouter()
edger_router = APIRouter()

_SETTLEMENT_VISIBLE_CLIENT = (OrderStatus.READY, OrderStatus.COMPLETED)


# --- shared builders --------------------------------------------------------


def _price(order: Order) -> PriceBreakdown:
    return PriceBreakdown(
        subtotal_cutting_tiyin=order.subtotal_cutting_tiyin,
        subtotal_materials_tiyin=order.subtotal_materials_tiyin,
        subtotal_edge_banding_tiyin=order.subtotal_edge_banding_tiyin,
        discount_tiyin=order.discount_tiyin,
        total_tiyin=order.total_tiyin,
        currency=order.currency.value,
    )


def _items_out(items: list[OrderItem]) -> list[OrderItemOut]:
    return [OrderItemOut.model_validate(i) for i in items]


async def _timeline(db: AsyncSession, order_id: uuid.UUID) -> list[TimelineEvent]:
    events = await service.order_status_events(db, order_id)
    return [
        TimelineEvent(
            from_status=e.from_status,
            to_status=e.to_status,
            actor_type=e.actor_type.value,
            reason=e.reason,
            metadata=e.event_metadata,
            changed_at=e.changed_at,
        )
        for e in events
    ]


def _card(order: Order, item_count: int) -> OrderCardOut:
    return OrderCardOut(
        id=order.id,
        order_number=order.order_number,
        branch_id=order.branch_id,
        status=order.status,
        total_tiyin=order.total_tiyin,
        item_count=item_count,
        created_at=order.created_at,
        contact_name=order.contact_name,
        contact_phone=order.contact_phone,
        assigned_cutter_user_id=order.assigned_cutter_user_id,
        assigned_edger_user_id=order.assigned_edger_user_id,
    )


async def _cards(db: AsyncSession, orders: list[Order]) -> list[OrderCardOut]:
    out: list[OrderCardOut] = []
    for o in orders:
        items = await service.order_items_for_read(db, o.id)
        out.append(_card(o, len(items)))
    return out


def _available_actions(order: Order) -> list[str]:
    match order.status:
        case OrderStatus.NEW:
            return ["approve", "cancel", "apply_discount"]
        case OrderStatus.CONFIRMED:
            return ["assign", "apply_discount", "cancel"]
        case OrderStatus.CUTTING:
            return ["cutting_done", "revert", "cancel"]
        case OrderStatus.EDGE_BANDING:
            return ["banding_done", "revert", "cancel"]
        case OrderStatus.READY:
            return ["mark_collected", "revert", "cancel"]
        case _:
            return []


def _can_view_finance(principal: Principal, order: Order) -> bool:
    return principal.has_permission(
        Permission.VIEW_FINANCE_REPORTS, order.branch_id
    ) or principal.has_permission(Permission.MANAGE_FINANCE, order.branch_id)


async def _settlement(db: AsyncSession, order: Order) -> SettlementOut:
    paid = await finance.order_paid_total(db, order.id)
    return SettlementOut(
        total_tiyin=order.total_tiyin,
        recorded_tiyin=paid,
        balance_tiyin=order.total_tiyin - paid,
    )


# --- client: placement + reads ----------------------------------------------


@client_router.post("", response_model=ClientOrderDetail, status_code=201)
async def place_order(
    body: PlaceOrderIn, principal: CurrentClient, db: Session
) -> ClientOrderDetail:
    order = await service.place_order(
        db,
        principal,
        draft_id=body.draft_id,
        branch_id=body.branch_id,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        note_client=body.note_client,
    )
    return await _client_detail(db, order)


@client_router.get("", response_model=OrderListOut)
async def list_my_orders(
    principal: CurrentClient,
    db: Session,
    scope: Annotated[str, Query(pattern="^(all|active|completed|cancelled)$")] = "all",
    search: str | None = None,
) -> OrderListOut:
    orders = await service.list_client_orders(db, principal.id, scope=scope, search=search)
    return OrderListOut(orders=await _cards(db, orders))


@client_router.get("/{order_id}", response_model=ClientOrderDetail)
async def get_my_order(
    order_id: uuid.UUID, principal: CurrentClient, db: Session
) -> ClientOrderDetail:
    order = await service.get_client_order(db, principal.id, order_id)
    return await _client_detail(db, order)


@client_router.post("/{order_id}/cancel", response_model=TransitionOut)
async def client_cancel(
    order_id: uuid.UUID, body: ReasonIn, principal: CurrentClient, db: Session
) -> TransitionOut:
    order = await service.cancel(
        db, principal, order_id, reason=body.reason, expected_version=body.expected_version
    )
    return TransitionOut(id=order.id, status=order.status, version=order.version)


async def _client_detail(db: AsyncSession, order: Order) -> ClientOrderDetail:
    items = await service.order_items_for_read(db, order.id)
    settlement = None
    if order.status in _SETTLEMENT_VISIBLE_CLIENT:
        settlement = await _settlement(db, order)
    cancellation = await service.order_cancellation(db, order.id)
    return ClientOrderDetail(
        id=order.id,
        order_number=order.order_number,
        branch_id=order.branch_id,
        status=order.status,
        cutting_result_id=order.cutting_result_id,
        note_client=order.note_client,
        contact_name=order.contact_name,
        contact_phone=order.contact_phone,
        created_at=order.created_at,
        confirmed_at=order.confirmed_at,
        completed_at=order.completed_at,
        cancelled_at=order.cancelled_at,
        price=_price(order),
        items=_items_out(items),
        timeline=await _timeline(db, order.id),
        settlement=settlement,
        cancellation_reason=cancellation.reason if cancellation else None,
    )


# --- workshop: board / table / detail ---------------------------------------


@workshop_router.get("", response_model=WorkshopBoardOut)
async def list_workshop_orders(
    principal: CurrentWorkshopUser,
    db: Session,
    branch_id: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    search: str | None = None,
) -> WorkshopBoardOut:
    orders = await service.list_workshop_orders(
        db, principal, branch_id=branch_id, status=status, search=search
    )
    counts = await service.workshop_board_counts(db, principal, branch_id=branch_id)
    return WorkshopBoardOut(counts=counts, orders=await _cards(db, orders))


@workshop_router.get("/{order_id}", response_model=WorkshopOrderDetail)
async def get_workshop_order(
    order_id: uuid.UUID, principal: CurrentWorkshopUser, db: Session
) -> WorkshopOrderDetail:
    order = await service._scoped_order_for_workshop(db, principal, order_id)
    return await _workshop_detail(db, principal, order)


async def _workshop_detail(
    db: AsyncSession, principal: Principal, order: Order
) -> WorkshopOrderDetail:
    items = await service.order_items_for_read(db, order.id)
    settlement = await _settlement(db, order) if _can_view_finance(principal, order) else None
    warnings: list[dict[str, Any]] = []
    if order.status in (OrderStatus.NEW, OrderStatus.CONFIRMED):
        warnings = await service.shop_stock_warnings(db, order)
    cancellation = await service.order_cancellation(db, order.id)
    return WorkshopOrderDetail(
        id=order.id,
        order_number=order.order_number,
        branch_id=order.branch_id,
        workshop_id=order.workshop_id,
        status=order.status,
        version=order.version,
        cutting_result_id=order.cutting_result_id,
        note_client=order.note_client,
        note_workshop=order.note_workshop,
        contact_name=order.contact_name,
        contact_phone=order.contact_phone,
        created_at=order.created_at,
        confirmed_at=order.confirmed_at,
        completed_at=order.completed_at,
        cancelled_at=order.cancelled_at,
        price=_price(order),
        items=_items_out(items),
        timeline=await _timeline(db, order.id),
        stamps=ProductionStamps.model_validate(order),
        available_actions=_available_actions(order),
        settlement=settlement,
        stock_warnings=warnings,
        cancellation_reason=cancellation.reason if cancellation else None,
    )


# --- workshop: action endpoints ---------------------------------------------


@workshop_router.post("/{order_id}/approve", response_model=TransitionOut)
async def approve(
    order_id: uuid.UUID, body: VersionedIn, principal: CurrentWorkshopUser, db: Session
) -> TransitionOut:
    order, warnings = await service.approve(
        db, principal, order_id, expected_version=body.expected_version
    )
    return TransitionOut(
        id=order.id, status=order.status, version=order.version, stock_warnings=warnings
    )


@workshop_router.post("/{order_id}/assign", response_model=TransitionOut)
async def assign(
    order_id: uuid.UUID, body: AssignIn, principal: CurrentWorkshopUser, db: Session
) -> TransitionOut:
    order = await service.assign_cutter(
        db,
        principal,
        order_id,
        cutter_user_id=body.cutter_user_id,
        edger_user_id=body.edger_user_id,
        expected_version=body.expected_version,
    )
    return TransitionOut(id=order.id, status=order.status, version=order.version)


@workshop_router.post("/{order_id}/cutting-done", response_model=TransitionOut)
async def cutting_done(
    order_id: uuid.UUID, body: OnBehalfIn, principal: CurrentWorkshopUser, db: Session
) -> TransitionOut:
    order = await service.cutting_done(
        db,
        principal,
        order_id,
        on_behalf_user_id=body.on_behalf_user_id,
        expected_version=body.expected_version,
    )
    return TransitionOut(id=order.id, status=order.status, version=order.version)


@workshop_router.post("/{order_id}/banding-done", response_model=TransitionOut)
async def banding_done(
    order_id: uuid.UUID, body: OnBehalfIn, principal: CurrentWorkshopUser, db: Session
) -> TransitionOut:
    order = await service.banding_done(
        db,
        principal,
        order_id,
        on_behalf_user_id=body.on_behalf_user_id,
        expected_version=body.expected_version,
    )
    return TransitionOut(id=order.id, status=order.status, version=order.version)


@workshop_router.post("/{order_id}/mark-collected", response_model=TransitionOut)
async def mark_collected(
    order_id: uuid.UUID, body: VersionedIn, principal: CurrentWorkshopUser, db: Session
) -> TransitionOut:
    order = await service.mark_collected(
        db, principal, order_id, expected_version=body.expected_version
    )
    return TransitionOut(id=order.id, status=order.status, version=order.version)


@workshop_router.post("/{order_id}/revert", response_model=TransitionOut)
async def revert(
    order_id: uuid.UUID, body: ReasonIn, principal: CurrentWorkshopUser, db: Session
) -> TransitionOut:
    order = await service.revert(
        db, principal, order_id, reason=body.reason, expected_version=body.expected_version
    )
    return TransitionOut(id=order.id, status=order.status, version=order.version)


@workshop_router.post("/{order_id}/cancel", response_model=TransitionOut)
async def workshop_cancel(
    order_id: uuid.UUID, body: ReasonIn, principal: CurrentWorkshopUser, db: Session
) -> TransitionOut:
    order = await service.cancel(
        db, principal, order_id, reason=body.reason, expected_version=body.expected_version
    )
    return TransitionOut(id=order.id, status=order.status, version=order.version)


@workshop_router.post("/{order_id}/apply-discount", response_model=TransitionOut)
async def apply_discount(
    order_id: uuid.UUID, body: DiscountIn, principal: CurrentWorkshopUser, db: Session
) -> TransitionOut:
    order = await service.apply_discount(
        db,
        principal,
        order_id,
        discount_tiyin=body.discount_tiyin,
        reason=body.reason,
        expected_version=body.expected_version,
    )
    return TransitionOut(id=order.id, status=order.status, version=order.version)


# --- cutter / edger workspaces ----------------------------------------------


@cutter_router.get("", response_model=OrderListOut)
async def my_cutting(principal: CurrentWorkshopUser, db: Session) -> OrderListOut:
    """Orders assigned to me at confirmed (awaiting) or cutting (in progress)."""
    orders = await service.list_my_production(
        db, principal, statuses=(OrderStatus.CONFIRMED, OrderStatus.CUTTING)
    )
    mine = [o for o in orders if o.assigned_cutter_user_id == principal.id]
    return OrderListOut(orders=await _cards(db, mine))


@edger_router.get("", response_model=OrderListOut)
async def my_banding(principal: CurrentWorkshopUser, db: Session) -> OrderListOut:
    """edge_banding orders assigned to me."""
    orders = await service.list_my_production(db, principal, statuses=(OrderStatus.EDGE_BANDING,))
    mine = [o for o in orders if o.assigned_edger_user_id == principal.id]
    return OrderListOut(orders=await _cards(db, mine))
