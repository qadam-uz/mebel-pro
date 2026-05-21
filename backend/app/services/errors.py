"""Application error monitor — group occurrences by code, notify on spikes.

The generic 500 handler (and any deliberate caller) records an error here. It
upserts an :class:`ErrorGroup` by ``code`` (bumping the count, refreshing the
last occurrence + preview) and inserts an :class:`ErrorEvent` carrying the
masked context and trace id. When a code's rolling 24 h count crosses a
threshold, platform operators get one notification (docs/ref/features/platform.md).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ErrorGroupStatus, PrincipalType, UserStatus
from app.models.identity import PlatformUser
from app.models.platform import ErrorEvent, ErrorGroup
from app.services import notifications as notif_service

# Sensitive keys masked in any recorded context (defence in depth — callers
# should already mask, but we never want a raw secret to land in the monitor).
_SENSITIVE_KEYS = {
    "password",
    "new_password",
    "current_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "password_hash",
    "api_key",
}

_SPIKE_THRESHOLD_24H = 50


def mask_context(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if context is None:
        return None
    masked: dict[str, Any] = {}
    for key, value in context.items():
        if key.lower() in _SENSITIVE_KEYS:
            masked[key] = "***"
        elif isinstance(value, dict):
            masked[key] = mask_context(value)
        else:
            masked[key] = value
    return masked


async def _count_since(db: AsyncSession, group_id: uuid.UUID, since: datetime) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(ErrorEvent)
            .where(ErrorEvent.error_group_id == group_id, ErrorEvent.occurred_at >= since)
        )
    ).scalar_one()


async def record_error(
    db: AsyncSession,
    *,
    code: str,
    module: str | None = None,
    message: str | None = None,
    stack: str | None = None,
    context: dict[str, Any] | None = None,
    trace_id: str | None = None,
    workshop_id: uuid.UUID | None = None,
) -> ErrorGroup:
    """Upsert the group by code, insert an event, and notify on a 24 h spike."""
    now = datetime.now(UTC)
    group = (
        await db.execute(select(ErrorGroup).where(ErrorGroup.code == code))
    ).scalar_one_or_none()
    if group is None:
        group = ErrorGroup(
            code=code,
            module=module,
            message_preview=(message or "")[:400] or None,
            count_total=0,
            status=ErrorGroupStatus.OPEN,
        )
        db.add(group)
        await db.flush()
    else:
        if module is not None:
            group.module = module
        if message:
            group.message_preview = message[:400]
        # A new occurrence reopens a resolved group.
        if group.status is ErrorGroupStatus.RESOLVED:
            group.status = ErrorGroupStatus.OPEN
            group.resolved_at = None

    group.count_total += 1
    group.last_occurred_at = now

    event = ErrorEvent(
        error_group_id=group.id,
        message=message,
        stack=stack,
        context=mask_context(context),
        trace_id=trace_id,
        workshop_id=workshop_id,
        occurred_at=now,
    )
    db.add(event)
    await db.flush()

    count_24h = await _count_since(db, group.id, now - timedelta(hours=24))
    if count_24h == _SPIKE_THRESHOLD_24H:
        await _notify_spike(db, group, count_24h)

    return group


async def _notify_spike(db: AsyncSession, group: ErrorGroup, count_24h: int) -> None:
    operator_ids = (
        (await db.execute(select(PlatformUser.id).where(PlatformUser.status == UserStatus.ACTIVE)))
        .scalars()
        .all()
    )
    await notif_service.notify_many(
        db,
        recipients=[(PrincipalType.PLATFORM_USER, uid) for uid in operator_ids],
        event_code="platform.error_spike",
        entity_type="error_group",
        entity_id=group.id,
        payload={"code": group.code, "count_24h": count_24h},
    )


# --- queries for the monitor routes -----------------------------------------


async def list_groups(
    db: AsyncSession,
    *,
    module: str | None = None,
    code: str | None = None,
    status: ErrorGroupStatus | None = None,
    since: datetime | None = None,
    min_count_24h: int | None = None,
) -> list[dict[str, Any]]:
    stmt = select(ErrorGroup)
    if module is not None:
        stmt = stmt.where(ErrorGroup.module == module)
    if code is not None:
        stmt = stmt.where(ErrorGroup.code == code)
    if status is not None:
        stmt = stmt.where(ErrorGroup.status == status)
    if since is not None:
        stmt = stmt.where(ErrorGroup.last_occurred_at >= since)
    stmt = stmt.order_by(ErrorGroup.last_occurred_at.desc().nullslast())
    groups = list((await db.execute(stmt)).scalars().all())

    now = datetime.now(UTC)
    out: list[dict[str, Any]] = []
    for group in groups:
        count_24h = await _count_since(db, group.id, now - timedelta(hours=24))
        count_7d = await _count_since(db, group.id, now - timedelta(days=7))
        if min_count_24h is not None and count_24h < min_count_24h:
            continue
        out.append(
            {
                "id": group.id,
                "code": group.code,
                "module": group.module,
                "message_preview": group.message_preview,
                "status": group.status,
                "count_total": group.count_total,
                "count_24h": count_24h,
                "count_7d": count_7d,
                "last_occurred_at": group.last_occurred_at,
            }
        )
    return out


async def get_group_detail(db: AsyncSession, group_id: uuid.UUID) -> dict[str, Any] | None:
    group = await db.get(ErrorGroup, group_id)
    if group is None:
        return None
    events = list(
        (
            await db.execute(
                select(ErrorEvent)
                .where(ErrorEvent.error_group_id == group_id)
                .order_by(ErrorEvent.occurred_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    workshops = sorted({str(e.workshop_id) for e in events if e.workshop_id is not None})
    trace_ids = [e.trace_id for e in events if e.trace_id is not None][:50]
    now = datetime.now(UTC)
    return {
        "id": group.id,
        "code": group.code,
        "module": group.module,
        "message_preview": group.message_preview,
        "status": group.status,
        "count_total": group.count_total,
        "count_24h": await _count_since(db, group.id, now - timedelta(hours=24)),
        "count_7d": await _count_since(db, group.id, now - timedelta(days=7)),
        "last_occurred_at": group.last_occurred_at,
        "resolved_at": group.resolved_at,
        "affected_workshops": workshops,
        "trace_ids": trace_ids,
        "events": events,
    }


async def resolve_group(db: AsyncSession, group_id: uuid.UUID) -> ErrorGroup | None:
    group = await db.get(ErrorGroup, group_id)
    if group is None:
        return None
    group.status = ErrorGroupStatus.RESOLVED
    group.resolved_at = datetime.now(UTC)
    await db.flush()
    return group
