"""Finance ledger and report API schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import (
    ExpenseCategory,
    IncomeType,
    InvoicePaymentStatus,
    LedgerStatus,
    MoneyMethod,
    OrderStatus,
)
from app.schemas.common import APIModel


class IncomeCreateRequest(BaseModel):
    type: IncomeType
    branch_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    amount_tiyin: int
    method: MoneyMethod
    received_on: date
    note: str | None = None
    receipt_file_id: uuid.UUID | None = None


class IncomePatchRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    amount_tiyin: int | None = None
    method: MoneyMethod | None = None
    received_on: date | None = None
    note: str | None = None
    receipt_file_id: uuid.UUID | None = None


class ExpenseCreateRequest(BaseModel):
    """A cost. With `invoice_id` set it is a payment against a supplier faktura,
    and supplier + branch are taken from the invoice, not from the caller."""

    branch_id: uuid.UUID | None = None
    category: ExpenseCategory
    amount_tiyin: int
    incurred_on: date
    description: str
    vendor: str | None = None
    supplier_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    receipt_file_id: uuid.UUID | None = None


class ExpensePatchRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    category: ExpenseCategory | None = None
    amount_tiyin: int | None = None
    incurred_on: date | None = None
    description: str | None = None
    vendor: str | None = None
    supplier_id: uuid.UUID | None = None
    receipt_file_id: uuid.UUID | None = None


class VoidLedgerRequest(BaseModel):
    reason: str


class IncomeOrderRef(APIModel):
    """The order an order-payment income points at, resolved on the income row.

    Carried here so the ledger and the edit form never read the order back
    through `sales`: that read is gated on order permissions the accountant
    doesn't hold, and a settled order can never reappear in the payable-orders
    picker to supply its own label.
    """

    order_id: uuid.UUID
    order_number: str
    contact_name: str
    total_tiyin: int
    recorded_tiyin: int
    balance_tiyin: int


class IncomeResponse(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    branch_id: uuid.UUID | None
    type: IncomeType
    order_id: uuid.UUID | None
    amount_tiyin: int
    method: MoneyMethod
    received_on: date
    note: str | None
    receipt_file_id: uuid.UUID | None
    status: LedgerStatus
    voided_reason: str | None
    recorded_by_user_id: uuid.UUID
    # Who handled the money — resolved at read time, never stored twice.
    recorded_by_name: str | None = None
    voided_by_user_id: uuid.UUID | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Null for a non-order income, and for the (unreachable) case of an order
    # that no longer resolves — the client falls back to the raw id there.
    order: IncomeOrderRef | None = None


class ExpenseResponse(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    branch_id: uuid.UUID | None
    category: ExpenseCategory
    amount_tiyin: int
    incurred_on: date
    description: str
    vendor: str | None
    supplier_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    invoice_no: str | None = None
    receipt_file_id: uuid.UUID | None
    status: LedgerStatus
    voided_reason: str | None
    recorded_by_user_id: uuid.UUID
    # Who handled the money — resolved at read time, never stored twice.
    recorded_by_name: str | None = None
    voided_by_user_id: uuid.UUID | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PayableInvoiceResponse(APIModel):
    """One row of the expense form's invoice picker — what is still owed on it."""

    id: uuid.UUID
    invoice_no: str
    invoice_date: date
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    branch_id: uuid.UUID
    branch_name: str | None
    line_count: int
    total_tiyin: int
    paid_tiyin: int
    outstanding_tiyin: int
    payment_status: InvoicePaymentStatus


class PayableOrderResponse(APIModel):
    """One order-payment candidate, with its settlement already folded in.

    `balance_tiyin` is the number the operator acts on; `total` and `recorded`
    are shown beside it so the figure can be checked without opening the order.
    """

    order_id: uuid.UUID
    order_number: str
    contact_name: str
    contact_phone: str
    status: OrderStatus
    created_at: datetime
    total_tiyin: int
    recorded_tiyin: int
    balance_tiyin: int


class FinanceBranchSummary(APIModel):
    branch_id: uuid.UUID | None
    income_tiyin: int
    expense_tiyin: int
    net_tiyin: int


