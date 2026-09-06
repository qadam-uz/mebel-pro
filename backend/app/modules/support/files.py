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
from fastapi.responses import Response
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
from app.modules.catalog.contracts import BranchMaterial, Decor, DecorFormat
from app.modules.finance.contracts import Expense, Income
from app.modules.inventory.contracts import StockItem, StockTransaction
from app.modules.support.contracts import File as StoredFile
from app.modules.support.image_variants import (
    RENDERABLE_CONTENT_TYPES,
    ImageDecodeError,
    ImageVariant,
    VariantChoice,
    resize_image,
    resolve_variant,
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
# One definition, in the module that decides what can be downscaled: the set an
# attachment accepts as "an image" and the set that gets renditions must not drift.
IMAGE_CONTENT_TYPES = RENDERABLE_CONTENT_TYPES
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

    The return value is what belongs in `files.variant_keys`, and its three
    shapes are the three states the read path distinguishes:

    * a map — these renditions exist;
    * `{}` — settled, and there is nothing to serve but the original: a source
      already smaller than every budget, or bytes Pillow cannot read. Recorded
      so neither the backfill nor a read ever tries again;
    * `None` — *not settled*. Either the file is not an image, or the object
      store refused a write. Both leave the column NULL; the second is a
      transient the next backfill run (or the next sized read) retries.

    Best effort by design. The original is already saved by the time this runs,
    so a failure here costs a larger download — never a lost upload. Raising
    instead would mean one unreadable image could block an operator from
    attaching a photo at all.

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
        # Permanent: these bytes will not become readable on a retry, and the
        # original is what every read of them serves from here on.
        logger.warning("image_variant_decode_failed", storage_key=storage_key, reason=str(exc))
        return {}

    keys: dict[str, str] = {}
    for item in rendered:
        key = variant_storage_key(storage_key, item.variant)
        try:
            await anyio.to_thread.run_sync(
                partial(storage.put, key, item.content, item.content_type)
            )
        except FileStorageUnavailable as exc:
            # A half-written set is not a state worth recording: leave the column
            # NULL so the whole file is rendered again later. The keys are derived
            # from the original's, so a re-run overwrites rather than orphans.
            logger.warning(
                "image_variant_write_failed",
                storage_key=key,
                storage_error=str(exc),
            )
            return None
        keys[item.variant.value] = key
    return keys


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
    # decor: the reshape re-pointed `files.entity_id` at the decor id but left the
    # tag alone on purpose. Rewriting the tag would 403 every historical catalog
    # photo for everyone but platform admins, with nothing to type-check it.
    if (
        row.entity_type == "material"
        and row.entity_id is not None
        and await _can_read_decor_file(db, principal=principal, decor_id=row.entity_id)
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


async def get_stored_file(db: AsyncSession, *, file_id: uuid.UUID) -> StoredFile | None:
    """The row behind a file id, or `None` when there is nothing to serve.

    Deliberately unauthorised: it answers *does this file exist*, never *may you
    read it*. Only a caller that already holds its own capability — the workshop
    code on the public logo route, say — may reach a file through it; everything
    addressed by a bare file id goes through `get_file_for_read`.
    """
    row = await db.get(StoredFile, file_id)
    if row is None or row.storage_status is not FileStorageStatus.STORED:
        return None
    return row


# A stored file is immutable: re-uploading produces a new row with a new id and a
# new storage_key, and nothing mutates an existing object. So the body for a given
# id can never change, and a strong validator built from the (unique) storage_key
# is always correct.
#
# `private` — not `public` — because reads are authorised per principal: a shared
# cache must never hand one workshop's file to another. A browser's own cache is
# private by definition, which is the one we want, and `fetch()` uses it by default.
FILE_CACHE_CONTROL = "private, max-age=31536000, immutable"


def file_etag(storage_key: str) -> str:
    return f'"{storage_key}"'


def etag_matches(header: str | None, etag: str) -> bool:
    """RFC 9110 If-None-Match: `*`, or any member of the comma-separated list.

    Weak validators (`W/"x"`) compare equal to their strong form here, which is
    correct for a body that is byte-identical for the life of the id.
    """
    if not header:
        return False
    candidates = (value.strip() for value in header.split(","))
    return any(candidate == "*" or candidate.removeprefix("W/") == etag for candidate in candidates)


async def _render_missing_variants(
    db: AsyncSession,
    *,
    row: StoredFile,
    storage: FileStorage,
) -> None:
    """Render an image nobody has rendered yet — once, and record the result.

    The state this exists for is real and was the whole of the reported
    slowness: every file uploaded before renditions shipped carries
    `variant_keys IS NULL`, so `?size=sm` quietly served the full original.
    The backfill command fixes a database on demand; this makes the *first*
    request for such a file fix it too, so a restored dump, a re-seeded stack or
    an upload whose rendition write failed cannot leave a catalog page pulling
    originals for the rest of its life.

    Costs one decode and two resizes, once per file ever. Failures are logged
    and swallowed: the response still has the original to fall back on, and a
    read is not the place to fail on account of a thumbnail.
    """
    try:
        content = await anyio.to_thread.run_sync(storage.open, row.storage_key)
    # Broad on purpose: boto raises a wide family here, and none of it is a
    # reason to fail a read that has the original to serve.
    except Exception as exc:
        logger.warning(
            "image_variant_lazy_read_failed",
            storage_key=row.storage_key,
            storage_error=_storage_error_code(exc),
        )
        return
    keys = await build_image_variants(
        storage,
        storage_key=row.storage_key,
        content_type=row.content_type,
        content=content,
    )
    if keys is None:
        # Not settled (the store refused a write). Leave the column NULL so this
        # is retried, rather than pinning the file to the original forever.
        return
    row.variant_keys = keys
    await db.flush()
    logger.info("image_variants_rendered_on_read", storage_key=row.storage_key, variants=len(keys))


async def serve_stored_file(
    *,
    row: StoredFile,
    storage: FileStorage,
    if_none_match: str | None,
    size: ImageVariant | None = None,
    db: AsyncSession | None = None,
) -> Response:
    """Turn a stored file into an HTTP response — bytes, type, validators.

    The mechanics live here rather than in a route so every surface that serves a
    file serves it identically: same rendition fallback, same cache policy, same
    revalidation. Authorisation is the *caller's* job and has to have happened
    before this is reached.

    `db` is what lets an unrendered image heal itself (see `_ensure_renditions`).
    Without it the renditions cannot be *recorded*, and re-rendering per request
    would be worse than the download it saves — so a caller with no session gets
    the old fallback and the backfill command remains the fix.
    """

    # Resolved before the validator is built, because the key IS the validator.
    # `sm` and the original are different bytes under one file id, so an ETag that
    # ignored `size` would let a cache answer one with the other.
    def choose() -> VariantChoice:
        return resolve_variant(
            requested=size,
            variant_keys=row.variant_keys,
            original_key=row.storage_key,
            original_content_type=row.content_type,
        )

    choice = choose()
    if choice.needs_render and db is not None:
        await _render_missing_variants(db, row=row, storage=storage)
        choice = choose()
    key, media_type = choice.key, choice.content_type
    etag = file_etag(key)
    headers = {
        "Cache-Control": FILE_CACHE_CONTROL,
        "ETag": etag,
        # Same URL, different body per `size`. Without this a shared cache keyed
        # on the URL alone could serve the wrong rendition; `private` already
        # rules those out, and this states the contract regardless.
        "Vary": "Accept-Encoding",
    }

    # Revalidation hit: the caller's permission check already ran, so this is
    # safe — and it skips both the object-store round trip and the body transfer.
    if etag_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)

    # `storage.open` is a blocking boto3 call. Inline it would stall the whole
    # event loop for the duration of the download — a catalog page opens ~50 of
    # these at once, so every other request in the process queues behind them.
    content = await anyio.to_thread.run_sync(storage.open, key)
    return Response(content=content, media_type=media_type, headers=headers)


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


async def _can_read_decor_file(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    decor_id: uuid.UUID,
) -> bool:
    """Catalog-image visibility, anchored on the decor.

    One photo serves every format of a decor, so the reachability test is
    "does any branch this principal can see carry *some* format of this
    decor" — a branch_material -> decor_format -> decor join.
    """
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return True
    decor = await db.get(Decor, decor_id)
    if decor is None:
        return False
    if principal.principal_type is AuthenticatedPrincipalType.CLIENT:
        if decor.status is not MaterialStatus.ACTIVE:
            return False
        return (
            await db.scalar(
                select(BranchMaterial.id)
                .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
                .join(Branch, Branch.id == BranchMaterial.branch_id)
                .join(Workshop, Workshop.id == Branch.workshop_id)
                .where(
                    DecorFormat.decor_id == decor_id,
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
            .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
            .where(
                DecorFormat.decor_id == decor_id,
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
