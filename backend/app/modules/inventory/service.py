"""Inventory, stock transaction, and supplier use cases."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

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
from app.modules.access.api import BranchScope, resolve_branch_scope
from app.modules.access.contracts import PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.inventory.contracts import StockItem, StockTransaction, Supplier
from app.modules.inventory.schemas import (
    StockAdjustmentRequest,
    StockInRequest,
    SupplierCreateRequest,
    SupplierPatchRequest,
)
from app.modules.support.api import (
    RECEIPT_CONTENT_TYPES,
    attach_file,
    record_action,
    record_status_change,
)
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
        .order_by(Manufacturer.name, Material.name)
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
) -> list[TransactionRecord]:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    query = (
        select(StockTransaction, StockItem, Material, Supplier)
        .join(StockItem, StockItem.id == StockTransaction.stock_item_id)
        .join(Material, Material.id == StockItem.material_id)
        .outerjoin(Supplier, Supplier.id == StockTransaction.supplier_id)
        .where(StockItem.branch_id == scope.branch_id)
        .order_by(StockTransaction.created_at.desc())
    )
    if material_id is not None:
        query = query.where(StockItem.material_id == material_id)
    return [
        TransactionRecord(transaction=tx, stock_item=item, material=material, supplier=supplier)
        for tx, item, material, supplier in (await db.execute(query)).all()
    ]


async def list_suppliers(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    status_filter: SupplierStatus | None = None,
) -> list[Supplier]:
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
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
    scope = await _inventory_scope(db, principal=principal, branch_id=branch_id)
    if payload.quantity <= 0:
        raise APIError("invalid_quantity", "Quantity must be positive", status_code=400)
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
    item, material = await _stock_item_for_movement(
        db,
        scope=scope,
        material_id=payload.material_id,
    )
    transaction = await _apply_stock_delta(
        db,
        principal=principal,
        stock_item=item,
        type_=StockTransactionType.STOCK_IN,
        quantity=payload.quantity,
        supplier_id=supplier.id,
        note=_optional_text(payload.note),
    )
    transaction.receipt_file_id = await attach_file(
        db,
        principal=principal,
        file_id=payload.receipt_file_id,
        entity_type="stock_transaction",
        entity_id=transaction.id,
        allowed_content_types=RECEIPT_CONTENT_TYPES,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="inventory.stock_in",
        entity_type="stock_transaction",
        entity_id=transaction.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Recorded stock-in for {material.name}",
        details={"quantity": payload.quantity, "material_id": str(payload.material_id)},
    )
    await _emit_low_stock_if_needed(db, scope=scope, stock_item=item, material=material)
    return TransactionRecord(
        transaction=transaction,
        stock_item=item,
        material=material,
        supplier=supplier,
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
    await _emit_low_stock_if_needed(db, scope=scope, stock_item=item, material=material)
    return TransactionRecord(
        transaction=transaction,
        stock_item=item,
        material=material,
        supplier=None,
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
    item, material = await _stock_item_for_movement(db, scope=scope, material_id=material_id)
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
    await _emit_low_stock_if_needed(db, scope=scope, stock_item=item, material=material)
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
    item, material = await _stock_item_for_movement(db, scope=scope, material_id=material_id)
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
    await _emit_low_stock_if_needed(db, scope=scope, stock_item=item, material=material)
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
) -> StockTransaction:
    next_balance = stock_item.on_hand + quantity
    if next_balance < 0:
        raise APIError("stock_below_zero", "Stock cannot go below zero", status_code=400)
    stock_item.on_hand = next_balance
    stock_item.updated_at = datetime.now(UTC)
    transaction = StockTransaction(
        stock_item_id=stock_item.id,
        type=type_,
        quantity=quantity,
        balance_after=next_balance,
        order_id=order_id,
        supplier_id=supplier_id,
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
) -> tuple[StockItem, Material]:
    branch_material = await db.scalar(
        select(BranchMaterial).where(
            BranchMaterial.branch_id == scope.branch_id,
            BranchMaterial.material_id == material_id,
        )
    )
    if branch_material is None:
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
            min_stock=branch_material.min_stock,
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


async def _emit_low_stock_if_needed(
    db: AsyncSession,
    *,
    scope: BranchScope,
    stock_item: StockItem,
    material: Material,
) -> None:
    if stock_item.on_hand > stock_item.min_stock:
        return
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
                event_code="inventory.low_stock",
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
