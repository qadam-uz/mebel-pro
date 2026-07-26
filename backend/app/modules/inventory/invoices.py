"""Supplier invoices — the document grain a stock arrival is recorded in.

An accountant negotiates with a supplier in invoice totals, not in individual
stock-ins: the discount lives on the document as a whole. Every stock-in the
platform records therefore hangs off exactly one invoice, and the payable side
of the supplier balance folds over `SupplierInvoice.total_tiyin` (post
skidka/ustama) rather than over raw line prices.

Payment status is derived here, never stored: it is the same subtraction as the
supplier balance, one grain finer.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from fastapi import status
from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    InvoicePaymentStatus,
    LedgerStatus,
    StockTransactionType,
    SupplierStatus,
)
from app.modules.access.contracts import WorkshopUser
from app.modules.catalog.contracts import Material
from app.modules.finance.contracts import Expense
from app.modules.inventory.contracts import StockItem, StockTransaction, Supplier, SupplierInvoice
from app.modules.inventory.schemas import SupplierInvoiceCreateRequest, SupplierInvoiceLineInput
from app.modules.inventory.service import (
    _apply_stock_delta,
    _create_supplier_for_scope,
    _emit_low_stock_if_needed,
    _inventory_scope,
    _optional_text,
    _stock_item_for_movement,
    _supplier_in_scope,
    stock_in_total_tiyin,
)
from app.modules.support.api import record_action
from app.modules.workshop.contracts import Branch

# `K-0008` — per workshop, no yearly reset. Workshop-level because the debt
# scope is: two branches both minting `K-0008` would be ambiguous to the
# accountant who reads invoices across branches.
INVOICE_NUMBER_PREFIX = "K-"


@dataclass(frozen=True)
class InvoiceLineRecord:
    transaction: StockTransaction
    stock_item: StockItem
    material: Material


@dataclass(frozen=True)
class InvoiceRecord:
    invoice: SupplierInvoice
    supplier: Supplier | None
    branch_name: str | None
    recorded_by: WorkshopUser | None
    lines: list[InvoiceLineRecord]
    paid_tiyin: int

    @property
    def outstanding_tiyin(self) -> int:
        return max(self.invoice.total_tiyin - self.paid_tiyin, 0)

    @property
    def payment_status(self) -> InvoicePaymentStatus:
        return payment_status_for(self.invoice.total_tiyin, self.paid_tiyin)


def payment_status_for(total_tiyin: int, paid_tiyin: int) -> InvoicePaymentStatus:
    """Nothing outstanding reads as paid — including a zero-total arrival."""

    if total_tiyin <= 0 or paid_tiyin >= total_tiyin:
        return InvoicePaymentStatus.PAID
    if paid_tiyin <= 0:
        return InvoicePaymentStatus.UNPAID
    return InvoicePaymentStatus.PARTIAL


async def create_invoice(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: SupplierInvoiceCreateRequest,
) -> InvoiceRecord:
    """Create the invoice and every stock-in line on it in one transaction.

    Either the whole arrival lands or none of it does: a failure on any line
    leaves no invoice and no stock movement (the request session rolls back).
    """

    scope = await _inventory_scope(db, principal=principal, branch_id=payload.branch_id)
    if not payload.lines:
        raise APIError("invoice_lines_required", "Add at least one material line", status_code=400)
    if payload.discount_tiyin < 0 or payload.surcharge_tiyin < 0:
        raise APIError(
            "invalid_adjustment",
            "Discount and surcharge cannot be negative",
            status_code=400,
        )
    if payload.supplier_id is not None and payload.supplier is not None:
        raise APIError(
            "invalid_supplier",
            "Choose existing or inline supplier, not both",
            status_code=400,
        )
    if payload.supplier_id is None and payload.supplier is None:
        raise APIError("supplier_required", "Supplier is required", status_code=400)
    supplier = (
        await _supplier_in_scope(db, scope=scope, supplier_id=payload.supplier_id)
        if payload.supplier_id is not None
        else await _create_supplier_for_scope(
            db,
            principal=principal,
            scope=scope,
            name=payload.supplier.name if payload.supplier else "",
            phone=payload.supplier.phone if payload.supplier else None,
            note=payload.supplier.note if payload.supplier else None,
        )
    )
    if supplier.status is not SupplierStatus.ACTIVE:
        raise APIError("supplier_inactive", "Supplier is inactive", status_code=400)
    invoice_date = payload.invoice_date or _today()
    _not_future(invoice_date)

    # Resolve and price every line first: the invoice row must carry the
    # subtotal, and it must exist before its lines can point at it.
    priced: list[tuple[SupplierInvoiceLineInput, StockItem, Material, int]] = []
    subtotal = 0
    for line in payload.lines:
        if line.quantity <= 0:
            raise APIError("invalid_quantity", "Quantity must be positive", status_code=400)
        if line.unit_price_tiyin < 0:
            raise APIError("invalid_price", "Price cannot be negative", status_code=400)
        item, material = await _stock_item_for_movement(
            db,
            scope=scope,
            material_id=line.material_id,
        )
        line_total = stock_in_total_tiyin(material.kind, line.quantity, line.unit_price_tiyin)
        subtotal += line_total
        priced.append((line, item, material, line_total))

    if payload.discount_tiyin > subtotal:
        raise APIError(
            "discount_above_subtotal",
            "Discount cannot exceed the invoice subtotal",
            status_code=400,
        )
    invoice = SupplierInvoice(
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        supplier_id=supplier.id,
        invoice_no=await next_invoice_no(db, workshop_id=scope.workshop_id),
        invoice_date=invoice_date,
        subtotal_tiyin=subtotal,
        discount_tiyin=payload.discount_tiyin,
        surcharge_tiyin=payload.surcharge_tiyin,
        total_tiyin=subtotal - payload.discount_tiyin + payload.surcharge_tiyin,
        note=_optional_text(payload.note),
        recorded_by_user_id=principal.principal_id,
    )
    db.add(invoice)
    await db.flush()

    lines: list[InvoiceLineRecord] = []
    for line, item, material, line_total in priced:
        transaction = await _apply_stock_delta(
            db,
            principal=principal,
            stock_item=item,
            type_=StockTransactionType.STOCK_IN,
            quantity=line.quantity,
            supplier_id=supplier.id,
            note=_optional_text(line.note),
            unit_price_tiyin=line.unit_price_tiyin,
            total_price_tiyin=line_total,
            invoice_id=invoice.id,
        )
        lines.append(InvoiceLineRecord(transaction=transaction, stock_item=item, material=material))

    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="inventory.invoice.create",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Recorded arrival {invoice.invoice_no}",
        details={"lines": len(lines), "total_tiyin": invoice.total_tiyin},
    )
    # One notification per stock item, not per line: the same material twice on
    # one faktura is a single low-stock fact.
    for item in {line.stock_item.id: line.stock_item for line in lines}.values():
        material = next(row.material for row in lines if row.stock_item.id == item.id)
        await _emit_low_stock_if_needed(db, scope=scope, stock_item=item, material=material)

    return InvoiceRecord(
        invoice=invoice,
        supplier=supplier,
        branch_name=await _branch_name(db, branch_id=scope.branch_id),
        recorded_by=await db.get(WorkshopUser, principal.principal_id),
        lines=lines,
        paid_tiyin=0,
    )


async def list_invoices(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    supplier_id: uuid.UUID | None = None,
    search: str | None = None,
    payment_status: InvoicePaymentStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InvoiceRecord]:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    query = _invoice_query().where(SupplierInvoice.branch_id == scope.branch_id)
    if supplier_id is not None:
        query = query.where(SupplierInvoice.supplier_id == supplier_id)
    normalized = _optional_text(search)
    if normalized:
        pattern = f"%{normalized}%"
        query = query.where(
            SupplierInvoice.invoice_no.ilike(pattern)
            | Supplier.name.ilike(pattern)
            | SupplierInvoice.note.ilike(pattern)
        )
    if payment_status is not None:
        query = query.where(_payment_status_clause(payment_status))
    query = query.limit(max(1, min(limit, 100))).offset(max(0, offset))
    return await _records_for(db, query=query)


async def get_invoice(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    invoice_id: uuid.UUID,
) -> InvoiceRecord:
    invoice = await db.get(SupplierInvoice, invoice_id)
    if invoice is None:
        raise APIError("invoice_not_found", "Invoice not found", status_code=404)
    # Scope on the invoice's own branch: reading it needs inventory rights there.
    await _inventory_scope(db, principal=principal, branch_id=invoice.branch_id)
    records = await _records_for(db, query=_invoice_query().where(SupplierInvoice.id == invoice_id))
    if not records:  # pragma: no cover - the row was just loaded
        raise APIError("invoice_not_found", "Invoice not found", status_code=404)
    return records[0]


async def list_payable_invoices(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    search: str | None = None,
    limit: int = 50,
) -> list[InvoiceRecord]:
    """Unpaid and partially paid invoices for the expense picker, newest first.

    Workshop-scoped rather than branch-scoped: the accountant pays fakturas
    across branches, and the branch comes back on the invoice itself.
    """

    query = _invoice_query().where(
        SupplierInvoice.workshop_id == workshop_id,
        SupplierInvoice.supplier_id.is_not(None),
        or_(
            _payment_status_clause(InvoicePaymentStatus.UNPAID),
            _payment_status_clause(InvoicePaymentStatus.PARTIAL),
        ),
    )
    normalized = _optional_text(search)
    if normalized:
        pattern = f"%{normalized}%"
        query = query.where(
            SupplierInvoice.invoice_no.ilike(pattern) | Supplier.name.ilike(pattern)
        )
    return await _records_for(db, query=query.limit(max(1, min(limit, 100))))


async def invoice_for_payment(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    invoice_id: uuid.UUID,
) -> SupplierInvoice:
    """The invoice an expense is being booked against, tenant-checked."""

    invoice = await db.get(SupplierInvoice, invoice_id)
    if invoice is None or invoice.workshop_id != workshop_id:
        raise APIError("invoice_not_found", "Invoice not found", status_code=404)
    return invoice


async def next_invoice_no(db: AsyncSession, *, workshop_id: uuid.UUID) -> str:
    """`K-0008`, per workshop. Safe under the platform's no-deletes invariant."""

    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(f"supplier_invoices:{workshop_id}")))
        )
    count = await db.scalar(
        select(func.count(SupplierInvoice.id)).where(SupplierInvoice.workshop_id == workshop_id)
    )
    return f"{INVOICE_NUMBER_PREFIX}{int(count or 0) + 1:04d}"


