"""File metadata response schema (docs/ref/entities/support.md)."""

import uuid

from app.models.enums import FileStorageStatus, PrincipalType
from app.schemas.common import APIModel


class FileOut(APIModel):
    id: uuid.UUID
    storage_key: str
    original_name: str
    content_type: str
    size_bytes: int
    storage_status: FileStorageStatus
    entity_type: str | None
    entity_id: uuid.UUID | None
    uploaded_by_type: PrincipalType
    uploaded_by_id: uuid.UUID
