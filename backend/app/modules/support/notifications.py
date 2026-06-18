"""Principal-scoped notification inbox use cases."""

import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import AuthenticatedPrincipal
from app.modules.support.contracts import Notification


async def list_notifications(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> list[Notification]:
    conditions = (
        Notification.recipient_type == principal.principal_type,
        Notification.recipient_id == principal.principal_id,
    )
    query = select(Notification).where(*conditions).order_by(Notification.created_at.desc())
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    # Paginate (CB-41): the client appends pages via offset; the unread_only filter
    # is applied server-side so a future "unread" toggle spans all pages.
    query = query.limit(max(1, min(limit, 100))).offset(max(0, offset))
    return list((await db.scalars(query)).all())


async def unread_count(db: AsyncSession, *, principal: AuthenticatedPrincipal) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_type == principal.principal_type,
                Notification.recipient_id == principal.principal_id,
                Notification.read_at.is_(None),
            )
        )
        or 0
    )


async def mark_notification_read(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    notification_id: uuid.UUID,
) -> Notification:
    row = await db.get(Notification, notification_id)
    if (
        row is None
        or row.recipient_type != principal.principal_type
        or row.recipient_id != principal.principal_id
    ):
        from app.core.errors import APIError

        raise APIError(
            "notification_not_found",
            "Notification not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    row.read_at = row.read_at or datetime.now(UTC)
    await db.flush()
    return row


async def mark_all_notifications_read(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> int:
    rows = list(
        (
            await db.scalars(
                select(Notification).where(
                    Notification.recipient_type == principal.principal_type,
                    Notification.recipient_id == principal.principal_id,
                    Notification.read_at.is_(None),
                )
            )
        ).all()
    )
    now = datetime.now(UTC)
    for row in rows:
        row.read_at = now
    await db.flush()
    return len(rows)
