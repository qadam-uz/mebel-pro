"""Supplier invoices — the document grain a stock arrival is recorded in.

An accountant negotiates with a supplier in invoice totals, not in individual
stock-ins: the discount lives on the document as a whole. Every stock-in the
platform records therefore hangs off exactly one invoice, and the payable side
of the supplier balance folds over `SupplierInvoice.total_tiyin` (post
skidka/ustama) rather than over raw line prices.

Payment status is derived here, never stored: it is the same subtraction as the
supplier balance, one grain finer.

An invoice is a ledger document: it can be **voided** with a mandatory reason
(stock reversed, the document dropping out of every derived reader) and
**corrected** while recorded — header facts and lines alike. A line edit is not
delta arithmetic: the movements it changes already have later movements behind
them carrying `balance_after` snapshots, so the lines are rewritten wholesale
and each touched stock item's chain is replayed (`service.replay_stock_chain`).
"""

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta

from fastapi import status
from sqlalchemy import ColumnElement, Select, and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    InvoicePaymentStatus,
    LedgerStatus,
    StockTransactionType,
    SupplierStatus,
)
from app.modules.access.api import BranchScope
from app.modules.access.contracts import WorkshopUser
from app.modules.catalog.api import branch_material_label
from app.modules.catalog.contracts import BranchMaterial, Decor, DecorFormat, Manufacturer
from app.modules.finance.contracts import Expense
from app.modules.inventory.contracts import StockItem, StockTransaction, Supplier, SupplierInvoice
from app.modules.inventory.schemas import (
    SupplierInvoiceCreateRequest,
    SupplierInvoiceLineInput,
    SupplierInvoicePatchRequest,
    SupplierInvoiceVoidRequest,
)
from app.modules.inventory.service import (
    MaterialRecord,
    _apply_stock_delta,
    _create_supplier_for_scope,
    _emit_negative_stock,
    _inventory_scope,
    _material_join,
    _optional_text,
    _required_text,
    _stock_item_for_movement,
    _supplier_in_scope,
    replay_stock_chain,
    stock_in_total_tiyin,
)
from app.modules.support.api import record_action, record_status_change
from app.modules.workshop.contracts import Branch

# `K-0008` — per workshop, no yearly reset. Workshop-level because the debt
# scope is: two branches both minting `K-0008` would be ambiguous to the
# accountant who reads invoices across branches.
INVOICE_NUMBER_PREFIX = "K-"


@dataclass(frozen=True)
class InvoiceLineRecord:
    transaction: StockTransaction
    stock_item: StockItem
    branch_material: BranchMaterial
    decor_format: DecorFormat
    decor: Decor
    manufacturer: Manufacturer

    @property
    def label(self) -> str:
        """The line's material as a human reads it — computed, never stored."""

        return branch_material_label(
            self.decor_format, self.decor, self.manufacturer, self.branch_material.id
        )


@dataclass(frozen=True)
class InvoicePaymentRecord:
    """An expense booked against the invoice, recorded or voided."""

    expense_id: uuid.UUID
    spent_on: date
    amount_tiyin: int
    status: LedgerStatus


