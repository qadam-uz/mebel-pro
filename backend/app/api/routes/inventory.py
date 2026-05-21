"""Inventory routes — stock ops, transactions (per branch), suppliers."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentWorkshopUser, Session
from app.schemas.inventory import (
    StockAdjustIn,
    StockInIn,
    StockItemOut,
    StockMinUpdate,
    StockTransactionOut,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
)
from app.services import inventory as inventory_service

# --- stock (per branch) -----------------------------------------------------

stock_router = APIRouter()


@stock_router.get("", response_model=list[StockItemOut])
async def list_stock(
    branch_id: uuid.UUID, principal: CurrentWorkshopUser, db: Session
) -> list[StockItemOut]:
    rows = await inventory_service.list_stock(db, principal, branch_id)
    return [StockItemOut.model_validate(r) for r in rows]


@stock_router.get("/transactions", response_model=list[StockTransactionOut])
async def list_transactions(
    branch_id: uuid.UUID,
    principal: CurrentWorkshopUser,
    db: Session,
    stock_item_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[StockTransactionOut]:
    rows = await inventory_service.list_transactions(
        db, principal, branch_id, stock_item_id=stock_item_id, limit=limit, offset=offset
    )
    return [StockTransactionOut.model_validate(r) for r in rows]


@stock_router.post("/stock-in", response_model=StockTransactionOut, status_code=201)
async def stock_in(
    branch_id: uuid.UUID, body: StockInIn, principal: CurrentWorkshopUser, db: Session
) -> StockTransactionOut:
    txn = await inventory_service.stock_in(
        db,
        principal,
        branch_id,
        material_id=body.material_id,
        qty=body.quantity,
        supplier_id=body.supplier_id,
        note=body.note,
    )
    return StockTransactionOut.model_validate(txn)


@stock_router.post("/adjust", response_model=StockTransactionOut, status_code=201)
async def adjust(
    branch_id: uuid.UUID, body: StockAdjustIn, principal: CurrentWorkshopUser, db: Session
) -> StockTransactionOut:
    txn = await inventory_service.adjust(
        db,
        principal,
        branch_id,
        material_id=body.material_id,
        delta=body.delta,
        note=body.note,
    )
    return StockTransactionOut.model_validate(txn)


@stock_router.patch("/{material_id}/min-stock", response_model=StockItemOut)
async def set_min_stock(
    branch_id: uuid.UUID,
    material_id: uuid.UUID,
    body: StockMinUpdate,
    principal: CurrentWorkshopUser,
    db: Session,
) -> StockItemOut:
    item = await inventory_service.set_min_stock(
        db, principal, branch_id, material_id=material_id, min_stock=body.min_stock
    )
    return StockItemOut.model_validate(item)


# --- suppliers (workshop-scoped) -------------------------------------------

suppliers_router = APIRouter()


@suppliers_router.get("", response_model=list[SupplierOut])
async def list_suppliers(
    principal: CurrentWorkshopUser, db: Session, active_only: bool = False
) -> list[SupplierOut]:
    rows = await inventory_service.list_suppliers(db, principal, active_only=active_only)
    return [SupplierOut.model_validate(r) for r in rows]


@suppliers_router.post("", response_model=SupplierOut, status_code=201)
async def create_supplier(
    body: SupplierCreate, principal: CurrentWorkshopUser, db: Session
) -> SupplierOut:
    supplier = await inventory_service.create_supplier(
        db, principal, name=body.name, phone=body.phone, note=body.note
    )
    return SupplierOut.model_validate(supplier)


@suppliers_router.patch("/{supplier_id}", response_model=SupplierOut)
async def edit_supplier(
    supplier_id: uuid.UUID, body: SupplierUpdate, principal: CurrentWorkshopUser, db: Session
) -> SupplierOut:
    supplier = await inventory_service.edit_supplier(
        db,
        principal,
        supplier_id,
        name=body.name,
        phone=body.phone,
        phone_set=body.phone_set,
        note=body.note,
        note_set=body.note_set,
    )
    return SupplierOut.model_validate(supplier)


@suppliers_router.post("/{supplier_id}/deactivate", response_model=SupplierOut)
async def deactivate_supplier(
    supplier_id: uuid.UUID, principal: CurrentWorkshopUser, db: Session
) -> SupplierOut:
    supplier = await inventory_service.set_supplier_status(db, principal, supplier_id, active=False)
    return SupplierOut.model_validate(supplier)


@suppliers_router.post("/{supplier_id}/activate", response_model=SupplierOut)
async def activate_supplier(
    supplier_id: uuid.UUID, principal: CurrentWorkshopUser, db: Session
) -> SupplierOut:
    supplier = await inventory_service.set_supplier_status(db, principal, supplier_id, active=True)
    return SupplierOut.model_validate(supplier)
