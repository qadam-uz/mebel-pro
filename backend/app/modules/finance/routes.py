"""Workshop finance ledger and report routes."""

import re
import unicodedata
import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import ExpenseCategory, IncomeType, LedgerStatus, MoneyMethod
from app.modules.finance.api import (
    StatementPdfContext,
    create_adjustment,
    create_expense,
    create_income,
    finance_summary,
    get_client_statement,
    get_supplier_statement,
    income_response,
    income_responses,
    invoice_numbers_for,
    list_client_debts,
    list_expenses,
    list_incomes,
    list_payable_orders,
    list_payable_supplier_invoices,
    list_supplier_debts,
    recorded_by_names,
    render_statement_pdf_async,
    update_expense,
    update_income,
    void_adjustment,
    void_expense,
    void_income,
    worker_production,
)
from app.modules.finance.contracts import Expense
from app.modules.finance.schemas import (
    AdjustmentCreateRequest,
    CounterpartyAdjustmentResponse,
    DebtListResponse,
    DebtStatementResponse,
    ExpenseCreateRequest,
    ExpensePatchRequest,
    ExpenseResponse,
    FinanceSummaryResponse,
    IncomeCreateRequest,
    IncomePatchRequest,
    IncomeResponse,
    PayableInvoiceResponse,
    PayableOrderResponse,
    VoidLedgerRequest,
    WorkerProductionResponse,
)
from app.modules.finance.statement_pdf import StatementSide

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
    recorded_by_user_id: uuid.UUID | None = None,
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
        recorded_by_user_id=recorded_by_user_id,
        min_amount_tiyin=min_amount_tiyin,
        max_amount_tiyin=max_amount_tiyin,
    )
    return await income_responses(db, incomes=rows)


@router.get("/payable-orders", response_model=list[PayableOrderResponse])
async def payable_orders_index(
    principal: AccountReadyPrincipal,
    db: Session,
    branch_id: uuid.UUID | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PayableOrderResponse]:
    rows = await list_payable_orders(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        limit=limit,
    )
    return [PayableOrderResponse.model_validate(row) for row in rows]


