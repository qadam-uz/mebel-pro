"""Order API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import ActorType, Currency, MaterialSource, OrderStatus
from app.modules.cutting.schemas import CuttingResultResponse
from app.schemas.common import APIModel


class ClientOrderCreateRequest(BaseModel):
    draft_id: uuid.UUID
    branch_id: uuid.UUID
    contact_name: str
    contact_phone: str
    note_client: str | None = None


class WorkshopOrderCreateRequest(BaseModel):
    """Staff placing an order on behalf of a walk-in client. The client is the
    draft owner (resolved earlier by phone); contact fields are the frozen order
    snapshot, prefilled from that client but staff-editable."""

    draft_id: uuid.UUID
    branch_id: uuid.UUID
    contact_name: str
    contact_phone: str
    note_client: str | None = None


class MaterialPriceLine(APIModel):
    material_id: uuid.UUID
    material_name: str
    panels_used: int
    unit_price_tiyin: int
    line_total_tiyin: int


class EdgePriceLine(APIModel):
    material_id: uuid.UUID
    material_name: str
    consumed_mm: int
    material_cost_tiyin: int
    service_cost_tiyin: int
    line_total_tiyin: int


class OrderQuoteResponse(APIModel):
    draft_id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    branch_address: str
    branch_phone: str
    today_hours: dict[str, str | None]
    subtotal_cutting_tiyin: int
    subtotal_materials_tiyin: int
    subtotal_edge_banding_tiyin: int
    total_tiyin: int
    # Itemized breakdown so the card/checkout can show how the price is built
    # (CB-117): cutting = panels_used * cutting_rate, plus per-material/per-edge lines.
    panels_used: int
    cutting_rate_tiyin: int
    material_lines: list[MaterialPriceLine]
    edge_lines: list[EdgePriceLine]


class BatchOrderQuoteRequest(BaseModel):
    draft_id: uuid.UUID
    branch_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class BatchOrderQuoteResponse(APIModel):
    # Per-branch quote keyed by branch_id; errors carries a code (or null) per
    # branch that failed, so the client attributes each failure correctly (CB-12).
    quotes: dict[str, OrderQuoteResponse]
    errors: dict[str, str | None]


class VersionedRequest(BaseModel):
    version: int


class ReasonedVersionedRequest(VersionedRequest):
    reason: str


class WorkshopOrderAssignRequest(VersionedRequest):
    cutter_user_id: uuid.UUID | None = None
    edger_user_id: uuid.UUID | None = None


class WorkshopOrderCompleteRequest(VersionedRequest):
    completed_by_user_id: uuid.UUID | None = None


class WorkshopOrderAdjustmentRequest(VersionedRequest):
    """A manual price adjustment — a discount or a surcharge. `value` is tiyin
    when `kind="fixed"`, or a whole percent (0-100) when `kind="percent"`,
    resolved against the order's computed subtotal at apply time."""

    kind: Literal["fixed", "percent"]
    value: int
    reason: str


class WorkshopOrderDiscountRequest(WorkshopOrderAdjustmentRequest):
    pass


class WorkshopOrderSurchargeRequest(WorkshopOrderAdjustmentRequest):
    pass


class WorkshopOrderNoteRequest(BaseModel):
    note_workshop: str | None = None


class WorkshopOrderEditApplyRequest(VersionedRequest):
    """Apply the order's revision draft back onto the order (orders.md:
    "Revising a placed order"). The reason is optional — the edit event carries
    it when staff give one."""

    reason: str | None = None


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


class OrderEdgeMaterialDemand(APIModel):
    material_id: uuid.UUID
    material_label: str
    thickness_mm: Decimal | None = None
    color: str | None = None
    consumed_mm: int


class OrderPriceLine(APIModel):
    """One material's share of the order price, rebuilt from order-time
    snapshots (item snapshot prices x cutting-result demands) so the itemized
    breakdown reconciles with the stored subtotals even after price-list
    changes. Panel lines carry panels_used; edge lines carry consumed_mm and
    only the material share (edge labor stays an aggregate)."""

    material_id: uuid.UUID
    material_name: str
    kind: Literal["panel", "edge"]
    panels_used: int | None = None
    consumed_mm: int | None = None
    line_total_tiyin: int


