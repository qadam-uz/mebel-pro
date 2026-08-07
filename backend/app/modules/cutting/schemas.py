"""Cutting draft, result, and plan API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    CuttingResultSource,
    CuttingResultStatus,
    DekorType,
    MaterialSource,
)
from app.modules.cutting.imports.base import ImportMapLayout
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
    branch_material_id: uuid.UUID
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


class ClientCatalogMaterialOption(APIModel):
    """One format a branch carries, as the cutting editors' pickers see it.

    `id` is the branch material — the id a part's `material_id` must resolve to.
    Listings are always branch-scoped now, so there is no `branch_carried` flag:
    every row returned is carried by construction.
    """

    id: uuid.UUID
    tur: DekorType
    manufacturer_id: uuid.UUID
    manufacturer_name: str
    kod: str | None
    nomi: str
    tolali: bool
    image_file_id: uuid.UUID | None
    qalinlik_mm: Decimal
    uzunlik_mm: int | None
    eni_mm: int | None
    kromka_eni_mm: int | None
    price_tiyin: int
    # 0 means "the branch has not priced this format yet", not "free". Only the
    # workshop-facing listing ever returns such a row; clients never see one.
    price_unset: bool
    display_unit: str
