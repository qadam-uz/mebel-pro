"""Finance routes — income, expenses, worker-production + finance reports.

All under `/workshop/finance`. Mutating actions need ``manage_finance`` on the
relevant branch; reports/lists need ``view_finance_reports`` or ``manage_finance``.
Routes stay thin — logic lives in ``app.services.finance``.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentWorkshopUser, Session
from app.models.enums import ExpenseCategory, IncomeType, LedgerStatus
from app.schemas.finance import (
    ExpenseEditIn,
    ExpenseIn,
    ExpenseOut,
    FinanceReportOut,
    IncomeEditIn,
    IncomeIn,
    IncomeOut,
    VoidIn,
    WorkerProductionRow,
)
from app.services import finance as service

income_router = APIRouter()
expense_router = APIRouter()
report_router = APIRouter()


# --- income -----------------------------------------------------------------


@income_router.post("", response_model=IncomeOut, status_code=201)
async def record_income(body: IncomeIn, principal: CurrentWorkshopUser, db: Session) -> IncomeOut:
    income = await service.record_income(
        db,
        principal,
        type=body.type,
        order_id=body.order_id,
        amount_tiyin=body.amount_tiyin,
        method=body.method,
        received_on=body.received_on,
        branch_id=body.branch_id,
        note=body.note,
        receipt_file_id=body.receipt_file_id,
    )
    return IncomeOut.model_validate(income)


@income_router.get("", response_model=list[IncomeOut])
async def list_income(
    principal: CurrentWorkshopUser,
    db: Session,
    branch_id: uuid.UUID | None = None,
    type: IncomeType | None = None,
    status: LedgerStatus | None = None,
) -> list[IncomeOut]:
    rows = await service.list_income(db, principal, branch_id=branch_id, type=type, status=status)
    return [IncomeOut.model_validate(r) for r in rows]


@income_router.patch("/{income_id}", response_model=IncomeOut)
async def edit_income(
    income_id: uuid.UUID, body: IncomeEditIn, principal: CurrentWorkshopUser, db: Session
) -> IncomeOut:
    income = await service.edit_income(
        db,
        principal,
        income_id,
        amount_tiyin=body.amount_tiyin,
        method=body.method,
        received_on=body.received_on,
        note=body.note,
        note_set=body.note_set,
    )
    return IncomeOut.model_validate(income)


@income_router.post("/{income_id}/void", response_model=IncomeOut)
async def void_income(
    income_id: uuid.UUID, body: VoidIn, principal: CurrentWorkshopUser, db: Session
) -> IncomeOut:
    income = await service.void_income(db, principal, income_id, reason=body.reason)
    return IncomeOut.model_validate(income)


# --- expense ----------------------------------------------------------------


@expense_router.post("", response_model=ExpenseOut, status_code=201)
async def record_expense(
    body: ExpenseIn, principal: CurrentWorkshopUser, db: Session
) -> ExpenseOut:
    expense = await service.record_expense(
        db,
        principal,
        category=body.category,
        amount_tiyin=body.amount_tiyin,
        incurred_on=body.incurred_on,
        description=body.description,
        branch_id=body.branch_id,
        vendor=body.vendor,
        receipt_file_id=body.receipt_file_id,
    )
    return ExpenseOut.model_validate(expense)


@expense_router.get("", response_model=list[ExpenseOut])
async def list_expense(
    principal: CurrentWorkshopUser,
    db: Session,
    branch_id: uuid.UUID | None = None,
    category: ExpenseCategory | None = None,
    status: LedgerStatus | None = None,
) -> list[ExpenseOut]:
    rows = await service.list_expense(
        db, principal, branch_id=branch_id, category=category, status=status
    )
    return [ExpenseOut.model_validate(r) for r in rows]


@expense_router.patch("/{expense_id}", response_model=ExpenseOut)
async def edit_expense(
    expense_id: uuid.UUID, body: ExpenseEditIn, principal: CurrentWorkshopUser, db: Session
) -> ExpenseOut:
    expense = await service.edit_expense(
        db,
        principal,
        expense_id,
        category=body.category,
        amount_tiyin=body.amount_tiyin,
        incurred_on=body.incurred_on,
        description=body.description,
        vendor=body.vendor,
        vendor_set=body.vendor_set,
    )
    return ExpenseOut.model_validate(expense)


@expense_router.post("/{expense_id}/void", response_model=ExpenseOut)
async def void_expense(
    expense_id: uuid.UUID, body: VoidIn, principal: CurrentWorkshopUser, db: Session
) -> ExpenseOut:
    expense = await service.void_expense(db, principal, expense_id, reason=body.reason)
    return ExpenseOut.model_validate(expense)


# --- reports ----------------------------------------------------------------


@report_router.get("/production", response_model=list[WorkerProductionRow])
async def worker_production(
    principal: CurrentWorkshopUser,
    db: Session,
    period_start: date,
    period_end: date,
    branch_id: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> list[WorkerProductionRow]:
    rows = await service.worker_production_report(
        db,
        principal,
        period_start=period_start,
        period_end=period_end,
        branch_ids=branch_id,
    )
    return [WorkerProductionRow(**r) for r in rows]


@report_router.get("/report", response_model=FinanceReportOut)
async def finance_report(
    principal: CurrentWorkshopUser,
    db: Session,
    period_start: date,
    period_end: date,
    branch_id: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> FinanceReportOut:
    report = await service.finance_report(
        db,
        principal,
        period_start=period_start,
        period_end=period_end,
        branch_ids=branch_id,
    )
    return FinanceReportOut(**report)
