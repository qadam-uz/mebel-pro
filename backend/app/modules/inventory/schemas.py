"""Inventory and supplier API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import MaterialKind, StockTransactionType, SupplierStatus
from app.modules.catalog.schemas import MaterialResponse
from app.schemas.common import APIModel


class SupplierCreateRequest(BaseModel):
    name: str
    phone: str | None = None
    note: str | None = None


class SupplierPatchRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    note: str | None = None


class SupplierResponse(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    name: str
    phone: str | None
    note: str | None
    status: SupplierStatus
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class InlineSupplierInput(BaseModel):
    name: str
    phone: str | None = None
    note: str | None = None


class StockInRequest(BaseModel):
    material_id: uuid.UUID
    quantity: int
    unit_price_tiyin: int
    supplier_id: uuid.UUID | None = None
    supplier: InlineSupplierInput | None = None
    note: str | None = None


class StockAdjustmentRequest(BaseModel):
    material_id: uuid.UUID
    quantity: int
    note: str


class StockItemResponse(APIModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    material_id: uuid.UUID
    material: MaterialResponse
    kind: MaterialKind
    stock_unit: str
    display_unit: str
    on_hand: int
    min_stock: int
    is_low_stock: bool
    updated_at: datetime


class StockTransactionResponse(APIModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    material_id: uuid.UUID
    material_name: str
    type: StockTransactionType
    quantity: int
    balance_after: int
    unit_price_tiyin: int | None
    total_price_tiyin: int | None
    order_id: uuid.UUID | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    note: str | None
    created_at: datetime


class StockValueResponse(APIModel):
    """On-hand quantity valued at the latest purchase price — derived, never stored."""

    value_tiyin: int


class StockLastPriceResponse(APIModel):
    """Latest purchase price for a material in a branch — all fields null when never priced."""

    unit_price_tiyin: int | None
    recorded_at: datetime | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