@router.post("/income", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
async def income_create(
    payload: IncomeCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> IncomeResponse:
    row = await create_income(db, principal=principal, payload=payload)
    return await income_response(db, income=row)


@router.patch("/income/{income_id}", response_model=IncomeResponse)
async def income_update(
    income_id: uuid.UUID,
    payload: IncomePatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> IncomeResponse:
    row = await update_income(db, principal=principal, income_id=income_id, payload=payload)
    return await income_response(db, income=row)


@router.post("/income/{income_id}/void", response_model=IncomeResponse)
async def income_void(
    income_id: uuid.UUID,
    payload: VoidLedgerRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> IncomeResponse:
    row = await void_income(db, principal=principal, income_id=income_id, payload=payload)
    return await income_response(db, income=row)


@router.get("/expenses", response_model=list[ExpenseResponse])
async def expenses_index(
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
    category: ExpenseCategory | None = None,
    status_filter: LedgerStatusQuery = None,
    recorded_by_user_id: uuid.UUID | None = None,
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
        recorded_by_user_id=recorded_by_user_id,
        min_amount_tiyin=min_amount_tiyin,
        max_amount_tiyin=max_amount_tiyin,
    )
    return await _expense_responses(db, rows)


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def expenses_create(
    payload: ExpenseCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ExpenseResponse:
    row = await create_expense(db, principal=principal, payload=payload)
    return (await _expense_responses(db, [row]))[0]


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
async def expenses_update(
    expense_id: uuid.UUID,
    payload: ExpensePatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ExpenseResponse:
    row = await update_expense(db, principal=principal, expense_id=expense_id, payload=payload)
    return (await _expense_responses(db, [row]))[0]


@router.post("/expenses/{expense_id}/void", response_model=ExpenseResponse)
async def expenses_void(
    expense_id: uuid.UUID,
    payload: VoidLedgerRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ExpenseResponse:
    row = await void_expense(db, principal=principal, expense_id=expense_id, payload=payload)
    return (await _expense_responses(db, [row]))[0]


@router.get("/payable-invoices", response_model=list[PayableInvoiceResponse])
async def payable_invoices_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
) -> list[PayableInvoiceResponse]:
    return await list_payable_supplier_invoices(db, principal=principal, search=search)


@router.get("/debts/suppliers", response_model=DebtListResponse)
async def supplier_debts_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    only_with_debt: bool = True,
    branch_id: uuid.UUID | None = None,
) -> DebtListResponse:
    return await list_supplier_debts(
        db,
        principal=principal,
        search=search,
        only_with_debt=only_with_debt,
        branch_id=branch_id,
    )


@router.get("/debts/suppliers/{supplier_id}/statement", response_model=DebtStatementResponse)
async def supplier_debt_statement(
    supplier_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
) -> DebtStatementResponse:
    return await get_supplier_statement(
        db,
        principal=principal,
        supplier_id=supplier_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )


@router.get("/debts/suppliers/{supplier_id}/statement.pdf")
async def supplier_debt_statement_pdf(
    supplier_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
) -> Response:
    statement = await get_supplier_statement(
        db,
        principal=principal,
        supplier_id=supplier_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )
    return await _statement_pdf_response(statement, side="suppliers")


@router.get("/debts/clients", response_model=DebtListResponse)
async def client_debts_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    only_with_debt: bool = True,
    branch_id: uuid.UUID | None = None,
) -> DebtListResponse:
    return await list_client_debts(
        db,
        principal=principal,
        search=search,
        only_with_debt=only_with_debt,
        branch_id=branch_id,
    )


@router.get("/debts/clients/{client_id}/statement", response_model=DebtStatementResponse)
async def client_debt_statement(
    client_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
) -> DebtStatementResponse:
    return await get_client_statement(
        db,
        principal=principal,
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )


@router.get("/debts/clients/{client_id}/statement.pdf")
async def client_debt_statement_pdf(
    client_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
) -> Response:
    statement = await get_client_statement(
        db,
        principal=principal,
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )
    return await _statement_pdf_response(statement, side="clients")


@router.post(
    "/debts/adjustments",
    response_model=CounterpartyAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def adjustments_create(
    payload: AdjustmentCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CounterpartyAdjustmentResponse:
    row = await create_adjustment(db, principal=principal, payload=payload)
    return CounterpartyAdjustmentResponse.model_validate(row)


@router.post(
    "/debts/adjustments/{adjustment_id}/void",
    response_model=CounterpartyAdjustmentResponse,
)
async def adjustments_void(
    adjustment_id: uuid.UUID,
    payload: VoidLedgerRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CounterpartyAdjustmentResponse:
    row = await void_adjustment(
        db,
        principal=principal,
        adjustment_id=adjustment_id,
        payload=payload,
    )
    return CounterpartyAdjustmentResponse.model_validate(row)


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


async def _statement_pdf_response(
    statement: DebtStatementResponse, *, side: StatementSide
) -> Response:
    """The akt sverka as a file. Rendered in a worker thread, like the cutting maps."""

    slug = _ascii_slug(statement.name) or statement.counterparty_id.hex[:8]
    filename = f"akt-sverka-{slug}.pdf"
    return Response(
        await render_statement_pdf_async(statement, StatementPdfContext(side=side)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _ascii_slug(value: str) -> str:
    """A filename-safe stem. Uzbek names carry apostrophes and non-ASCII letters,
    which a bare `filename=` header cannot express — those characters drop out."""

    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()[:40]


async def _expense_responses(db: Session, rows: list[Expense]) -> list[ExpenseResponse]:
    """Expense rows plus the `K-…` label of the invoice each pays and who booked it."""

    numbers = await invoice_numbers_for(db, expenses=rows)
    names = await recorded_by_names(db, user_ids=(row.recorded_by_user_id for row in rows))
    return [
        ExpenseResponse.model_validate(row).model_copy(
            update={
                "invoice_no": numbers.get(row.invoice_id) if row.invoice_id else None,
                "recorded_by_name": names.get(row.recorded_by_user_id),
            }
        )
        for row in rows
    ]


def _period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    start = date_from or today.replace(day=1)
    end = date_to or today
    return start, end
