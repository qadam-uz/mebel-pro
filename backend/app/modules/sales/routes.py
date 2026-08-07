"""Client and workshop order routes."""

import uuid
from datetime import date

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import AccountReadyPrincipal, Session
from app.core.trace import get_trace_id
from app.modules.cutting.api import PdfContext, cutting_result_response, render_cutting_pdf
from app.modules.cutting.schemas import CuttingDraftResponse
from app.modules.sales.api import (
    apply_discount,
    apply_order_edit,
    apply_surcharge,
    approve_order,
    assign_order_workers,
    begin_order_edit,
    cancel_client_order,
    cancel_workshop_order,
    complete_banding,
    complete_cutting,
    count_new_workshop_orders,
    get_client_order,
    get_client_order_cutting_result,
    get_production_job,
    get_workshop_order,
    get_workshop_order_cutting_result,
    list_client_orders,
    list_production_queue,
    list_worker_options,
    list_workshop_orders,
    mark_collected,
    place_client_order,
    place_workshop_order,
    quote_client_order,
    quote_client_order_batch,
    quote_workshop_order,
    revert_order,
    set_order_own_material,
    set_order_prices,
    start_banding,
    start_cutting,
    update_workshop_note,
)
from app.modules.sales.schemas import (
    BatchOrderQuoteRequest,
    BatchOrderQuoteResponse,
    ClientOrderCreateRequest,
    NewOrderCountResponse,
    OrderDetailResponse,
    OrderQuoteResponse,
    OrderSummaryResponse,
    ProductionJobDetail,
    ProductionQueueResponse,
    ReasonedVersionedRequest,
    VersionedRequest,
    WorkshopOrderAssignRequest,
    WorkshopOrderCompleteRequest,
    WorkshopOrderCreateRequest,
    WorkshopOrderDiscountRequest,
    WorkshopOrderEditApplyRequest,
    WorkshopOrderNoteRequest,
    WorkshopOrderOwnMaterialRequest,
    WorkshopOrderPricesRequest,
    WorkshopOrderSurchargeRequest,
    WorkshopWorkerOption,
)

router = APIRouter(tags=["orders"])


