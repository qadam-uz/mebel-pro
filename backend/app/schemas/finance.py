"""Finance schemas — income, expense, reports."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    ExpenseCategory,
    IncomeType,
    LedgerStatus,
    PaymentMethod,
)
from app.schemas.common import APIModel

# --- income -----------------------------------------------------------------


class IncomeIn(BaseModel):
    type: IncomeType
    order_id: uuid.UUID | None = None
    amount_tiyin: int = Field(gt=0)
    method: PaymentMethod
    received_on: date
    branch_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)
    receipt_file_id: uuid.UUID | None = None


class IncomeEditIn(BaseModel):
    amount_tiyin: int | None = Field(default=None, gt=0)
    method: PaymentMethod | None = None
    received_on: date | None = None
    note: str | None = None
    note_set: bool = False


class VoidIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class IncomeOut(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    type: IncomeType
    order_id: uuid.UUID | None = None
    amount_tiyin: int
    method: PaymentMethod
    received_on: date
    note: str | None = None
    receipt_file_id: uuid.UUID | None = None
    status: LedgerStatus
    voided_reason: str | None = None
    recorded_by_user_id: uuid.UUID
    created_at: datetime


# --- expense ----------------------------------------------------------------


class ExpenseIn(BaseModel):
    category: ExpenseCategory
    amount_tiyin: int = Field(gt=0)
    incurred_on: date
    description: str = Field(min_length=1, max_length=500)
    branch_id: uuid.UUID | None = None
    vendor: str | None = Field(default=None, max_length=200)
    receipt_file_id: uuid.UUID | None = None


class ExpenseEditIn(BaseModel):
    category: ExpenseCategory | None = None
    amount_tiyin: int | None = Field(default=None, gt=0)
    incurred_on: date | None = None
    description: str | None = None
    vendor: str | None = None
    vendor_set: bool = False


class ExpenseOut(APIModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    category: ExpenseCategory
    amount_tiyin: int
    incurred_on: date
    description: str
    vendor: str | None = None
    receipt_file_id: uuid.UUID | None = None
    status: LedgerStatus
    voided_reason: str | None = None
    recorded_by_user_id: uuid.UUID
    created_at: datetime


# --- reports ----------------------------------------------------------------


class WorkerProductionRow(BaseModel):
    user_id: str
    sheets_cut: int
    cut_count: int
    orders_banded: int
    metres_by_thickness: dict[str, int]


class FinanceReportOut(BaseModel):
    period_start: str
    period_end: str
    income_total_tiyin: int
    income_order_payment_tiyin: int
    income_other_tiyin: int
    expense_total_tiyin: int
    expenses_by_category: dict[str, int]
    net_tiyin: int
    per_branch: dict[str, dict[str, int]]
