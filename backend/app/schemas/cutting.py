"""Cutting schemas — draft parts editor, optimise results, branches indicator."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CuttingResultStatus, MaterialSource
from app.schemas.common import APIModel

# Edge-banding thickness: none, 0.4 mm, or 2.0 mm.
_VALID_EDGE_THICKNESS = {0.4, 2.0}
EdgeThickness = float | None


def _validate_edge(value: float | None) -> float | None:
    if value is not None and value not in _VALID_EDGE_THICKNESS:
        raise ValueError("Edge banding must be 0.4, 2.0, or null.")
    return value


# --- draft parts ------------------------------------------------------------


class PartIn(BaseModel):
    """One part line as the client edits it. ``part_ref`` is client-assigned and
    stable across edits; if omitted, the service assigns one."""

    part_ref: uuid.UUID | None = None
    material_id: uuid.UUID
    material_source: MaterialSource = MaterialSource.SHOP
    length_mm: int = Field(gt=0)
    width_mm: int = Field(gt=0)
    quantity: int = Field(ge=1)
    edge_top_mm: EdgeThickness = None
    edge_bottom_mm: EdgeThickness = None
    edge_left_mm: EdgeThickness = None
    edge_right_mm: EdgeThickness = None

    @field_validator("edge_top_mm", "edge_bottom_mm", "edge_left_mm", "edge_right_mm")
    @classmethod
    def _check_edges(cls, value: float | None) -> float | None:
        return _validate_edge(value)


class DraftUpdate(BaseModel):
    parts: list[PartIn] = Field(min_length=1, max_length=100)


class PartOut(BaseModel):
    part_ref: str
    material_id: uuid.UUID
    material_source: MaterialSource
    length_mm: int
    width_mm: int
    quantity: int
    edge_top_mm: float | None = None
    edge_bottom_mm: float | None = None
    edge_left_mm: float | None = None
    edge_right_mm: float | None = None


# --- results ----------------------------------------------------------------


class PlacementOut(APIModel):
    part_ref: str
    part_quantity_index: int
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int
    rotated: bool


class SheetOut(APIModel):
    id: uuid.UUID
    material_id: uuid.UUID
    sheet_index: int
    waste_area_mm2: int
    placements: list[PlacementOut] = Field(default_factory=list)


class ResultOut(APIModel):
    id: uuid.UUID
    draft_id: uuid.UUID | None = None
    algorithm_name: str
    algorithm_version: str
    status: CuttingResultStatus
    kerf_mm: int
    edge_trim_mm: int
    sheets_used_by_material: dict[str, Any] = Field(default_factory=dict)
    waste_percentage: float
    total_cut_length_mm: int
    total_edge_length_mm: int
    edge_length_by_thickness: dict[str, Any] = Field(default_factory=dict)
    order_id: uuid.UUID | None = None
    created_at: datetime
    confirmed_at: datetime | None = None
    invalidated_at: datetime | None = None
    sheets: list[SheetOut] = Field(default_factory=list)


class DraftOut(APIModel):
    id: uuid.UUID
    client_id: uuid.UUID
    parts_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    chosen_result_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class OptimiseOut(BaseModel):
    draft_id: uuid.UUID
    chosen_result_id: uuid.UUID | None = None
    results: list[ResultOut]


# --- branches indicator -----------------------------------------------------


class BranchAvailability(BaseModel):
    branch_id: uuid.UUID
    name: str


class BranchesOut(BaseModel):
    # "branches" | "any" (all-own composition) | "none"
    mode: Literal["branches", "any", "none"]
    branches: list[BranchAvailability] = Field(default_factory=list)
    # material ids (shop-source) not carried by any active branch
    uncovered_material_ids: list[uuid.UUID] = Field(default_factory=list)
