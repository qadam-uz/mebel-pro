"""Inventory, stock transaction, and supplier use cases."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from fastapi import status
from sqlalchemy import ColumnElement, Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.core.search_query import SearchPlan, capped, run_search_tiers
from app.models.enums import (
    AuthenticatedPrincipalType,
    DecorType,
    LedgerStatus,
    Permission,
    StockTransactionType,
    SupplierStatus,
)
from app.modules.access.api import BranchScope, resolve_branch_scope, resolve_branch_scope_any
from app.modules.access.contracts import PermissionGrant, WorkshopUser

# The label and its snapshot vocabulary are catalog's to define — inventory only
# renders them. Importing through catalog's public api keeps one writer for the
# key set that `app/core/material_label.py` reads.
from app.modules.catalog.api import (
    apply_decor_search,
    branch_material_label,
    format_dimension_arms,
    set_branch_material_min_stock,
)
from app.modules.catalog.contracts import BranchMaterial, Decor, DecorFormat, Manufacturer, is_tape
from app.modules.inventory.contracts import StockItem, StockTransaction, Supplier, SupplierInvoice
from app.modules.inventory.schemas import (
    StockAdjustmentRequest,
    StockInRequest,
    SupplierCreateRequest,
    SupplierInvoiceCreateRequest,
    SupplierInvoiceLineInput,
    SupplierPatchRequest,
)

# Only the `order_number` a consume/restore row carries — sales owns the model
# and exports it for exactly this kind of same-transaction SQL composition.
from app.modules.sales.contracts import Order
from app.modules.support.api import record_action, record_status_change
from app.modules.support.contracts import Notification


@dataclass(frozen=True)
class MaterialRecord:
    """The four rows that together are "a material" after the format reshape.

    Stock points at a `BranchMaterial` (the branch's decision to carry a
    format); the `DecorFormat` says what the sheet or tape physically is, and
    the decor plus its manufacturer carry the pattern identity that gets
    displayed. There is no stored name anywhere, so every caller that needs one
    asks `label`.
    """

    branch_material: BranchMaterial
    decor_format: DecorFormat
    decor: Decor
    manufacturer: Manufacturer

    @property
    def label(self) -> str:
        return branch_material_label(
            self.decor_format, self.decor, self.manufacturer, self.branch_material.id
        )

    @property
    def type(self) -> DecorType:
        return self.decor_format.type


def is_low_stock(on_hand: int, min_stock: int) -> bool:
    """The one low-stock predicate, in Python.

    A row is low when the books went negative, or when the owner set a real
    threshold and the balance has reached it. `min_stock = 0` means monitoring
    is **off**: attaching a format mints a zero-balance stock row, and a branch
    that registers its supplier's whole price list would otherwise see every one
    of those rows wearing the warning — a warning that is everywhere is nowhere.

    The `on_hand < 0` arm is load-bearing and independent of the threshold: a
    negative balance is an unrecorded arrival (QAD-150) and has to stay visible
    under the "Kam qolgan" filter and in the dashboard card that counts it.
    """

    return on_hand < 0 or (min_stock > 0 and on_hand <= min_stock)


def low_stock_condition() -> ColumnElement[bool]:
    """The same predicate in SQL, over `StockItem` joined to `BranchMaterial`."""

    return or_(
        StockItem.on_hand < 0,
        and_(BranchMaterial.min_stock > 0, StockItem.on_hand <= BranchMaterial.min_stock),
    )


@dataclass(frozen=True)
class StockRecord:
    stock_item: StockItem
    branch_material: BranchMaterial
    decor_format: DecorFormat
    decor: Decor
    manufacturer: Manufacturer

    @property
    def label(self) -> str:
        return branch_material_label(
            self.decor_format, self.decor, self.manufacturer, self.branch_material.id
        )

    @property
    def is_low(self) -> bool:
        return is_low_stock(self.stock_item.on_hand, self.branch_material.min_stock)


@dataclass(frozen=True)
class TransactionRecord:
    transaction: StockTransaction
    stock_item: StockItem
    branch_material: BranchMaterial
    decor_format: DecorFormat
    decor: Decor
    manufacturer: Manufacturer
    supplier: Supplier | None
    actor: WorkshopUser | None
    # The `K-…` of the arrival document, when the row belongs to one — the
    # transactions tab renders it as the link into the invoice detail.
    invoice_no: str | None = None
    # The order a `consume` / `restore` belongs to. Same reason as `invoice_no`:
    # a movement's context is a document the reader can open, and an opaque id
    # prefix is not a document reference.
    order_number: str | None = None

    @property
    def label(self) -> str:
        return branch_material_label(
            self.decor_format, self.decor, self.manufacturer, self.branch_material.id
        )


def priced_from_a_live_invoice() -> ColumnElement[bool]:
    """True for a stock-in row whose document still stands.

    A voided invoice's prices stop being price history: the typo that forced the
    void is exactly the number that must not come back as tomorrow's suggestion,
    and stock the document never really delivered must not be valued at it. Rows
    with no invoice at all (pre-document arrivals) are unaffected.
    """

    return ~(
        select(SupplierInvoice.id)
        .where(
            SupplierInvoice.id == StockTransaction.invoice_id,
            SupplierInvoice.status == LedgerStatus.VOIDED,
        )
        .exists()
    )


@dataclass(frozen=True)
class LastPriceRecord:
    unit_price_tiyin: int
    recorded_at: datetime
    supplier_id: uuid.UUID | None
    supplier_name: str | None


async def ensure_stock_item_for_branch_material(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
) -> StockItem:
    """The branch's balance row for one branch material, created at zero if absent.

    `branch_id` is the denormalized scoping column on `stock_items`: callers must
    pass the branch material's own branch, never an unrelated one (see the note
    on `StockItem`). The row itself is keyed by `branch_material_id` alone, which
    is what the unique index enforces.

    Idempotent, and it no longer carries a threshold: the low-stock threshold is
    read from `branch_materials.min_stock` wherever it is needed, so there is
    nothing here left to keep in sync.
    """

    row = await db.scalar(
        select(StockItem).where(StockItem.branch_material_id == branch_material_id)
    )
    if row is not None:
        return row
    row = StockItem(
        branch_id=branch_id,
        branch_material_id=branch_material_id,
        on_hand=0,
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


async def list_stock(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    search: str | None = None,
    low_stock_only: bool = False,
    moved_only: bool = False,
    types: list[DecorType] | None = None,
    limit: int | None = None,
) -> list[StockRecord]:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    query = _material_join(
        select(StockItem, BranchMaterial, DecorFormat, Decor, Manufacturer)
    ).where(StockItem.branch_id == scope.branch_id)
    if types:
        # Plural, mirroring the catalog's `types`: one label the operator reads
        # can cover more than one wire value — `ldsp` and `dsp` are both «LDSP»
        # on every screen — and a filter must never make the reader guess which
        # of two identical-looking options is theirs.
        query = query.where(DecorFormat.type.in_(types))
    if low_stock_only:
        # The threshold lives on the branch material, which `_material_join` has
        # already joined — so the single source of truth costs nothing here.
        query = query.where(low_stock_condition())
    if moved_only:
        # "Has moved" is deliberately *any* movement, a lone adjust or a
        # consume-driven negative included: one movement is exactly what makes a
        # row warehouse rather than catalog ballast. A plain EXISTS over the FK
        # is enough at a few hundred rows per branch — measure before inventing
        # a `last_movement_at` column to denormalize it.
        query = query.where(
            select(StockTransaction.id)
            .where(StockTransaction.stock_item_id == StockItem.id)
            .exists()
        )

    async def run(plan: SearchPlan) -> list[StockRecord]:
        # The catalog's one matcher, with the warehouse's own ordering under it:
        # a negative balance is a state that wants resolving, so it sorts to the
        # top and nobody scrolls past a minus sign to find it (QAD-150). There is
        # no stored material name to sort on any more, so the rest of the order
        # is the identity the reader sees: maker, decor, then thickness. The row
        # here *is* a format, so a number is matched on it directly.
        searched = apply_decor_search(
            query,
            plan,
            ordering=(
                (StockItem.on_hand < 0).desc(),
                Manufacturer.name,
                Decor.name,
                DecorFormat.thickness_mm,
            ),
            dimension_arms=format_dimension_arms,
        )
        page = capped(limit, plan.limit)
        if page is not None:
            # Callers that only render a few rows (the global search preview) say
            # so. Unbounded is still the default: the inventory table itself
            # pages in the client and a silent cap there would hide stock.
            searched = searched.limit(page)
        return [
            StockRecord(
                stock_item=item,
                branch_material=branch_material,
                decor_format=decor_format,
                decor=decor,
                manufacturer=manufacturer,
            )
            for item, branch_material, decor_format, decor, manufacturer in (
                await db.execute(searched)
            ).all()
        ]

    return await run_search_tiers(db, search, run)


async def list_transactions(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TransactionRecord]:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    query = (
        _material_join(
            select(
                StockTransaction,
                StockItem,
                BranchMaterial,
                DecorFormat,
                Decor,
                Manufacturer,
                Supplier,
                WorkshopUser,
                SupplierInvoice.invoice_no,
                Order.order_number,
            ).join(StockItem, StockItem.id == StockTransaction.stock_item_id)
        )
        .outerjoin(Supplier, Supplier.id == StockTransaction.supplier_id)
        .outerjoin(WorkshopUser, WorkshopUser.id == StockTransaction.actor_user_id)
        .outerjoin(SupplierInvoice, SupplierInvoice.id == StockTransaction.invoice_id)
        .outerjoin(Order, Order.id == StockTransaction.order_id)
        .where(StockItem.branch_id == scope.branch_id)
        .order_by(StockTransaction.created_at.desc())
    )
    if branch_material_id is not None:
        query = query.where(StockItem.branch_material_id == branch_material_id)
    if date_from is not None:
        query = query.where(
            StockTransaction.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC)
        )
    if date_to is not None:
        query = query.where(
            StockTransaction.created_at
            < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
        )
    query = query.limit(max(1, min(limit, 100))).offset(max(0, offset))
    return [
        TransactionRecord(
            transaction=tx,
            stock_item=item,
            branch_material=branch_material,
            decor_format=decor_format,
            decor=decor,
            manufacturer=manufacturer,
            supplier=supplier,
            actor=actor,
            invoice_no=invoice_no,
            order_number=order_number,
        )
        for (
            tx,
            item,
            branch_material,
            decor_format,
            decor,
            manufacturer,
            supplier,
            actor,
            invoice_no,
            order_number,
        ) in (await db.execute(query)).all()
    ]


async def list_suppliers(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    status_filter: SupplierStatus | None = None,
) -> list[Supplier]:
    scope = await _supplier_read_scope(db, principal=principal, branch_id=branch_id)
    query = (
        select(Supplier)
        .where(Supplier.workshop_id == scope.workshop_id)
        .order_by(Supplier.status, Supplier.name)
    )
    if status_filter is not None:
        query = query.where(Supplier.status == status_filter)
    return list((await db.scalars(query)).all())


async def create_supplier(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: SupplierCreateRequest,
) -> Supplier:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    row = await _create_supplier_for_scope(
        db,
        principal=principal,
        scope=scope,
        name=payload.name,
        phone=payload.phone,
        note=payload.note,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="inventory.supplier.create",
        entity_type="supplier",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Created supplier {row.name}",
    )
    await db.refresh(row)
    return row


async def update_supplier(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    supplier_id: uuid.UUID,
    payload: SupplierPatchRequest,
) -> Supplier:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    row = await _supplier_in_scope(db, scope=scope, supplier_id=supplier_id)
    if "name" in payload.model_fields_set and payload.name is not None:
        row.name = _required_text(payload.name, "supplier_name_required")
    if "phone" in payload.model_fields_set:
        row.phone = _optional_text(payload.phone)
    if "note" in payload.model_fields_set:
        row.note = _optional_text(payload.note)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="inventory.supplier.update",
        entity_type="supplier",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Updated supplier {row.name}",
    )
    await db.refresh(row)
    return row


async def set_supplier_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    supplier_id: uuid.UUID,
    to_status: SupplierStatus,
) -> Supplier:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    row = await _supplier_in_scope(db, scope=scope, supplier_id=supplier_id)
    if row.status is to_status:
        return row
    from_status = row.status.value
    row.status = to_status
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"inventory.supplier.{to_status.value}",
        entity_type="supplier",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Set supplier {row.name} to {to_status.value}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="supplier",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        from_status=from_status,
        to_status=to_status.value,
        action_log_id=action.id,
    )
    await db.refresh(row)
    return row


async def record_stock_in(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: StockInRequest,
) -> TransactionRecord:
    """Record a single-material arrival as a one-line invoice.

    Kept as its own use case for callers that hand over one material at a time,
    but it goes through the same document path as a multi-line faktura: a
    stock-in without an invoice would silently drop out of the supplier balance,
    which now folds over invoice totals.
    """

    # Local import: `invoices` builds on this module's movement helpers, so the
    # dependency can only be closed at call time.
    from app.modules.inventory.invoices import create_invoice

    record = await create_invoice(
        db,
        principal=principal,
        payload=SupplierInvoiceCreateRequest(
            branch_id=branch_id,
            supplier_id=payload.supplier_id,
            supplier=payload.supplier,
            note=payload.note,
            lines=[
                SupplierInvoiceLineInput(
                    branch_material_id=payload.branch_material_id,
                    quantity=payload.quantity,
                    unit_price_tiyin=payload.unit_price_tiyin,
                    note=payload.note,
                )
            ],
        ),
    )
    line = record.lines[0]
    return TransactionRecord(
        transaction=line.transaction,
        stock_item=line.stock_item,
        branch_material=line.branch_material,
        decor_format=line.decor_format,
        decor=line.decor,
        manufacturer=line.manufacturer,
        supplier=record.supplier,
        actor=record.recorded_by,
    )


async def get_last_price(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    supplier_id: uuid.UUID | None = None,
) -> LastPriceRecord | None:
    """Latest priced stock-in for a branch's material, preferring the given supplier's."""

    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)

    def query(only_supplier: uuid.UUID | None) -> Select[tuple[StockTransaction, Supplier]]:
        q = (
            select(StockTransaction, Supplier)
            .join(StockItem, StockItem.id == StockTransaction.stock_item_id)
            .outerjoin(Supplier, Supplier.id == StockTransaction.supplier_id)
            .where(
                StockItem.branch_id == scope.branch_id,
                StockItem.branch_material_id == branch_material_id,
                StockTransaction.type == StockTransactionType.STOCK_IN,
                StockTransaction.unit_price_tiyin.is_not(None),
                priced_from_a_live_invoice(),
            )
        )
        if only_supplier is not None:
            q = q.where(StockTransaction.supplier_id == only_supplier)
        return q.order_by(StockTransaction.created_at.desc()).limit(1)

    row = None
    if supplier_id is not None:
        row = (await db.execute(query(supplier_id))).first()
    if row is None:
        row = (await db.execute(query(None))).first()
    if row is None:
        return None
    transaction, supplier = row
    if transaction.unit_price_tiyin is None:  # pragma: no cover - filtered in the query
        return None
    return LastPriceRecord(
        unit_price_tiyin=transaction.unit_price_tiyin,
        recorded_at=transaction.created_at,
        supplier_id=transaction.supplier_id,
        supplier_name=supplier.name if supplier else None,
    )


async def record_adjustment(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: StockAdjustmentRequest,
) -> TransactionRecord:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    if payload.quantity == 0:
        raise APIError("invalid_quantity", "Quantity cannot be zero", status_code=400)
    note = _required_text(payload.note, "adjustment_note_required")
    item, material = await _stock_item_for_movement(
        db,
        scope=scope,
        branch_material_id=payload.branch_material_id,
    )
    transaction = await _apply_stock_delta(
        db,
        principal=principal,
        stock_item=item,
        type_=StockTransactionType.ADJUST,
        quantity=payload.quantity,
        supplier_id=None,
        note=note,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="inventory.adjust",
        entity_type="stock_transaction",
        entity_id=transaction.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Adjusted stock for {material.label}",
        details={
            "quantity": payload.quantity,
            "branch_material_id": str(payload.branch_material_id),
        },
    )
    return TransactionRecord(
        transaction=transaction,
        stock_item=item,
        branch_material=material.branch_material,
        decor_format=material.decor_format,
        decor=material.decor,
        manufacturer=material.manufacturer,
        supplier=None,
        actor=await db.get(WorkshopUser, principal.principal_id),
    )


async def stock_row_for_material(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_material_id: uuid.UUID,
) -> StockRecord:
    """One material's balance row, addressed by the material alone.

    The stock surface is branch-scoped everywhere else, because a warehouse is a
    branch's. A material *page* cannot be: it is opened from a link, a reload or
    a colleague's message, and asking the reader to first put the topbar on the
    right branch would make half of those land on the wrong warehouse — or on
    nothing. A branch material belongs to exactly one branch, so the branch is
    derivable, and deriving it is what makes the URL self-contained.

    Read-only: unlike the movement paths this never mints a missing balance row.
    """

    row = (
        await db.execute(
            _material_join(
                select(StockItem, BranchMaterial, DecorFormat, Decor, Manufacturer)
            ).where(StockItem.branch_material_id == branch_material_id)
        )
    ).first()
    if row is None:
        raise APIError(
            "stock_item_not_found",
            "Stock item not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    item, branch_material, decor_format, decor, manufacturer = row
    # The permission check runs against the branch the row itself names, so a
    # reader who may not see that branch gets the same refusal as anywhere else.
    await _inventory_scope(db, principal=principal, branch_id=item.branch_id)
    return StockRecord(
        stock_item=item,
        branch_material=branch_material,
        decor_format=decor_format,
        decor=decor,
        manufacturer=manufacturer,
    )


async def set_min_stock(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    min_stock: int,
) -> StockRecord:
    """Set a material's low-stock threshold from the stock surface.

    Two doors, one fact: the catalog form (`manage_catalog`) and this route
    (`manage_inventory`) write the same `branch_materials.min_stock` column —
    the threshold is warehouse policy, and "5 emas, 10 bo'lsin" is decided
    standing in front of the shelf. The row itself belongs to the catalog
    module, so the write goes through its public api.
    """

    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    item, material = await _stock_item_for_movement(
        db,
        scope=scope,
        branch_material_id=branch_material_id,
    )
    previous = material.branch_material.min_stock
    await set_branch_material_min_stock(
        db,
        branch_material_id=branch_material_id,
        branch_id=scope.branch_id,
        min_stock=min_stock,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="inventory.min_stock.update",
        entity_type="branch_material",
        entity_id=branch_material_id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Set min stock for {material.label} from {previous} to {min_stock}",
        details={"min_stock": min_stock, "previous_min_stock": previous},
    )
    return StockRecord(
        stock_item=item,
        branch_material=material.branch_material,
        decor_format=material.decor_format,
        decor=material.decor,
        manufacturer=material.manufacturer,
    )


async def consume_order_stock(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    order_id: uuid.UUID,
    quantity: int,
) -> StockTransaction:
    """Consume branch stock for an order-driven production step."""

    if quantity <= 0:
        raise APIError("invalid_quantity", "Quantity must be positive", status_code=400)
    scope = await _system_scope_for_branch(db, branch_id=branch_id)
    item, material = await _stock_item_for_movement(
        db,
        scope=scope,
        branch_material_id=branch_material_id,
    )
    transaction = await _apply_stock_delta(
        db,
        principal=None,
        stock_item=item,
        type_=StockTransactionType.CONSUME,
        quantity=-quantity,
        supplier_id=None,
        order_id=order_id,
        note=None,
    )
    if item.on_hand < 0:
        await _emit_negative_stock(db, scope=scope, stock_item=item, material=material)
    return transaction


async def restore_order_stock(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    order_id: uuid.UUID,
    quantity: int,
) -> StockTransaction:
    """Restore branch stock for an order revert."""

    if quantity <= 0:
        raise APIError("invalid_quantity", "Quantity must be positive", status_code=400)
    scope = await _system_scope_for_branch(db, branch_id=branch_id)
    # A restore raises the balance, so nothing here needs to notify: the
    # material is looked up only to create/validate the stock row.
    item, _ = await _stock_item_for_movement(
        db,
        scope=scope,
        branch_material_id=branch_material_id,
    )
    transaction = await _apply_stock_delta(
        db,
        principal=None,
        stock_item=item,
        type_=StockTransactionType.RESTORE,
        quantity=quantity,
        supplier_id=None,
        order_id=order_id,
        note=None,
    )
    return transaction


async def replay_stock_chain(db: AsyncSession, *, stock_item_id: uuid.UUID) -> int:
    """Recompute a stock item's whole movement chain from its transactions.

    Every other movement in this module only ever *appends*, where the cheap
    delta arithmetic in `_apply_stock_delta` is correct. Editing an invoice's
    lines is the one path that rewrites movements which already have later
    movements behind them, and no delta can repair the `balance_after`
    snapshots those later rows carry.

    So the chain is replayed instead of patched: read the item's transactions in
    ledger order, run the sum, rewrite every `balance_after`, and land `on_hand`
    on the total. That promotes an invariant which until now held only by
    construction into one the code enforces — **`on_hand == Σ quantity` over the
    item's transactions, always.**

    A voided invoice's `stock_in` rows are deliberately *not* skipped: its
    `stock_in_void` rows cancel them, so the arithmetic is right and the history
    stays readable as what happened.

    Returns the resulting balance, which **may be negative** — the caller
    decides whether that crossing deserves a notification.
    """

    item = await db.scalar(select(StockItem).where(StockItem.id == stock_item_id).with_for_update())
    if item is None:  # pragma: no cover - the caller always holds a real row
        raise APIError("stock_item_not_found", "Stock item not found", status_code=404)
    # `(created_at, id)` is the ledger's own order — the same one the
    # transactions log and the invoice line read use, so a replayed
    # `balance_after` column reads consistently down the screen.
    rows = (
        await db.scalars(
            select(StockTransaction)
            .where(StockTransaction.stock_item_id == stock_item_id)
            .order_by(StockTransaction.created_at, StockTransaction.id)
        )
    ).all()
    running = 0
    for row in rows:
        running += row.quantity
        row.balance_after = running
    item.on_hand = running
    item.updated_at = datetime.now(UTC)
    await db.flush()
    return running


_MAY_GO_NEGATIVE: frozenset[StockTransactionType] = frozenset(
    {StockTransactionType.CONSUME, StockTransactionType.STOCK_IN_VOID}
)


async def _apply_stock_delta(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal | None,
    stock_item: StockItem,
    type_: StockTransactionType,
    quantity: int,
    supplier_id: uuid.UUID | None,
    note: str | None,
    order_id: uuid.UUID | None = None,
    unit_price_tiyin: int | None = None,
    total_price_tiyin: int | None = None,
    invoice_id: uuid.UUID | None = None,
) -> StockTransaction:
    next_balance = stock_item.on_hand + quantity
    # Only system-driven movements may drive the balance negative: they record
    # material that physically already moved, and the arrival that was never
    # entered fixes the balance by itself once someone records it. A human typing
    # a stock-out that would go negative is almost certainly a typo, so those keep
    # the guard. Movements that *raise* the balance (stock-in, restore, a positive
    # adjustment) are always allowed — they heal a negative balance, never deepen
    # it, so a revert works from below zero too (QAD-150).
    #
    # `STOCK_IN_VOID` joins `CONSUME` on the system side: the paper was wrong but
    # the goods either never arrived or already left, so refusing the reversal
    # would leave the books permanently too high — the exact failure QAD-150 was
    # written against. It notifies instead of blocking.
    if next_balance < 0 and quantity < 0 and type_ not in _MAY_GO_NEGATIVE:
        raise APIError("stock_below_zero", "Stock cannot go below zero", status_code=400)
    stock_item.on_hand = next_balance
    stock_item.updated_at = datetime.now(UTC)
    transaction = StockTransaction(
        stock_item_id=stock_item.id,
        type=type_,
        quantity=quantity,
        balance_after=next_balance,
        unit_price_tiyin=unit_price_tiyin,
        total_price_tiyin=total_price_tiyin,
        order_id=order_id,
        supplier_id=supplier_id,
        invoice_id=invoice_id,
        actor_user_id=principal.principal_id if principal is not None else None,
        note=note,
        created_at=datetime.now(UTC),
    )
    db.add(transaction)
    await db.flush()
    return transaction


async def _stock_item_for_movement(
    db: AsyncSession,
    *,
    scope: BranchScope,
    branch_material_id: uuid.UUID,
) -> tuple[StockItem, MaterialRecord]:
    """The branch's locked stock row for a branch material, created at zero if absent.

    The old `allow_unlisted_material` escape hatch is gone with the model it was
    written for. It existed because an order could reference a *platform*
    material the branch never listed, and QAD-150 says material that physically
    moved must still be recordable: consume/restore therefore created a bare
    stock row while the catalog stayed untouched. Now the branch material *is*
    the material — an order item points straight at this row — so "the branch
    does not carry it" is no longer a state an order can be in; de-catalogued
    means `status = inactive`, which still consumes. What QAD-150 actually needs
    survives untouched: the stock row is created at zero when it is missing, and
    `_apply_stock_delta` still lets an order-driven consume go negative.

    Deliberately no status filter, exactly as before: a material withdrawn from
    the branch's offer list can still receive and release stock.
    """

    row = (
        await db.execute(
            select(BranchMaterial, DecorFormat, Decor, Manufacturer)
            .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
            .join(Decor, Decor.id == DecorFormat.decor_id)
            .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
            .where(
                BranchMaterial.id == branch_material_id,
                # Branch-scoped, so another branch's format id can never mint a
                # stock row whose `branch_id` disagrees with its material's.
                BranchMaterial.branch_id == scope.branch_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise APIError(
            "branch_material_not_found",
            "Material is not selected in this branch",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    branch_material, decor_format, decor, manufacturer = row
    material = MaterialRecord(
        branch_material=branch_material,
        decor_format=decor_format,
        decor=decor,
        manufacturer=manufacturer,
    )
    item = await db.scalar(
        select(StockItem)
        .where(StockItem.branch_material_id == branch_material.id)
        .with_for_update()
    )
    if item is None:
        item = await ensure_stock_item_for_branch_material(
            db,
            branch_id=branch_material.branch_id,
            branch_material_id=branch_material.id,
        )
    return item, material


def _material_join[SelectT: Select[Any]](query: SelectT) -> SelectT:
    """Stock -> branch material -> decor format -> decor -> manufacturer.

    The branch row carries only price, threshold and status now; the substrate
    and every dimension live on the platform's format, and the pattern identity
    on the decor. Every read that shows a material to a human needs all four.
    """

    return (
        query.join(BranchMaterial, BranchMaterial.id == StockItem.branch_material_id)
        .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
        .join(Decor, Decor.id == DecorFormat.decor_id)
        .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
    )


async def _inventory_scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> BranchScope:
    if principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_INVENTORY,
    )


async def _supplier_read_scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> BranchScope:
    """Read scope for the supplier lookup list — inventory **or** finance.

    The list names counterparties, not stock: Ombor picks one for an arrival and
    the finance ledger attributes an expense to one. `manage_finance` already
    reads and writes supplier money workshop-wide (debts, invoice payments), so
    gating the names behind `manage_inventory` gave the accountant an empty
    picker on the page built for them (QAD-169). Writes stay inventory-only.
    """
    if principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return await resolve_branch_scope_any(
        db,
        principal,
        branch_id=branch_id,
        permissions=(Permission.MANAGE_INVENTORY, Permission.MANAGE_FINANCE),
    )


async def _system_scope_for_branch(db: AsyncSession, *, branch_id: uuid.UUID) -> BranchScope:
    from app.modules.workshop.contracts import Branch

    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise APIError("branch_not_found", "Branch not found", status_code=404)
    return BranchScope(workshop_id=branch.workshop_id, branch_id=branch.id)


async def _supplier_in_scope(
    db: AsyncSession,
    *,
    scope: BranchScope,
    supplier_id: uuid.UUID,
) -> Supplier:
    row = await db.get(Supplier, supplier_id)
    if row is None or row.workshop_id != scope.workshop_id:
        raise APIError("supplier_not_found", "Supplier not found", status_code=404)
    return row


async def _create_supplier_for_scope(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    scope: BranchScope,
    name: str,
    phone: str | None,
    note: str | None,
) -> Supplier:
    row = Supplier(
        workshop_id=scope.workshop_id,
        name=_required_text(name, "supplier_name_required"),
        phone=_optional_text(phone),
        note=_optional_text(note),
        status=SupplierStatus.ACTIVE,
        created_by_user_id=principal.principal_id,
    )
    db.add(row)
    await db.flush()
    return row


async def _emit_negative_stock(
    db: AsyncSession,
    *,
    scope: BranchScope,
    stock_item: StockItem,
    material: MaterialRecord,
) -> None:
    """A consume drove the books negative — nobody is blocked, but it can't be silent."""

    await _notify_inventory_holders(
        db,
        scope=scope,
        stock_item=stock_item,
        material=material,
        event_code="inventory.negative_stock",
    )


