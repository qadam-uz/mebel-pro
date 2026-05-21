"""Finance — the workshop money ledger: income, expenses, and reports.

v1 tracks money, never moves it. An accountant (``manage_finance``) records each
income and expense by hand; the reports recompute over a period (so a void shows
up immediately). Worker-production reports read straight from the order
production stamps. All money is integer tiyin.

Order settlement helpers (``order_paid_total`` / ``order_balance``) are imported
by the orders read layer. Spec: docs/ref/features/finance.md,
docs/ref/entities/finance.md.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, bad_request, forbidden, not_found
from app.core.principal import Principal
from app.models.enums import (
    ExpenseCategory,
    IncomeType,
    LedgerStatus,
    PaymentMethod,
    Permission,
)
from app.models.finance import Expense, Income
from app.models.sales import Order
from app.models.workshop import Branch
from app.services import audit

# --- access helpers ---------------------------------------------------------


def _require_manage_finance_anywhere(principal: Principal) -> None:
    if principal.is_owner:
        return
    if not any(p is Permission.MANAGE_FINANCE for (p, _b) in principal.grants):
        raise forbidden()


def _require_finance_read_anywhere(principal: Principal) -> None:
    if principal.is_owner:
        return
    grants = {p for (p, _b) in principal.grants}
    if Permission.MANAGE_FINANCE not in grants and Permission.VIEW_FINANCE_REPORTS not in grants:
        raise forbidden()


def _require_manage_finance_branch(principal: Principal, branch_id: uuid.UUID | None) -> None:
    """manage_finance on the relevant branch (or workshop-wide for the owner)."""
    if principal.is_owner:
        return
    if branch_id is None:
        # workshop-level money: need manage_finance somewhere
        _require_manage_finance_anywhere(principal)
        return
    if not principal.has_permission(Permission.MANAGE_FINANCE, branch_id):
        raise forbidden()


async def _branch_in_workshop(
    db: AsyncSession, workshop_id: uuid.UUID, branch_id: uuid.UUID | None
) -> None:
    if branch_id is None:
        return
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.workshop_id != workshop_id:
        raise not_found("Branch not found.")


def _not_future(d: date, label: str) -> None:
    if d > datetime.now(UTC).date():
        raise bad_request(f"{label} can't be in the future.", code="date_in_future")


# --- order settlement (imported by the orders read layer) -------------------


async def order_paid_total(db: AsyncSession, order_id: uuid.UUID) -> int:
    """Σ of an order's ``recorded`` ``order_payment`` incomes (integer tiyin)."""
    total = (
        await db.execute(
            select(func.coalesce(func.sum(Income.amount_tiyin), 0)).where(
                Income.order_id == order_id,
                Income.type == IncomeType.ORDER_PAYMENT,
                Income.status == LedgerStatus.RECORDED,
            )
        )
    ).scalar_one()
    return int(total or 0)


async def order_balance(db: AsyncSession, order: Order) -> int:
    return int(order.total_tiyin) - await order_paid_total(db, order.id)


# --- income (manage_finance) ------------------------------------------------


async def record_income(
    db: AsyncSession,
    principal: Principal,
    *,
    type: IncomeType,
    order_id: uuid.UUID | None,
    amount_tiyin: int,
    method: PaymentMethod,
    received_on: date,
    branch_id: uuid.UUID | None = None,
    note: str | None = None,
    receipt_file_id: uuid.UUID | None = None,
) -> Income:
    assert principal.workshop_id is not None
    if amount_tiyin <= 0:
        raise bad_request("Amount must be > 0.", code="invalid_amount")
    _not_future(received_on, "received_on")

    if type is IncomeType.ORDER_PAYMENT:
        if order_id is None:
            raise bad_request("order_payment requires an order_id.", code="order_required")
        order = await db.get(Order, order_id)
        if order is None or order.workshop_id != principal.workshop_id:
            raise not_found("Order not found.")
        branch_id = order.branch_id  # the order's branch is authoritative
        _require_manage_finance_branch(principal, branch_id)
        # running sum of recorded order_payment ≤ order.total_tiyin
        already = await order_paid_total(db, order_id)
        if already + amount_tiyin > order.total_tiyin:
            raise AppError(
                "payment_exceeds_total",
                "This payment would exceed the order total.",
                status_code=409,
            )
    else:
        if order_id is not None:
            raise bad_request("Only order_payment carries an order_id.", code="order_not_allowed")
        await _branch_in_workshop(db, principal.workshop_id, branch_id)
        _require_manage_finance_branch(principal, branch_id)

    income = Income(
        workshop_id=principal.workshop_id,
        branch_id=branch_id,
        type=type,
        order_id=order_id,
        amount_tiyin=amount_tiyin,
        method=method,
        received_on=received_on,
        note=note.strip() if note else None,
        receipt_file_id=receipt_file_id,
        status=LedgerStatus.RECORDED,
        recorded_by_user_id=principal.id,
    )
    db.add(income)
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="income.recorded",
        entity_type="income",
        entity_id=income.id,
        workshop_id=principal.workshop_id,
        branch_id=branch_id,
        details={"amount_tiyin": amount_tiyin, "type": type.value},
    )
    await db.refresh(income)
    return income