@router.get("/client/orders", response_model=list[OrderSummaryResponse])
async def client_orders_index(
    principal: AccountReadyPrincipal,
    db: Session,
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[OrderSummaryResponse]:
    return await list_client_orders(
        db,
        principal=principal,
        status_filter=status,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/client/orders",
    response_model=OrderDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def client_orders_create(
    payload: ClientOrderCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await place_client_order(db, principal=principal, payload=payload)


@router.get("/client/orders/quote", response_model=OrderQuoteResponse)
async def client_orders_quote(
    draft_id: uuid.UUID,
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderQuoteResponse:
    return await quote_client_order(
        db,
        principal=principal,
        draft_id=draft_id,
        branch_id=branch_id,
    )


@router.post("/client/orders/quote/batch", response_model=BatchOrderQuoteResponse)
async def client_orders_quote_batch(
    payload: BatchOrderQuoteRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BatchOrderQuoteResponse | JSONResponse:
    result = await quote_client_order_batch(
        db,
        principal=principal,
        draft_id=payload.draft_id,
        branch_ids=payload.branch_ids,
    )
    if not result.quotes and result.errors:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "code": "order_quote_unavailable",
                "message": "No requested branch can accept this order",
                "trace_id": get_trace_id(),
                "quotes": {},
                "errors": result.errors,
            },
        )
    return result


@router.get("/client/orders/{order_id}", response_model=OrderDetailResponse)
async def client_orders_show(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await get_client_order(db, principal=principal, order_id=order_id)


@router.post("/client/orders/{order_id}/cancel", response_model=OrderDetailResponse)
async def client_orders_cancel(
    order_id: uuid.UUID,
    payload: ReasonedVersionedRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await cancel_client_order(db, principal=principal, order_id=order_id, payload=payload)


@router.get("/client/orders/{order_id}/cutting/pdf")
async def client_order_cutting_pdf(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    order = await get_client_order(db, principal=principal, order_id=order_id)
    result = await get_client_order_cutting_result(db, principal=principal, order_id=order_id)
    headers = {"Content-Disposition": f'inline; filename="cutting-{result.id}.pdf"'}
    return Response(
        render_cutting_pdf(
            await cutting_result_response(db, result),
            PdfContext(
                order_number=order.order_number,
                client_name=order.client_name,
                client_phone=order.client_phone,
                branch_name=order.branch_name,
                branch_address=order.branch_address,
                branch_phone=order.branch_phone,
                workshop_name=order.workshop_name,
            ),
        ),
        media_type="application/pdf",
        headers=headers,
    )


@router.get("/workshop/orders", response_model=list[OrderSummaryResponse])
async def workshop_orders_index(
    principal: AccountReadyPrincipal,
    db: Session,
    branch_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    contact_phone: str | None = None,
    assigned_cutter_user_id: uuid.UUID | None = None,
    assigned_edger_user_id: uuid.UUID | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[OrderSummaryResponse]:
    return await list_workshop_orders(
        db,
        principal=principal,
        branch_id=branch_id,
        status_filter=status,
        search=search,
        date_from=date_from,
        date_to=date_to,
        contact_phone=contact_phone,
        assigned_cutter_user_id=assigned_cutter_user_id,
        assigned_edger_user_id=assigned_edger_user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/workshop/orders/workers", response_model=list[WorkshopWorkerOption])
async def workshop_order_workers(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[WorkshopWorkerOption]:
    return await list_worker_options(db, principal=principal, branch_id=branch_id)


# Ambient count behind the sidebar badge (QAD-156). Declared BEFORE `/{order_id}`
# so the literal `new-count` segment isn't captured as an order id.
@router.get("/workshop/orders/new-count", response_model=NewOrderCountResponse)
async def workshop_orders_new_count(
    principal: AccountReadyPrincipal,
    db: Session,
    branch_id: uuid.UUID | None = None,
) -> NewOrderCountResponse:
    return await count_new_workshop_orders(db, principal=principal, branch_id=branch_id)


# Staff create + quote for walk-in orders. Declared BEFORE `/{order_id}` so the
# literal `quote` segment isn't captured as an order id.
@router.get("/workshop/orders/quote", response_model=OrderQuoteResponse)
async def workshop_orders_quote(
    draft_id: uuid.UUID,
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderQuoteResponse:
    return await quote_workshop_order(
        db,
        principal=principal,
        draft_id=draft_id,
        branch_id=branch_id,
    )


@router.post(
    "/workshop/orders",
    response_model=OrderDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workshop_orders_create(
    payload: WorkshopOrderCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await place_workshop_order(db, principal=principal, payload=payload)


@router.get("/workshop/orders/{order_id}", response_model=OrderDetailResponse)
async def workshop_orders_show(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await get_workshop_order(db, principal=principal, order_id=order_id)


@router.post("/workshop/orders/{order_id}/approve", response_model=OrderDetailResponse)
async def workshop_orders_approve(
    order_id: uuid.UUID,
    payload: VersionedRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await approve_order(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/assign", response_model=OrderDetailResponse)
async def workshop_orders_assign(
    order_id: uuid.UUID,
    payload: WorkshopOrderAssignRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await assign_order_workers(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/start-cutting", response_model=OrderDetailResponse)
async def workshop_orders_start_cutting(
    order_id: uuid.UUID,
    payload: VersionedRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await start_cutting(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/start-banding", response_model=OrderDetailResponse)
async def workshop_orders_start_banding(
    order_id: uuid.UUID,
    payload: VersionedRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await start_banding(db, principal=principal, order_id=order_id, payload=payload)


@router.get("/workshop/production/queue", response_model=ProductionQueueResponse)
async def workshop_production_queue(
    principal: AccountReadyPrincipal,
    db: Session,
    station: str,
    branch_id: uuid.UUID | None = None,
) -> ProductionQueueResponse:
    return await list_production_queue(
        db, principal=principal, station=station, branch_id=branch_id
    )


@router.get("/workshop/production/jobs/{order_id}", response_model=ProductionJobDetail)
async def workshop_production_job(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ProductionJobDetail:
    return await get_production_job(db, principal=principal, order_id=order_id)


@router.post("/workshop/orders/{order_id}/cutting-done", response_model=OrderDetailResponse)
async def workshop_orders_cutting_done(
    order_id: uuid.UUID,
    payload: WorkshopOrderCompleteRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await complete_cutting(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/banding-done", response_model=OrderDetailResponse)
async def workshop_orders_banding_done(
    order_id: uuid.UUID,
    payload: WorkshopOrderCompleteRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await complete_banding(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/mark-collected", response_model=OrderDetailResponse)
async def workshop_orders_mark_collected(
    order_id: uuid.UUID,
    payload: VersionedRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await mark_collected(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/revert", response_model=OrderDetailResponse)
async def workshop_orders_revert(
    order_id: uuid.UUID,
    payload: ReasonedVersionedRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await revert_order(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/cancel", response_model=OrderDetailResponse)
async def workshop_orders_cancel(
    order_id: uuid.UUID,
    payload: ReasonedVersionedRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await cancel_workshop_order(db, principal=principal, order_id=order_id, payload=payload)


# Revision — editing a placed order (docs/ref/features/orders.md). Begin is
# idempotent (resumes an open revision); apply rebinds atomically; discard is
# the plain workshop cutting-draft DELETE.
@router.post("/workshop/orders/{order_id}/revision", response_model=CuttingDraftResponse)
async def workshop_orders_revision_begin(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await begin_order_edit(db, principal=principal, order_id=order_id)


@router.post("/workshop/orders/{order_id}/revision/apply", response_model=OrderDetailResponse)
async def workshop_orders_revision_apply(
    order_id: uuid.UUID,
    payload: WorkshopOrderEditApplyRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await apply_order_edit(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/prices", response_model=OrderDetailResponse)
async def workshop_orders_prices(
    order_id: uuid.UUID,
    payload: WorkshopOrderPricesRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await set_order_prices(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/own-material", response_model=OrderDetailResponse)
async def workshop_orders_own_material(
    order_id: uuid.UUID,
    payload: WorkshopOrderOwnMaterialRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await set_order_own_material(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/discount", response_model=OrderDetailResponse)
async def workshop_orders_discount(
    order_id: uuid.UUID,
    payload: WorkshopOrderDiscountRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await apply_discount(db, principal=principal, order_id=order_id, payload=payload)


@router.post("/workshop/orders/{order_id}/surcharge", response_model=OrderDetailResponse)
async def workshop_orders_surcharge(
    order_id: uuid.UUID,
    payload: WorkshopOrderSurchargeRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await apply_surcharge(db, principal=principal, order_id=order_id, payload=payload)


@router.patch("/workshop/orders/{order_id}/note", response_model=OrderDetailResponse)
async def workshop_orders_note(
    order_id: uuid.UUID,
    payload: WorkshopOrderNoteRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await update_workshop_note(db, principal=principal, order_id=order_id, payload=payload)


@router.get("/workshop/orders/{order_id}/cutting/pdf")
async def workshop_order_cutting_pdf(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    order = await get_workshop_order(db, principal=principal, order_id=order_id)
    result = await get_workshop_order_cutting_result(db, principal=principal, order_id=order_id)
    headers = {"Content-Disposition": f'inline; filename="cutting-{result.id}.pdf"'}
    return Response(
        render_cutting_pdf(
            await cutting_result_response(db, result),
            PdfContext(
                order_number=order.order_number,
                client_name=order.client_name,
                client_phone=order.client_phone,
                branch_name=order.branch_name,
                branch_address=order.branch_address,
                branch_phone=order.branch_phone,
                workshop_name=order.workshop_name,
            ),
        ),
        media_type="application/pdf",
        headers=headers,
    )
