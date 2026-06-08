"""Audit and status-log helpers."""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import ActorContext
from app.modules.support.contracts import ActionLog, StatusChangeLog

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "temp_password",
    "otp",
    "otp_code",
    "code",
    "code_hash",
    "access_token",
    "refresh_token",
    "token",
    "token_hash",
    "authorization",
    "cookie",
    "payment_credentials",
    "secret",
}

SENSITIVE_KEY_FRAGMENTS = {
    "password",
    "passwordhash",
    "temppassword",
    "otp",
    "codehash",
    "accesstoken",
    "refreshtoken",
    "token",
    "tokenhash",
    "authorization",
    "cookie",
    "paymentcredentials",
    "secret",
}

SENSITIVE_TEXT_RE = re.compile(
    r"(?i)\b(password|password_hash|passwordHash|temp_password|otp|otp_code|code_hash|"
    r"access_token|refresh_token|token|token_hash|authorization|cookie|secret)"
    r"(\s*[=:]\s*)([^\s,;]+)"
)


def is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return key.lower() in SENSITIVE_KEYS or any(
        fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS
    )


def scrub_text(value: str) -> str:
    return SENSITIVE_TEXT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}***", value)


def scrub_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, nested in value.items():
            if is_sensitive_key(str(key)):
                out[key] = "***"
            else:
                out[key] = scrub_sensitive(nested)
        return out
    if isinstance(value, list):
        return [scrub_sensitive(item) for item in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value


async def record_action(
    db: AsyncSession,
    *,
    actor: ActorContext,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    summary: str | None = None,
    details: dict[str, Any] | None = None,
) -> ActionLog:
    row = ActionLog(
        actor_type=actor.actor_type,
        actor_user_id=actor.actor_user_id,
        actor_client_id=actor.actor_client_id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        details=scrub_sensitive(details) if details is not None else None,
        trace_id=actor.trace_id,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


async def record_status_change(
    db: AsyncSession,
    *,
    actor: ActorContext,
    entity_type: str,
    entity_id: uuid.UUID,
    to_status: str,
    from_status: str | None = None,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    reason: str | None = None,
    action_log_id: uuid.UUID | None = None,
) -> StatusChangeLog:
    row = StatusChangeLog(
        entity_type=entity_type,
        entity_id=entity_id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        from_status=from_status,
        to_status=to_status,
        actor_type=actor.actor_type,
        actor_user_id=actor.actor_user_id,
        actor_client_id=actor.actor_client_id,
        reason=reason,
        action_log_id=action_log_id,
        changed_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


async def list_action_logs(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = 50,
) -> list[ActionLog]:
    query = select(ActionLog).order_by(ActionLog.created_at.desc())
    if workshop_id is not None:
        query = query.where(ActionLog.workshop_id == workshop_id)
    if branch_id is not None:
        query = query.where(ActionLog.branch_id == branch_id)
    if action is not None:
        query = query.where(ActionLog.action == action)
    return list((await db.scalars(query.limit(_bounded_limit(limit)))).all())


async def list_status_change_logs(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: int = 50,
) -> list[StatusChangeLog]:
    query = select(StatusChangeLog).order_by(StatusChangeLog.changed_at.desc())
    if workshop_id is not None:
        query = query.where(StatusChangeLog.workshop_id == workshop_id)
    if branch_id is not None:
        query = query.where(StatusChangeLog.branch_id == branch_id)
    if entity_type is not None:
        query = query.where(StatusChangeLog.entity_type == entity_type)
    return list((await db.scalars(query.limit(_bounded_limit(limit)))).all())


def _bounded_limit(limit: int) -> int:
    return max(1, min(limit, 200))