async def _owned_income(db: AsyncSession, principal: Principal, income_id: uuid.UUID) -> Income:
    income = await db.get(Income, income_id)
    if income is None or income.workshop_id != principal.workshop_id:
        raise not_found("Income not found.")
    return income


async def edit_income(
    db: AsyncSession,
    principal: Principal,
    income_id: uuid.UUID,
    *,
    amount_tiyin: int | None = None,
    method: PaymentMethod | None = None,
    received_on: date | None = None,
    note: str | None = None,
    note_set: bool = False,
) -> Income:
    income = await _owned_income(db, principal, income_id)
    _require_manage_finance_branch(principal, income.branch_id)
    if income.status is not LedgerStatus.RECORDED:
        raise bad_request("Only a recorded income can be edited.", code="not_editable")
    if amount_tiyin is not None:
        if amount_tiyin <= 0:
            raise bad_request("Amount must be > 0.", code="invalid_amount")
        if income.type is IncomeType.ORDER_PAYMENT and income.order_id is not None:
            order = await db.get(Order, income.order_id)
            if order is not None:
                others = await order_paid_total(db, income.order_id) - income.amount_tiyin
                if others + amount_tiyin > order.total_tiyin:
                    raise AppError(
                        "payment_exceeds_total",
                        "This change would exceed the order total.",
                        status_code=409,
                    )
        income.amount_tiyin = amount_tiyin
    if method is not None:
        income.method = method
    if received_on is not None:
        _not_future(received_on, "received_on")
        income.received_on = received_on
    if note_set:
        income.note = note.strip() if note else None
    await audit.record_action(
        db,
        actor=principal,
        action="income.edited",
        entity_type="income",
        entity_id=income.id,
        workshop_id=principal.workshop_id,
        branch_id=income.branch_id,
    )
    await db.refresh(income)
    return income


async def void_income(
    db: AsyncSession, principal: Principal, income_id: uuid.UUID, *, reason: str
) -> Income:
    income = await _owned_income(db, principal, income_id)
    _require_manage_finance_branch(principal, income.branch_id)
    if not reason or not reason.strip():
        raise bad_request("A void requires a reason.", code="reason_required")
    if income.status is LedgerStatus.VOIDED:
        raise bad_request("Income is already voided.", code="already_voided")
    from_status = income.status
    income.status = LedgerStatus.VOIDED
    income.voided_reason = reason.strip()
    income.voided_by_user_id = principal.id
    income.voided_at = datetime.now(UTC)
    await db.flush()
    log = await audit.record_action(
        db,
        actor=principal,
        action="income.voided",
        entity_type="income",
        entity_id=income.id,
        workshop_id=principal.workshop_id,
        branch_id=income.branch_id,
        summary=reason.strip(),
    )
    await audit.record_status_change(
        db,
        entity_type="income",
        entity_id=income.id,
        from_status=from_status.value,
        to_status=income.status.value,
        actor=principal,
        workshop_id=principal.workshop_id,
        branch_id=income.branch_id,
        reason=reason.strip(),
        action_log_id=log.id,
    )
    await db.refresh(income)
    return income


# --- expense (manage_finance) -----------------------------------------------


