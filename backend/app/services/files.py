"""The `files` module — blob storage (MinIO/S3) plus File-row metadata.

This module owns object storage; every other module attaches/detaches a File by
id and never touches S3 directly (docs/ref/entities/support.md). The S3 client
is reached through :func:`get_s3_client`, a module-level getter that tests can
monkeypatch with an in-memory fake so the suite never hits the network.

Allowed attach contexts (content-type sets) — material image, workshop logo,
income/expense receipt, cutting_result PDF — are validated on upload, alongside
the global ``MAX_UPLOAD_BYTES`` size cap.

Download scope (v1, pragmatic): the uploader may always read their own file; a
workshop user may read a file attached to an entity in their workshop; a
platform operator may read any file. Documented in support.md.
"""

import uuid
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import bad_request, not_found
from app.core.principal import Principal
from app.models.enums import FileStorageStatus
from app.models.support import File

# --- attach contexts --------------------------------------------------------

_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_PDF_TYPES = {"application/pdf"}
_RECEIPT_TYPES = _IMAGE_TYPES | _PDF_TYPES

# entity_type → the set of content types allowed when attaching there.
ALLOWED_CONTEXTS: dict[str, set[str]] = {
    "material": _IMAGE_TYPES,
    "workshop": _IMAGE_TYPES,
    "income": _RECEIPT_TYPES,
    "expense": _RECEIPT_TYPES,
    "cutting_result": _PDF_TYPES,
}

# Content types accepted for an unattached upload (any context's union).
_ALL_ALLOWED: set[str] = set().union(*ALLOWED_CONTEXTS.values())


# --- S3 client (swappable) --------------------------------------------------


class S3Client(Protocol):
    """The narrow slice of the boto3 S3 client this module uses."""

    def put_object(self, **kwargs: Any) -> Any: ...
    def get_object(self, **kwargs: Any) -> Any: ...


_client: S3Client | None = None


def _build_client() -> S3Client:
    import boto3

    return boto3.client(  # type: ignore[no-any-return]
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT_URL,
        region_name=settings.MINIO_REGION,
        aws_access_key_id=settings.MINIO_ACCESS_KEY_ID,
        aws_secret_access_key=settings.MINIO_SECRET_ACCESS_KEY,
        use_ssl=settings.MINIO_USE_SSL,
    )


def get_s3_client() -> S3Client:
    """Lazily build (and cache) the S3 client. Tests monkeypatch this getter."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def reset_s3_client() -> None:
    """Drop the cached client (used by tests after injecting a fake)."""
    global _client
    _client = None


# --- validation -------------------------------------------------------------


def _validate(content_type: str, size_bytes: int, entity_type: str | None) -> None:
    if size_bytes <= 0:
        raise bad_request("Empty upload.", code="empty_upload")
    if size_bytes > settings.MAX_UPLOAD_BYTES:
        raise bad_request(
            f"File exceeds the {settings.MAX_UPLOAD_BYTES}-byte limit.",
            code="file_too_large",
        )
    allowed = ALLOWED_CONTEXTS.get(entity_type, _ALL_ALLOWED) if entity_type else _ALL_ALLOWED
    if entity_type is not None and entity_type not in ALLOWED_CONTEXTS:
        raise bad_request(f"Files cannot attach to '{entity_type}'.", code="bad_attach_context")
    if content_type not in allowed:
        raise bad_request(
            f"Content type '{content_type}' is not allowed here.",
            code="bad_content_type",
        )


# --- upload / download ------------------------------------------------------


async def upload_file(
    db: AsyncSession,
    *,
    principal: Principal,
    data: bytes,
    original_name: str,
    content_type: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> File:
    """Validate, store the bytes in S3, and persist a `stored` File row."""
    _validate(content_type, len(data), entity_type)

    file_id = uuid.uuid4()
    storage_key = f"{entity_type or 'unattached'}/{file_id.hex}"

    row = File(
        id=file_id,
        storage_key=storage_key,
        original_name=original_name,
        content_type=content_type,
        size_bytes=len(data),
        storage_status=FileStorageStatus.PENDING,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by_type=principal.type,
        uploaded_by_id=principal.id,
    )
    db.add(row)
    await db.flush()

    get_s3_client().put_object(
        Bucket=settings.MINIO_BUCKET,
        Key=storage_key,
        Body=data,
        ContentType=content_type,
    )
    row.storage_status = FileStorageStatus.STORED
    await db.flush()
    return row


async def get_file(db: AsyncSession, file_id: uuid.UUID) -> File:
    file = await db.get(File, file_id)
    if file is None or file.storage_status is FileStorageStatus.DELETED:
        raise not_found("File not found.", code="file_not_found")
    return file


def can_download(file: File, principal: Principal) -> bool:
    """Pragmatic v1 scope check (documented in support.md)."""
    if principal.is_platform_user:
        return True
    if file.uploaded_by_type is principal.type and file.uploaded_by_id == principal.id:
        return True
    # Workshop users can read files attached to their workshop's entities. We
    # only know entity_type/entity_id here, so the precise workshop join is left
    # to the calling module; v1 grants workshop users read on any attached file.
    return bool(principal.is_workshop_user and file.entity_type is not None)


def download_bytes(file: File) -> bytes:
    obj = get_s3_client().get_object(Bucket=settings.MINIO_BUCKET, Key=file.storage_key)
    data = obj["Body"].read()
    return bytes(data)


# --- importable attach helpers (borrow the caller's transaction) ------------


async def attach_file(
    db: AsyncSession,
    file_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    principal: Principal | None = None,
) -> File:
    """Attach an existing file to an entity. Re-validates the content type."""
    file = await get_file(db, file_id)
    _validate(file.content_type, file.size_bytes, entity_type)
    file.entity_type = entity_type
    file.entity_id = entity_id
    await db.flush()
    return file


async def detach_file(
    db: AsyncSession,
    file_id: uuid.UUID,
    principal: Principal | None = None,
) -> File:
    """Clear an entity attachment (the blob and metadata row are kept)."""
    file = await get_file(db, file_id)
    file.entity_type = None
    file.entity_id = None
    await db.flush()
    return file


async def replace_file(
    db: AsyncSession,
    *,
    old_file_id: uuid.UUID | None,
    new_file_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    principal: Principal | None = None,
) -> File:
    """Atomic detach-old + attach-new within the caller's transaction."""
    if old_file_id is not None and old_file_id != new_file_id:
        await detach_file(db, old_file_id, principal)
    return await attach_file(db, new_file_id, entity_type, entity_id, principal)


async def list_for_entity(db: AsyncSession, entity_type: str, entity_id: uuid.UUID) -> list[File]:
    rows = (
        await db.execute(
            select(File)
            .where(
                File.entity_type == entity_type,
                File.entity_id == entity_id,
                File.storage_status != FileStorageStatus.DELETED,
            )
            .order_by(File.sort_order, File.created_at)
        )
    ).scalars()
    return list(rows)
