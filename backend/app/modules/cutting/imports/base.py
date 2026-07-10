"""Shared import parser contracts."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import APIModel

MAX_IMPORT_FILE_BYTES = 1_048_576
MAX_SCAN_ROWS = 2000
MAX_SCAN_COLS = 30
PREVIEW_ROWS = 15
PREVIEW_COLS = 20
MAX_IMPORT_PIECES = 100

SourceFormat = Literal["csv", "bazis_xml", "map_2dplace"]
ImportStatus = Literal["needs_mapping", "parsed"]
ImportRole = Literal[
    "length_mm",
    "width_mm",
    "quantity",
    "material",
    "thickness_mm",
    "follow_grain",
    "edge_top",
    "edge_bottom",
    "edge_left",
    "edge_right",
]
SkipReason = Literal[
    "non_numeric_length",
    "non_numeric_width",
    "non_numeric_quantity",
    "quantity_not_integer",
    "quantity_not_positive",
    "dimension_not_positive",
    "dimension_too_large",
]
WarningCode = Literal[
    "dimension_rounded",
    "quantity_defaulted",
    "grain_token_unknown",
    "non_rectangular",
    "ignored_holes",
    "ignored_grooves",
    "edge_see_drawing",
]

IMPORT_ROLES: tuple[ImportRole, ...] = (
    "length_mm",
    "width_mm",
    "quantity",
    "material",
    "thickness_mm",
    "follow_grain",
    "edge_top",
    "edge_bottom",
    "edge_left",
    "edge_right",
)


class ImportParseError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
        status_code: int = 422,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code
        super().__init__(message)


class ImportParseOptions(BaseModel):
    skip_rows: int = Field(default=0, ge=0)
    mapping: dict[ImportRole, int] | None = None


def parse_options_json(options: str | None) -> ImportParseOptions:
    if not options:
        return ImportParseOptions()
    try:
        data = json.loads(options)
    except json.JSONDecodeError as exc:
        raise ImportParseError("invalid_mapping", "Invalid import options") from exc
    try:
        return ImportParseOptions.model_validate(data)
    except ValueError as exc:
        raise ImportParseError("invalid_mapping", "Invalid import options") from exc


class ImportSkippedRow(APIModel):
    row: int
    reason: SkipReason
    preview: str


class ImportWarning(APIModel):
    code: WarningCode
    rows: list[int]


class ImportedPart(APIModel):
    row: int
    length_mm: int
    width_mm: int
    quantity: int
    material_key: str
    follow_grain: bool
    edges: dict[Literal["top", "bottom", "left", "right"], str | None]


class ImportMapMaterialGroup(APIModel):
    key: str
    label: str
    width_mm: int
    height_mm: int
    sheet_count: int
    hint: str | None = None


class ImportMapPartRow(APIModel):
    row: int
    part_ref: str
    material_key: str
    length_mm: int
    width_mm: int
    quantity: int
    follow_grain: bool
    edges: dict[Literal["top", "bottom", "left", "right"], bool]
    name: str


class ImportMapPlacement(APIModel):
    sheet_index: int
    sheet_name: str
    material_key: str
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int
    name: str
    edges: dict[Literal["top", "bottom", "left", "right"], bool]
    is_waste: bool
    is_remainder: bool
    part_ref: str | None = None
    part_quantity_index: int | None = None
    rotated: bool = False


class ImportMapSheet(APIModel):
    sheet_index: int
    name: str
    material_key: str
    width_mm: int
    height_mm: int
    placements: list[ImportMapPlacement]
    parts_count: int
    waste_count: int
    remainder_count: int
    parts_area_mm2: int
    fill_percentage: float


class ImportMapLayout(APIModel):
    description: str = ""
    customer_name: str = ""
    order_type: str = ""
    sheets: list[ImportMapSheet]
    part_rows: list[ImportMapPartRow]


class ImportPanelMaterialGroup(APIModel):
    key: str
    label: str
    part_count: int
    thickness_hint: str | None = None


class ImportEdgeMaterialGroup(APIModel):
    key: str
    label: str
    side_count: int


class ImportNeedsMappingResponse(APIModel):
    status: Literal["needs_mapping"] = "needs_mapping"
    source_format: SourceFormat = "csv"
    grid: list[list[str | None]]
    guessed_mapping: dict[ImportRole, int]
    guessed_skip_rows: int


class ImportParsedResponse(APIModel):
    status: Literal["parsed"] = "parsed"
    source_format: SourceFormat = "csv"
    parts: list[ImportedPart]
    panel_materials: list[ImportPanelMaterialGroup]
    edge_materials: list[ImportEdgeMaterialGroup]
    skipped_rows: list[ImportSkippedRow]
    warnings: list[ImportWarning]
    ignored_object_count: int = 0
    material_groups: list[ImportMapMaterialGroup] = Field(default_factory=list)
    map_layout: ImportMapLayout | None = None
    total_parts: int
    total_pieces: int


ImportParseResponse = ImportNeedsMappingResponse | ImportParsedResponse