async def record_expense(
    db: AsyncSession,
    principal: Principal,
    *,
    category: ExpenseCategory,
    amount_tiyin: int,
    incurred_on: date,
    description: str,
    branch_id: uuid.UUID | None = None,
    vendor: str | None = None,
    receipt_file_id: uuid.UUID | None = None,
) -> Expense:
    assert principal.workshop_id is not None
    if amount_tiyin <= 0:
        raise bad_request("Amount must be > 0.", code="invalid_amount")
    if not description or not description.strip():
        raise bad_request("A description is required.", code="description_required")
    _not_future(incurred_on, "incurred_on")
    await _branch_in_workshop(db, principal.workshop_id, branch_id)
    _require_manage_finance_branch(principal, branch_id)

    expense = Expense(
        workshop_id=principal.workshop_id,
        branch_id=branch_id,
        category=category,
        amount_tiyin=amount_tiyin,
        incurred_on=incurred_on,
        description=description.strip(),
        vendor=vendor.strip() if vendor else None,
        receipt_file_id=receipt_file_id,
        status=LedgerStatus.RECORDED,
        recorded_by_user_id=principal.id,
    )
    db.add(expense)
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="expense.recorded",
        entity_type="expense",
        entity_id=expense.id,
        workshop_id=principal.workshop_id,
        branch_id=branch_id,
        details={"amount_tiyin": amount_tiyin, "category": category.value},
    )
    await db.refresh(expense)
    return expense


async def _owned_expense(db: AsyncSession, principal: Principal, expense_id: uuid.UUID) -> Expense:
    expense = await db.get(Expense, expense_id)
    if expense is None or expense.workshop_id != principal.workshop_id:
        raise not_found("Expense not found.")
    return expense


async def edit_expense(
    db: AsyncSession,
    principal: Principal,
    expense_id: uuid.UUID,
    *,
    category: ExpenseCategory | None = None,
    amount_tiyin: int | None = None,
    incurred_on: date | None = None,
    description: str | None = None,
    vendor: str | None = None,
    vendor_set: bool = False,
) -> Expense:
    expense = await _owned_expense(db, principal, expense_id)
    _require_manage_finance_branch(principal, expense.branch_id)
    if expense.status is not LedgerStatus.RECORDED:
        raise bad_request("Only a recorded expense can be edited.", code="not_editable")
    if category is not None:
        expense.category = category
    if amount_tiyin is not None:
        if amount_tiyin <= 0:
            raise bad_request("Amount must be > 0.", code="invalid_amount")
        expense.amount_tiyin = amount_tiyin
    if incurred_on is not None:
        _not_future(incurred_on, "incurred_on")
        expense.incurred_on = incurred_on
    if description is not None:
        if not description.strip():
            raise bad_request("A description is required.", code="description_required")
        expense.description = description.strip()
    if vendor_set:
        expense.vendor = vendor.strip() if vendor else None
    await audit.record_action(
        db,
        actor=principal,
        action="expense.edited",
        entity_type="expense",
        entity_id=expense.id,
        workshop_id=principal.workshop_id,
        branch_id=expense.branch_id,
    )
    await db.refresh(expense)
    return expense


async def void_expense(
    db: AsyncSession, principal: Principal, expense_id: uuid.UUID, *, reason: str
) -> Expense:
    expense = await _owned_expense(db, principal, expense_id)
    _require_manage_finance_branch(principal, expense.branch_id)
    if not reason or not reason.strip():
        raise bad_request("A void requires a reason.", code="reason_required")
    if expense.status is LedgerStatus.VOIDED:
        raise bad_request("Expense is already voided.", code="already_voided")
    from_status = expense.status
    expense.status = LedgerStatus.VOIDED
    expense.voided_reason = reason.strip()
    expense.voided_by_user_id = principal.id
    expense.voided_at = datetime.now(UTC)
    await db.flush()
    log = await audit.record_action(
        db,
        actor=principal,
        action="expense.voided",
        entity_type="expense",
        entity_id=expense.id,
        workshop_id=principal.workshop_id,
        branch_id=expense.branch_id,
        summary=reason.strip(),
    )
    await audit.record_status_change(
        db,
        entity_type="expense",
        entity_id=expense.id,
        from_status=from_status.value,
        to_status=expense.status.value,
        actor=principal,
        workshop_id=principal.workshop_id,
        branch_id=expense.branch_id,
        reason=reason.strip(),
        action_log_id=log.id,
    )
    await db.refresh(expense)
    return expense


# --- list reads -------------------------------------------------------------