# The joined shape every invoice read returns. Outer joins mean the three
# companions can be absent (a supplier-less backfill row, a deleted-name user),
# which the row unpacking below already treats as optional. The settlement fold
# rides along as a correlated subquery so payment status can be filtered and
# paginated in SQL — after the backfill there is one invoice per historical
# stock-in, far too many to sort out in Python.
_InvoiceQuery = Select[tuple[SupplierInvoice, Supplier, Branch, WorkshopUser, int]]


def _paid_tiyin() -> ColumnElement[int]:
    """Recorded expenses booked against the invoice — the settlement fold."""

    return (
        select(func.coalesce(func.sum(Expense.amount_tiyin), 0))
        .where(
            Expense.invoice_id == SupplierInvoice.id,
            Expense.status == LedgerStatus.RECORDED,
        )
        .correlate(SupplierInvoice)
        .scalar_subquery()
    )


def _payment_status_clause(wanted: InvoicePaymentStatus) -> ColumnElement[bool]:
    """`payment_status_for`, expressed where the rows are."""

    total = SupplierInvoice.total_tiyin
    paid = _paid_tiyin()
    if wanted is InvoicePaymentStatus.PAID:
        return or_(total <= 0, paid >= total)
    if wanted is InvoicePaymentStatus.UNPAID:
        return and_(total > 0, paid <= 0)
    return and_(total > 0, paid > 0, paid < total)


