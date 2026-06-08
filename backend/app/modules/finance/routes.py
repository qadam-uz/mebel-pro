"""Workshop finance ledger and report routes."""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import ExpenseCategory, IncomeType, LedgerStatus, MoneyMethod
from app.modules.finance.api import (
    create_expense,
    create_income,
    finance_summary,
    list_expenses,
    list_incomes,
    update_expense,
    update_income,
    void_expense,
    void_income,
    worker_production,
)
from app.modules.finance.schemas import (
    ExpenseCreateRequest,
    ExpensePatchRequest,
    ExpenseResponse,
    FinanceSummaryResponse,
    IncomeCreateRequest,
    IncomePatchRequest,
    IncomeResponse,
    VoidLedgerRequest,
    WorkerProductionResponse,
)

router = APIRouter(prefix="/workshop/finance", tags=["finance"])
IncomeTypeQuery = Annotated[IncomeType | None, Query(alias="type")]
LedgerStatusQuery = Annotated[LedgerStatus | None, Query(alias="status")]


@router.get("/summary", response_model=FinanceSummaryResponse)
async def summary_show(
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
) -> FinanceSummaryResponse:
    start, end = _period(date_from, date_to)
    return await finance_summary(
        db,
        principal=principal,
        date_from=start,
        date_to=end,
        branch_id=branch_id,
    )


@router.get("/income", response_model=list[IncomeResponse])
async def income_index(
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
    income_type: IncomeTypeQuery = None,
    method: MoneyMethod | None = None,
    status_filter: LedgerStatusQuery = None,
    min_amount_tiyin: int | None = None,
    max_amount_tiyin: int | None = None,
) -> list[IncomeResponse]:
    start, end = _period(date_from, date_to)
    rows = await list_incomes(
        db,
        principal=principal,
        date_from=start,
        date_to=end,
        branch_id=branch_id,
        income_type=income_type,
        method=method,
        status_filter=status_filter,
        min_amount_tiyin=min_amount_tiyin,
        max_amount_tiyin=max_amount_tiyin,
    )
    return [IncomeResponse.model_validate(row) for row in rows]


@router.post("/income", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
async def income_create(
    payload: IncomeCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> IncomeResponse:
    row = await create_income(db, principal=principal, payload=payload)
    return IncomeResponse.model_validate(row)


@router.patch("/income/{income_id}", response_model=IncomeResponse)
async def income_update(
    income_id: uuid.UUID,
    payload: IncomePatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> IncomeResponse:
    row = await update_income(db, principal=principal, income_id=income_id, payload=payload)
    return IncomeResponse.model_validate(row)


@router.post("/income/{income_id}/void", response_model=IncomeResponse)
async def income_void(
    income_id: uuid.UUID,
    payload: VoidLedgerRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> IncomeResponse:
    row = await void_income(db, principal=principal, income_id=income_id, payload=payload)
    return IncomeResponse.model_validate(row)


@router.get("/expenses", response_model=list[ExpenseResponse])
async def expenses_index(
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
    category: ExpenseCategory | None = None,
    status_filter: LedgerStatusQuery = None,
    min_amount_tiyin: int | None = None,
    max_amount_tiyin: int | None = None,
) -> list[ExpenseResponse]:
    start, end = _period(date_from, date_to)
    rows = await list_expenses(
        db,
        principal=principal,
        date_from=start,
        date_to=end,
        branch_id=branch_id,
        category=category,
        status_filter=status_filter,
        min_amount_tiyin=min_amount_tiyin,
        max_amount_tiyin=max_amount_tiyin,
    )
    return [ExpenseResponse.model_validate(row) for row in rows]


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def expenses_create(
    payload: ExpenseCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ExpenseResponse:
    row = await create_expense(db, principal=principal, payload=payload)
    return ExpenseResponse.model_validate(row)


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
async def expenses_update(
    expense_id: uuid.UUID,
    payload: ExpensePatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ExpenseResponse:
    row = await update_expense(db, principal=principal, expense_id=expense_id, payload=payload)
    return ExpenseResponse.model_validate(row)


@router.post("/expenses/{expense_id}/void", response_model=ExpenseResponse)
async def expenses_void(
    expense_id: uuid.UUID,
    payload: VoidLedgerRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ExpenseResponse:
    row = await void_expense(db, principal=principal, expense_id=expense_id, payload=payload)
    return ExpenseResponse.model_validate(row)


@router.get("/production", response_model=WorkerProductionResponse)
async def production_show(
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
) -> WorkerProductionResponse:
    start, end = _period(date_from, date_to)
    return await worker_production(
        db,
        principal=principal,
        date_from=start,
        date_to=end,
        branch_id=branch_id,
    )


def _period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    start = date_from or today.replace(day=1)
    end = date_to or today
    return start, end
