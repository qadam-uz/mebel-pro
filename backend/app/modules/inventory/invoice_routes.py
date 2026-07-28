"""Workshop supplier-invoice routes — the arrival document surface."""

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import InvoicePaymentStatus
from app.modules.inventory.api import (
    InvoiceRecord,
    create_invoice,
    display_unit,
    get_invoice,
    list_invoices,
)
from app.modules.inventory.schemas import (
    SupplierInvoiceCreateRequest,
    SupplierInvoiceLineResponse,
    SupplierInvoiceResponse,
)

router = APIRouter(prefix="/workshop/inventory", tags=["inventory"])


@router.get("/invoices", response_model=list[SupplierInvoiceResponse])
async def invoices_index(
    principal: AccountReadyPrincipal,
    db: Session,
    branch_id: uuid.UUID,
    supplier_id: uuid.UUID | None = None,
    search: str | None = None,
    payment_status: InvoicePaymentStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[SupplierInvoiceResponse]:
    rows = await list_invoices(
        db,
        principal=principal,
        branch_id=branch_id,
        supplier_id=supplier_id,
        search=search,
        payment_status=payment_status,
        limit=limit,
        offset=offset,
    )
    return [invoice_response(row) for row in rows]


@router.post(
    "/invoices", response_model=SupplierInvoiceResponse, status_code=status.HTTP_201_CREATED
)
async def invoices_create(
    payload: SupplierInvoiceCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> SupplierInvoiceResponse:
    row = await create_invoice(db, principal=principal, payload=payload)
    return invoice_response(row)


@router.get("/invoices/{invoice_id}", response_model=SupplierInvoiceResponse)
async def invoices_show(
    invoice_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> SupplierInvoiceResponse:
    row = await get_invoice(db, principal=principal, invoice_id=invoice_id)
    return invoice_response(row)


def invoice_response(record: InvoiceRecord) -> SupplierInvoiceResponse:
    invoice = record.invoice
    return SupplierInvoiceResponse(
        id=invoice.id,
        workshop_id=invoice.workshop_id,
        branch_id=invoice.branch_id,
        branch_name=record.branch_name,
        supplier_id=invoice.supplier_id,
        supplier_name=record.supplier.name if record.supplier else None,
        invoice_no=invoice.invoice_no,
        invoice_date=invoice.invoice_date,
        subtotal_tiyin=invoice.subtotal_tiyin,
        discount_tiyin=invoice.discount_tiyin,
        surcharge_tiyin=invoice.surcharge_tiyin,
        total_tiyin=invoice.total_tiyin,
        note=invoice.note,
        line_count=len(record.lines),
        paid_tiyin=record.paid_tiyin,
        outstanding_tiyin=record.outstanding_tiyin,
        payment_status=record.payment_status,
        recorded_by_user_id=invoice.recorded_by_user_id,
        recorded_by_name=record.recorded_by.full_name if record.recorded_by else None,
        created_at=invoice.created_at,
        lines=[
            SupplierInvoiceLineResponse(
                transaction_id=line.transaction.id,
                material_id=line.stock_item.material_id,
                material_name=line.material.name,
                kind=line.material.kind,
                display_unit=display_unit(line.material.kind),
                quantity=line.transaction.quantity,
                unit_price_tiyin=line.transaction.unit_price_tiyin,
                total_price_tiyin=line.transaction.total_price_tiyin,
                note=line.transaction.note,
            )
            for line in record.lines
        ],
    )
