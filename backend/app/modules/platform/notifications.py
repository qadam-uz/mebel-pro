"""Platform-owned notification producers."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuthenticatedPrincipalType, UserStatus
from app.modules.access.contracts import PlatformUser
from app.modules.support.contracts import Notification


async def notify_platform_users(
    db: AsyncSession,
    *,
    event_code: str,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    payload: dict[str, Any],
) -> int:
    """Fan one platform event to each active platform operator."""
    recipient_ids = list(
        (
            await db.scalars(
                select(PlatformUser.id).where(PlatformUser.status == UserStatus.ACTIVE)
            )
        ).all()
    )
    now = datetime.now(UTC)
    for recipient_id in recipient_ids:
        db.add(
            Notification(
                recipient_type=AuthenticatedPrincipalType.PLATFORM_USER,
                recipient_id=recipient_id,
                event_code=event_code,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
                created_at=now,
            )
        )
    await db.flush()
    return len(recipient_ids)
