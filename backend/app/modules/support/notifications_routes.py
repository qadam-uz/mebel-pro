"""Principal notification inbox routes."""

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.modules.support.api import (
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    unread_count,
)
from app.modules.support.notifications_schemas import (
    NotificationCountResponse,
    NotificationResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def notifications_index(
    principal: AccountReadyPrincipal,
    db: Session,
    unread_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[NotificationResponse]:
    rows = await list_notifications(
        db,
        principal=principal,
        unread_only=unread_only,
        limit=limit,
    )
    return [NotificationResponse.model_validate(row) for row in rows]


@router.get("/unread-count", response_model=NotificationCountResponse)
async def notifications_unread_count(
    principal: AccountReadyPrincipal,
    db: Session,
) -> NotificationCountResponse:
    return NotificationCountResponse(unread=await unread_count(db, principal=principal))


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def notifications_mark_read(
    notification_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> NotificationResponse:
    row = await mark_notification_read(
        db,
        principal=principal,
        notification_id=notification_id,
    )
    return NotificationResponse.model_validate(row)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def notifications_mark_all_read(
    principal: AccountReadyPrincipal,
    db: Session,
) -> None:
    await mark_all_notifications_read(db, principal=principal)
