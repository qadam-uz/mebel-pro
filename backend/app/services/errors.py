"""Application error-monitor recording."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import ErrorOccurrence, ErrorRecord
from app.services.audit import scrub_sensitive, scrub_text


async def record_application_error(
    db: AsyncSession,
    *,
    code: str,
    module: str,
    message: str,
    trace_id: str,
    stack: str | None = None,
    context: dict[str, Any] | None = None,
) -> ErrorRecord:
    now = datetime.now(UTC)
    safe_message = scrub_text(message)
    safe_stack = scrub_text(stack) if stack is not None else None
    record = await db.scalar(select(ErrorRecord).where(ErrorRecord.code == code))
    if record is None:
        record = ErrorRecord(
            code=code,
            module=module,
            count_24h=0,
            count_7d=0,
            preview_message=safe_message[:240],
        )
        db.add(record)
        await db.flush()
    record.count_24h += 1
    record.count_7d += 1
    record.last_occurred_at = now
    record.preview_message = safe_message[:240]
    db.add(
        ErrorOccurrence(
            error_record_id=record.id,
            trace_id=trace_id,
            message=safe_message,
            stack=safe_stack,
            context=scrub_sensitive(context) if context is not None else None,
            occurred_at=now,
        )
    )
    await db.flush()
    return record
