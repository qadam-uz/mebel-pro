"""Derived counterparty debt balances, statements, and signed adjustments.

No balance is ever stored: every number here is a fold over the append-only
ledgers (priced stock-ins, supplier-linked expenses, order payments, signed
adjustments). Sign convention everywhere: positive = they owe us.
"""

import uuid
from datetime import UTC, date, datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    IncomeType,
    LedgerStatus,
    OrderStatus,
    Permission,
    StockTransactionType,
)
from app.modules.access.contracts import Client
from app.modules.catalog.contracts import Material
from app.modules.finance.models import CounterpartyAdjustment, Expense, Income
from app.modules.finance.schemas import (
    AdjustmentCreateRequest,
    DebtListResponse,
    DebtRow,
    DebtStatementResponse,
    DebtStatementRow,
    VoidLedgerRequest,
)
from app.modules.finance.service import (
    _not_future,
    _optional_text,
    _required_text,
    _workshop_principal_id,
)
from app.modules.inventory.contracts import StockItem, StockTransaction, Supplier
from app.modules.sales.contracts import Order
from app.modules.support.api import record_action, record_status_change

_PANEL = "panel"
_METRE = "metre"

# Same-second tiebreak for statement rows. Entry timestamps come from two
# clocks (app for stock-ins, DB default for ledger rows) whose sub-second
# precision differs, so ordering inside one second falls back to the natural
# business order of a trading day: goods move, then money, then corrections.
_KIND_RANK = {"delivery": 0, "order": 0, "payment": 1, "adjustment": 2}


def _statement_sort_key(row: DebtStatementRow) -> tuple[date, datetime, int, datetime]:
    at = row.at.replace(tzinfo=None)
    return (row.on, at.replace(microsecond=0), _KIND_RANK.get(row.kind, 3), at)


async def debts_scope(db: AsyncSession, *, principal: AuthenticatedPrincipal) -> uuid.UUID:
    """Debts are workshop-level; owner or any manage_finance grant may read/write."""

    workshop_id = _workshop_principal_id(principal)
    if principal.is_owner:
        return workshop_id
    if any(grant.permission is Permission.MANAGE_FINANCE for grant in principal.grants):
        return workshop_id
    raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


async def list_supplier_debts(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
    only_with_debt: bool = True,
) -> DebtListResponse:
    workshop_id = await debts_scope(db, principal=principal)
    balances = await _supplier_balances(db, workshop_id=workshop_id)

    query = select(Supplier).where(Supplier.workshop_id == workshop_id)
    normalized = _optional_text(search)
    if normalized:
        query = query.where(Supplier.name.ilike(f"%{normalized}%"))
    suppliers = list((await db.scalars(query)).all())

    rows = [
        DebtRow(
            counterparty_id=supplier.id,
            name=supplier.name,
            phone=supplier.phone,
            inactive=supplier.status.value != "active",
            balance_tiyin=balances.get(supplier.id, 0),
        )
        for supplier in suppliers
    ]
    if only_with_debt:
        rows = [row for row in rows if row.balance_tiyin != 0]
    # Most we-owe first — that is the list the accountant works through.
    rows.sort(key=lambda row: (row.balance_tiyin, row.name))
    return DebtListResponse(
        rows=rows,
        we_owe_total_tiyin=sum(-b for b in balances.values() if b < 0),
        they_owe_total_tiyin=sum(b for b in balances.values() if b > 0),
    )


