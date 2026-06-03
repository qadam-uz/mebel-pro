"""File metadata and object-storage seam."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import boto3
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.models.catalog import BranchMaterial, Material
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    FileStorageStatus,
    MaterialStatus,
    Permission,
    WorkshopStatus,
)
from app.models.inventory import StockItem, StockTransaction
from app.models.support import File as StoredFile
from app.models.workshop import Branch, Workshop
from app.services.authz import can_access_branch

ALLOWED_UPLOAD_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    }
)
IMAGE_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
RECEIPT_CONTENT_TYPES = ALLOWED_UPLOAD_CONTENT_TYPES
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    content_type: str


class FileStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> StoredObject: ...

    def open(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class S3FileStorage:
    def __init__(self) -> None:
        self._bucket = settings.MINIO_BUCKET
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT_URL,
            region_name=settings.MINIO_REGION,
            aws_access_key_id=settings.MINIO_ACCESS_KEY_ID,
            aws_secret_access_key=settings.MINIO_SECRET_ACCESS_KEY,
            use_ssl=settings.MINIO_USE_SSL,
        )

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return StoredObject(key=key, size_bytes=len(content), content_type=content_type)

    def open(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body = response["Body"]
        data = body.read()
        return bytes(data)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


class InMemoryFileStorage:
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}
        self.contents: dict[str, bytes] = {}

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        obj = StoredObject(key=key, size_bytes=len(content), content_type=content_type)
        self.objects[key] = obj
        self.contents[key] = content
        return obj

    def open(self, key: str) -> bytes:
        return self.contents[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)
        self.contents.pop(key, None)


def file_storage() -> FileStorage:
    return S3FileStorage()


async def create_uploaded_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    storage: FileStorage,
    original_name: str,
    content_type: str,
    content: bytes,
) -> StoredFile:
    if content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise APIError(
            "unsupported_file_type",
            "Unsupported file type",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise APIError(
            "file_too_large",
            "File is too large",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    safe_name = _safe_filename(original_name)
    storage_key = f"uploads/{uuid.uuid4().hex}/{safe_name}"
    stored = storage.put(storage_key, content, content_type)
    row = StoredFile(
        storage_key=stored.key,
        original_name=safe_name,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        storage_status=FileStorageStatus.STORED,
        uploaded_by_type=principal.principal_type,
        uploaded_by_id=principal.principal_id,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def attach_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    file_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    allowed_content_types: frozenset[str],
) -> uuid.UUID | None:
    if file_id is None:
        return None
    row = await db.get(StoredFile, file_id)
    if row is None or row.storage_status is not FileStorageStatus.STORED:
        raise APIError("file_not_found", "File not found", status_code=status.HTTP_404_NOT_FOUND)
    if row.content_type not in allowed_content_types:
        raise APIError(
            "invalid_file_type",
            "File type is not allowed for this attachment",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if not _is_self_uploaded(row, principal):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    if row.entity_type is not None and (
        row.entity_type != entity_type or row.entity_id != entity_id
    ):
        raise APIError(
            "file_already_attached",
            "File is already attached",
            status_code=status.HTTP_409_CONFLICT,
        )
    row.entity_type = entity_type
    row.entity_id = entity_id
    await db.flush()
    return row.id


async def replace_attached_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    file_id: uuid.UUID | None,
    current_file_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    allowed_content_types: frozenset[str],
) -> uuid.UUID | None:
    if file_id == current_file_id:
        return current_file_id
    attached_id = await attach_file(
        db,
        principal=principal,
        file_id=file_id,
        entity_type=entity_type,
        entity_id=entity_id,
        allowed_content_types=allowed_content_types,
    )
    if current_file_id is not None:
        await _detach_file_if_current(
            db,
            file_id=current_file_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    return attached_id


async def get_file_for_read(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    file_id: uuid.UUID,
) -> StoredFile:
    row = await db.get(StoredFile, file_id)
    if row is None or row.storage_status is not FileStorageStatus.STORED:
        raise APIError("file_not_found", "File not found", status_code=status.HTTP_404_NOT_FOUND)
    if row.entity_type is None and _is_self_uploaded(row, principal):
        return row
    if (
        row.entity_type == "material"
        and row.entity_id is not None
        and await _can_read_material_file(db, principal=principal, material_id=row.entity_id)
    ):
        return row
    if (
        row.entity_type == "workshop"
        and row.entity_id is not None
        and await _can_read_workshop_file(db, principal=principal, workshop_id=row.entity_id)
    ):
        return row
    if (
        row.entity_type == "stock_transaction"
        and row.entity_id is not None
        and await _can_read_stock_transaction_file(
            db,
            principal=principal,
            transaction_id=row.entity_id,
        )
    ):
        return row
    raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


def _safe_filename(original_name: str) -> str:
    name = Path(original_name or "upload").name
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return normalized[:120] or "upload"


def _is_self_uploaded(row: StoredFile, principal: AuthenticatedPrincipal) -> bool:
    return (
        row.uploaded_by_type is principal.principal_type
        and row.uploaded_by_id == principal.principal_id
    )


async def _detach_file_if_current(
    db: AsyncSession,
    *,
    file_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> None:
    row = await db.get(StoredFile, file_id)
    if row is None:
        return
    if row.entity_type == entity_type and row.entity_id == entity_id:
        row.entity_type = None
        row.entity_id = None
        await db.flush()


async def _can_read_material_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    material_id: uuid.UUID,
) -> bool:
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return True
    material = await db.get(Material, material_id)
    if material is None:
        return False
    if principal.principal_type is AuthenticatedPrincipalType.CLIENT:
        if material.status is not MaterialStatus.ACTIVE:
            return False
        return (
            await db.scalar(
                select(BranchMaterial.id)
                .join(Branch, Branch.id == BranchMaterial.branch_id)
                .join(Workshop, Workshop.id == Branch.workshop_id)
                .where(
                    BranchMaterial.material_id == material_id,
                    BranchMaterial.status == MaterialStatus.ACTIVE,
                    Branch.status.in_([BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED]),
                    Workshop.status == WorkshopStatus.ACTIVE,
                )
                .limit(1)
            )
            is not None
        )
    if principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER:
        return False
    if principal.workshop_id is None:
        return False
    rows = (
        await db.execute(
            select(Branch)
            .join(BranchMaterial, BranchMaterial.branch_id == Branch.id)
            .where(
                BranchMaterial.material_id == material_id,
                Branch.workshop_id == principal.workshop_id,
            )
        )
    ).scalars()
    return any(_has_any_branch_access(principal, branch) for branch in rows)


async def _can_read_workshop_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    workshop_id: uuid.UUID,
) -> bool:
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return True
    workshop = await db.get(Workshop, workshop_id)
    if workshop is None:
        return False
    if principal.principal_type is AuthenticatedPrincipalType.WORKSHOP_USER:
        return principal.workshop_id == workshop_id
    if principal.principal_type is AuthenticatedPrincipalType.CLIENT:
        if workshop.status is not WorkshopStatus.ACTIVE:
            return False
        return (
            await db.scalar(
                select(Branch.id)
                .where(
                    Branch.workshop_id == workshop_id,
                    Branch.status.in_([BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED]),
                )
                .limit(1)
            )
            is not None
        )
    return False


def _has_any_branch_access(principal: AuthenticatedPrincipal, branch: Branch) -> bool:
    if principal.workshop_id != branch.workshop_id:
        return False
    if principal.is_owner:
        return True
    if branch.status is BranchStatus.INACTIVE:
        return False
    return any(grant.branch_id == branch.id for grant in principal.grants)


async def _can_read_stock_transaction_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    transaction_id: uuid.UUID,
) -> bool:
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return True
    result = await db.execute(
        select(StockTransaction, StockItem, Branch)
        .join(StockItem, StockItem.id == StockTransaction.stock_item_id)
        .join(Branch, Branch.id == StockItem.branch_id)
        .where(StockTransaction.id == transaction_id)
    )
    row = result.one_or_none()
    if row is None:
        return False
    _, stock_item, branch = row
    return can_access_branch(
        principal,
        workshop_id=branch.workshop_id,
        branch_id=stock_item.branch_id,
        permission=Permission.MANAGE_INVENTORY,
    )
