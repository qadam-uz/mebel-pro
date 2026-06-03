"""Order API schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import ActorType, Currency, MaterialSource, OrderStatus
from app.schemas.common import APIModel
from app.schemas.cutting import CuttingResultResponse


class ClientOrderCreateRequest(BaseModel):
    draft_id: uuid.UUID
    branch_id: uuid.UUID
    contact_name: str
    contact_phone: str
    note_client: str | None = None


class OrderQuoteResponse(APIModel):
    draft_id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    branch_address: str
    branch_phone: str
    subtotal_cutting_tiyin: int
    subtotal_materials_tiyin: int
    subtotal_edge_banding_tiyin: int
    total_tiyin: int


class VersionedRequest(BaseModel):
    version: int


class ReasonedVersionedRequest(VersionedRequest):
    reason: str


class WorkshopOrderAssignRequest(VersionedRequest):
    cutter_user_id: uuid.UUID | None = None
    edger_user_id: uuid.UUID | None = None


class WorkshopOrderCompleteRequest(VersionedRequest):
    completed_by_user_id: uuid.UUID | None = None


class WorkshopOrderDiscountRequest(VersionedRequest):
    kind: Literal["fixed", "percent"]
    value: int
    reason: str


class WorkshopOrderNoteRequest(BaseModel):
    note_workshop: str | None = None


class OrderItemResponse(APIModel):
    id: uuid.UUID
    material_id: uuid.UUID
    material_source: MaterialSource
    material_snapshot: dict[str, Any]
    part_ref: str
    length_mm: int
    width_mm: int
    quantity: int
    edge_top: dict[str, Any] | None
    edge_bottom: dict[str, Any] | None
    edge_left: dict[str, Any] | None
    edge_right: dict[str, Any] | None
    unit_cutting_price_tiyin: int
    unit_material_price_tiyin: int
    edge_cost_tiyin: int
    line_total_tiyin: int


class OrderStatusEventResponse(APIModel):
    id: uuid.UUID
    from_status: OrderStatus | None
    to_status: OrderStatus
    actor_type: ActorType
    actor_user_id: uuid.UUID | None
    actor_client_id: uuid.UUID | None
    reason: str | None
    metadata: dict[str, Any] | None
    changed_at: datetime


class OrderStockWarning(APIModel):
    material_id: uuid.UUID
    material_name: str
    kind: str
    on_hand: int
    required: int
    projected_after: int


class WorkshopWorkerOption(APIModel):
    id: uuid.UUID
    full_name: str
    is_owner: bool
    home_branch_id: uuid.UUID | None


class OrderSummaryResponse(APIModel):
    id: uuid.UUID
    order_number: str
    client_id: uuid.UUID
    client_name: str
    client_phone: str
    contact_name: str
    contact_phone: str
    workshop_id: uuid.UUID
    workshop_name: str
    branch_id: uuid.UUID
    branch_name: str
    branch_address: str
    branch_phone: str
    cutting_result_id: uuid.UUID
    status: OrderStatus
    version: int
    note_client: str | None
    note_workshop: str | None
    subtotal_cutting_tiyin: int
    subtotal_materials_tiyin: int
    subtotal_edge_banding_tiyin: int
    discount_tiyin: int
    discount_reason: str | None
    discount_applied_by_user_id: uuid.UUID | None
    total_tiyin: int
    currency: Currency
    assigned_cutter_user_id: uuid.UUID | None
    assigned_edger_user_id: uuid.UUID | None
    cutter_user_id: uuid.UUID | None
    cut_completed_at: datetime | None
    panels_used_snapshot: int | None
    cut_count_snapshot: int | None
    edger_user_id: uuid.UUID | None
    edge_completed_at: datetime | None
    edge_length_snapshot: dict[str, int] | None
    picked_up_at: datetime | None
    confirmed_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    item_count: int
    has_banding: bool
    stock_warnings: list[OrderStockWarning] = Field(default_factory=list)


class OrderDetailResponse(OrderSummaryResponse):
    items: list[OrderItemResponse] = Field(default_factory=list)
    events: list[OrderStatusEventResponse] = Field(default_factory=list)
    cutting_result: CuttingResultResponse | None = None
