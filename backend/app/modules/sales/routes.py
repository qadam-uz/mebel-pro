"""Client and workshop order routes."""

import uuid

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AccountReadyPrincipal, Session
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
    quote_client_order,
    revert_order,
    update_workshop_note,
)
from app.modules.sales.schemas import (
    ClientOrderCreateRequest,
    OrderDetailResponse,
    OrderQuoteResponse,
    OrderSummaryResponse,
    ReasonedVersionedRequest,
    VersionedRequest,
    WorkshopOrderAssignRequest,
    WorkshopOrderCompleteRequest,
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
) -> list[OrderSummaryResponse]:
    return await list_workshop_orders(
        db,
        principal=principal,
        branch_id=branch_id,
        status_filter=status,
        search=search,
    )


@router.get("/workshop/orders/workers", response_model=list[WorkshopWorkerOption])
async def workshop_order_workers(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[WorkshopWorkerOption]:
    return await list_worker_options(db, principal=principal, branch_id=branch_id)


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
