"""Finance ledger and report API schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import ExpenseCategory, IncomeType, LedgerStatus, MoneyMethod
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
    branch_id: uuid.UUID | None = None
    category: ExpenseCategory
    amount_tiyin: int
    incurred_on: date
    description: str
    vendor: str | None = None
    supplier_id: uuid.UUID | None = None
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
    voided_by_user_id: uuid.UUID | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime


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
    receipt_file_id: uuid.UUID | None
    status: LedgerStatus
    voided_reason: str | None
    recorded_by_user_id: uuid.UUID
    voided_by_user_id: uuid.UUID | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime


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

    supplier_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    amount_tiyin: int
    adjusted_on: date
    note: str


class CounterpartyAdjustmentResponse(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
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
    Optional detail fields depend on `kind`: deliveries carry material info,
    payments carry the money detail, orders carry the order number.
    """

    kind: str
    on: date
    at: datetime
    reference_id: uuid.UUID
    amount_tiyin: int
    balance_after_tiyin: int
    note: str | None = None
    material_name: str | None = None
    quantity: int | None = None
    display_unit: str | None = None
    category: ExpenseCategory | None = None
    method: MoneyMethod | None = None
    order_number: str | None = None


class DebtStatementResponse(APIModel):
    counterparty_id: uuid.UUID
    name: str
    phone: str | None
    date_from: date | None
    date_to: date | None
    opening_balance_tiyin: int
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
    user_id: uuid.UUID
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