async def _notify_inventory_holders(
    db: AsyncSession,
    *,
    scope: BranchScope,
    stock_item: StockItem,
    material: MaterialRecord,
    event_code: str,
) -> None:
    recipient_ids = set(
        (
            await db.scalars(
                select(WorkshopUser.id).where(
                    WorkshopUser.workshop_id == scope.workshop_id,
                    WorkshopUser.is_owner.is_(True),
                )
            )
        ).all()
    )
    recipient_ids.update(
        (
            await db.scalars(
                select(PermissionGrant.workshop_user_id).where(
                    PermissionGrant.branch_id == scope.branch_id,
                    PermissionGrant.permission == Permission.MANAGE_INVENTORY,
                )
            )
        ).all()
    )
    now = datetime.now(UTC)
    # `material_name` is a computed label now — there is no stored name to read —
    # but the payload key stays: it is what the notification renderers read.
    material_name = material.label
    for recipient_id in recipient_ids:
        db.add(
            Notification(
                recipient_type=AuthenticatedPrincipalType.WORKSHOP_USER,
                recipient_id=recipient_id,
                event_code=event_code,
                entity_type="stock_item",
                entity_id=stock_item.id,
                payload={
                    "branch_id": str(scope.branch_id),
                    "branch_material_id": str(material.branch_material.id),
                    "material_name": material_name,
                    "on_hand": stock_item.on_hand,
                    "min_stock": material.branch_material.min_stock,
                },
                created_at=now,
            )
        )
    await db.flush()


