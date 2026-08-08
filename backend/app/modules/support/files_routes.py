"""Authenticated file upload/read routes."""

import uuid
from typing import Annotated

import anyio.to_thread
from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import AccountReadyPrincipal, Session
from app.modules.support.api import (
    FileStorage,
    create_uploaded_file,
    file_storage,
    get_file_for_read,
)
from app.modules.support.files_schemas import FileResponse

router = APIRouter(prefix="/files", tags=["files"])

FileStorageDep = Annotated[FileStorage, Depends(file_storage)]


@router.post("", response_model=FileResponse)
async def files_create(
    upload: UploadFile,
    principal: AccountReadyPrincipal,
    db: Session,
    storage: FileStorageDep,
) -> FileResponse:
    content = await upload.read()
    row = await create_uploaded_file(
        db,
        principal=principal,
        storage=storage,
        original_name=upload.filename or "upload",
        content_type=upload.content_type or "application/octet-stream",
        content=content,
    )
    return FileResponse.model_validate(row)


# A stored file is immutable: re-uploading produces a new row with a new id and a
# new storage_key, and nothing mutates an existing object. So the body for a given
# id can never change, and a strong validator built from the (unique) storage_key
# is always correct.
#
# `private` — not `public` — because reads are authorised per principal: a shared
# cache must never hand one workshop's file to another. A browser's own cache is
# private by definition, which is the one we want, and `fetch()` uses it by default.
_FILE_CACHE_CONTROL = "private, max-age=31536000, immutable"


def _file_etag(storage_key: str) -> str:
    return f'"{storage_key}"'


@router.get("/{file_id}")
async def files_show(
    file_id: uuid.UUID,
    request: Request,
    principal: AccountReadyPrincipal,
    db: Session,
    storage: FileStorageDep,
) -> Response:
    row = await get_file_for_read(db, principal=principal, file_id=file_id)
    etag = _file_etag(row.storage_key)
    headers = {"Cache-Control": _FILE_CACHE_CONTROL, "ETag": etag}

    # Revalidation hit: the permission check above already ran, so this is safe —
    # and it skips both the object-store round trip and the body transfer.
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)

    # `storage.open` is a blocking boto3 call. Inline it would stall the whole
    # event loop for the duration of the download — a catalog page opens ~50 of
    # these at once, so every other request in the process queues behind them.
    content = await anyio.to_thread.run_sync(storage.open, row.storage_key)
    return Response(content=content, media_type=row.content_type, headers=headers)


def _etag_matches(header: str | None, etag: str) -> bool:
    """RFC 9110 If-None-Match: `*`, or any member of the comma-separated list.

    Weak validators (`W/"x"`) compare equal to their strong form here, which is
    correct for a body that is byte-identical for the life of the id.
    """
    if not header:
        return False
    candidates = (value.strip() for value in header.split(","))
    return any(candidate == "*" or candidate.removeprefix("W/") == etag for candidate in candidates)