@dataclass(frozen=True)
class InvoiceRecord:
    invoice: SupplierInvoice
    supplier: Supplier | None
    branch_name: str | None
    recorded_by: WorkshopUser | None
    lines: list[InvoiceLineRecord]
    paid_tiyin: int
    voided_by: WorkshopUser | None = None
    # Filled by the single-invoice read only; the table never needs it.
    payments: list[InvoicePaymentRecord] = field(default_factory=list)

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
    priced: list[tuple[SupplierInvoiceLineInput, StockItem, MaterialRecord, int]] = []
    subtotal = 0
    for line in payload.lines:
        if line.quantity <= 0:
            raise APIError("invalid_quantity", "Quantity must be positive", status_code=400)
        if line.unit_price_tiyin < 0:
            raise APIError("invalid_price", "Price cannot be negative", status_code=400)
        # Deliberately no "create the material if it is missing" fallback here:
        # an arrival for a format the branch does not carry is a typo, and this
        # path must never quietly extend the catalog. Only the order-driven
        # movements in service.py may proceed on a freshly created stock row.
        item, material = await _stock_item_for_movement(
            db,
            scope=scope,
            branch_material_id=line.branch_material_id,
        )
        line_total = stock_in_total_tiyin(material.type, line.quantity, line.unit_price_tiyin)
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
        lines.append(
            InvoiceLineRecord(
                transaction=transaction,
                stock_item=item,
                branch_material=material.branch_material,
                decor_format=material.decor_format,
                decor=material.decor,
                manufacturer=material.manufacturer,
            )
        )

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
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InvoiceRecord]:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    query = _invoice_query().where(SupplierInvoice.branch_id == scope.branch_id)
    if supplier_id is not None:
        query = query.where(SupplierInvoice.supplier_id == supplier_id)
    # `invoice_date` is a calendar date, not a timestamp, so the range needs no
    # timezone anchoring — the day the operator picks is the day stored.
    if date_from is not None:
        query = query.where(SupplierInvoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.where(SupplierInvoice.invoice_date <= date_to)
    normalized = _optional_text(search)
    if normalized:
        pattern = f"%{normalized}%"
        # The box matches the document number and nothing else: the supplier is
        # its own dropdown filter, and `note` is no longer enterable, so matching
        # either here would only blur what a typed query means.
        query = query.where(SupplierInvoice.invoice_no.ilike(pattern))
    if payment_status is not None:
        # A voided invoice owes nothing and is owed nothing — it appears in the
        # unfiltered list with its own badge, but under no payment-status filter.
        query = query.where(
            SupplierInvoice.status == LedgerStatus.RECORDED,
            _payment_status_clause(payment_status),
        )
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
    record = records[0]
    return replace(record, payments=await _payments_for(db, invoice_id=invoice_id))


async def _payments_for(
    db: AsyncSession,
    *,
    invoice_id: uuid.UUID,
) -> list[InvoicePaymentRecord]:
    """Every expense booked against the invoice, newest first, voided included.

    Read through the same finance contract surface the paid-sum fold uses — a
    disputed document is read with its whole story, so a voided payment stays
    visible with its status rather than vanishing.
    """

    rows = (
        await db.execute(
            select(Expense.id, Expense.incurred_on, Expense.amount_tiyin, Expense.status)
            .where(Expense.invoice_id == invoice_id)
            .order_by(Expense.incurred_on.desc(), Expense.created_at.desc())
        )
    ).all()
    return [
        InvoicePaymentRecord(
            expense_id=expense_id,
            spent_on=spent_on,
            amount_tiyin=int(amount),
            status=expense_status,
        )
        for expense_id, spent_on, amount, expense_status in rows
    ]


async def void_invoice(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    invoice_id: uuid.UUID,
    payload: SupplierInvoiceVoidRequest,
) -> InvoiceRecord:
    """Cancel the document and reverse every line it moved, in one transaction.

    Every reader of the header is derived at read time, so the void needs no
    cleanup pass: the invoice simply stops being `recorded` and leaves the debt
    fold, the payable set and the price history at once.
    """

    invoice = await _invoice_for_mutation(db, principal=principal, invoice_id=invoice_id)
    scope = await _inventory_scope(db, principal=principal, branch_id=invoice.branch_id)
    reason = _required_text(payload.reason, "invoice_void_reason_required")
    if invoice.status is not LedgerStatus.RECORDED:
        raise APIError(
            "invoice_already_voided",
            "This invoice is already cancelled",
            status_code=status.HTTP_409_CONFLICT,
        )
    # Money and goods reverse in separate, explicit steps: voiding an invoice
    # under a live payment would silently turn that payment into a dangling
    # advance against the supplier.
    settled = await db.scalar(
        select(func.count(Expense.id)).where(
            Expense.invoice_id == invoice.id,
            Expense.status == LedgerStatus.RECORDED,
        )
    )
    if settled:
        raise APIError(
            "invoice_has_payments",
            "Void the payment in Moliya first, then cancel this invoice",
            status_code=status.HTTP_409_CONFLICT,
        )

    lines = (await _lines_by_invoice(db, invoice_ids=[invoice.id])).get(invoice.id, [])
    # Deterministic lock order — the same discipline creation uses — so two
    # concurrent voids touching overlapping materials cannot deadlock.
    for line in sorted(lines, key=lambda row: str(row.stock_item.branch_material_id)):
        item, material = await _stock_item_for_movement(
            db,
            scope=scope,
            branch_material_id=line.stock_item.branch_material_id,
        )
        await _apply_stock_delta(
            db,
            principal=principal,
            stock_item=item,
            type_=StockTransactionType.STOCK_IN_VOID,
            quantity=-line.transaction.quantity,
            supplier_id=line.transaction.supplier_id,
            # The reason lives once, on the invoice — a copy on every reversal
            # row is a second place for it to be edited out of agreement.
            note=None,
            invoice_id=invoice.id,
        )
        # A reversal is system-driven in the sense QAD-150 means it: the paper
        # was wrong, the physical world already happened. It may take the books
        # negative, and when it does that must not be silent.
        if item.on_hand < 0:
            await _emit_negative_stock(db, scope=scope, stock_item=item, material=material)

    from_status = invoice.status.value
    invoice.status = LedgerStatus.VOIDED
    invoice.voided_reason = reason
    invoice.voided_by_user_id = principal.principal_id
    invoice.voided_at = datetime.now(UTC)
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="inventory.invoice.void",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        workshop_id=invoice.workshop_id,
        branch_id=invoice.branch_id,
        summary=f"Voided arrival {invoice.invoice_no}",
        details={"reason": reason, "lines": len(lines), "total_tiyin": invoice.total_tiyin},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        workshop_id=invoice.workshop_id,
        branch_id=invoice.branch_id,
        from_status=from_status,
        to_status=invoice.status.value,
        reason=reason,
        action_log_id=action.id,
    )
    await db.flush()
    return await get_invoice(db, principal=principal, invoice_id=invoice.id)