class OrderSettlementResponse(APIModel):
    total_tiyin: int
    recorded_tiyin: int
    balance_tiyin: int


class WorkshopWorkerOption(APIModel):
    id: uuid.UUID
    full_name: str
    is_owner: bool
    home_branch_id: uuid.UUID


class NewOrderCountResponse(APIModel):
    """Ambient count behind the workshop sidebar's `+N` badge."""

    count: int


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
    today_hours: dict[str, str | None]
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
    surcharge_tiyin: int
    surcharge_reason: str | None
    surcharge_applied_by_user_id: uuid.UUID | None
    total_tiyin: int
    currency: Currency
    assigned_cutter_user_id: uuid.UUID | None
    assigned_edger_user_id: uuid.UUID | None
    cutter_assigned_at: datetime | None
    edger_assigned_at: datetime | None
    cutting_started_at: datetime | None
    banding_started_at: datetime | None
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
    planned_panels: int = 0
    planned_edge_lines: list[OrderEdgeMaterialDemand] = Field(default_factory=list)
    stock_warnings: list[OrderStockWarning] = Field(default_factory=list)


class OrderDetailResponse(OrderSummaryResponse):
    items: list[OrderItemResponse] = Field(default_factory=list)
    events: list[OrderStatusEventResponse] = Field(default_factory=list)
    price_lines: list[OrderPriceLine] = Field(default_factory=list)
    cutting_result: CuttingResultResponse | None = None
    settlement: OrderSettlementResponse | None = None
    # The order's open revision draft, surfaced on the workshop detail only —
    # lets the UI offer resume/discard instead of starting a fresh revision.
    revision_draft_id: uuid.UUID | None = None
    # Set only by the two production-completion endpoints, when the consume they
    # just recorded drove a branch balance below zero. Informational: the
    # transition already succeeded (QAD-150).
    stock_shortfall: bool = False


# --- Production terminal (worker-scoped, money-free) -------------------------
#
# The station workspace and job sheet payloads. Deliberately separate from the
# order schemas: no price/discount/settlement fields, no client phone, first
# name only — the boundary is enforced by construction, not by trimming.


class ProductionWorkerRef(APIModel):
    id: uuid.UUID
    full_name: str


class ProductionEdgeSide(APIModel):
    material_label: str
    thickness_mm: Decimal | None = None
    color: str | None = None
    source: MaterialSource


class ProductionJobItem(APIModel):
    id: uuid.UUID
    part_ref: str
    length_mm: int
    width_mm: int
    quantity: int
    material_label: str
    edge_top: ProductionEdgeSide | None = None
    edge_bottom: ProductionEdgeSide | None = None
    edge_left: ProductionEdgeSide | None = None
    edge_right: ProductionEdgeSide | None = None


class ProductionJobCard(APIModel):
    id: uuid.UUID
    order_number: str
    status: OrderStatus
    version: int
    client_first_name: str
    branch_id: uuid.UUID
    branch_name: str
    item_count: int
    has_banding: bool
    planned_panels: int = 0
    planned_edge_lines: list[OrderEdgeMaterialDemand] = Field(default_factory=list)
    material_labels: list[str] = Field(default_factory=list)
    assigned_cutter: ProductionWorkerRef | None = None
    assigned_edger: ProductionWorkerRef | None = None
    cutter_assigned_at: datetime | None = None
    edger_assigned_at: datetime | None = None
    cutting_started_at: datetime | None = None
    banding_started_at: datetime | None = None
    cut_completed_at: datetime | None = None
    edge_completed_at: datetime | None = None
    created_at: datetime


class ProductionQueueResponse(APIModel):
    station: Literal["cutting", "banding"]
    jobs: list[ProductionJobCard] = Field(default_factory=list)
    completed_today: list[ProductionJobCard] = Field(default_factory=list)


class ProductionJobDetail(ProductionJobCard):
    items: list[ProductionJobItem] = Field(default_factory=list)
    cutting_result: CuttingResultResponse | None = None
