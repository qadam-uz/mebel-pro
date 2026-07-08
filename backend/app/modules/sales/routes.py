"""Client and workshop order routes."""

import uuid
from csv import writer
from datetime import date
from io import StringIO

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import AccountReadyPrincipal, Session
from app.core.trace import get_trace_id
from app.modules.cutting.api import cutting_result_response, render_cutting_pdf, render_cutting_svg
from app.modules.sales.api import (
    apply_discount,
    approve_order,
    assign_order_workers,
    cancel_client_order,
    cancel_workshop_order,
    complete_banding,
    complete_cutting,
    get_client_order,
    get_client_order_cutting_result,
    get_workshop_order,
    get_workshop_order_cutting_result,
    list_client_orders,
    list_worker_options,
    list_workshop_orders,
    mark_collected,
    place_client_order,
    place_workshop_order,
    quote_client_order,
    quote_client_order_batch,
    quote_workshop_order,
    revert_order,
    update_workshop_note,
)
from app.modules.sales.schemas import (
    BatchOrderQuoteRequest,
    BatchOrderQuoteResponse,
    ClientOrderCreateRequest,
    OrderDetailResponse,
    OrderQuoteResponse,
    OrderSummaryResponse,
    ReasonedVersionedRequest,
    VersionedRequest,
    WorkshopOrderAssignRequest,
    WorkshopOrderCompleteRequest,
    WorkshopOrderCreateRequest,
    WorkshopOrderDiscountRequest,
    WorkshopOrderNoteRequest,
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


@router.get("/client/orders/{order_id}/cutting/svg")
async def client_order_cutting_svg(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    result = await get_client_order_cutting_result(db, principal=principal, order_id=order_id)
    rendered = render_cutting_svg(await cutting_result_response(db, result))
    return Response(rendered, media_type="image/svg+xml")


@router.get("/client/orders/{order_id}/cutting/pdf")
async def client_order_cutting_pdf(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    result = await get_client_order_cutting_result(db, principal=principal, order_id=order_id)
    headers = {"Content-Disposition": f'attachment; filename="cutting-{result.id}.pdf"'}
    return Response(
        render_cutting_pdf(await cutting_result_response(db, result)),
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
        assigned_cutter_user_id=assigned_cutter_user_id,
        assigned_edger_user_id=assigned_edger_user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/workshop/orders/export.csv")
async def workshop_orders_export_csv(
    principal: AccountReadyPrincipal,
    db: Session,
    branch_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    assigned_cutter_user_id: uuid.UUID | None = None,
    assigned_edger_user_id: uuid.UUID | None = None,
    limit: int = Query(default=1000, ge=1, le=1000),
) -> Response:
    rows = await list_workshop_orders(
        db,
        principal=principal,
        branch_id=branch_id,
        status_filter=status,
        search=search,
        date_from=date_from,
        date_to=date_to,
        assigned_cutter_user_id=assigned_cutter_user_id,
        assigned_edger_user_id=assigned_edger_user_id,
        limit=limit,
        offset=0,
        max_limit=1000,
    )
    output = StringIO()
    csv_writer = writer(output)
    csv_writer.writerow(
        [
            "order_number",
            "client_name",
            "client_phone",
            "branch_name",
            "status",
            "total_tiyin",
            "created_at",
        ]
    )
    for row in rows:
        csv_writer.writerow(
            [
                row.order_number,
                row.client_name,
                row.client_phone,
                row.branch_name,
                row.status.value,
                row.total_tiyin,
                row.created_at.isoformat(),
            ]
        )
    headers = {"Content-Disposition": 'attachment; filename="workshop-orders.csv"'}
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/workshop/orders/workers", response_model=list[WorkshopWorkerOption])
async def workshop_order_workers(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[WorkshopWorkerOption]:
    return await list_worker_options(db, principal=principal, branch_id=branch_id)


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


@router.post("/workshop/orders/{order_id}/discount", response_model=OrderDetailResponse)
async def workshop_orders_discount(
    order_id: uuid.UUID,
    payload: WorkshopOrderDiscountRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await apply_discount(db, principal=principal, order_id=order_id, payload=payload)


@router.patch("/workshop/orders/{order_id}/note", response_model=OrderDetailResponse)
async def workshop_orders_note(
    order_id: uuid.UUID,
    payload: WorkshopOrderNoteRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> OrderDetailResponse:
    return await update_workshop_note(db, principal=principal, order_id=order_id, payload=payload)


@router.get("/workshop/orders/{order_id}/cutting/svg")
async def workshop_order_cutting_svg(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    result = await get_workshop_order_cutting_result(db, principal=principal, order_id=order_id)
    rendered = render_cutting_svg(await cutting_result_response(db, result))
    return Response(rendered, media_type="image/svg+xml")


@router.get("/workshop/orders/{order_id}/cutting/pdf")
async def workshop_order_cutting_pdf(
    order_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    result = await get_workshop_order_cutting_result(db, principal=principal, order_id=order_id)
    headers = {"Content-Disposition": f'attachment; filename="cutting-{result.id}.pdf"'}
    return Response(
        render_cutting_pdf(await cutting_result_response(db, result)),
        media_type="application/pdf",
        headers=headers,
    )
