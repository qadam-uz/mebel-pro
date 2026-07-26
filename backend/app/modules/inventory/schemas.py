"""Inventory and supplier API schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import (
    InvoicePaymentStatus,
    MaterialKind,
    StockTransactionType,
    SupplierStatus,
)
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


class SupplierInvoiceLineInput(BaseModel):
    material_id: uuid.UUID
    quantity: int
    unit_price_tiyin: int
    note: str | None = None


class SupplierInvoiceCreateRequest(BaseModel):
    """One arrival document and every stock-in line on it, saved atomically."""

    branch_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    supplier: InlineSupplierInput | None = None
    invoice_date: date | None = None
    discount_tiyin: int = 0
    surcharge_tiyin: int = 0
    note: str | None = None
    lines: list[SupplierInvoiceLineInput]


class SupplierInvoiceLineResponse(APIModel):
    transaction_id: uuid.UUID
    material_id: uuid.UUID
    material_name: str
    kind: MaterialKind
    display_unit: str
    quantity: int
    unit_price_tiyin: int | None
    total_price_tiyin: int | None
    note: str | None


class SupplierInvoiceResponse(APIModel):
    """An invoice with its lines and its derived settlement position."""

    id: uuid.UUID
    workshop_id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    invoice_no: str
    invoice_date: date
    subtotal_tiyin: int
    discount_tiyin: int
    surcharge_tiyin: int
    total_tiyin: int
    note: str | None
    line_count: int
    paid_tiyin: int
    outstanding_tiyin: int
    payment_status: InvoicePaymentStatus
    recorded_by_user_id: uuid.UUID
    recorded_by_name: str | None
    created_at: datetime
    lines: list[SupplierInvoiceLineResponse]


class StockLastPriceResponse(APIModel):
    """Latest purchase price for a material in a branch — all fields null when never priced."""

    unit_price_tiyin: int | None
    recorded_at: datetime | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
