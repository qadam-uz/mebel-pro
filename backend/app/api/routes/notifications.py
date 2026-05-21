"""Notifications inbox routes — the current principal's own inbox.

Any authenticated principal (client / workshop user / platform user) reads their
own inbox: paginated newest-first list, the unread count for the bell badge, and
mark-one / mark-all read (docs/ref/features/notifications.md). Logic lives in
``app.services.notifications``.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.api.deps import CurrentPrincipal, Session
from app.core.errors import not_found
from app.schemas.notifications import NotificationOut, UnreadCount
from app.services import notifications as service

router = APIRouter()


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    principal: CurrentPrincipal,
    db: Session,
    unread_only: bool = False,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationOut]:
    rows = await service.list_for(
        db,
        principal.type,
        principal.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    if since is not None:
        rows = [r for r in rows if r.created_at >= since]
    return [NotificationOut.model_validate(r) for r in rows]


@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(principal: CurrentPrincipal, db: Session) -> UnreadCount:
    count = await service.unread_count(db, principal.type, principal.id)
    return UnreadCount(unread=count)


@router.post("/{notification_id}/mark-read", status_code=204)
async def mark_read(
    notification_id: uuid.UUID, principal: CurrentPrincipal, db: Session
) -> Response:
    ok = await service.mark_read(db, principal.type, principal.id, notification_id)
    if not ok:
        raise not_found("Notification not found.", code="notification_not_found")
    return Response(status_code=204)


@router.post("/mark-all-read", response_model=UnreadCount)
async def mark_all_read(principal: CurrentPrincipal, db: Session) -> UnreadCount:
    await service.mark_all_read(db, principal.type, principal.id)
    return UnreadCount(unread=0)
