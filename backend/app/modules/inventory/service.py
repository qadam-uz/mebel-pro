"""Inventory, stock transaction, and supplier use cases."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from fastapi import status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    AuthenticatedPrincipalType,
    MaterialKind,
    Permission,
    StockTransactionType,
    SupplierStatus,
)
from app.modules.access.api import BranchScope, resolve_branch_scope, resolve_branch_scope_any
from app.modules.access.contracts import PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.inventory.contracts import StockItem, StockTransaction, Supplier
from app.modules.inventory.schemas import (
    StockAdjustmentRequest,
    StockInRequest,
    SupplierCreateRequest,
    SupplierInvoiceCreateRequest,
    SupplierInvoiceLineInput,
    SupplierPatchRequest,
)
from app.modules.support.api import record_action, record_status_change
from app.modules.support.contracts import Notification


@dataclass(frozen=True)
class StockRecord:
    stock_item: StockItem
    material: Material
    manufacturer: Manufacturer


@dataclass(frozen=True)
class TransactionRecord:
    transaction: StockTransaction
    stock_item: StockItem
    material: Material
    supplier: Supplier | None
    actor: WorkshopUser | None


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
    material_id: uuid.UUID,
    min_stock: int,
) -> StockItem:
    row = await db.scalar(
        select(StockItem).where(
            StockItem.branch_id == branch_id,
            StockItem.material_id == material_id,
        )
    )
    now = datetime.now(UTC)
    if row is None:
        row = StockItem(
            branch_id=branch_id,
            material_id=material_id,
            on_hand=0,
            min_stock=min_stock,
            updated_at=now,
        )
        db.add(row)
    else:
        row.min_stock = min_stock
        row.updated_at = now
    await db.flush()
    return row


async def sync_stock_item_min_stock(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    material_id: uuid.UUID,
    min_stock: int,
) -> StockItem:
    row = await ensure_stock_item_for_branch_material(
        db,
        branch_id=branch_id,
        material_id=material_id,
        min_stock=min_stock,
    )
    return row


async def list_stock(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    search: str | None = None,
    low_stock_only: bool = False,
) -> list[StockRecord]:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    query = (
        select(StockItem, Material, Manufacturer)
        .join(Material, Material.id == StockItem.material_id)
        .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
        .where(StockItem.branch_id == scope.branch_id)
        # A negative balance is a state that wants resolving — it sorts to the
        # top so nobody has to scroll past a minus sign to find it (QAD-150).
        .order_by((StockItem.on_hand < 0).desc(), Manufacturer.name, Material.name)
    )
    normalized = _optional_text(search)
    if normalized:
        pattern = f"%{normalized}%"
        query = query.where(
            Material.name.ilike(pattern)
            | Material.color.ilike(pattern)
            | Material.decor_code.ilike(pattern)
            | Manufacturer.name.ilike(pattern)
        )
    if low_stock_only:
        query = query.where(StockItem.on_hand <= StockItem.min_stock)
    return [
        StockRecord(stock_item=item, material=material, manufacturer=manufacturer)
        for item, material, manufacturer in (await db.execute(query)).all()
    ]


async def list_transactions(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    material_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TransactionRecord]:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    query = (
        select(StockTransaction, StockItem, Material, Supplier, WorkshopUser)
        .join(StockItem, StockItem.id == StockTransaction.stock_item_id)
        .join(Material, Material.id == StockItem.material_id)
        .outerjoin(Supplier, Supplier.id == StockTransaction.supplier_id)
        .outerjoin(WorkshopUser, WorkshopUser.id == StockTransaction.actor_user_id)
        .where(StockItem.branch_id == scope.branch_id)
        .order_by(StockTransaction.created_at.desc())
    )
    if material_id is not None:
        query = query.where(StockItem.material_id == material_id)
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
            material=material,
            supplier=supplier,
            actor=actor,
        )
        for tx, item, material, supplier, actor in (await db.execute(query)).all()
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
                    material_id=payload.material_id,
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
        material=line.material,
        supplier=record.supplier,
        actor=record.recorded_by,
    )


async def get_last_price(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    material_id: uuid.UUID,
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
                StockItem.material_id == material_id,
                StockTransaction.type == StockTransactionType.STOCK_IN,
                StockTransaction.unit_price_tiyin.is_not(None),
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
        material_id=payload.material_id,
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
        summary=f"Adjusted stock for {material.name}",
        details={"quantity": payload.quantity, "material_id": str(payload.material_id)},
    )
    return TransactionRecord(
        transaction=transaction,
        stock_item=item,
        material=material,
        supplier=None,
        actor=await db.get(WorkshopUser, principal.principal_id),
    )


async def consume_order_stock(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    material_id: uuid.UUID,
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
        material_id=material_id,
        allow_unlisted_material=True,
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
    material_id: uuid.UUID,
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
        material_id=material_id,
        allow_unlisted_material=True,
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
    # Only order-driven CONSUME may drive the balance negative: it records
    # material that physically already moved, and the arrival that was never
    # entered fixes the balance by itself once someone records it. A human typing
    # a stock-out that would go negative is almost certainly a typo, so those keep
    # the guard. Movements that *raise* the balance (stock-in, restore, a positive
    # adjustment) are always allowed — they heal a negative balance, never deepen
    # it, so a revert works from below zero too (QAD-150).
    if next_balance < 0 and quantity < 0 and type_ is not StockTransactionType.CONSUME:
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
    material_id: uuid.UUID,
    allow_unlisted_material: bool = False,
) -> tuple[StockItem, Material]:
    """The branch's locked stock row for a material, created at zero if absent.

    `allow_unlisted_material` is for the order-driven paths only. The branch
    catalog governs what is *offerable to new clients*; it must not govern
    whether material that already physically moved can be recorded (QAD-150), so
    consume/restore proceed on a zero-balance row and the material stays out of
    the catalog. Human-facing movements keep the catalog check.
    """

    branch_material = await db.scalar(
        select(BranchMaterial).where(
            BranchMaterial.branch_id == scope.branch_id,
            BranchMaterial.material_id == material_id,
        )
    )
    if branch_material is None and not allow_unlisted_material:
        raise APIError(
            "branch_material_not_found",
            "Material is not selected in this branch",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    query: Select[tuple[StockItem, Material]] = (
        select(StockItem, Material)
        .join(Material, Material.id == StockItem.material_id)
        .where(StockItem.branch_id == scope.branch_id, StockItem.material_id == material_id)
        .with_for_update()
    )
    row = (await db.execute(query)).one_or_none()
    if row is None:
        item = await ensure_stock_item_for_branch_material(
            db,
            branch_id=scope.branch_id,
            material_id=material_id,
            min_stock=branch_material.min_stock if branch_material is not None else 0,
        )
        material = await db.get(Material, material_id)
        if material is None:
            raise APIError("material_not_found", "Material not found", status_code=404)
        return item, material
    item, material = row
    return item, material


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
    material: Material,
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
    material: Material,
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
                    "material_id": str(material.id),
                    "material_name": material.name,
                    "on_hand": stock_item.on_hand,
                    "min_stock": stock_item.min_stock,
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
        )
        .order_by(StockTransaction.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(StockItem.on_hand, Material.kind, latest_price)
            .join(Material, Material.id == StockItem.material_id)
            .where(StockItem.branch_id == scope.branch_id, StockItem.on_hand != 0)
        )
    ).all()
    total = 0
    for on_hand, kind, price in rows:
        if price is None:
            continue
        if kind is MaterialKind.PANEL:
            total += on_hand * int(price)
        else:
            total += on_hand * int(price) // 1000
    return total


def stock_in_total_tiyin(kind: MaterialKind, quantity: int, unit_price_tiyin: int) -> int:
    """Total for a priced stock-in: per-panel for panels, per-metre over mm for edges.

    Mirrors the sale-side per-metre arithmetic so buy and sell math can't drift.
    """

    if kind is MaterialKind.PANEL:
        return quantity * unit_price_tiyin
    return quantity * unit_price_tiyin // 1000


def stock_unit(kind: MaterialKind) -> str:
    return "panel" if kind is MaterialKind.PANEL else "millimetre"


def display_unit(kind: MaterialKind) -> str:
    return "panel" if kind is MaterialKind.PANEL else "metre"


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