async def update_invoice(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    invoice_id: uuid.UUID,
    payload: SupplierInvoicePatchRequest,
) -> InvoiceRecord:
    """Correct the document — header facts, and optionally its whole line set.

    Supplier, date and doc number are all read derived, so changing one
    self-corrects the debt fold, the payment pill and the list with no sync
    step. Lines are the harder half: their movements already happened and later
    movements carry `balance_after` snapshots taken against them. They are
    therefore rewritten **wholesale** — the old `stock_in` rows are dropped, the
    submitted set is inserted, and every touched stock item has its whole chain
    replayed (`replay_stock_chain`). No delta arithmetic anywhere: the replay is
    what makes the edit safe.
    """

    invoice = await _invoice_for_mutation(db, principal=principal, invoice_id=invoice_id)
    scope = await _inventory_scope(db, principal=principal, branch_id=invoice.branch_id)
    if invoice.status is not LedgerStatus.RECORDED:
        raise APIError(
            "invoice_voided",
            "A cancelled invoice cannot be edited",
            status_code=status.HTTP_409_CONFLICT,
        )
    provided = payload.model_fields_set
    # Validate the whole edit before writing a single attribute. A half-applied
    # header left on a rejected request is not merely untidy: the request session
    # is shared, so the dirty row autoflushes into the next statement and fails
    # the DB CHECK far from the field that was actually wrong.
    supplier_id = payload.supplier_id if "supplier_id" in provided else invoice.supplier_id
    invoice_date = payload.invoice_date or invoice.invoice_date

    if supplier_id is not None and supplier_id != invoice.supplier_id:
        supplier = await _supplier_in_scope(db, scope=scope, supplier_id=supplier_id)
        if supplier.status is not SupplierStatus.ACTIVE:
            raise APIError("supplier_inactive", "Supplier is inactive", status_code=400)
    _not_future(invoice_date)

    # Resolve and price the new lines before anything is written, exactly as
    # creation does — a rejected line must leave neither header nor stock moved.
    priced = (
        await _priced_lines(db, scope=scope, lines=payload.lines)
        if payload.lines is not None
        else None
    )
    subtotal = (
        sum(line_total for _, _, _, line_total in priced)
        if priced is not None
        else invoice.subtotal_tiyin
    )
    # The two adjustment columns are no longer enterable but still stored, and
    # the DB CHECK caps the discount at the subtotal — a legacy row whose lines
    # are edited down below its discount is refused rather than corrupted.
    if invoice.discount_tiyin > subtotal:
        raise APIError(
            "invoice_discount_too_big",
            "Discount cannot exceed the invoice subtotal",
            status_code=400,
        )

    changed: dict[str, object] = {}
    if supplier_id != invoice.supplier_id:
        changed["supplier_id"] = str(supplier_id) if supplier_id else None
        invoice.supplier_id = supplier_id
    if invoice_date != invoice.invoice_date:
        changed["invoice_date"] = invoice_date.isoformat()
        invoice.invoice_date = invoice_date
    if priced is not None:
        total_before = invoice.total_tiyin
        removed = await _rewrite_lines(db, scope=scope, invoice=invoice, priced=priced)
        invoice.subtotal_tiyin = subtotal
        changed["lines"] = f"{removed} → {len(priced)}"
        changed["total_tiyin_before"] = total_before
    elif "supplier_id" in changed:
        # Header-only supplier change: the denormalized column on the lines feeds
        # the transactions tab and the last-price supplier preference, so it must
        # not go stale behind the header. (A line rewrite already writes it.)
        await db.execute(
            update(StockTransaction)
            .where(StockTransaction.invoice_id == invoice.id)
            .values(supplier_id=supplier_id)
        )
    # The stored total follows the same formula the DB CHECK enforces.
    invoice.total_tiyin = subtotal - invoice.discount_tiyin + invoice.surcharge_tiyin

    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="inventory.invoice.update",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        workshop_id=invoice.workshop_id,
        branch_id=invoice.branch_id,
        summary=f"Updated arrival {invoice.invoice_no}",
        details={"fields": sorted(changed), "values": changed, "total_tiyin": invoice.total_tiyin},
    )
    await db.flush()
    return await get_invoice(db, principal=principal, invoice_id=invoice.id)


