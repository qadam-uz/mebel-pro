"""Inventory schemas — stock operations, transactions, suppliers."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import StockTransactionType, SupplierStatus
from app.schemas.common import APIModel

# --- stock ------------------------------------------------------------------


class StockItemOut(APIModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    material_id: uuid.UUID
    on_hand: int
    min_stock: int
    updated_at: datetime


class StockInIn(BaseModel):
    material_id: uuid.UUID
    quantity: int = Field(gt=0)
    supplier_id: uuid.UUID
    note: str | None = Field(default=None, max_length=500)


class StockAdjustIn(BaseModel):
    material_id: uuid.UUID
    delta: int
    note: str = Field(min_length=1, max_length=500)


class StockMinUpdate(BaseModel):
    min_stock: int = Field(ge=0)


class StockTransactionOut(APIModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    type: StockTransactionType
    quantity: int
    balance_after: int
    order_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None
    note: str | None = None
    created_at: datetime


# --- suppliers --------------------------------------------------------------


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    note: str | None = Field(default=None, max_length=500)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    phone_set: bool = False
    note: str | None = Field(default=None, max_length=500)
    note_set: bool = False


class SupplierOut(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    name: str
    phone: str | None = None
    note: str | None = None
    status: SupplierStatus
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
