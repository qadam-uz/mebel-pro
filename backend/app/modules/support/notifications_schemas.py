"""Notification inbox API schemas."""

import uuid
from datetime import datetime
from typing import Any

from app.models.enums import AuthenticatedPrincipalType
from app.schemas.common import APIModel


class NotificationResponse(APIModel):
    id: uuid.UUID
    recipient_type: AuthenticatedPrincipalType
    recipient_id: uuid.UUID
    event_code: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None


class NotificationCountResponse(APIModel):
    unread: int