async def get_supplier_statement(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    supplier_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DebtStatementResponse:
    workshop_id = await debts_scope(db, principal=principal)
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None or supplier.workshop_id != workshop_id:
        raise APIError("supplier_not_found", "Supplier not found", status_code=404)
    terms = await _supplier_terms(db, workshop_id=workshop_id, supplier_id=supplier_id)
    return _build_statement(
        terms,
        counterparty_id=supplier.id,
        name=supplier.name,
        phone=supplier.phone,
        date_from=date_from,
        date_to=date_to,
    )


async def list_client_debts(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
    only_with_debt: bool = True,
) -> DebtListResponse:
    workshop_id = await debts_scope(db, principal=principal)
    balances = await _client_balances(db, workshop_id=workshop_id)
    if not balances:
        return DebtListResponse(rows=[], we_owe_total_tiyin=0, they_owe_total_tiyin=0)

    query = select(Client).where(Client.id.in_(balances.keys()))
    normalized = _optional_text(search)
    if normalized:
        pattern = f"%{normalized}%"
        query = query.where(Client.name.ilike(pattern) | Client.phone.ilike(pattern))
    clients = list((await db.scalars(query)).all())

    rows = [
        DebtRow(
            counterparty_id=client.id,
            name=client.name,
            phone=client.phone,
            inactive=False,
            balance_tiyin=balances.get(client.id, 0),
        )
        for client in clients
    ]
    if only_with_debt:
        rows = [row for row in rows if row.balance_tiyin != 0]
    # Most they-owe first — receivables are what the accountant chases.
    rows.sort(key=lambda row: (-row.balance_tiyin, row.name))
    return DebtListResponse(
        rows=rows,
        we_owe_total_tiyin=sum(-b for b in balances.values() if b < 0),
        they_owe_total_tiyin=sum(b for b in balances.values() if b > 0),
    )


async def get_client_statement(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    client_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DebtStatementResponse:
    workshop_id = await debts_scope(db, principal=principal)
    client = await db.get(Client, client_id)
    if client is None:
        raise APIError("client_not_found", "Client not found", status_code=404)
    terms = await _client_terms(db, workshop_id=workshop_id, client_id=client_id)
    return _build_statement(
        terms,
        counterparty_id=client.id,
        name=client.name,
        phone=client.phone,
        date_from=date_from,
        date_to=date_to,
    )


async def create_adjustment(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: AdjustmentCreateRequest,
) -> CounterpartyAdjustment:
    workshop_id = await debts_scope(db, principal=principal)
    if (payload.supplier_id is None) == (payload.client_id is None):
        raise APIError(
            "invalid_party",
            "Exactly one of supplier_id or client_id is required",
            status_code=400,
        )
    if payload.amount_tiyin == 0:
        raise APIError("invalid_amount", "Amount cannot be zero", status_code=400)
    _not_future(payload.adjusted_on)
    if payload.supplier_id is not None:
        supplier = await db.get(Supplier, payload.supplier_id)
        if supplier is None or supplier.workshop_id != workshop_id:
            raise APIError("supplier_not_found", "Supplier not found", status_code=404)
    if payload.client_id is not None:
        client = await db.get(Client, payload.client_id)
        if client is None:
            raise APIError("client_not_found", "Client not found", status_code=404)
    adjustment = CounterpartyAdjustment(
        workshop_id=workshop_id,
        supplier_id=payload.supplier_id,
        client_id=payload.client_id,
        amount_tiyin=payload.amount_tiyin,
        adjusted_on=payload.adjusted_on,
        note=_required_text(payload.note, "note_required"),
        status=LedgerStatus.RECORDED,
        recorded_by_user_id=principal.principal_id,
    )
    db.add(adjustment)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="finance.adjustment.create",
        entity_type="counterparty_adjustment",
        entity_id=adjustment.id,
        workshop_id=workshop_id,
        branch_id=None,
        summary=f"Recorded debt adjustment {adjustment.amount_tiyin}",
        details={
            "supplier_id": str(payload.supplier_id) if payload.supplier_id else None,
            "client_id": str(payload.client_id) if payload.client_id else None,
        },
    )
    await db.refresh(adjustment)
    return adjustment


async def void_adjustment(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    adjustment_id: uuid.UUID,
    payload: VoidLedgerRequest,
) -> CounterpartyAdjustment:
    workshop_id = await debts_scope(db, principal=principal)
    adjustment = await db.get(CounterpartyAdjustment, adjustment_id)
    if adjustment is None or adjustment.workshop_id != workshop_id:
        raise APIError("adjustment_not_found", "Adjustment not found", status_code=404)
    if adjustment.status is not LedgerStatus.RECORDED:
        raise APIError("ledger_not_recorded", "Only recorded entries can change", status_code=409)
    reason = _required_text(payload.reason, "reason_required")
    from_status = adjustment.status.value
    adjustment.status = LedgerStatus.VOIDED
    adjustment.voided_reason = reason
    adjustment.voided_by_user_id = principal.principal_id
    adjustment.voided_at = datetime.now(UTC)
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="finance.adjustment.void",
        entity_type="counterparty_adjustment",
        entity_id=adjustment.id,
        workshop_id=workshop_id,
        branch_id=None,
        summary=f"Voided debt adjustment {adjustment.id}",
        details={"reason": reason},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="counterparty_adjustment",
        entity_id=adjustment.id,
        workshop_id=workshop_id,
        branch_id=None,
        from_status=from_status,
        to_status=adjustment.status.value,
        reason=reason,
        action_log_id=action.id,
    )
    await db.refresh(adjustment)
    return adjustment