_PricedLine = tuple[SupplierInvoiceLineInput, StockItem, MaterialRecord, int]


async def _priced_lines(
    db: AsyncSession,
    *,
    scope: BranchScope,
    lines: list[SupplierInvoiceLineInput],
) -> list[_PricedLine]:
    """Validate, resolve and price a submitted line set — creation's rules, reused.

    Stock rows are locked in `branch_material_id` order (the discipline creation
    and the void both use), so two concurrent edits touching overlapping
    materials cannot deadlock.
    """

    if not lines:
        raise APIError("invoice_lines_required", "Add at least one material line", status_code=400)
    for line in lines:
        if line.quantity <= 0:
            raise APIError("invalid_quantity", "Quantity must be positive", status_code=400)
        if line.unit_price_tiyin < 0:
            raise APIError("invalid_price", "Price cannot be negative", status_code=400)
    resolved: dict[uuid.UUID, tuple[StockItem, MaterialRecord]] = {}
    for branch_material_id in sorted(
        {line.branch_material_id for line in lines}, key=lambda value: str(value)
    ):
        resolved[branch_material_id] = await _stock_item_for_movement(
            db,
            scope=scope,
            branch_material_id=branch_material_id,
        )
    priced: list[_PricedLine] = []
    for line in lines:
        item, material = resolved[line.branch_material_id]
        priced.append(
            (
                line,
                item,
                material,
                stock_in_total_tiyin(material.type, line.quantity, line.unit_price_tiyin),
            )
        )
    return priced


async def _rewrite_lines(
    db: AsyncSession,
    *,
    scope: BranchScope,
    invoice: SupplierInvoice,
    priced: list[_PricedLine],
) -> int:
    """Swap the invoice's stock-in rows for the submitted set, then replay.

    The replacement rows keep the arrival's **original** entry timestamp and its
    original recorder as actor: an arrival must not jump to the top of the
    transactions log because someone fixed a typo, and who did the fixing is the
    audit log's job, not the ledger's.

    Returns how many lines the invoice carried before, for the audit entry.
    """

    existing = (await _lines_by_invoice(db, invoice_ids=[invoice.id])).get(invoice.id, [])
    # The lines' own timestamp, not the invoice row's: they are written a beat
    # after the header, and reusing the header's would nudge every corrected
    # arrival a few microseconds earlier in the ledger on each edit.
    entered_at = min(
        (line.transaction.created_at for line in existing),
        default=invoice.created_at,
    )
    # The union of the removed and the added items: dropping a material's only
    # line still has to take its quantity back out of that material's balance.
    touched = {line.stock_item.id for line in existing} | {item.id for _, item, _, _ in priced}
    await db.execute(
        delete(StockTransaction).where(
            StockTransaction.invoice_id == invoice.id,
            StockTransaction.type == StockTransactionType.STOCK_IN,
        )
    )
    for line, item, _, line_total in priced:
        db.add(
            StockTransaction(
                stock_item_id=item.id,
                type=StockTransactionType.STOCK_IN,
                quantity=line.quantity,
                # Rewritten by the replay below — every row on the chain is.
                balance_after=0,
                unit_price_tiyin=line.unit_price_tiyin,
                total_price_tiyin=line_total,
                supplier_id=invoice.supplier_id,
                invoice_id=invoice.id,
                actor_user_id=invoice.recorded_by_user_id,
                note=_optional_text(line.note),
                created_at=entered_at,
            )
        )
    await db.flush()
    # Deterministic lock order again — the replay takes its own `FOR UPDATE`.
    for stock_item_id in sorted(touched, key=lambda value: str(value)):
        balance = await replay_stock_chain(db, stock_item_id=stock_item_id)
        if balance >= 0:
            continue
        # Same call as `consume` and the void: the paper is being corrected to
        # match a physical world that already happened, so the edit is allowed
        # to land below zero — but it must not do so silently.
        replayed = await db.get(StockItem, stock_item_id)
        if replayed is None:  # pragma: no cover - the id came from a row just replayed
            continue
        _, material = await _stock_item_for_movement(
            db,
            scope=scope,
            branch_material_id=replayed.branch_material_id,
        )
        await _emit_negative_stock(db, scope=scope, stock_item=replayed, material=material)
    return len(existing)


