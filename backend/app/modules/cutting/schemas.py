"""Cutting draft, result, and plan API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    CuttingResultSource,
    CuttingResultStatus,
    MaterialKind,
    MaterialSource,
    PanelMaterialType,
)
from app.modules.cutting.imports.base import ImportMapLayout
from app.schemas.common import APIModel


class CuttingEdgeBand(BaseModel):
    material_id: uuid.UUID
    source: MaterialSource = MaterialSource.SHOP


class CuttingPart(BaseModel):
    part_ref: str
    name: str | None = Field(default=None, max_length=64)
    material_id: uuid.UUID
    material_source: MaterialSource = MaterialSource.SHOP
    follow_grain: bool = True
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
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class CuttingDraftPatchRequest(BaseModel):
    preferred_branch_id: uuid.UUID | None = None
    parts_snapshot: list[CuttingPart] | None = None


class CuttingChooseResultRequest(BaseModel):
    result_id: uuid.UUID


class CuttingMapImportCommitRequest(BaseModel):
    preferred_branch_id: uuid.UUID | None = None
    parts: list[CuttingPart]
    map_layout: ImportMapLayout
    panel_picks: dict[str, uuid.UUID]


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
    material_id: uuid.UUID
    panel_index: int
    waste_area_mm2: int
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
    preferred_branch_id: uuid.UUID | None
    parts_snapshot: list[dict[str, Any]]
    chosen_result_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    results: list[CuttingResultResponse] = Field(default_factory=list)


class ClientCatalogMaterialOption(APIModel):
    id: uuid.UUID
    kind: MaterialKind
    manufacturer_id: uuid.UUID
    manufacturer_name: str
    type: PanelMaterialType | None
    name: str
    thickness_mm: Decimal
    color: str
    decor_code: str | None
    panel_length_mm: int | None
    panel_width_mm: int | None
    grain_direction: bool | None
    edge_width_mm: int | None
    image_file_id: uuid.UUID | None
    branch_carried: bool
    price_tiyin: int | None
    display_unit: str
