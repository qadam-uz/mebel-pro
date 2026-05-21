"""Catalog schemas — platform materials, branch selections, branch pricing."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CatalogStatus, CuttingModel, MaterialKind, MaterialType
from app.schemas.common import APIModel

# --- platform materials -----------------------------------------------------


class MaterialCreate(BaseModel):
    kind: MaterialKind
    type: MaterialType | None = None
    name: str = Field(min_length=1, max_length=200)
    thickness_mm: float = Field(gt=0)
    color: str = Field(min_length=1, max_length=80)
    decor_code: str | None = Field(default=None, max_length=80)
    sheet_length_mm: int | None = Field(default=None, gt=0)
    sheet_width_mm: int | None = Field(default=None, gt=0)
    grain_direction: bool | None = None
    image_file_id: uuid.UUID | None = None


class MaterialUpdate(BaseModel):
    type: MaterialType | None = None
    type_set: bool = False
    name: str | None = Field(default=None, max_length=200)
    thickness_mm: float | None = Field(default=None, gt=0)
    color: str | None = Field(default=None, max_length=80)
    decor_code: str | None = Field(default=None, max_length=80)
    decor_code_set: bool = False
    sheet_length_mm: int | None = Field(default=None, gt=0)
    sheet_width_mm: int | None = Field(default=None, gt=0)
    grain_direction: bool | None = None
    image_file_id: uuid.UUID | None = None
    image_file_id_set: bool = False


class MaterialOut(APIModel):
    id: uuid.UUID
    kind: MaterialKind
    type: MaterialType | None = None
    name: str
    thickness_mm: float
    color: str
    decor_code: str | None = None
    sheet_length_mm: int | None = None
    sheet_width_mm: int | None = None
    grain_direction: bool | None = None
    image_file_id: uuid.UUID | None = None
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime


# --- branch material selection ----------------------------------------------


class BranchMaterialCreate(BaseModel):
    material_id: uuid.UUID
    price_tiyin: int = Field(ge=0)
    min_stock: int = Field(default=0, ge=0)


class BranchMaterialUpdate(BaseModel):
    price_tiyin: int | None = Field(default=None, ge=0)
    min_stock: int | None = Field(default=None, ge=0)


class BranchMaterialOut(APIModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    material_id: uuid.UUID
    price_tiyin: int
    min_stock: int
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime


# --- branch pricing ---------------------------------------------------------


class BranchPricingUpdate(BaseModel):
    cutting_model: CuttingModel
    cutting_rate_tiyin: int = Field(ge=0)
    # map "thickness_mm" -> rate_tiyin per metre
    edge_banding_rates: dict[str, int] = Field(default_factory=dict)


class BranchPricingOut(APIModel):
    branch_id: uuid.UUID
    cutting_model: CuttingModel | None = None
    cutting_rate_tiyin: int
    edge_banding_rates: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime
    updated_by_user_id: uuid.UUID | None = None