async def _invoice_for_mutation(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    invoice_id: uuid.UUID,
) -> SupplierInvoice:
    """The invoice row a void/edit is about, existence-checked before scoping."""

    invoice = await db.get(SupplierInvoice, invoice_id)
    if invoice is None:
        raise APIError("invoice_not_found", "Invoice not found", status_code=404)
    await _inventory_scope(db, principal=principal, branch_id=invoice.branch_id)
    return invoice


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
        # A cancelled document is not payable — it left the debt fold too.
        SupplierInvoice.status == LedgerStatus.RECORDED,
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
    if invoice.status is not LedgerStatus.RECORDED:
        raise APIError(
            "invoice_voided",
            "This invoice is cancelled and cannot be paid",
            status_code=status.HTTP_409_CONFLICT,
        )
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
_InvoiceQuery = Select[tuple[SupplierInvoice, Supplier, Branch, WorkshopUser, WorkshopUser, int]]

# The voider is a second, independent join onto the same table as the recorder.
_VoidedBy = aliased(WorkshopUser, name="voided_by_user")


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
        select(SupplierInvoice, Supplier, Branch, WorkshopUser, _VoidedBy, _paid_tiyin())
        .outerjoin(Supplier, Supplier.id == SupplierInvoice.supplier_id)
        .outerjoin(Branch, Branch.id == SupplierInvoice.branch_id)
        .outerjoin(WorkshopUser, WorkshopUser.id == SupplierInvoice.recorded_by_user_id)
        .outerjoin(_VoidedBy, _VoidedBy.id == SupplierInvoice.voided_by_user_id)
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
            voided_by=voider,
        )
        for invoice, supplier, branch, recorder, voider, paid in rows
    ]


async def _lines_by_invoice(
    db: AsyncSession,
    *,
    invoice_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[InvoiceLineRecord]]:
    rows = (
        await db.execute(
            _material_join(
                select(
                    StockTransaction,
                    StockItem,
                    BranchMaterial,
                    DecorFormat,
                    Decor,
                    Manufacturer,
                ).join(StockItem, StockItem.id == StockTransaction.stock_item_id)
            )
            # `stock_in` only: a voided invoice also owns its `stock_in_void`
            # reversals, and those are movements on the transaction log, not
            # lines of the document.
            .where(
                StockTransaction.invoice_id.in_(invoice_ids),
                StockTransaction.type == StockTransactionType.STOCK_IN,
            )
            .order_by(StockTransaction.created_at, StockTransaction.id)
        )
    ).all()
    grouped: dict[uuid.UUID, list[InvoiceLineRecord]] = {}
    for transaction, item, branch_material, decor_format, decor, manufacturer in rows:
        if transaction.invoice_id is None:  # pragma: no cover - filtered in the query
            continue
        grouped.setdefault(transaction.invoice_id, []).append(
            InvoiceLineRecord(
                transaction=transaction,
                stock_item=item,
                branch_material=branch_material,
                decor_format=decor_format,
                decor=decor,
                manufacturer=manufacturer,
            )
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