def _invoice_query() -> _InvoiceQuery:
    return (
        select(SupplierInvoice, Supplier, Branch, WorkshopUser, _paid_tiyin())
        .outerjoin(Supplier, Supplier.id == SupplierInvoice.supplier_id)
        .outerjoin(Branch, Branch.id == SupplierInvoice.branch_id)
        .outerjoin(WorkshopUser, WorkshopUser.id == SupplierInvoice.recorded_by_user_id)
        .order_by(SupplierInvoice.invoice_date.desc(), SupplierInvoice.created_at.desc())
    )


async def _records_for(
    db: AsyncSession,
    *,
    query: _InvoiceQuery,
) -> list[InvoiceRecord]:
    rows = (await db.execute(query)).all()
    if not rows:
        return []
    # Lines are fetched only for the page that came back, never for the table.
    lines = await _lines_by_invoice(db, invoice_ids=[row[0].id for row in rows])
    return [
        InvoiceRecord(
            invoice=invoice,
            supplier=supplier,
            branch_name=branch.name if branch else None,
            recorded_by=recorder,
            lines=lines.get(invoice.id, []),
            paid_tiyin=int(paid),
        )
        for invoice, supplier, branch, recorder, paid in rows
    ]


async def _lines_by_invoice(
    db: AsyncSession,
    *,
    invoice_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[InvoiceLineRecord]]:
    rows = (
        await db.execute(
            select(StockTransaction, StockItem, Material)
            .join(StockItem, StockItem.id == StockTransaction.stock_item_id)
            .join(Material, Material.id == StockItem.material_id)
            .where(StockTransaction.invoice_id.in_(invoice_ids))
            .order_by(StockTransaction.created_at, StockTransaction.id)
        )
    ).all()
    grouped: dict[uuid.UUID, list[InvoiceLineRecord]] = {}
    for transaction, item, material in rows:
        if transaction.invoice_id is None:  # pragma: no cover - filtered in the query
            continue
        grouped.setdefault(transaction.invoice_id, []).append(
            InvoiceLineRecord(transaction=transaction, stock_item=item, material=material)
        )
    return grouped


async def _branch_name(db: AsyncSession, *, branch_id: uuid.UUID) -> str | None:
    branch = await db.get(Branch, branch_id)
    return branch.name if branch else None


def _today() -> date:
    return datetime.now(UTC).date()


def _not_future(value: date) -> None:
    # Same rule as the finance ledger: invoice dates are picked in the actor's
    # local calendar (UTC+5 here), which can read a day ahead of UTC just after
    # local midnight. Compare against the furthest-ahead real-world local date.
    if value > (datetime.now(UTC) + timedelta(hours=14)).date():
        raise APIError(
            "future_date_not_allowed",
            "Invoice date cannot be in the future",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
