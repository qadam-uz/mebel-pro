"""Workshop inventory and supplier routes."""

import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import DecorType, SupplierStatus
from app.modules.catalog.api import branch_material_response_from_models
from app.modules.inventory.api import (
    StockRecord,
    TransactionRecord,
    create_supplier,
    display_unit,
    get_last_price,
    is_low_stock,
    list_stock,
    list_suppliers,
    list_transactions,
    record_adjustment,
    record_stock_in,
    set_min_stock,
    set_supplier_status,
    stock_row_for_material,
    stock_unit,
    stock_value,
    update_supplier,
)
from app.modules.inventory.schemas import (
    StockAdjustmentRequest,
    StockInRequest,
    StockItemResponse,
    StockLastPriceResponse,
    StockMinStockRequest,
    StockTransactionResponse,
    StockValueResponse,
    SupplierCreateRequest,
    SupplierPatchRequest,
    SupplierResponse,
)

router = APIRouter(prefix="/workshop/branches/{branch_id}", tags=["inventory"])
# The stock surface's one write that moves no stock. It lives under the module's
# `/workshop/inventory` prefix (the one `invoice_routes` already uses) because
# the threshold is a policy edit on a material, not a movement on a balance.
stock_router = APIRouter(prefix="/workshop/inventory", tags=["inventory"])
SUPPLIER_STATUS_QUERY = Query(default=None, alias="status")
# Opt-in cap for callers that render a preview rather than the table (the global
# search shows five rows). Default stays unbounded so the inventory screen, which
# pages client-side, keeps seeing every row.
STOCK_LIMIT_QUERY = Query(default=None, ge=1, le=200)
# Repeated query param (?types=ldsp&types=dsp) — the catalog's `types` shape.
# A module-level singleton so the default isn't a Query() call (ruff B008).
TYPES_QUERY = Query(default=None)


@router.get("/stock", response_model=list[StockItemResponse])
async def stock_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    low_stock: bool = False,
    # Off by default so every existing caller — the global search preview, the
    # material pickers — keeps seeing the branch's whole catalog. Only the
    # Zaxira table asks for the moved scope.
    moved_only: bool = False,
    types: list[DecorType] | None = TYPES_QUERY,
    limit: int | None = STOCK_LIMIT_QUERY,
) -> list[StockItemResponse]:
    rows = await list_stock(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        low_stock_only=low_stock,
        moved_only=moved_only,
        types=types,
        limit=limit,
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


@router.get("/stock-value", response_model=StockValueResponse)
async def stock_value_get(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> StockValueResponse:
    value = await stock_value(db, principal=principal, branch_id=branch_id)
    return StockValueResponse(value_tiyin=value)


@router.get("/materials/{branch_material_id}/last-price", response_model=StockLastPriceResponse)
async def material_last_price(
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    supplier_id: uuid.UUID | None = None,
) -> StockLastPriceResponse:
    row = await get_last_price(
        db,
        principal=principal,
        branch_id=branch_id,
        branch_material_id=branch_material_id,
        supplier_id=supplier_id,
    )
    if row is None:
        return StockLastPriceResponse(
            unit_price_tiyin=None,
            recorded_at=None,
            supplier_id=None,
            supplier_name=None,
        )
    return StockLastPriceResponse(
        unit_price_tiyin=row.unit_price_tiyin,
        recorded_at=row.recorded_at,
        supplier_id=row.supplier_id,
        supplier_name=row.supplier_name,
    )


@router.get("/stock-transactions", response_model=list[StockTransactionResponse])
async def stock_transactions_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    branch_material_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[StockTransactionResponse]:
    rows = await list_transactions(
        db,
        principal=principal,
        branch_id=branch_id,
        branch_material_id=branch_material_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
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


# The material page reads its own row by material alone: a page URL has to work
# from a link or a reload, and the branch is derivable from the material.
@stock_router.get("/materials/{branch_material_id}/stock", response_model=StockItemResponse)
async def material_stock_get(
    branch_material_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> StockItemResponse:
    row = await stock_row_for_material(
        db,
        principal=principal,
        branch_material_id=branch_material_id,
    )
    return _stock_response(row)


@stock_router.put(
    "/branches/{branch_id}/stock/{branch_material_id}/min-stock",
    response_model=StockItemResponse,
)
async def stock_min_stock_update(
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    payload: StockMinStockRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> StockItemResponse:
    row = await set_min_stock(
        db,
        principal=principal,
        branch_id=branch_id,
        branch_material_id=branch_material_id,
        min_stock=payload.min_stock,
    )
    return _stock_response(row)


def _stock_response(row: StockRecord) -> StockItemResponse:
    item = row.stock_item
    return StockItemResponse(
        id=item.id,
        branch_id=item.branch_id,
        branch_material_id=item.branch_material_id,
        material=branch_material_response_from_models(
            row.branch_material, row.decor_format, row.decor, row.manufacturer
        ),
        type=row.decor_format.type,
        stock_unit=stock_unit(row.decor_format.type),
        display_unit=display_unit(row.decor_format.type),
        on_hand=item.on_hand,
        min_stock=row.branch_material.min_stock,
        is_low_stock=is_low_stock(item.on_hand, row.branch_material.min_stock),
        updated_at=item.updated_at,
    )


def _transaction_response(row: TransactionRecord) -> StockTransactionResponse:
    tx = row.transaction
    return StockTransactionResponse(
        id=tx.id,
        stock_item_id=tx.stock_item_id,
        branch_material_id=row.stock_item.branch_material_id,
        material_name=row.label,
        type=tx.type,
        quantity=tx.quantity,
        balance_after=tx.balance_after,
        unit_price_tiyin=tx.unit_price_tiyin,
        total_price_tiyin=tx.total_price_tiyin,
        order_id=tx.order_id,
        order_number=row.order_number,
        invoice_id=tx.invoice_id,
        invoice_no=row.invoice_no,
        supplier_id=tx.supplier_id,
        supplier_name=row.supplier.name if row.supplier else None,
        actor_user_id=tx.actor_user_id,
        actor_name=row.actor.full_name if row.actor else None,
        note=tx.note,
        created_at=tx.created_at,
    )
