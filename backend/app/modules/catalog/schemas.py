"""Catalog and branch material API schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import MaterialKind, MaterialStatus, PanelMaterialType
from app.schemas.common import APIModel


class ManufacturerCreateRequest(BaseModel):
    name: str
    country: str | None = None
    note: str | None = None


class ManufacturerPatchRequest(BaseModel):
    name: str | None = None
    country: str | None = None
    note: str | None = None


class ManufacturerResponse(APIModel):
    id: uuid.UUID
    name: str
    country: str | None
    note: str | None
    status: MaterialStatus
    created_at: datetime
    updated_at: datetime


class MaterialCreateRequest(BaseModel):
    kind: MaterialKind
    manufacturer_id: uuid.UUID
    type: PanelMaterialType | None = None
    thickness_mm: Decimal
    color: str
    decor_code: str | None = None
    panel_length_mm: int | None = None
    panel_width_mm: int | None = None
    grain_direction: bool | None = None
    edge_width_mm: int | None = None
    image_file_id: uuid.UUID | None = None


class MaterialPatchRequest(BaseModel):
    manufacturer_id: uuid.UUID | None = None
    type: PanelMaterialType | None = None
    thickness_mm: Decimal | None = None
    color: str | None = None
    decor_code: str | None = None
    panel_length_mm: int | None = None
    panel_width_mm: int | None = None
    grain_direction: bool | None = None
    edge_width_mm: int | None = None
    image_file_id: uuid.UUID | None = None


class MaterialResponse(APIModel):
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
    status: MaterialStatus
    # AB-22: how many distinct branches carry this platform material. Populated on
    # the platform materials list; 0 on single-material / branch responses that
    # don't compute it.
    branch_usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class BranchMaterialCreateRequest(BaseModel):
    material_id: uuid.UUID
    price_tiyin: int
    min_stock: int = 0


class BranchMaterialBulkItem(BaseModel):
    material_id: uuid.UUID
    price_tiyin: int
    min_stock: int = 0


class BranchMaterialBulkCreateRequest(BaseModel):
    items: list[BranchMaterialBulkItem]


class BranchMaterialPatchRequest(BaseModel):
    price_tiyin: int | None = None
    min_stock: int | None = None


class BranchMaterialResponse(APIModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    material_id: uuid.UUID
    material: MaterialResponse
    price_tiyin: int
    min_stock: int
    status: MaterialStatus
    created_at: datetime
    updated_at: datetime


class BranchCatalogMaterialOption(APIModel):
    material: MaterialResponse


class BranchCatalogOptionsPage(APIModel):
    """QAD-159: the attach picker needs an honest `Filtrdagi hammasi (N)` count, so
    this endpoint breaks the house bare-list convention and returns the page plus
    the total number of attachable materials matching the same filters."""

    items: list[BranchCatalogMaterialOption]
    total: int


class BranchCatalogManufacturerOption(APIModel):
    id: uuid.UUID
    name: str


class BranchCatalogFiltersResponse(APIModel):
    """Facet values for the attach picker's dropdowns, over the materials this
    branch could still attach."""

    manufacturers: list[BranchCatalogManufacturerOption]
    thicknesses: list[Decimal]


class BranchMaterialBulkResponse(APIModel):
    created: list[BranchMaterialResponse]
    # Materials a concurrent attach already linked to the branch: the picker excludes
    # attached materials, so these are races, not user error — skipped, not rejected.
    skipped_material_ids: list[uuid.UUID]
