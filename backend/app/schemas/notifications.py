"""Notification inbox schemas (docs/ref/features/notifications.md)."""

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import APIModel


class NotificationOut(APIModel):
    id: uuid.UUID
    event_code: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None


class UnreadCount(APIModel):
    unread: int