async def _supplier_balances(db: AsyncSession, *, workshop_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Per supplier: balance = sum(payments) - sum(deliveries) + sum(adjustments)."""

    deliveries = {
        row[0]: int(row[1])
        for row in (
            await db.execute(
                select(
                    StockTransaction.supplier_id,
                    func.coalesce(func.sum(StockTransaction.total_price_tiyin), 0),
                )
                .join(Supplier, Supplier.id == StockTransaction.supplier_id)
                .where(
                    Supplier.workshop_id == workshop_id,
                    StockTransaction.type == StockTransactionType.STOCK_IN,
                    StockTransaction.total_price_tiyin.is_not(None),
                )
                .group_by(StockTransaction.supplier_id)
            )
        ).all()
        if row[0] is not None
    }
    payments = {
        row[0]: int(row[1])
        for row in (
            await db.execute(
                select(Expense.supplier_id, func.coalesce(func.sum(Expense.amount_tiyin), 0))
                .where(
                    Expense.workshop_id == workshop_id,
                    Expense.supplier_id.is_not(None),
                    Expense.status == LedgerStatus.RECORDED,
                )
                .group_by(Expense.supplier_id)
            )
        ).all()
        if row[0] is not None
    }
    adjustments = {
        row[0]: int(row[1])
        for row in (
            await db.execute(
                select(
                    CounterpartyAdjustment.supplier_id,
                    func.coalesce(func.sum(CounterpartyAdjustment.amount_tiyin), 0),
                )
                .where(
                    CounterpartyAdjustment.workshop_id == workshop_id,
                    CounterpartyAdjustment.supplier_id.is_not(None),
                    CounterpartyAdjustment.status == LedgerStatus.RECORDED,
                )
                .group_by(CounterpartyAdjustment.supplier_id)
            )
        ).all()
        if row[0] is not None
    }
    balances: dict[uuid.UUID, int] = {}
    for supplier_id in {*deliveries, *payments, *adjustments}:
        balances[supplier_id] = (
            payments.get(supplier_id, 0)
            - deliveries.get(supplier_id, 0)
            + adjustments.get(supplier_id, 0)
        )
    return balances


# An order joins the client fold once the shop commits to it (confirmed and
# beyond); `new` is a quote, `cancelled` leaves the fold — while any recorded
# payment stays, so a cancelled prepaid order correctly shows as our debt.
_CLIENT_DEBT_EXCLUDED = (OrderStatus.NEW, OrderStatus.CANCELLED)


async def _client_balances(db: AsyncSession, *, workshop_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Per client: balance = sum(order totals) - sum(payments) + sum(adjustments)."""

    orders = {
        row[0]: int(row[1])
        for row in (
            await db.execute(
                select(Order.client_id, func.coalesce(func.sum(Order.total_tiyin), 0))
                .where(
                    Order.workshop_id == workshop_id,
                    Order.status.not_in(_CLIENT_DEBT_EXCLUDED),
                )
                .group_by(Order.client_id)
            )
        ).all()
    }
    payments = {
        row[0]: int(row[1])
        for row in (
            await db.execute(
                select(Order.client_id, func.coalesce(func.sum(Income.amount_tiyin), 0))
                .join(Order, Order.id == Income.order_id)
                .where(
                    Income.workshop_id == workshop_id,
                    Income.type == IncomeType.ORDER_PAYMENT,
                    Income.status == LedgerStatus.RECORDED,
                )
                .group_by(Order.client_id)
            )
        ).all()
    }
    adjustments = {
        row[0]: int(row[1])
        for row in (
            await db.execute(
                select(
                    CounterpartyAdjustment.client_id,
                    func.coalesce(func.sum(CounterpartyAdjustment.amount_tiyin), 0),
                )
                .where(
                    CounterpartyAdjustment.workshop_id == workshop_id,
                    CounterpartyAdjustment.client_id.is_not(None),
                    CounterpartyAdjustment.status == LedgerStatus.RECORDED,
                )
                .group_by(CounterpartyAdjustment.client_id)
            )
        ).all()
        if row[0] is not None
    }
    balances: dict[uuid.UUID, int] = {}
    for client_id in {*orders, *payments, *adjustments}:
        balances[client_id] = (
            orders.get(client_id, 0) - payments.get(client_id, 0) + adjustments.get(client_id, 0)
        )
    return balances


async def _client_terms(
    db: AsyncSession, *, workshop_id: uuid.UUID, client_id: uuid.UUID
) -> list[DebtStatementRow]:
    """Every fold term for one client, unsorted, without running balances."""

    rows: list[DebtStatementRow] = []
    orders = (
        await db.scalars(
            select(Order).where(
                Order.workshop_id == workshop_id,
                Order.client_id == client_id,
                Order.status.not_in(_CLIENT_DEBT_EXCLUDED),
            )
        )
    ).all()
    for order in orders:
        confirmed = order.confirmed_at or order.created_at
        rows.append(
            DebtStatementRow(
                kind="order",
                on=confirmed.date(),
                at=confirmed,
                reference_id=order.id,
                amount_tiyin=order.total_tiyin,
                balance_after_tiyin=0,
                order_number=order.order_number,
            )
        )
    payments = (
        await db.execute(
            select(Income, Order.order_number)
            .join(Order, Order.id == Income.order_id)
            .where(
                Income.workshop_id == workshop_id,
                Order.client_id == client_id,
                Income.type == IncomeType.ORDER_PAYMENT,
                Income.status == LedgerStatus.RECORDED,
            )
        )
    ).all()
    for income, order_number in payments:
        rows.append(
            DebtStatementRow(
                kind="payment",
                on=income.received_on,
                at=income.created_at,
                reference_id=income.id,
                amount_tiyin=-income.amount_tiyin,
                balance_after_tiyin=0,
                note=income.note,
                method=income.method,
                order_number=order_number,
            )
        )
    adjustments = (
        await db.scalars(
            select(CounterpartyAdjustment).where(
                CounterpartyAdjustment.workshop_id == workshop_id,
                CounterpartyAdjustment.client_id == client_id,
                CounterpartyAdjustment.status == LedgerStatus.RECORDED,
            )
        )
    ).all()
    for adjustment in adjustments:
        rows.append(
            DebtStatementRow(
                kind="adjustment",
                on=adjustment.adjusted_on,
                at=adjustment.created_at,
                reference_id=adjustment.id,
                amount_tiyin=adjustment.amount_tiyin,
                balance_after_tiyin=0,
                note=adjustment.note,
            )
        )
    return rows


async def _supplier_terms(
    db: AsyncSession, *, workshop_id: uuid.UUID, supplier_id: uuid.UUID
) -> list[DebtStatementRow]:
    """Every fold term for one supplier, unsorted, without running balances."""

    rows: list[DebtStatementRow] = []
    deliveries = (
        await db.execute(
            select(StockTransaction, Material)
            .join(StockItem, StockItem.id == StockTransaction.stock_item_id)
            .join(Material, Material.id == StockItem.material_id)
            .where(
                StockTransaction.supplier_id == supplier_id,
                StockTransaction.type == StockTransactionType.STOCK_IN,
                StockTransaction.total_price_tiyin.is_not(None),
            )
        )
    ).all()
    for transaction, material in deliveries:
        total = transaction.total_price_tiyin
        if total is None:  # pragma: no cover - filtered in the query
            continue
        rows.append(
            DebtStatementRow(
                kind="delivery",
                on=transaction.created_at.date(),
                at=transaction.created_at,
                reference_id=transaction.id,
                amount_tiyin=-total,
                balance_after_tiyin=0,
                note=transaction.note,
                material_name=material.name,
                quantity=transaction.quantity,
                display_unit=_PANEL if material.kind.value == "panel" else _METRE,
            )
        )
    expenses = (
        await db.scalars(
            select(Expense).where(
                Expense.workshop_id == workshop_id,
                Expense.supplier_id == supplier_id,
                Expense.status == LedgerStatus.RECORDED,
            )
        )
    ).all()
    for expense in expenses:
        rows.append(
            DebtStatementRow(
                kind="payment",
                on=expense.incurred_on,
                at=expense.created_at,
                reference_id=expense.id,
                amount_tiyin=expense.amount_tiyin,
                balance_after_tiyin=0,
                note=expense.description,
                category=expense.category,
            )
        )
    adjustments = (
        await db.scalars(
            select(CounterpartyAdjustment).where(
                CounterpartyAdjustment.workshop_id == workshop_id,
                CounterpartyAdjustment.supplier_id == supplier_id,
                CounterpartyAdjustment.status == LedgerStatus.RECORDED,
            )
        )
    ).all()
    for adjustment in adjustments:
        rows.append(
            DebtStatementRow(
                kind="adjustment",
                on=adjustment.adjusted_on,
                at=adjustment.created_at,
                reference_id=adjustment.id,
                amount_tiyin=adjustment.amount_tiyin,
                balance_after_tiyin=0,
                note=adjustment.note,
            )
        )
    return rows


def _build_statement(
    terms: list[DebtStatementRow],
    *,
    counterparty_id: uuid.UUID,
    name: str,
    phone: str | None,
    date_from: date | None,
    date_to: date | None,
) -> DebtStatementResponse:
    """Sort fold terms, split around the range, and thread the running balance."""

    terms.sort(key=_statement_sort_key)
    opening = 0
    in_range: list[DebtStatementRow] = []
    current = 0
    for row in terms:
        current += row.amount_tiyin
        if date_from is not None and row.on < date_from:
            opening += row.amount_tiyin
            continue
        if date_to is not None and row.on > date_to:
            continue
        in_range.append(row)
    balance = opening
    threaded: list[DebtStatementRow] = []
    for row in in_range:
        balance += row.amount_tiyin
        threaded.append(row.model_copy(update={"balance_after_tiyin": balance}))
    return DebtStatementResponse(
        counterparty_id=counterparty_id,
        name=name,
        phone=phone,
        date_from=date_from,
        date_to=date_to,
        opening_balance_tiyin=opening,
        closing_balance_tiyin=balance,
        current_balance_tiyin=current,
        rows=threaded,
    )
