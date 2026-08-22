"""Cutting draft, result, and plan API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    CuttingResultSource,
    CuttingResultStatus,
    DecorType,
    MaterialSource,
)
from app.modules.cutting.imports.base import ImportMapLayout
from app.modules.cutting.optimizer import MAX_PANELS_PER_MATERIAL
from app.schemas.common import APIModel


def normalize_name(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class CuttingEdgeBand(BaseModel):
    material_id: uuid.UUID
    source: MaterialSource = MaterialSource.SHOP


class CuttingPart(BaseModel):
    part_ref: str
    name: str | None = Field(default=None, max_length=64)
    material_id: uuid.UUID
    material_source: MaterialSource = MaterialSource.SHOP
    follow_grain: bool = True
    # Thickening (utolshenie / obmanka, stamped "UT" on the drawing): a second
    # strip of the same panel is glued under this part so its banded edge reads
    # twice as thick. Purely an instruction to the workshop — it never enters
    # the layout, so the strip is not planned, priced, or counted. It does
    # raise the edge tape the part needs: the visible edge is 2x the panel.
    thickened: bool = False
    length_mm: int
    width_mm: int
    quantity: int
    edge_top: CuttingEdgeBand | None = None
    edge_bottom: CuttingEdgeBand | None = None
    edge_left: CuttingEdgeBand | None = None
    edge_right: CuttingEdgeBand | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return normalize_name(value)


class CuttingDraftPart(BaseModel):
    """A work-in-progress row stored by a cutting draft.

    Drafts deliberately retain incomplete rows while an operator is entering a
    drawing. ``CuttingPart`` remains the strict shape accepted by optimisation
    and map import.
    """

    part_ref: str
    name: str | None = Field(default=None, max_length=64)
    material_id: uuid.UUID | None = None
    material_source: MaterialSource = MaterialSource.SHOP
    follow_grain: bool = True
    thickened: bool = False
    length_mm: int = 0
    width_mm: int = 0
    quantity: int = 0
    edge_top: CuttingEdgeBand | None = None
    edge_bottom: CuttingEdgeBand | None = None
    edge_left: CuttingEdgeBand | None = None
    edge_right: CuttingEdgeBand | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return normalize_name(value)

    @field_validator("material_id", mode="before")
    @classmethod
    def normalize_material_id(cls, value: object) -> object:
        return None if value == "" else value


class CuttingDraftPatchRequest(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    preferred_branch_id: uuid.UUID | None = None
    parts_snapshot: list[CuttingDraftPart] | None = None
    # Client-supplied material (cutting.md, "Own material"). Sheets are claimed
    # per catalog material; the claim is not capped to the current layout, since
    # the next edit may need the sheets this one does not.
    own_panel_counts: dict[uuid.UUID, int] | None = None
    own_edge_material_ids: list[uuid.UUID] | None = None

    @field_validator("own_panel_counts")
    @classmethod
    def reject_negative_counts(
        cls, value: dict[uuid.UUID, int] | None
    ) -> dict[uuid.UUID, int] | None:
        if value and any(count < 0 for count in value.values()):
            raise ValueError("own panel count cannot be negative")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_draft_name(cls, value: object) -> object:
        return normalize_name(value)


class CuttingChooseResultRequest(BaseModel):
    result_id: uuid.UUID


class CuttingMapImportCommitRequest(BaseModel):
    preferred_branch_id: uuid.UUID | None = None
    parts: list[CuttingPart]
    map_layout: ImportMapLayout
    panel_picks: dict[str, uuid.UUID]
    # The uploaded file's name (e.g. "AFZAL.map") — the wizard already knows it
    # from the file picker. Used only to derive the new draft's `name`
    # (imports/common.py:draft_name_from_filename); never persisted verbatim.
    source_filename: str | None = None


class WorkshopCuttingMapImportCommitRequest(CuttingMapImportCommitRequest):
    """MAP import committed by workshop staff for a walk-in client.

    ``branch_id`` is the frozen workshop context; ``preferred_branch_id`` from
    the shared client payload is accepted for shape compatibility but the
    workshop commit always uses this branch.
    """

    client_id: uuid.UUID
    branch_id: uuid.UUID


class WorkshopCuttingDraftCreateRequest(BaseModel):
    """Staff opening a draft for a walk-in client at a fixed branch (both
    resolved before the editor: the client by phone, the branch from context)."""

    client_id: uuid.UUID
    branch_id: uuid.UUID


class CuttingPlacementResponse(APIModel):
    id: uuid.UUID
    part_ref: str
    part_quantity_index: int
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int
    rotated: bool


class CuttingOffcutResponse(APIModel):
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int
    usable: bool


class CuttingPanelResponse(APIModel):
    id: uuid.UUID
    # The panel's material key: a branch material id, or — for a sheet the
    # walk-in brought — a customer board id. Two disjoint UUID namespaces, one
    # opaque key, which is exactly how `material_snapshots` and
    # `own_panel_counts` are keyed. Named `material_id` like the sibling
    # price/warning/demand schemas; it was `branch_material_id` while customer
    # boards were branch materials, and that name is now a lie.
    material_id: uuid.UUID
    panel_index: int
    waste_area_mm2: int
    cut_count: int | None = None
    cut_length_mm: int | None = None
    offcuts: list[CuttingOffcutResponse] = Field(default_factory=list)
    placements: list[CuttingPlacementResponse]


class CuttingResultResponse(APIModel):
    id: uuid.UUID
    draft_id: uuid.UUID | None
    algorithm_name: str
    algorithm_version: str
    source: CuttingResultSource
    status: CuttingResultStatus
    kerf_mm: int
    edge_trim_mm: int
    panels_used_by_material: dict[str, int]
    # How many of those sheets the client supplies, per panel branch material —
    # already clamped to this layout and frozen once confirmed. The edge
    # equivalents below have always been serialized; sheets were the asymmetry,
    # which left every order surface unable to say what the client must bring.
    own_panel_counts: dict[str, int] = Field(default_factory=dict)
    waste_percentage: Decimal
    total_cut_length_mm: int
    total_edge_length_mm: int
    edge_length_by_material: dict[str, int]
    parts_snapshot: list[dict[str, Any]]
    material_snapshots: dict[str, dict[str, Any]]
    edge_length_shop_by_material: dict[str, int]
    edge_length_own_by_material: dict[str, int]
    edge_consumed_shop_by_material: dict[str, int]
    edge_consumed_own_by_material: dict[str, int]
    edge_banded_sides_by_material: dict[str, dict[str, int]]
    order_id: uuid.UUID | None
    created_at: datetime
    confirmed_at: datetime | None
    invalidated_at: datetime | None
    panels: list[CuttingPanelResponse]


class CuttingDraftResponse(APIModel):
    id: uuid.UUID
    client_id: uuid.UUID
    name: str | None
    preferred_branch_id: uuid.UUID | None
    # Effective kerf/edge-trim for this draft, resolved from its branch (or the
    # platform defaults for a branch-less draft) on every read — never a
    # snapshot; a branch edit changes these on the next fetch.
    kerf_mm: int
    edge_trim_mm: int
    # Whether the draft's branch takes client-supplied sheets, resolved the same
    # way — so the editor can hide the own-material affordance instead of
    # offering a claim the server will drop on save.
    own_material_allowed: bool = False
    parts_snapshot: list[dict[str, Any]]
    own_panel_counts: dict[str, int] = Field(default_factory=dict)
    own_edge_material_ids: list[str] = Field(default_factory=list)
    chosen_result_id: uuid.UUID | None
    # Set only on an order's revision draft (orders.md: "Revising a placed
    # order") — the editor switches to revision mode when present.
    revision_of_order_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    results: list[CuttingResultResponse] = Field(default_factory=list)


class WorkshopCuttingDraftSummary(APIModel):
    """A staff-minted walk-in draft on the workshop's saved-drafts surface
    (cutting.md#workshop-side). Denormalizes the walk-in client and branch so the
    list card needs no per-row fetch; `has_result` is the derived readiness the UI
    turns into a status label (a draft carries no status of its own)."""

    id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    client_phone: str
    name: str | None
    preferred_branch_id: uuid.UUID | None
    branch_name: str | None
    part_count: int
    panel_count: int
    waste_percentage: Decimal | None
    has_result: bool
    created_at: datetime
    updated_at: datetime


class CustomerBoardCreateRequest(BaseModel):
    """A sheet the walk-in carried in, as the operator typed it.

    `name` is optional because the customer rarely knows what their board is;
    the size is what the layout needs. `thickness_mm` is required even though the
    handoff form omits it — it is NOT NULL on the material, part of the format
    key, and printed in every label, so inventing one server-side would make two
    genuinely different boards render identically.
    """

    name: str | None = Field(default=None, max_length=80)
    length_mm: int = Field(gt=0, le=6000)
    width_mm: int = Field(gt=0, le=6000)
    thickness_mm: Decimal = Field(gt=0, le=100)
    sheets: int = Field(gt=0, le=MAX_PANELS_PER_MATERIAL)
    has_grain: bool = False


class ClientCatalogMaterialOption(APIModel):
    """One format a branch carries, as the cutting editors' pickers see it.

    `id` is the id a part's `material_id` must resolve to — a branch material
    for a carried format, a customer board for the walk-in's own sheet.
    Listings are always branch-scoped, so there is no `branch_carried` flag:
    every row returned is pickable by construction.
    """

    id: uuid.UUID
    type: DecorType
    # Null for a customer-supplied board: nobody knows who made the sheet the
    # walk-in carried in, and it is not part of any manufacturer's catalog.
    manufacturer_id: uuid.UUID | None
    manufacturer_name: str
    code: str | None
    name: str
    has_grain: bool
    image_file_id: uuid.UUID | None
    thickness_mm: Decimal
    length_mm: int | None
    width_mm: int | None
    tape_width_mm: int | None
    # 1 or 2 for the board types, null otherwise — the platform's fact about
    # this format, not the branch's.
    finished_sides: int | None = None
    # The platform retired this format (no longer produced). The row stays
    # pickable — the branch may still hold stock — but the picker says so, the
    # same way a deactivated decor would not: that one is simply absent.
    discontinued: bool = False
    price_tiyin: int
    # 0 means "the branch has not priced this format yet", not "free". Only the
    # workshop-facing listing ever returns such a row; the client listing drops
    # them. A customer-supplied board is the one row where 0 IS free, so it
    # never sets this flag — see `customer_supplied`.
    price_unset: bool
    display_unit: str
    # A sheet the walk-in carried in. It is a `customer_boards` row, not a
    # branch material — its own table, never stocked, never in any catalog,
    # reachable only from the drawing that recorded it. Its `price_tiyin` is the
    # branch's price for the same size when there is one; that is what makes the
    # SHORTAGE price itself, since the demand the quote sees is already
    # `needed - brought`.
    customer_supplied: bool = False
