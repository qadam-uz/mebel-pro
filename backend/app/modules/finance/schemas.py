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
    receipt_file_id: uuid.UUID | None = None


class ExpensePatchRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    category: ExpenseCategory | None = None
    amount_tiyin: int | None = None
    incurred_on: date | None = None
    description: str | None = None
    vendor: str | None = None
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
