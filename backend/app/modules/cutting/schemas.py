"""Cutting draft, result, and plan API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CuttingResultStatus, MaterialKind, MaterialSource, PanelMaterialType
from app.schemas.common import APIModel


class CuttingEdgeBand(BaseModel):
    material_id: uuid.UUID
    source: MaterialSource = MaterialSource.SHOP


class CuttingPart(BaseModel):
    part_ref: str
    material_id: uuid.UUID
    material_source: MaterialSource = MaterialSource.SHOP
    length_mm: int
    width_mm: int
    quantity: int
    edge_top: CuttingEdgeBand | None = None
    edge_bottom: CuttingEdgeBand | None = None
    edge_left: CuttingEdgeBand | None = None
    edge_right: CuttingEdgeBand | None = None


class CuttingDraftPatchRequest(BaseModel):
    preferred_branch_id: uuid.UUID | None = None
    parts_snapshot: list[CuttingPart] | None = None


class CuttingChooseResultRequest(BaseModel):
    result_id: uuid.UUID


class CuttingPlacementResponse(APIModel):
    id: uuid.UUID
    part_ref: str
    part_quantity_index: int
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int
    rotated: bool


class CuttingPanelResponse(APIModel):
    id: uuid.UUID
    material_id: uuid.UUID
    panel_index: int
    waste_area_mm2: int
    placements: list[CuttingPlacementResponse]


class CuttingResultResponse(APIModel):
    id: uuid.UUID
    draft_id: uuid.UUID | None
    algorithm_name: str
    algorithm_version: str
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
    image_file_id: uuid.UUID | None
    branch_carried: bool
    price_tiyin: int | None
    display_unit: str


class WorkshopCuttingPlanSummary(APIModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    client_id: uuid.UUID
    branch_id: uuid.UUID
    algorithm_name: str
    waste_percentage: Decimal
    panels_used_by_material: dict[str, int]
    total_cut_length_mm: int
    total_edge_length_mm: int
    confirmed_at: datetime | None


class WorkshopCuttingPlanDetail(WorkshopCuttingPlanSummary):
    result: CuttingResultResponse
