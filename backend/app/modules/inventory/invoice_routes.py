"""Workshop supplier-invoice routes — the arrival document surface."""

import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import InvoicePaymentStatus
from app.modules.inventory.api import (
    InvoiceRecord,
    create_invoice,
    display_unit,
    get_invoice,
    list_invoices,
    update_invoice,
    void_invoice,
)
from app.modules.inventory.schemas import (
    SupplierInvoiceCreateRequest,
    SupplierInvoiceLineResponse,
    SupplierInvoicePatchRequest,
    SupplierInvoicePaymentResponse,
    SupplierInvoiceResponse,
    SupplierInvoiceVoidRequest,
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
    date_from: date | None = None,
    date_to: date | None = None,
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
        date_from=date_from,
        date_to=date_to,
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


@router.patch("/invoices/{invoice_id}", response_model=SupplierInvoiceResponse)
async def invoices_update(
    invoice_id: uuid.UUID,
    payload: SupplierInvoicePatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> SupplierInvoiceResponse:
    row = await update_invoice(db, principal=principal, invoice_id=invoice_id, payload=payload)
    return invoice_response(row)


@router.post("/invoices/{invoice_id}/void", response_model=SupplierInvoiceResponse)
async def invoices_void(
    invoice_id: uuid.UUID,
    payload: SupplierInvoiceVoidRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> SupplierInvoiceResponse:
    row = await void_invoice(db, principal=principal, invoice_id=invoice_id, payload=payload)
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
        status=invoice.status,
        voided_reason=invoice.voided_reason,
        voided_at=invoice.voided_at,
        voided_by_name=record.voided_by.full_name if record.voided_by else None,
        recorded_by_user_id=invoice.recorded_by_user_id,
        recorded_by_name=record.recorded_by.full_name if record.recorded_by else None,
        created_at=invoice.created_at,
        payments=[
            SupplierInvoicePaymentResponse(
                expense_id=payment.expense_id,
                spent_on=payment.spent_on,
                amount_tiyin=payment.amount_tiyin,
                status=payment.status,
            )
            for payment in record.payments
        ],
        lines=[
            SupplierInvoiceLineResponse(
                transaction_id=line.transaction.id,
                branch_material_id=line.stock_item.branch_material_id,
                material_name=line.label,
                type=line.decor_format.type,
                display_unit=display_unit(line.decor_format.type),
                quantity=line.transaction.quantity,
                unit_price_tiyin=line.transaction.unit_price_tiyin,
                total_price_tiyin=line.transaction.total_price_tiyin,
                note=line.transaction.note,
            )
            for line in record.lines
        ],
    )
