"""Inventory and supplier API schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    DecorType,
    InvoicePaymentStatus,
    LedgerStatus,
    StockTransactionType,
    SupplierStatus,
)
from app.modules.catalog.schemas import BranchMaterialResponse
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
    branch_material_id: uuid.UUID
    quantity: int
    unit_price_tiyin: int
    supplier_id: uuid.UUID | None = None
    supplier: InlineSupplierInput | None = None
    note: str | None = None


class StockAdjustmentRequest(BaseModel):
    branch_material_id: uuid.UUID
    quantity: int
    note: str


class StockMinStockRequest(BaseModel):
    """The low-stock threshold, in the material's stock unit. `0` = monitoring off.

    Deliberately no `ge=0` constraint: a negative value earns the named
    `min_stock_invalid` code from the module rather than a shapeless 422, so the
    client can say what is wrong in the operator's language.
    """

    min_stock: int


class StockItemResponse(APIModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_material_id: uuid.UUID
    # The branch's own format of a decor — identity nested under `.decor`. There
    # is no stored name, so the display string arrives as `material.label`.
    material: BranchMaterialResponse
    type: DecorType
    stock_unit: str
    display_unit: str
    on_hand: int
    min_stock: int
    is_low_stock: bool
    updated_at: datetime


class StockTransactionResponse(APIModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    branch_material_id: uuid.UUID
    # Computed label, not a stored column — see app/core/material_label.py.
    material_name: str
    type: StockTransactionType
    quantity: int
    balance_after: int
    unit_price_tiyin: int | None
    total_price_tiyin: int | None
    order_id: uuid.UUID | None
    # The order's own `2026-000123` number — a movement's context has to be a
    # document the reader can recognise and open, not an id prefix.
    order_number: str | None
    # The arrival document a stock-in (or its void reversal) belongs to — the
    # transactions tab deep-links to the invoice detail through it, showing the
    # `K-…` so the link names the document instead of an opaque id.
    invoice_id: uuid.UUID | None
    invoice_no: str | None
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
    branch_material_id: uuid.UUID
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


class SupplierInvoicePatchRequest(BaseModel):
    """The correction an invoice accepts — its header, and optionally its lines.

    `extra="forbid"` is the contract, not defensiveness: a client sending a
    field this endpoint no longer honours (`note`, `discount_tiyin`,
    `surcharge_tiyin` — dropped from the UI) must be told the request is wrong
    rather than have it silently ignored while the rest saves.

    `lines` omitted = a header-only edit. `lines` present = the **full desired
    line set**; the invoice's stock-in rows are rewritten to match it.
    """

    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID | None = None
    invoice_date: date | None = None
    lines: list[SupplierInvoiceLineInput] | None = None


class SupplierInvoiceVoidRequest(BaseModel):
    reason: str


class SupplierInvoiceLineResponse(APIModel):
    transaction_id: uuid.UUID
    branch_material_id: uuid.UUID
    material_name: str
    type: DecorType
    display_unit: str
    quantity: int
    unit_price_tiyin: int | None
    total_price_tiyin: int | None
    note: str | None


class SupplierInvoicePaymentResponse(APIModel):
    """One expense booked against the invoice — voided ones included.

    A disputed document is read with its whole story, so a payment that was
    itself voided still shows, tagged rather than hidden.
    """

    expense_id: uuid.UUID
    spent_on: date
    amount_tiyin: int
    status: LedgerStatus


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
    status: LedgerStatus
    voided_reason: str | None
    voided_at: datetime | None
    voided_by_name: str | None
    recorded_by_user_id: uuid.UUID
    recorded_by_name: str | None
    created_at: datetime
    lines: list[SupplierInvoiceLineResponse]
    # Only the single-invoice read fills this — the list never needs it.
    payments: list[SupplierInvoicePaymentResponse] = Field(default_factory=list)


class StockLastPriceResponse(APIModel):
    """Latest purchase price for a material in a branch — all fields null when never priced."""

    unit_price_tiyin: int | None
    recorded_at: datetime | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
