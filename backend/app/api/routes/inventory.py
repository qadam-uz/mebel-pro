"""Workshop inventory and supplier routes."""

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.api.routes.catalog import _material_from_models
from app.models.enums import SupplierStatus
from app.schemas.inventory import (
    StockAdjustmentRequest,
    StockInRequest,
    StockItemResponse,
    StockTransactionResponse,
    SupplierCreateRequest,
    SupplierPatchRequest,
    SupplierResponse,
)
from app.services.inventory import (
    StockRecord,
    TransactionRecord,
    create_supplier,
    display_unit,
    list_stock,
    list_suppliers,
    list_transactions,
    record_adjustment,
    record_stock_in,
    set_supplier_status,
    stock_unit,
    update_supplier,
)

router = APIRouter(prefix="/workshop/branches/{branch_id}", tags=["inventory"])
SUPPLIER_STATUS_QUERY = Query(default=None, alias="status")


@router.get("/stock", response_model=list[StockItemResponse])
async def stock_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    low_stock: bool = False,
) -> list[StockItemResponse]:
    rows = await list_stock(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        low_stock_only=low_stock,
    )
    return [_stock_response(row) for row in rows]


@router.post(
    "/stock-in",
    response_model=StockTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def stock_in_create(
    branch_id: uuid.UUID,
    payload: StockInRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> StockTransactionResponse:
    row = await record_stock_in(db, principal=principal, branch_id=branch_id, payload=payload)
    return _transaction_response(row)


@router.post(
    "/stock-adjustments",
    response_model=StockTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def stock_adjustments_create(
    branch_id: uuid.UUID,
    payload: StockAdjustmentRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> StockTransactionResponse:
    row = await record_adjustment(db, principal=principal, branch_id=branch_id, payload=payload)
    return _transaction_response(row)


@router.get("/stock-transactions", response_model=list[StockTransactionResponse])
async def stock_transactions_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    material_id: uuid.UUID | None = None,
) -> list[StockTransactionResponse]:
    rows = await list_transactions(
        db,
        principal=principal,
        branch_id=branch_id,
        material_id=material_id,
    )
    return [_transaction_response(row) for row in rows]


@router.get("/suppliers", response_model=list[SupplierResponse])
async def suppliers_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    status_filter: SupplierStatus | None = SUPPLIER_STATUS_QUERY,
) -> list[SupplierResponse]:
    rows = await list_suppliers(
        db,
        principal=principal,
        branch_id=branch_id,
        status_filter=status_filter,
    )
    return [SupplierResponse.model_validate(row) for row in rows]


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def suppliers_create(
    branch_id: uuid.UUID,
    payload: SupplierCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> SupplierResponse:
    row = await create_supplier(db, principal=principal, branch_id=branch_id, payload=payload)
    return SupplierResponse.model_validate(row)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def suppliers_update(
    branch_id: uuid.UUID,
    supplier_id: uuid.UUID,
    payload: SupplierPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> SupplierResponse:
    row = await update_supplier(
        db,
        principal=principal,
        branch_id=branch_id,
        supplier_id=supplier_id,
        payload=payload,
    )
    return SupplierResponse.model_validate(row)


@router.post("/suppliers/{supplier_id}/activate", response_model=SupplierResponse)
async def suppliers_activate(
    branch_id: uuid.UUID,
    supplier_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> SupplierResponse:
    row = await set_supplier_status(
        db,
        principal=principal,
        branch_id=branch_id,
        supplier_id=supplier_id,
        to_status=SupplierStatus.ACTIVE,
    )
    return SupplierResponse.model_validate(row)


@router.post("/suppliers/{supplier_id}/deactivate", response_model=SupplierResponse)
async def suppliers_deactivate(
    branch_id: uuid.UUID,
    supplier_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> SupplierResponse:
    row = await set_supplier_status(
        db,
        principal=principal,
        branch_id=branch_id,
        supplier_id=supplier_id,
        to_status=SupplierStatus.INACTIVE,
    )
    return SupplierResponse.model_validate(row)


def _stock_response(row: StockRecord) -> StockItemResponse:
    item = row.stock_item
    return StockItemResponse(
        id=item.id,
        branch_id=item.branch_id,
        material_id=item.material_id,
        material=_material_from_models(row.material, row.manufacturer),
        kind=row.material.kind,
        stock_unit=stock_unit(row.material.kind),
        display_unit=display_unit(row.material.kind),
        on_hand=item.on_hand,
        min_stock=item.min_stock,
        is_low_stock=item.on_hand <= item.min_stock,
        updated_at=item.updated_at,
    )


def _transaction_response(row: TransactionRecord) -> StockTransactionResponse:
    tx = row.transaction
    return StockTransactionResponse(
        id=tx.id,
        stock_item_id=tx.stock_item_id,
        material_id=row.stock_item.material_id,
        material_name=row.material.name,
        type=tx.type,
        quantity=tx.quantity,
        balance_after=tx.balance_after,
        order_id=tx.order_id,
        supplier_id=tx.supplier_id,
        supplier_name=row.supplier.name if row.supplier else None,
        receipt_file_id=tx.receipt_file_id,
        actor_user_id=tx.actor_user_id,
        note=tx.note,
        created_at=tx.created_at,
    )
