"""In-app notifications — v1's only channel. Producers fan out via this module.

A workshop-wide event fans out one row per recipient; each principal polls
their own unread count and list (docs/ref/features/notifications.md).
"""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PrincipalType
from app.models.support import Notification


async def notify(
    db: AsyncSession,
    *,
    recipient_type: PrincipalType,
    recipient_id: uuid.UUID,
    event_code: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> Notification:
    row = Notification(
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        event_code=event_code,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    db.add(row)
    await db.flush()
    return row


async def notify_many(
    db: AsyncSession,
    *,
    recipients: Iterable[tuple[PrincipalType, uuid.UUID]],
    event_code: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> int:
    count = 0
    seen: set[tuple[PrincipalType, uuid.UUID]] = set()
    for rtype, rid in recipients:
        if (rtype, rid) in seen:
            continue
        seen.add((rtype, rid))
        await notify(
            db,
            recipient_type=rtype,
            recipient_id=rid,
            event_code=event_code,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )
        count += 1
    return count


async def unread_count(
    db: AsyncSession, recipient_type: PrincipalType, recipient_id: uuid.UUID
) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_type == recipient_type,
                Notification.recipient_id == recipient_id,
                Notification.read_at.is_(None),
            )
        )
    ).scalar_one()


async def list_for(
    db: AsyncSession,
    recipient_type: PrincipalType,
    recipient_id: uuid.UUID,
    *,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> list[Notification]:
    stmt = select(Notification).where(
        Notification.recipient_type == recipient_type,
        Notification.recipient_id == recipient_id,
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


async def mark_read(
    db: AsyncSession,
    recipient_type: PrincipalType,
    recipient_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> bool:
    notif = await db.get(Notification, notification_id)
    if (
        notif is None
        or notif.recipient_type is not recipient_type
        or notif.recipient_id != recipient_id
    ):
        return False
    if notif.read_at is None:
        notif.read_at = datetime.now(UTC)
    return True


async def mark_all_read(
    db: AsyncSession, recipient_type: PrincipalType, recipient_id: uuid.UUID
) -> int:
    result = await db.execute(
        update(Notification)
        .where(
            Notification.recipient_type == recipient_type,
            Notification.recipient_id == recipient_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    return int(getattr(result, "rowcount", 0) or 0)
