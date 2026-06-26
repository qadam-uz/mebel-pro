"""Application error-monitor recording."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ErrorRecordStatus
from app.modules.platform.contracts import ErrorOccurrence, ErrorRecord
from app.modules.platform.notifications import notify_platform_users
from app.modules.support.api import scrub_sensitive, scrub_text

ROLLING_24H = timedelta(hours=24)
ROLLING_7D = timedelta(days=7)
ERROR_SPIKE_THRESHOLD_24H = 10


async def record_application_error(
    db: AsyncSession,
    *,
    code: str,
    module: str,
    message: str,
    trace_id: str,
    stack: str | None = None,
    context: dict[str, Any] | None = None,
    workshop_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> ErrorRecord:
    now = datetime.now(UTC)
    safe_message = scrub_text(message)
    safe_stack = scrub_text(stack) if stack is not None else None
    record = await db.scalar(
        select(ErrorRecord)
        .where(ErrorRecord.code == code, ErrorRecord.module == module)
        .with_for_update()
    )
    if record is None:
        try:
            async with db.begin_nested():
                record = ErrorRecord(
                    code=code,
                    module=module,
                    count_24h=0,
                    count_7d=0,
                    preview_message=safe_message[:240],
                )
                db.add(record)
                await db.flush()
        except IntegrityError:
            record = await db.scalar(
                select(ErrorRecord)
                .where(ErrorRecord.code == code, ErrorRecord.module == module)
                .with_for_update()
            )
            if record is None:
                raise
    previous_24h_count = await _count_occurrences_since(db, record.id, now - ROLLING_24H)
    record.status = ErrorRecordStatus.OPEN
    record.last_occurred_at = now
    record.preview_message = safe_message[:240]
    db.add(
        ErrorOccurrence(
            error_record_id=record.id,
            trace_id=trace_id,
            message=safe_message,
            stack=safe_stack,
            context=scrub_sensitive(context) if context is not None else None,
            workshop_id=workshop_id,
            user_id=user_id,
            occurred_at=now,
        )
    )
    await db.flush()
    await refresh_error_record_counts(db, [record], now=now)
    if previous_24h_count < ERROR_SPIKE_THRESHOLD_24H <= record.count_24h:
        await notify_platform_users(
            db,
            event_code="error.spike",
            entity_type="error_record",
            entity_id=record.id,
            payload={
                "code": record.code,
                "module": record.module,
                "count_24h": record.count_24h,
                "threshold": ERROR_SPIKE_THRESHOLD_24H,
            },
        )
    return record


async def refresh_error_record_counts(
    db: AsyncSession,
    records: list[ErrorRecord],
    *,
    now: datetime | None = None,
) -> list[ErrorRecord]:
    """Refresh persisted rolling error counters from occurrence timestamps."""
    if not records:
        return records
    current = now or datetime.now(UTC)
    for record in records:
        record.count_24h = await _count_occurrences_since(db, record.id, current - ROLLING_24H)
        record.count_7d = await _count_occurrences_since(db, record.id, current - ROLLING_7D)
    await db.flush()
    for record in records:
        await db.refresh(record)
    return records


async def _count_occurrences_since(
    db: AsyncSession,
    record_id: uuid.UUID,
    since: datetime,
) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(ErrorOccurrence)
        .where(
            ErrorOccurrence.error_record_id == record_id,
            ErrorOccurrence.occurred_at >= since,
        )
    )
    return int(count or 0)