class FinanceDailyIncome(APIModel):
    day: date
    income_tiyin: int


class FinanceSummaryResponse(APIModel):
    date_from: date
    date_to: date
    income_tiyin: int
    expense_tiyin: int
    net_tiyin: int
    income_by_type: dict[IncomeType, int]
    expense_by_category: dict[ExpenseCategory, int]
    salary_expense_tiyin: int
    branches: list[FinanceBranchSummary]
    daily_income: list[FinanceDailyIncome]


class AdjustmentCreateRequest(BaseModel):
    """A signed debt correction against exactly one counterparty.

    Sign convention: positive = they owe us more, negative = we owe them more.
    """

    branch_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    amount_tiyin: int
    adjusted_on: date
    note: str


class CounterpartyAdjustmentResponse(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    branch_id: uuid.UUID
    supplier_id: uuid.UUID | None
    client_id: uuid.UUID | None
    amount_tiyin: int
    adjusted_on: date
    note: str
    status: LedgerStatus
    voided_reason: str | None
    recorded_by_user_id: uuid.UUID
    voided_by_user_id: uuid.UUID | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DebtRow(APIModel):
    """One counterparty's derived balance. Positive = they owe us."""

    counterparty_id: uuid.UUID
    name: str
    phone: str | None
    inactive: bool
    balance_tiyin: int


class DebtListResponse(APIModel):
    rows: list[DebtRow]
    we_owe_total_tiyin: int
    they_owe_total_tiyin: int


class DebtStatementRow(APIModel):
    """One dated statement line with the running balance after it.

    `amount_tiyin` is the signed fold term (positive = their debt grew).
    Optional detail fields depend on `kind`: deliveries carry the invoice
    (number, line count, and the document's own skidka/ustama), payments carry
    the money detail, orders carry the order number.
    """

    kind: str
    on: date
    at: datetime
    reference_id: uuid.UUID
    amount_tiyin: int
    balance_after_tiyin: int
    note: str | None = None
    invoice_no: str | None = None
    line_count: int | None = None
    discount_tiyin: int | None = None
    surcharge_tiyin: int | None = None
    category: ExpenseCategory | None = None
    method: MoneyMethod | None = None
    order_number: str | None = None


class DebtStatementResponse(APIModel):
    """An akt sverka: both parties, the period, and the fold that spans it.

    Sign convention throughout: positive = they owe us. `period_increase_tiyin`
    sums the in-range terms that grew their debt, `period_decrease_tiyin` the
    absolute value of those that shrank it — the two turnover columns of the
    document, before either side's wording is applied to them.
    """

    counterparty_id: uuid.UUID
    name: str
    phone: str | None
    # Our side of the reconciliation. A statement is workshop-level, so the
    # phone is the primary branch's — the workshop record carries no number.
    workshop_name: str
    workshop_phone: str | None
    date_from: date | None
    date_to: date | None
    opening_balance_tiyin: int
    period_increase_tiyin: int
    period_decrease_tiyin: int
    closing_balance_tiyin: int
    current_balance_tiyin: int
    rows: list[DebtStatementRow]


class WorkerProductionEdgeLine(APIModel):
    material_id: uuid.UUID
    material_label: str
    thickness_mm: Decimal | None = None
    color: str | None = None
    length_mm: int


class WorkerProductionThicknessLine(APIModel):
    thickness_mm: Decimal | None = None
    length_mm: int


class WorkerProductionRow(APIModel):
    # Null on the unassigned bucket — the volume a simple-mode order recorded
    # with nobody credited (orders.md). It is a bucket, not a worker: it carries
    # no user to pay, and the client labels it from the null id.
    user_id: uuid.UUID | None
    full_name: str
    panels_cut: int
    cut_count: int
    orders_banded: int
    edge_length_by_material: dict[str, int]
    edge_lines: list[WorkerProductionEdgeLine]
    edge_length_by_thickness: list[WorkerProductionThicknessLine]


class WorkerProductionResponse(APIModel):
    date_from: date
    date_to: date
    rows: list[WorkerProductionRow]
