"""Finance ledger and report use cases."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import status
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    AuthenticatedPrincipalType,
    ExpenseCategory,
    IncomeType,
    LedgerStatus,
    MoneyMethod,
    Permission,
)
from app.modules.access.api import BranchScope, resolve_branch_scope
from app.modules.finance.contracts import Expense, Income
from app.modules.finance.schemas import (
    ExpenseCreateRequest,
    ExpensePatchRequest,
    FinanceBranchSummary,
    FinanceDailyIncome,
    FinanceSummaryResponse,
    IncomeCreateRequest,
    IncomePatchRequest,
    VoidLedgerRequest,
    WorkerProductionEdgeLine,
    WorkerProductionResponse,
    WorkerProductionRow,
    WorkerProductionThicknessLine,
)
from app.modules.sales.api import get_order_finance_target, list_worker_production_records
from app.modules.support.api import (
    RECEIPT_CONTENT_TYPES,
    attach_file,
    record_action,
    record_status_change,
    replace_attached_file,
)


@dataclass(frozen=True)
class FinanceScope:
    workshop_id: uuid.UUID
    branch_ids: frozenset[uuid.UUID] | None


READ_PERMISSIONS = frozenset({Permission.MANAGE_FINANCE, Permission.VIEW_FINANCE_REPORTS})
WRITE_PERMISSIONS = frozenset({Permission.MANAGE_FINANCE})


async def list_incomes(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
    income_type: IncomeType | None = None,
    method: MoneyMethod | None = None,
    status_filter: LedgerStatus | None = None,
    min_amount_tiyin: int | None = None,
    max_amount_tiyin: int | None = None,
) -> list[Income]:
    _validate_amount_filters(min_amount_tiyin, max_amount_tiyin)
    scope = await _read_scope(db, principal=principal, branch_id=branch_id)
    query = (
        select(Income)
        .where(
            Income.workshop_id == scope.workshop_id,
            Income.received_on >= date_from,
            Income.received_on <= date_to,
        )
        .order_by(Income.received_on.desc(), Income.created_at.desc())
    )
    if scope.branch_ids is not None:
        branch_filter: ColumnElement[bool] = Income.branch_id.in_(scope.branch_ids)
        # Branch scoping must not hide workshop-level rows (branch IS NULL) from
        # the owner — HQ costs stay visible in every branch context.
        if principal.is_owner:
            branch_filter = or_(branch_filter, Income.branch_id.is_(None))
        query = query.where(branch_filter)
    if income_type is not None:
        query = query.where(Income.type == income_type)
    if method is not None:
        query = query.where(Income.method == method)
    if status_filter is not None:
        query = query.where(Income.status == status_filter)
    if min_amount_tiyin is not None:
        query = query.where(Income.amount_tiyin >= min_amount_tiyin)
    if max_amount_tiyin is not None:
        query = query.where(Income.amount_tiyin <= max_amount_tiyin)
    return list((await db.scalars(query)).all())


async def create_income(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: IncomeCreateRequest,
) -> Income:
    _positive_amount(payload.amount_tiyin)
    _not_future(payload.received_on)
    workshop_id = _workshop_principal_id(principal)
    branch_id = payload.branch_id
    order_id = payload.order_id
    if payload.type is IncomeType.ORDER_PAYMENT:
        if order_id is None:
            raise APIError("order_required", "Order payment income requires an order")
        target = await get_order_finance_target(
            db,
            principal=principal,
            order_id=order_id,
            permission=Permission.MANAGE_FINANCE,
        )
        if payload.branch_id is not None and payload.branch_id != target.branch_id:
            raise APIError("scope_mismatch", "Income branch does not match order branch")
        workshop_id = target.workshop_id
        branch_id = target.branch_id
        await _assert_order_payment_cap(
            db,
            order_id=order_id,
            amount_tiyin=payload.amount_tiyin,
            order_total_tiyin=target.total_tiyin,
        )
    else:
        if order_id is not None:
            raise APIError("order_not_allowed", "Only order payments may reference an order")
        await _write_scope(db, principal=principal, branch_id=branch_id)

    income = Income(
        workshop_id=workshop_id,
        branch_id=branch_id,
        type=payload.type,
        order_id=order_id,
        amount_tiyin=payload.amount_tiyin,
        method=payload.method,
        received_on=payload.received_on,
        note=_optional_text(payload.note),
        receipt_file_id=payload.receipt_file_id,
        status=LedgerStatus.RECORDED,
        recorded_by_user_id=principal.principal_id,
    )
    db.add(income)
    await db.flush()
    income.receipt_file_id = await attach_file(
        db,
        principal=principal,
        file_id=payload.receipt_file_id,
        entity_type="income",
        entity_id=income.id,
        allowed_content_types=RECEIPT_CONTENT_TYPES,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="finance.income.create",
        entity_type="income",
        entity_id=income.id,
        workshop_id=income.workshop_id,
        branch_id=income.branch_id,
        summary=f"Recorded income {income.amount_tiyin}",
        details={"type": income.type.value, "order_id": str(order_id) if order_id else None},
    )
    await db.refresh(income)
    return income


async def update_income(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    income_id: uuid.UUID,
    payload: IncomePatchRequest,
) -> Income:
    income = await _income_in_scope(db, principal=principal, income_id=income_id, mutate=True)
    _require_recorded(income.status)
    if income.type is IncomeType.ORDER_PAYMENT and payload.amount_tiyin is not None:
        target = await get_order_finance_target(
            db,
            principal=principal,
            order_id=_required_order_id(income),
            permission=Permission.MANAGE_FINANCE,
        )
        await _assert_order_payment_cap(
            db,
            order_id=target.order_id,
            amount_tiyin=payload.amount_tiyin,
            order_total_tiyin=target.total_tiyin,
            exclude_income_id=income.id,
        )
    if income.type is not IncomeType.ORDER_PAYMENT and "branch_id" in payload.model_fields_set:
        await _write_scope(db, principal=principal, branch_id=payload.branch_id)
        income.branch_id = payload.branch_id
    if payload.amount_tiyin is not None:
        _positive_amount(payload.amount_tiyin)
        income.amount_tiyin = payload.amount_tiyin
    if payload.method is not None:
        income.method = payload.method
    if payload.received_on is not None:
        _not_future(payload.received_on)
        income.received_on = payload.received_on
    if "note" in payload.model_fields_set:
        income.note = _optional_text(payload.note)
    if "receipt_file_id" in payload.model_fields_set:
        income.receipt_file_id = await replace_attached_file(
            db,
            principal=principal,
            file_id=payload.receipt_file_id,
            current_file_id=income.receipt_file_id,
            entity_type="income",
            entity_id=income.id,
            allowed_content_types=RECEIPT_CONTENT_TYPES,
        )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="finance.income.update",
        entity_type="income",
        entity_id=income.id,
        workshop_id=income.workshop_id,
        branch_id=income.branch_id,
        summary=f"Updated income {income.id}",
    )
    await db.flush()
    await db.refresh(income)
    return income


async def void_income(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    income_id: uuid.UUID,
    payload: VoidLedgerRequest,
) -> Income:
    income = await _income_in_scope(db, principal=principal, income_id=income_id, mutate=True)
    _require_recorded(income.status)
    reason = _required_text(payload.reason, "reason_required")
    from_status = income.status.value
    income.status = LedgerStatus.VOIDED
    income.voided_reason = reason
    income.voided_by_user_id = principal.principal_id
    income.voided_at = datetime.now(UTC)
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="finance.income.void",
        entity_type="income",
        entity_id=income.id,
        workshop_id=income.workshop_id,
        branch_id=income.branch_id,
        summary=f"Voided income {income.id}",
        details={"reason": reason},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="income",
        entity_id=income.id,
        workshop_id=income.workshop_id,
        branch_id=income.branch_id,
        from_status=from_status,
        to_status=income.status.value,
        reason=reason,
        action_log_id=action.id,
    )
    await db.flush()
    await db.refresh(income)
    return income


async def list_expenses(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
    category: ExpenseCategory | None = None,
    status_filter: LedgerStatus | None = None,
    min_amount_tiyin: int | None = None,
    max_amount_tiyin: int | None = None,
) -> list[Expense]:
    _validate_amount_filters(min_amount_tiyin, max_amount_tiyin)
    scope = await _read_scope(db, principal=principal, branch_id=branch_id)
    query = (
        select(Expense)
        .where(
            Expense.workshop_id == scope.workshop_id,
            Expense.incurred_on >= date_from,
            Expense.incurred_on <= date_to,
        )
        .order_by(Expense.incurred_on.desc(), Expense.created_at.desc())
    )
    if scope.branch_ids is not None:
        branch_filter: ColumnElement[bool] = Expense.branch_id.in_(scope.branch_ids)
        # Same owner rule as incomes: a branch context never hides HQ costs.
        if principal.is_owner:
            branch_filter = or_(branch_filter, Expense.branch_id.is_(None))
        query = query.where(branch_filter)
    if category is not None:
        query = query.where(Expense.category == category)
    if status_filter is not None:
        query = query.where(Expense.status == status_filter)
    if min_amount_tiyin is not None:
        query = query.where(Expense.amount_tiyin >= min_amount_tiyin)
    if max_amount_tiyin is not None:
        query = query.where(Expense.amount_tiyin <= max_amount_tiyin)
    return list((await db.scalars(query)).all())


async def create_expense(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: ExpenseCreateRequest,
) -> Expense:
    _positive_amount(payload.amount_tiyin)
    _not_future(payload.incurred_on)
    scope = await _write_scope(db, principal=principal, branch_id=payload.branch_id)
    expense = Expense(
        workshop_id=scope.workshop_id,
        branch_id=payload.branch_id,
        category=payload.category,
        amount_tiyin=payload.amount_tiyin,
        incurred_on=payload.incurred_on,
        description=_required_text(payload.description, "description_required"),
        vendor=_optional_text(payload.vendor),
        receipt_file_id=payload.receipt_file_id,
        status=LedgerStatus.RECORDED,
        recorded_by_user_id=principal.principal_id,
    )
    db.add(expense)
    await db.flush()
    expense.receipt_file_id = await attach_file(
        db,
        principal=principal,
        file_id=payload.receipt_file_id,
        entity_type="expense",
        entity_id=expense.id,
        allowed_content_types=RECEIPT_CONTENT_TYPES,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="finance.expense.create",
        entity_type="expense",
        entity_id=expense.id,
        workshop_id=expense.workshop_id,
        branch_id=expense.branch_id,
        summary=f"Recorded expense {expense.amount_tiyin}",
        details={"category": expense.category.value},
    )
    await db.refresh(expense)
    return expense


async def update_expense(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    expense_id: uuid.UUID,
    payload: ExpensePatchRequest,
) -> Expense:
    expense = await _expense_in_scope(db, principal=principal, expense_id=expense_id, mutate=True)
    _require_recorded(expense.status)
    if "branch_id" in payload.model_fields_set:
        await _write_scope(db, principal=principal, branch_id=payload.branch_id)
        expense.branch_id = payload.branch_id
    if payload.category is not None:
        expense.category = payload.category
    if payload.amount_tiyin is not None:
        _positive_amount(payload.amount_tiyin)
        expense.amount_tiyin = payload.amount_tiyin
    if payload.incurred_on is not None:
        _not_future(payload.incurred_on)
        expense.incurred_on = payload.incurred_on
    if payload.description is not None:
        expense.description = _required_text(payload.description, "description_required")
    if "vendor" in payload.model_fields_set:
        expense.vendor = _optional_text(payload.vendor)
    if "receipt_file_id" in payload.model_fields_set:
        expense.receipt_file_id = await replace_attached_file(
            db,
            principal=principal,
            file_id=payload.receipt_file_id,
            current_file_id=expense.receipt_file_id,
            entity_type="expense",
            entity_id=expense.id,
            allowed_content_types=RECEIPT_CONTENT_TYPES,
        )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="finance.expense.update",
        entity_type="expense",
        entity_id=expense.id,
        workshop_id=expense.workshop_id,
        branch_id=expense.branch_id,
        summary=f"Updated expense {expense.id}",
    )
    await db.flush()
    await db.refresh(expense)
    return expense


async def void_expense(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    expense_id: uuid.UUID,
    payload: VoidLedgerRequest,
) -> Expense:
    expense = await _expense_in_scope(db, principal=principal, expense_id=expense_id, mutate=True)
    _require_recorded(expense.status)
    reason = _required_text(payload.reason, "reason_required")
    from_status = expense.status.value
    expense.status = LedgerStatus.VOIDED
    expense.voided_reason = reason
    expense.voided_by_user_id = principal.principal_id
    expense.voided_at = datetime.now(UTC)
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="finance.expense.void",
        entity_type="expense",
        entity_id=expense.id,
        workshop_id=expense.workshop_id,
        branch_id=expense.branch_id,
        summary=f"Voided expense {expense.id}",
        details={"reason": reason},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="expense",
        entity_id=expense.id,
        workshop_id=expense.workshop_id,
        branch_id=expense.branch_id,
        from_status=from_status,
        to_status=expense.status.value,
        reason=reason,
        action_log_id=action.id,
    )
    await db.flush()
    await db.refresh(expense)
    return expense


async def finance_summary(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
) -> FinanceSummaryResponse:
    scope = await _read_scope(db, principal=principal, branch_id=branch_id)
    incomes = await list_incomes(
        db,
        principal=principal,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )
    expenses = await list_expenses(
        db,
        principal=principal,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )
    income_total = sum(row.amount_tiyin for row in incomes if row.status is LedgerStatus.RECORDED)
    expense_total = sum(row.amount_tiyin for row in expenses if row.status is LedgerStatus.RECORDED)
    income_by_type = {
        income_type: sum(
            row.amount_tiyin
            for row in incomes
            if row.status is LedgerStatus.RECORDED and row.type is income_type
        )
        for income_type in IncomeType
    }
    expense_by_category = {
        category: sum(
            row.amount_tiyin
            for row in expenses
            if row.status is LedgerStatus.RECORDED and row.category is category
        )
        for category in ExpenseCategory
    }
    branch_keys = {row.branch_id for row in incomes + expenses}
    if scope.branch_ids is not None:
        branch_keys &= set(scope.branch_ids)
    branches = [
        FinanceBranchSummary(
            branch_id=key,
            income_tiyin=sum(
                row.amount_tiyin
                for row in incomes
                if row.status is LedgerStatus.RECORDED and row.branch_id == key
            ),
            expense_tiyin=sum(
                row.amount_tiyin
                for row in expenses
                if row.status is LedgerStatus.RECORDED and row.branch_id == key
            ),
            net_tiyin=0,
        )
        for key in sorted(branch_keys, key=lambda value: str(value))
    ]
    branches = [
        FinanceBranchSummary(
            branch_id=row.branch_id,
            income_tiyin=row.income_tiyin,
            expense_tiyin=row.expense_tiyin,
            net_tiyin=row.income_tiyin - row.expense_tiyin,
        )
        for row in branches
    ]
    daily_income_by_date = {
        date_from + timedelta(days=offset): 0 for offset in range((date_to - date_from).days + 1)
    }
    for row in incomes:
        if row.status is LedgerStatus.RECORDED and row.received_on in daily_income_by_date:
            daily_income_by_date[row.received_on] += row.amount_tiyin
    return FinanceSummaryResponse(
        date_from=date_from,
        date_to=date_to,
        income_tiyin=income_total,
        expense_tiyin=expense_total,
        net_tiyin=income_total - expense_total,
        income_by_type=income_by_type,
        expense_by_category=expense_by_category,
        salary_expense_tiyin=expense_by_category[ExpenseCategory.SALARY],
        branches=branches,
        daily_income=[
            FinanceDailyIncome(day=day, income_tiyin=amount)
            for day, amount in daily_income_by_date.items()
        ],
    )


async def worker_production(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
) -> WorkerProductionResponse:
    scope = await _read_scope(db, principal=principal, branch_id=branch_id)
    records = await list_worker_production_records(
        db,
        workshop_id=scope.workshop_id,
        branch_ids=scope.branch_ids,
        date_from=date_from,
        date_to=date_to,
    )
    return WorkerProductionResponse(
        date_from=date_from,
        date_to=date_to,
        rows=[
            WorkerProductionRow(
                user_id=row.user_id,
                full_name=row.full_name,
                panels_cut=row.panels_cut,
                cut_count=row.cut_count,
                orders_banded=row.orders_banded,
                edge_length_by_material=row.edge_length_by_material,
                edge_lines=[
                    WorkerProductionEdgeLine(
                        material_id=line.material_id,
                        material_label=line.material_label,
                        thickness_mm=line.thickness_mm,
                        color=line.color,
                        length_mm=line.length_mm,
                    )
                    for line in row.edge_lines
                ],
                edge_length_by_thickness=[
                    WorkerProductionThicknessLine(
                        thickness_mm=_thickness_value(thickness),
                        length_mm=length,
                    )
                    for thickness, length in sorted(row.edge_length_by_thickness.items())
                ],
            )
            for row in records
        ],
    )


def _thickness_value(value: str) -> Decimal | None:
    if value == "unknown":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


async def _read_scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID | None,
) -> FinanceScope:
    return await _scope(db, principal=principal, branch_id=branch_id, permissions=READ_PERMISSIONS)


async def _write_scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID | None,
) -> FinanceScope:
    return await _scope(db, principal=principal, branch_id=branch_id, permissions=WRITE_PERMISSIONS)


async def _scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID | None,
    permissions: frozenset[Permission],
) -> FinanceScope:
    workshop_id = _workshop_principal_id(principal)
    if principal.is_owner:
        if branch_id is not None:
            branch_scope = await _resolve_branch_for_any_permission(
                db,
                principal=principal,
                branch_id=branch_id,
                workshop_id=workshop_id,
                permissions=permissions,
            )
            return FinanceScope(
                workshop_id=branch_scope.workshop_id,
                branch_ids=frozenset({branch_id}),
            )
        return FinanceScope(workshop_id=workshop_id, branch_ids=None)
    allowed = frozenset(
        grant.branch_id for grant in principal.grants if grant.permission in permissions
    )
    if branch_id is not None:
        if branch_id not in allowed:
            raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
        branch_scope = await _resolve_branch_for_any_permission(
            db,
            principal=principal,
            branch_id=branch_id,
            workshop_id=workshop_id,
            permissions=permissions,
        )
        return FinanceScope(workshop_id=branch_scope.workshop_id, branch_ids=frozenset({branch_id}))
    if not allowed:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    if permissions == WRITE_PERMISSIONS:
        raise APIError("branch_required", "Branch is required for staff finance entries")
    return FinanceScope(workshop_id=workshop_id, branch_ids=allowed)


async def _resolve_branch_for_any_permission(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    workshop_id: uuid.UUID,
    permissions: frozenset[Permission],
) -> BranchScope:
    last_error: APIError | None = None
    for permission in permissions:
        try:
            return await resolve_branch_scope(
                db,
                principal,
                branch_id=branch_id,
                permission=permission,
                claimed_workshop_id=workshop_id,
            )
        except APIError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


async def _income_in_scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    income_id: uuid.UUID,
    mutate: bool,
) -> Income:
    income = await db.get(Income, income_id)
    if income is None:
        raise APIError(
            "income_not_found",
            "Income not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    scope = await (_write_scope if mutate else _read_scope)(
        db,
        principal=principal,
        branch_id=income.branch_id,
    )
    if income.workshop_id != scope.workshop_id:
        raise APIError(
            "income_not_found",
            "Income not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return income


async def _expense_in_scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    expense_id: uuid.UUID,
    mutate: bool,
) -> Expense:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise APIError(
            "expense_not_found",
            "Expense not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    scope = await (_write_scope if mutate else _read_scope)(
        db,
        principal=principal,
        branch_id=expense.branch_id,
    )
    if expense.workshop_id != scope.workshop_id:
        raise APIError(
            "expense_not_found",
            "Expense not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return expense


async def _assert_order_payment_cap(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    amount_tiyin: int,
    order_total_tiyin: int,
    exclude_income_id: uuid.UUID | None = None,
) -> None:
    existing_query = select(func.coalesce(func.sum(Income.amount_tiyin), 0)).where(
        Income.order_id == order_id, Income.status == LedgerStatus.RECORDED
    )
    if exclude_income_id is not None:
        existing_query = existing_query.where(Income.id != exclude_income_id)
    existing = int(await db.scalar(existing_query) or 0)
    if existing + amount_tiyin > order_total_tiyin:
        raise APIError("order_payment_exceeds_total", "Order payment exceeds order total")


def _workshop_principal_id(principal: AuthenticatedPrincipal) -> uuid.UUID:
    if (
        principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER
        or principal.workshop_id is None
    ):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return principal.workshop_id


def _required_order_id(income: Income) -> uuid.UUID:
    if income.order_id is None:
        raise APIError("order_required", "Order payment income requires an order")
    return income.order_id


def _require_recorded(status_value: LedgerStatus) -> None:
    if status_value is not LedgerStatus.RECORDED:
        raise APIError("invalid_status", "Only recorded ledger rows can be changed")


def _positive_amount(value: int) -> None:
    if value <= 0:
        raise APIError("invalid_amount", "Amount must be positive")


def _not_future(value: date) -> None:
    # Ledger dates are picked in the actor's local calendar (the platform runs in
    # Uzbekistan, UTC+5), which can read a day ahead of UTC just after local
    # midnight. Compare against the furthest-ahead real-world local date (max TZ
    # offset is +14h) so a genuine same-day entry is never wrongly rejected as
    # "future"; a true future date (tomorrow onward, anywhere) is still refused.
    if value > (datetime.now(UTC) + timedelta(hours=14)).date():
        raise APIError("future_date_not_allowed", "Ledger date cannot be in the future")


def _validate_amount_filters(min_amount_tiyin: int | None, max_amount_tiyin: int | None) -> None:
    if min_amount_tiyin is not None:
        _positive_amount(min_amount_tiyin)
    if max_amount_tiyin is not None:
        _positive_amount(max_amount_tiyin)
    if (
        min_amount_tiyin is not None
        and max_amount_tiyin is not None
        and min_amount_tiyin > max_amount_tiyin
    ):
        raise APIError("invalid_amount_range", "Minimum amount cannot exceed maximum amount")


def _required_text(value: str, code: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise APIError(code, "Required field is missing")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None