async def stock_value(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> int:
    """The branch's on-hand quantity valued at the latest purchase price.

    Derived at read time like every other money number: per stock item, the most
    recent priced stock-in's unit price times what is physically on hand (edges:
    mm x per-metre // 1000). Items that never had a priced stock-in count zero.

    Negative balances count negatively rather than being clamped away: the figure
    is what the books say, and hiding an unrecorded arrival would make the total
    silently too high (QAD-150).
    """

    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    latest_price = (
        select(StockTransaction.unit_price_tiyin)
        .where(
            StockTransaction.stock_item_id == StockItem.id,
            StockTransaction.type == StockTransactionType.STOCK_IN,
            StockTransaction.unit_price_tiyin.is_not(None),
            priced_from_a_live_invoice(),
        )
        .order_by(StockTransaction.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(StockItem.on_hand, DecorFormat.type, latest_price)
            .join(BranchMaterial, BranchMaterial.id == StockItem.branch_material_id)
            .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
            .where(StockItem.branch_id == scope.branch_id, StockItem.on_hand != 0)
        )
    ).all()
    total = 0
    for on_hand, type, price in rows:
        if price is None:
            continue
        if is_tape(type):
            total += on_hand * int(price) // 1000
        else:
            total += on_hand * int(price)
    return total


def stock_in_total_tiyin(type: DecorType, quantity: int, unit_price_tiyin: int) -> int:
    """Total for a priced stock-in: per-panel for panels, per-metre over mm for kromka.

    Mirrors the sale-side per-metre arithmetic so buy and sell math can't drift.
    """

    if is_tape(type):
        return quantity * unit_price_tiyin // 1000
    return quantity * unit_price_tiyin


def stock_unit(type: DecorType) -> str:
    """The unit stock is *counted* in: whole panels, or millimetres of tape."""

    return "millimetre" if is_tape(type) else "panel"


def display_unit(type: DecorType) -> str:
    """The unit stock is *shown and priced* in: panels, or metres of tape."""

    return "metre" if is_tape(type) else "panel"


def _required_text(value: str, code: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise APIError(code, "Required field is missing", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None
