"""Order schemas — placement, transitions, client + workshop reads."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import MaterialSource, OrderStatus
from app.schemas.common import APIModel

# --- placement (client) -----------------------------------------------------


class PlaceOrderIn(BaseModel):
    draft_id: uuid.UUID
    branch_id: uuid.UUID
    contact_name: str = Field(min_length=1, max_length=120)
    contact_phone: str = Field(min_length=1, max_length=20)
    note_client: str | None = Field(default=None, max_length=1000)


# --- transition inputs (workshop) -------------------------------------------


class VersionedIn(BaseModel):
    expected_version: int | None = None


class AssignIn(VersionedIn):
    cutter_user_id: uuid.UUID
    edger_user_id: uuid.UUID | None = None


class OnBehalfIn(VersionedIn):
    on_behalf_user_id: uuid.UUID | None = None


class ReasonIn(VersionedIn):
    reason: str = Field(min_length=1, max_length=500)


class DiscountIn(VersionedIn):
    discount_tiyin: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=300)


# --- read schemas -----------------------------------------------------------


class OrderItemOut(APIModel):
    id: uuid.UUID
    material_id: uuid.UUID
    material_source: MaterialSource
    material_snapshot: dict[str, Any] = Field(default_factory=dict)
    part_ref: str
    length_mm: int
    width_mm: int
    quantity: int
    edge_top_mm: float | None = None
    edge_bottom_mm: float | None = None
    edge_left_mm: float | None = None
    edge_right_mm: float | None = None
    unit_cutting_price_tiyin: int
    unit_material_price_tiyin: int
    edge_cost_tiyin: int
    line_total_tiyin: int


class PriceBreakdown(BaseModel):
    subtotal_cutting_tiyin: int
    subtotal_materials_tiyin: int
    subtotal_edge_banding_tiyin: int
    discount_tiyin: int
    total_tiyin: int
    currency: str = "UZS"


class SettlementOut(BaseModel):
    total_tiyin: int
    recorded_tiyin: int
    balance_tiyin: int


class TimelineEvent(BaseModel):
    from_status: OrderStatus | None
    to_status: OrderStatus
    actor_type: str
    reason: str | None = None
    metadata: dict[str, Any] | None = None
    changed_at: datetime


class OrderCardOut(BaseModel):
    id: uuid.UUID
    order_number: str
    branch_id: uuid.UUID
    status: OrderStatus
    total_tiyin: int
    item_count: int
    created_at: datetime
    contact_name: str | None = None
    contact_phone: str | None = None
    assigned_cutter_user_id: uuid.UUID | None = None
    assigned_edger_user_id: uuid.UUID | None = None


class OrderListOut(BaseModel):
    orders: list[OrderCardOut]


class WorkshopBoardOut(BaseModel):
    counts: dict[str, int]
    orders: list[OrderCardOut]


class ProductionStamps(APIModel):
    assigned_cutter_user_id: uuid.UUID | None = None
    assigned_edger_user_id: uuid.UUID | None = None
    cutter_user_id: uuid.UUID | None = None
    cut_completed_at: datetime | None = None
    sheets_used_snapshot: int | None = None
    cut_count_snapshot: int | None = None
    edger_user_id: uuid.UUID | None = None
    edge_completed_at: datetime | None = None
    edge_length_snapshot: dict[str, Any] | None = None
    picked_up_at: datetime | None = None


class ClientOrderDetail(BaseModel):
    id: uuid.UUID
    order_number: str
    branch_id: uuid.UUID
    status: OrderStatus
    cutting_result_id: uuid.UUID
    note_client: str | None = None
    contact_name: str
    contact_phone: str
    created_at: datetime
    confirmed_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    price: PriceBreakdown
    items: list[OrderItemOut]
    timeline: list[TimelineEvent]
    # finance settlement only at ready/completed
    settlement: SettlementOut | None = None
    cancellation_reason: str | None = None


class WorkshopOrderDetail(BaseModel):
    id: uuid.UUID
    order_number: str
    branch_id: uuid.UUID
    workshop_id: uuid.UUID
    status: OrderStatus
    version: int
    cutting_result_id: uuid.UUID
    note_client: str | None = None
    note_workshop: str | None = None
    contact_name: str
    contact_phone: str
    created_at: datetime
    confirmed_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    price: PriceBreakdown
    items: list[OrderItemOut]
    timeline: list[TimelineEvent]
    stamps: ProductionStamps
    available_actions: list[str]
    # settlement summary for view_finance_reports / manage_finance at any status
    settlement: SettlementOut | None = None
    stock_warnings: list[dict[str, Any]] = Field(default_factory=list)
    cancellation_reason: str | None = None


class TransitionOut(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    version: int
    stock_warnings: list[dict[str, Any]] = Field(default_factory=list)
