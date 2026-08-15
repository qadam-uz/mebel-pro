"""File metadata and object-storage seam."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from functools import lru_cache, partial
from pathlib import Path
from typing import Protocol

import anyio.to_thread
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    FileStorageStatus,
    MaterialStatus,
    Permission,
    WorkshopStatus,
)
from app.modules.access.api import can_access_branch
from app.modules.catalog.contracts import BranchMaterial, Dekor
from app.modules.finance.contracts import Expense, Income
from app.modules.inventory.contracts import StockItem, StockTransaction
from app.modules.support.contracts import File as StoredFile
from app.modules.support.image_variants import (
    ImageDecodeError,
    resize_image,
    variant_storage_key,
)
from app.modules.workshop.contracts import Branch, Workshop

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
logger = get_logger(__name__)
S3_CLIENT_CONFIG = Config(
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
    s3={"addressing_style": "path"},
)


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    content_type: str


class FileStorageUnavailable(Exception):
    """Object storage rejected an operation."""


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
            config=S3_CLIENT_CONFIG,
        )

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise FileStorageUnavailable(_storage_error_code(exc)) from exc
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


@lru_cache(maxsize=1)
def _s3_storage() -> S3FileStorage:
    return S3FileStorage()


def file_storage() -> FileStorage:
    """FastAPI dependency for the object store.

    Memoised: building a boto3 client parses botocore's bundled service models,
    which cost far more than the request that needs it. This ran per request
    before — including per image on a catalog page. botocore clients are safe to
    share across threads, which matters now that reads run in the threadpool.
    """
    return _s3_storage()


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
    try:
        stored = storage.put(storage_key, content, content_type)
    except FileStorageUnavailable as exc:
        logger.warning(
            "file_storage_write_failed",
            storage_key=storage_key,
            storage_error=str(exc),
        )
        raise APIError(
            "file_storage_unavailable",
            "File storage is unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    row = StoredFile(
        storage_key=stored.key,
        original_name=safe_name,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        storage_status=FileStorageStatus.STORED,
        uploaded_by_type=principal.principal_type,
        uploaded_by_id=principal.principal_id,
        variant_keys=await build_image_variants(
            storage, storage_key=stored.key, content_type=stored.content_type, content=content
        ),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def build_image_variants(
    storage: FileStorage,
    *,
    storage_key: str,
    content_type: str,
    content: bytes,
) -> dict[str, str] | None:
    """Store downscaled renditions beside `storage_key`; return their keys.

    Best effort by design. The original is already saved by the time this runs,
    and every read falls back to it, so a failure here costs a larger download —
    never a lost upload. Raising instead would mean one unreadable image could
    block an operator from attaching a photo at all.

    Shared with the backfill command, which is why it takes the key and bytes
    rather than a row.
    """
    if content_type not in IMAGE_CONTENT_TYPES:
        return None
    try:
        # CPU-bound: a 2160x2160 source decodes and resamples in tens of
        # milliseconds, and this process runs one event loop for every tenant.
        rendered = await anyio.to_thread.run_sync(resize_image, content)
    except ImageDecodeError as exc:
        logger.warning("image_variant_decode_failed", storage_key=storage_key, reason=str(exc))
        return None

    keys: dict[str, str] = {}
    for item in rendered:
        key = variant_storage_key(storage_key, item.variant)
        try:
            await anyio.to_thread.run_sync(
                partial(storage.put, key, item.content, item.content_type)
            )
        except FileStorageUnavailable as exc:
            # Keep whatever did land: a half-populated map is valid, and the read
            # path falls back to the original for anything missing.
            logger.warning(
                "image_variant_write_failed",
                storage_key=key,
                storage_error=str(exc),
            )
            continue
        keys[item.variant.value] = key
    return keys or None


def _storage_error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code")
        if isinstance(code, str) and code:
            return code
    return exc.__class__.__name__


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
    # The stored literal stays `"material"` even though the image now hangs off a
    # dekor: the reshape re-pointed `files.entity_id` at the dekor id but left the
    # tag alone on purpose. Rewriting the tag would 403 every historical catalog
    # photo for everyone but platform admins, with nothing to type-check it.
    if (
        row.entity_type == "material"
        and row.entity_id is not None
        and await _can_read_dekor_file(db, principal=principal, dekor_id=row.entity_id)
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
    if (
        row.entity_type in {"income", "expense"}
        and row.entity_id is not None
        and await _can_read_finance_file(
            db,
            principal=principal,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
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


async def _can_read_dekor_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    dekor_id: uuid.UUID,
) -> bool:
    """Catalog-image visibility, now anchored on the dekor.

    One photo serves every format of a decor, so the reachability test is
    "does any branch this principal can see carry *some* format of this
    dekor" — a `branch_materials.dekor_id` join, one hop shorter than the old
    per-material one.
    """
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return True
    dekor = await db.get(Dekor, dekor_id)
    if dekor is None:
        return False
    if principal.principal_type is AuthenticatedPrincipalType.CLIENT:
        if dekor.holat is not MaterialStatus.ACTIVE:
            return False
        return (
            await db.scalar(
                select(BranchMaterial.id)
                .join(Branch, Branch.id == BranchMaterial.branch_id)
                .join(Workshop, Workshop.id == Branch.workshop_id)
                .where(
                    BranchMaterial.dekor_id == dekor_id,
                    BranchMaterial.status == MaterialStatus.ACTIVE,
                    # Otherwise one walk-in board would make every branch a
                    # "carrier" of the shared Mijoz dekor and grant its photo.
                    BranchMaterial.customer_supplied.is_(False),
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
                BranchMaterial.dekor_id == dekor_id,
                Branch.workshop_id == principal.workshop_id,
                BranchMaterial.customer_supplied.is_(False),
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


async def _can_read_finance_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    entity_type: str,
    entity_id: uuid.UUID,
) -> bool:
    if principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER:
        return False
    row = (
        await db.get(Income, entity_id)
        if entity_type == "income"
        else await db.get(Expense, entity_id)
    )
    if row is None or principal.workshop_id != row.workshop_id:
        return False
    if row.branch_id is None:
        return principal.is_owner
    return can_access_branch(
        principal,
        workshop_id=row.workshop_id,
        branch_id=row.branch_id,
        permission=Permission.MANAGE_FINANCE,
    ) or can_access_branch(
        principal,
        workshop_id=row.workshop_id,
        branch_id=row.branch_id,
        permission=Permission.VIEW_FINANCE_REPORTS,
    )