def _accessible_branches_filter(principal: Principal) -> set[uuid.UUID] | None:
    """None = owner (all). Otherwise the branch ids the principal can see finance on."""
    if principal.is_owner:
        return None
    return {
        b
        for (p, b) in principal.grants
        if p in (Permission.MANAGE_FINANCE, Permission.VIEW_FINANCE_REPORTS)
    }


async def list_income(
    db: AsyncSession,
    principal: Principal,
    *,
    branch_id: uuid.UUID | None = None,
    type: IncomeType | None = None,
    status: LedgerStatus | None = None,
) -> list[Income]:
    _require_finance_read_anywhere(principal)
    assert principal.workshop_id is not None
    stmt = select(Income).where(Income.workshop_id == principal.workshop_id)
    accessible = _accessible_branches_filter(principal)
    if accessible is not None:
        if not accessible:
            return []
        stmt = stmt.where(Income.branch_id.in_(accessible))
    if branch_id is not None:
        stmt = stmt.where(Income.branch_id == branch_id)
    if type is not None:
        stmt = stmt.where(Income.type == type)
    if status is not None:
        stmt = stmt.where(Income.status == status)
    stmt = stmt.order_by(Income.received_on.desc(), Income.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def list_expense(
    db: AsyncSession,
    principal: Principal,
    *,
    branch_id: uuid.UUID | None = None,
    category: ExpenseCategory | None = None,
    status: LedgerStatus | None = None,
) -> list[Expense]:
    _require_finance_read_anywhere(principal)
    assert principal.workshop_id is not None
    stmt = select(Expense).where(Expense.workshop_id == principal.workshop_id)
    accessible = _accessible_branches_filter(principal)
    if accessible is not None:
        if not accessible:
            return []
        # workshop-level (branch_id is null) expenses are visible to non-owners too
        stmt = stmt.where((Expense.branch_id.in_(accessible)) | (Expense.branch_id.is_(None)))
    if branch_id is not None:
        stmt = stmt.where(Expense.branch_id == branch_id)
    if category is not None:
        stmt = stmt.where(Expense.category == category)
    if status is not None:
        stmt = stmt.where(Expense.status == status)
    stmt = stmt.order_by(Expense.incurred_on.desc(), Expense.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


# --- worker-production report -----------------------------------------------


async def worker_production_report(
    db: AsyncSession,
    principal: Principal,
    *,
    period_start: date,
    period_end: date,
    branch_ids: list[uuid.UUID] | None = None,
) -> list[dict[str, Any]]:
    """Per-worker production over a period, read straight from order stamps.

    Cutter side: Σ sheets_used_snapshot / cut_count_snapshot over orders where the
    user is cutter_user_id and cut_completed_at is in the period. Edger side:
    count + Σ edge_length_snapshot by thickness where edger_user_id and
    edge_completed_at in the period. Reverted work has cleared stamps → excluded.
    """
    _require_finance_read_anywhere(principal)
    assert principal.workshop_id is not None
    start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(period_end, datetime.max.time(), tzinfo=UTC)

    branches = _scope_branches(principal, branch_ids)

    base = select(Order).where(Order.workshop_id == principal.workshop_id)
    if branches is not None:
        if not branches:
            return []
        base = base.where(Order.branch_id.in_(branches))

    agg: dict[uuid.UUID, dict[str, Any]] = defaultdict(
        lambda: {
            "sheets_cut": 0,
            "cut_count": 0,
            "orders_banded": 0,
            "metres_by_thickness": defaultdict(int),
        }
    )

    cut_orders = (
        (
            await db.execute(
                base.where(
                    Order.cutter_user_id.is_not(None),
                    Order.cut_completed_at >= start_dt,
                    Order.cut_completed_at <= end_dt,
                )
            )
        )
        .scalars()
        .all()
    )
    for o in cut_orders:
        assert o.cutter_user_id is not None
        bucket = agg[o.cutter_user_id]
        bucket["sheets_cut"] += int(o.sheets_used_snapshot or 0)
        bucket["cut_count"] += int(o.cut_count_snapshot or 0)

    band_orders = (
        (
            await db.execute(
                base.where(
                    Order.edger_user_id.is_not(None),
                    Order.edge_completed_at >= start_dt,
                    Order.edge_completed_at <= end_dt,
                )
            )
        )
        .scalars()
        .all()
    )
    for o in band_orders:
        assert o.edger_user_id is not None
        bucket = agg[o.edger_user_id]
        bucket["orders_banded"] += 1
        for thickness, mm in (o.edge_length_snapshot or {}).items():
            bucket["metres_by_thickness"][str(thickness)] += int(mm)

    out: list[dict[str, Any]] = []
    for user_id, data in agg.items():
        out.append(
            {
                "user_id": str(user_id),
                "sheets_cut": data["sheets_cut"],
                "cut_count": data["cut_count"],
                "orders_banded": data["orders_banded"],
                "metres_by_thickness": dict(data["metres_by_thickness"]),
            }
        )
    out.sort(key=lambda r: r["user_id"])
    return out


def _scope_branches(
    principal: Principal, requested: list[uuid.UUID] | None
) -> set[uuid.UUID] | None:
    """Intersect a requested branch filter with the principal's finance-readable
    branches. None = owner with no filter (all workshop branches)."""
    accessible = _accessible_branches_filter(principal)
    if accessible is None:
        return set(requested) if requested else None
    if requested:
        return accessible & set(requested)
    return accessible


# --- finance report ---------------------------------------------------------


async def finance_report(
    db: AsyncSession,
    principal: Principal,
    *,
    period_start: date,
    period_end: date,
    branch_ids: list[uuid.UUID] | None = None,
) -> dict[str, Any]:
    """Income (order_payment vs other), expenses by category, net, per-branch."""
    _require_finance_read_anywhere(principal)
    assert principal.workshop_id is not None
    branches = _scope_branches(principal, branch_ids)

    income_stmt = select(Income).where(
        Income.workshop_id == principal.workshop_id,
        Income.status == LedgerStatus.RECORDED,
        Income.received_on >= period_start,
        Income.received_on <= period_end,
    )
    expense_stmt = select(Expense).where(
        Expense.workshop_id == principal.workshop_id,
        Expense.status == LedgerStatus.RECORDED,
        Expense.incurred_on >= period_start,
        Expense.incurred_on <= period_end,
    )
    if branches is not None:
        if not branches:
            return _empty_report(period_start, period_end)
        income_stmt = income_stmt.where(Income.branch_id.in_(branches))
        expense_stmt = expense_stmt.where(
            (Expense.branch_id.in_(branches)) | (Expense.branch_id.is_(None))
        )

    incomes = list((await db.execute(income_stmt)).scalars().all())
    expenses = list((await db.execute(expense_stmt)).scalars().all())

    income_order = sum(i.amount_tiyin for i in incomes if i.type is IncomeType.ORDER_PAYMENT)
    income_other = sum(i.amount_tiyin for i in incomes if i.type is IncomeType.OTHER)
    income_total = income_order + income_other

    by_category: dict[str, int] = defaultdict(int)
    for e in expenses:
        by_category[e.category.value] += e.amount_tiyin
    expense_total = sum(by_category.values())

    per_branch: dict[str, dict[str, int]] = defaultdict(
        lambda: {"income": 0, "expenses": 0, "net": 0}
    )
    for i in incomes:
        key = str(i.branch_id) if i.branch_id else "unassigned"
        per_branch[key]["income"] += i.amount_tiyin
    for e in expenses:
        key = str(e.branch_id) if e.branch_id else "unassigned"
        per_branch[key]["expenses"] += e.amount_tiyin
    for vals in per_branch.values():
        vals["net"] = vals["income"] - vals["expenses"]

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "income_total_tiyin": int(income_total),
        "income_order_payment_tiyin": int(income_order),
        "income_other_tiyin": int(income_other),
        "expense_total_tiyin": int(expense_total),
        "expenses_by_category": {k: int(v) for k, v in by_category.items()},
        "net_tiyin": int(income_total) - int(expense_total),
        "per_branch": {k: {kk: int(vv) for kk, vv in v.items()} for k, v in per_branch.items()},
    }


def _empty_report(period_start: date, period_end: date) -> dict[str, Any]:
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "income_total_tiyin": 0,
        "income_order_payment_tiyin": 0,
        "income_other_tiyin": 0,
        "expense_total_tiyin": 0,
        "expenses_by_category": {},
        "net_tiyin": 0,
        "per_branch": {},
    }
