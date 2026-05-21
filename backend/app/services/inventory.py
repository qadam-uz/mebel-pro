"""Inventory — atomic, row-locked stock operations + suppliers.

Every operation locks the stock-item row (``FOR UPDATE`` where the dialect
supports it; a no-op on SQLite in tests), mutates ``on_hand``, writes one
``StockTransaction`` with ``balance_after``, and never lets ``on_hand`` go below
0. ``stock_in`` / ``adjust`` carry an actor; the system primitives ``consume`` /
``restore`` carry an ``order_id`` and no actor — the orders module imports them.
Low-stock fires to the branch's ``manage_inventory`` grantees + owner when
``on_hand <= min_stock`` after a change. Spec:
docs/ref/entities/inventory.md, docs/ref/features/catalog-inventory.md.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, forbidden, not_found
from app.core.principal import Principal
from app.models.enums import (
    OrderStatus,
    Permission,
    StockTransactionType,
    SupplierStatus,
)
from app.models.inventory import StockItem, StockTransaction, Supplier
from app.models.sales import Order, OrderItem
from app.models.workshop import Branch
from app.services import audit, notifications, recipients, workshops

# --- helpers ----------------------------------------------------------------


async def _lock_stock_item(db: AsyncSession, stock_item_id: uuid.UUID) -> StockItem:
    """Fetch a stock item with a row lock (no-op on SQLite)."""
    stmt = select(StockItem).where(StockItem.id == stock_item_id).with_for_update()
    item = (await db.execute(stmt)).scalar_one_or_none()
    if item is None:
        raise not_found("Stock item not found.")
    return item


async def get_or_create_stock_item(
    db: AsyncSession, branch_id: uuid.UUID, material_id: uuid.UUID
) -> StockItem:
    item = (
        await db.execute(
            select(StockItem).where(
                StockItem.branch_id == branch_id, StockItem.material_id == material_id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        item = StockItem(branch_id=branch_id, material_id=material_id, on_hand=0, min_stock=0)
        db.add(item)
        await db.flush()
    return item


async def _maybe_fire_low_stock(db: AsyncSession, branch: Branch, item: StockItem) -> None:
    if item.on_hand <= item.min_stock:
        await notifications.notify_many(
            db,
            recipients=await recipients.low_stock_recipients(db, branch),
            event_code="low_stock",
            entity_type="stock_item",
            entity_id=item.id,
            payload={
                "branch_id": str(branch.id),
                "material_id": str(item.material_id),
                "on_hand": item.on_hand,
                "min_stock": item.min_stock,
            },
        )


# --- system primitives (imported by the orders module) ---------------------


async def consume(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    material_id: uuid.UUID,
    qty: int,
    order_id: uuid.UUID,
) -> StockTransaction:
    """System decrement driven by the order state machine. No actor.

    ``on_hand -= qty``, bounded ≥ 0. Raises ``insufficient_stock`` if it would
    go negative.
    """
    if qty <= 0:
        raise bad_request("Consume quantity must be positive.", code="invalid_quantity")
    base = await get_or_create_stock_item(db, branch_id, material_id)
    item = await _lock_stock_item(db, base.id)
    if item.on_hand - qty < 0:
        raise bad_request("Not enough stock to consume.", code="insufficient_stock")
    item.on_hand -= qty
    txn = StockTransaction(
        stock_item_id=item.id,
        type=StockTransactionType.CONSUME,
        quantity=-qty,
        balance_after=item.on_hand,
        order_id=order_id,
    )
    db.add(txn)
    await db.flush()
    branch = await db.get(Branch, branch_id)
    if branch is not None:
        await _maybe_fire_low_stock(db, branch, item)
    return txn


async def restore(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    material_id: uuid.UUID,
    qty: int,
    order_id: uuid.UUID,
) -> StockTransaction:
    """System increment — an operator revert of a consumed step. No actor."""
    if qty <= 0:
        raise bad_request("Restore quantity must be positive.", code="invalid_quantity")
    base = await get_or_create_stock_item(db, branch_id, material_id)
    item = await _lock_stock_item(db, base.id)
    item.on_hand += qty
    txn = StockTransaction(
        stock_item_id=item.id,
        type=StockTransactionType.RESTORE,
        quantity=qty,
        balance_after=item.on_hand,
        order_id=order_id,
    )
    db.add(txn)
    await db.flush()
    return txn


async def projected_balance(
    db: AsyncSession, *, branch_id: uuid.UUID, material_id: uuid.UUID
) -> int:
    """Read-time "will we have enough?" balance for a material at a branch.

    ``projected = on_hand - sum(demand from active orders ahead that have not yet
    decremented this material)``. Sheets are owed by orders in confirmed/cutting;
    edge metres by orders in confirmed/cutting/edge_banding. We do not know the
    kind here, so we count demand across the union of those statuses for items
    of this material whose source is ``shop`` (own-source never touches stock).
    """
    item = (
        await db.execute(
            select(StockItem).where(
                StockItem.branch_id == branch_id, StockItem.material_id == material_id
            )
        )
    ).scalar_one_or_none()
    on_hand = item.on_hand if item is not None else 0
    demand_statuses = (
        OrderStatus.CONFIRMED,
        OrderStatus.CUTTING,
        OrderStatus.EDGE_BANDING,
    )
    demand = (
        await db.execute(
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.branch_id == branch_id,
                Order.status.in_(demand_statuses),
                OrderItem.material_id == material_id,
                OrderItem.material_source == "shop",
            )
        )
    ).scalar_one()
    return int(on_hand) - int(demand or 0)


# --- actor-driven operations (owner or manage_inventory) -------------------


def _require_inventory_access(principal: Principal, branch_id: uuid.UUID) -> None:
    if not principal.has_permission(Permission.MANAGE_INVENTORY, branch_id):
        raise forbidden()


async def stock_in(
    db: AsyncSession,
    principal: Principal,
    branch_id: uuid.UUID,
    *,
    material_id: uuid.UUID,
    qty: int,
    supplier_id: uuid.UUID,
    note: str | None,
) -> StockTransaction:
    if qty <= 0:
        raise bad_request("Stock-in quantity must be positive.", code="invalid_quantity")
    branch = await workshops.owned_branch(db, principal, branch_id)
    _require_inventory_access(principal, branch.id)
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None or supplier.workshop_id != branch.workshop_id:
        raise not_found("Supplier not found.")
    base = await get_or_create_stock_item(db, branch.id, material_id)
    item = await _lock_stock_item(db, base.id)
    item.on_hand += qty
    txn = StockTransaction(
        stock_item_id=item.id,
        type=StockTransactionType.STOCK_IN,
        quantity=qty,
        balance_after=item.on_hand,
        supplier_id=supplier_id,
        actor_user_id=principal.id,
        note=note,
    )
    db.add(txn)
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="stock.stock_in",
        entity_type="stock_item",
        entity_id=item.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
        details={"quantity": qty, "supplier_id": str(supplier_id)},
    )
    await _maybe_fire_low_stock(db, branch, item)
    return txn


async def adjust(
    db: AsyncSession,
    principal: Principal,
    branch_id: uuid.UUID,
    *,
    material_id: uuid.UUID,
    delta: int,
    note: str,
) -> StockTransaction:
    if delta == 0:
        raise bad_request("Adjustment delta must be non-zero.", code="invalid_quantity")
    if not note or not note.strip():
        raise bad_request("An adjustment requires a reason note.", code="note_required")
    branch = await workshops.owned_branch(db, principal, branch_id)
    _require_inventory_access(principal, branch.id)
    base = await get_or_create_stock_item(db, branch.id, material_id)
    item = await _lock_stock_item(db, base.id)
    if item.on_hand + delta < 0:
        raise bad_request("Adjustment would drop stock below 0.", code="below_zero")
    item.on_hand += delta
    txn = StockTransaction(
        stock_item_id=item.id,
        type=StockTransactionType.ADJUST,
        quantity=delta,
        balance_after=item.on_hand,
        actor_user_id=principal.id,
        note=note.strip(),
    )
    db.add(txn)
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="stock.adjust",
        entity_type="stock_item",
        entity_id=item.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
        details={"delta": delta},
    )
    await _maybe_fire_low_stock(db, branch, item)
    return txn


async def set_min_stock(
    db: AsyncSession,
    principal: Principal,
    branch_id: uuid.UUID,
    *,
    material_id: uuid.UUID,
    min_stock: int,
) -> StockItem:
    if min_stock < 0:
        raise bad_request("min_stock must be ≥ 0.", code="invalid_quantity")
    branch = await workshops.owned_branch(db, principal, branch_id)
    _require_inventory_access(principal, branch.id)
    item = await get_or_create_stock_item(db, branch.id, material_id)
    item.min_stock = min_stock
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="stock.min_stock_set",
        entity_type="stock_item",
        entity_id=item.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
    )
    await _maybe_fire_low_stock(db, branch, item)
    await db.refresh(item)
    return item


# --- reads ------------------------------------------------------------------


async def list_stock(
    db: AsyncSession, principal: Principal, branch_id: uuid.UUID
) -> list[StockItem]:
    branch = await workshops.readable_branch(db, principal, branch_id)
    _require_inventory_access(principal, branch.id)
    return list(
        (
            await db.execute(
                select(StockItem)
                .where(StockItem.branch_id == branch.id)
                .order_by(StockItem.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


async def list_transactions(
    db: AsyncSession,
    principal: Principal,
    branch_id: uuid.UUID,
    *,
    stock_item_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[StockTransaction]:
    branch = await workshops.readable_branch(db, principal, branch_id)
    _require_inventory_access(principal, branch.id)
    stock_ids = (
        (await db.execute(select(StockItem.id).where(StockItem.branch_id == branch.id)))
        .scalars()
        .all()
    )
    if not stock_ids:
        return []
    stmt = select(StockTransaction).where(StockTransaction.stock_item_id.in_(stock_ids))
    if stock_item_id is not None:
        if stock_item_id not in set(stock_ids):
            raise not_found("Stock item not found.")
        stmt = stmt.where(StockTransaction.stock_item_id == stock_item_id)
    stmt = stmt.order_by(StockTransaction.created_at.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


# --- suppliers (workshop-scoped) -------------------------------------------


async def create_supplier(
    db: AsyncSession,
    principal: Principal,
    *,
    name: str,
    phone: str | None,
    note: str | None,
) -> Supplier:
    assert principal.workshop_id is not None
    supplier = Supplier(
        workshop_id=principal.workshop_id,
        name=name.strip(),
        phone=phone.strip() if phone else None,
        note=note.strip() if note else None,
        status=SupplierStatus.ACTIVE,
        created_by_user_id=principal.id,
    )
    db.add(supplier)
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="supplier.created",
        entity_type="supplier",
        entity_id=supplier.id,
        workshop_id=principal.workshop_id,
        summary=f"Created supplier {supplier.name}",
    )
    await db.refresh(supplier)
    return supplier


async def _owned_supplier(
    db: AsyncSession, principal: Principal, supplier_id: uuid.UUID
) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None or supplier.workshop_id != principal.workshop_id:
        raise not_found("Supplier not found.")
    return supplier


async def edit_supplier(
    db: AsyncSession,
    principal: Principal,
    supplier_id: uuid.UUID,
    *,
    name: str | None = None,
    phone: str | None = None,
    phone_set: bool = False,
    note: str | None = None,
    note_set: bool = False,
) -> Supplier:
    supplier = await _owned_supplier(db, principal, supplier_id)
    if name is not None:
        supplier.name = name.strip()
    if phone_set:
        supplier.phone = phone.strip() if phone else None
    if note_set:
        supplier.note = note.strip() if note else None
    await audit.record_action(
        db,
        actor=principal,
        action="supplier.updated",
        entity_type="supplier",
        entity_id=supplier.id,
        workshop_id=principal.workshop_id,
    )
    await db.refresh(supplier)
    return supplier


async def set_supplier_status(
    db: AsyncSession, principal: Principal, supplier_id: uuid.UUID, *, active: bool
) -> Supplier:
    supplier = await _owned_supplier(db, principal, supplier_id)
    supplier.status = SupplierStatus.ACTIVE if active else SupplierStatus.INACTIVE
    await audit.record_action(
        db,
        actor=principal,
        action="supplier.activated" if active else "supplier.deactivated",
        entity_type="supplier",
        entity_id=supplier.id,
        workshop_id=principal.workshop_id,
    )
    await db.refresh(supplier)
    return supplier


async def list_suppliers(
    db: AsyncSession, principal: Principal, *, active_only: bool = False
) -> list[Supplier]:
    assert principal.workshop_id is not None
    stmt = select(Supplier).where(Supplier.workshop_id == principal.workshop_id)
    if active_only:
        stmt = stmt.where(Supplier.status == SupplierStatus.ACTIVE)
    stmt = stmt.order_by(Supplier.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())
