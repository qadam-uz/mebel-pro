"""File API schemas."""

import uuid
from datetime import datetime

from app.models.enums import AuthenticatedPrincipalType, FileStorageStatus
from app.schemas.common import APIModel


class FileResponse(APIModel):
    id: uuid.UUID
    original_name: str
    content_type: str
    size_bytes: int
    storage_status: FileStorageStatus
    entity_type: str | None
    entity_id: uuid.UUID | None
    uploaded_by_type: AuthenticatedPrincipalType
    uploaded_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
