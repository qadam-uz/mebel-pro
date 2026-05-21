"""Audit helpers — append-only action log + status change log.

Every mutating use case writes exactly one ``action_log`` row in the same
transaction as the change; every audited status transition writes one
``status_change_log`` row (docs/ref/entities/support.md).
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.core.trace import current_trace_id
from app.models.enums import ActorType, PrincipalType
from app.models.support import ActionLog, StatusChangeLog


def _actor_fields(
    principal: Principal | None,
) -> tuple[ActorType, uuid.UUID | None, uuid.UUID | None]:
    """Map a principal (or None = system) to (actor_type, user_id, client_id)."""
    if principal is None:
        return ActorType.SYSTEM, None, None
    if principal.type is PrincipalType.CLIENT:
        return ActorType.CLIENT, None, principal.id
    if principal.type is PrincipalType.PLATFORM_USER:
        return ActorType.PLATFORM_USER, principal.id, None
    return ActorType.WORKSHOP_USER, principal.id, None


async def record_action(
    db: AsyncSession,
    *,
    actor: Principal | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    summary: str | None = None,
    details: dict[str, Any] | None = None,
) -> ActionLog:
    actor_type, actor_user_id, actor_client_id = _actor_fields(actor)
    row = ActionLog(
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        actor_client_id=actor_client_id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        details=details,
        trace_id=current_trace_id(),
    )
    db.add(row)
    await db.flush()
    return row


async def record_status_change(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    from_status: str | None,
    to_status: str,
    actor: Principal | None,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    reason: str | None = None,
    action_log_id: uuid.UUID | None = None,
) -> StatusChangeLog:
    actor_type, actor_user_id, actor_client_id = _actor_fields(actor)
    row = StatusChangeLog(
        entity_type=entity_type,
        entity_id=entity_id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        from_status=from_status,
        to_status=to_status,
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        actor_client_id=actor_client_id,
        reason=reason,
        action_log_id=action_log_id,
    )
    db.add(row)
    await db.flush()
    return row
