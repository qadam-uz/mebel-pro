"""Order API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

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
    """One panel material's share of the quote.

    `panels_used` is what the layout needs; `own_panels` is how many of those the
    client supplies. The workshop charges the difference, which is what
    `line_total_tiyin` already holds — the receipt renders the subtraction rather
    than recomputing it.
    """

    material_id: uuid.UUID
    material_name: str
    panels_used: int
    own_panels: int = 0
    unit_price_tiyin: int
    line_total_tiyin: int


class EdgePriceLine(APIModel):
    """One tape's share of the quote.

    `consumed_mm` counts every banded millimetre; `own` says the client brought
    the roll, so the tape itself is free while the gluing is still charged.
    """

    material_id: uuid.UUID
    material_name: str
    consumed_mm: int
    own: bool = False
    # The branch's price per metre for this tape, so the receipt can print the
    # multiplication it charges rather than a total the reader has to trust.
    metre_price_tiyin: int = 0
    material_cost_tiyin: int
    service_cost_tiyin: int
    line_total_tiyin: int


class OrderQuoteResponse(APIModel):
    draft_id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    branch_address: str
    branch_phone: str
    # The checkout screen names who is doing the work, not just where to collect
    # it — the branch alone reads as an address without an owner.
    workshop_name: str = ""
    # Everything a client needs to actually reach the branch: every published
    # number, and the pin when the branch has one (an address alone does not
    # find a door on a street that repeats across the city).
    branch_additional_phones: list[str] = Field(default_factory=list)
    branch_latitude: Decimal | None = None
    branch_longitude: Decimal | None = None
    subtotal_cutting_tiyin: int
    subtotal_materials_tiyin: int
    subtotal_edge_banding_tiyin: int
    total_tiyin: int
    # Itemized breakdown so the card/checkout can show how the price is built
    # (CB-117): cutting = panels_used * cutting_rate, plus per-material/per-edge lines.
    panels_used: int
    cutting_rate_tiyin: int
    # Per-metre banding labour, so the receipt prints the same multiplication for
    # the edge service that it does for cutting.
    edge_banding_rate_tiyin: int = 0
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


class WorkshopOrderPricesRequest(VersionedRequest):
    """Unit prices staff agreed for one order, replacing the branch rate card.

    Every field is optional and `null` means "drop the agreement, go back to the
    branch's price" — so a request is read as the whole agreement, not a patch:
    a material left out of `material_prices` is billed at the branch's price.

    Quantities are never in here. What is negotiated at the counter is the price
    per sheet or per metre; how many sheets a layout needs is the optimiser's
    answer, and letting staff retype it would put the bill and the cutting plan
    out of step.
    """

    cutting_rate_tiyin: int | None = None
    edge_banding_rate_tiyin: int | None = None
    material_prices: dict[uuid.UUID, int] = Field(default_factory=dict)

    @field_validator("cutting_rate_tiyin", "edge_banding_rate_tiyin")
    @classmethod
    def reject_negative_rate(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("rate must be non-negative")
        return value

    @field_validator("material_prices")
    @classmethod
    def reject_negative_prices(cls, value: dict[uuid.UUID, int]) -> dict[uuid.UUID, int]:
        if any(price < 0 for price in value.values()):
            raise ValueError("material prices must be non-negative")
        return value


class WorkshopOrderOwnMaterialRequest(VersionedRequest):
    """What the client supplies, set by staff on a placed order.

    The whole claim, not a delta — an absent material means the client brings
    none of it, so clearing is the same call with the entry dropped. Counts are
    clamped to what the order's layout actually uses, so an over-claim is
    harmless rather than an error the counter has to reason about.

    Unlike the client's own path this is **not** gated by the branch's
    `own_material_allowed`: that setting is about what a client may arrange
    unattended in the app (workshop.md), and staff at the counter always may.
    """

    own_panel_counts: dict[uuid.UUID, int] = Field(default_factory=dict)

    @field_validator("own_panel_counts")
    @classmethod
    def reject_negative_counts(cls, value: dict[uuid.UUID, int]) -> dict[uuid.UUID, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("own panel counts must be non-negative")
        return value


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
    # The live FK, renamed with the column it mirrors (`_order_response` builds
    # this by `model_validate(item)`, so the two names must match exactly).
    # `material_snapshot` beside it is frozen history and keeps its old keys.
    branch_material_id: uuid.UUID
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
    # What the workshop supplies and therefore charges for.
    panels_used: int | None = None
    consumed_mm: int | None = None
    # The price this order is billed at per sheet (panel) or per metre (edge) —
    # the branch's, or whatever staff agreed for this order. It is the number
    # the receipt multiplies, so it is also the number staff edit.
    unit_price_tiyin: int = 0
    # What the client brings, alongside it. Kept as its own number rather than
    # folded into the one above: the charged figure has to keep reconciling with
    # the stored subtotals, while a fully client-supplied material otherwise
    # renders as `0 sheets, 0 so'm` — which reads as free, not as "you bring it".
    own_panels: int = 0
    own_mm: int = 0
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
    branch_additional_phones: list[str] = Field(default_factory=list)
    branch_latitude: Decimal | None = None
    branch_longitude: Decimal | None = None
    cutting_result_id: uuid.UUID
    status: OrderStatus
    version: int
    note_client: str | None
    note_workshop: str | None
    subtotal_cutting_tiyin: int
    subtotal_materials_tiyin: int
    subtotal_edge_banding_tiyin: int
    # The service rates this order is billed at — the branch's, or the ones
    # staff agreed for it, so the receipt can print the multiplication it
    # charges instead of a total the reader has to take on trust.
    cutting_rate_tiyin: int = 0
    edge_banding_rate_tiyin: int = 0
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
    # Identity the client actually recognises: the name they gave the drawing
    # this order was placed from. `None` when the drawing was never named — the
    # UI falls back to the order number rather than inventing a label.
    draft_name: str | None = None
    # The drawing was minted by workshop staff on the client's behalf. Such
    # drafts stay hidden from the client's own list until the order exists, so
    # the order is the first time they see it — the surface says who built it.
    created_via_workshop: bool = False
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
