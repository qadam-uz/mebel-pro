"""Authenticated file upload/read routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import AccountReadyPrincipal, Session
from app.modules.support.api import (
    FileStorage,
    ImageVariant,
    create_uploaded_file,
    file_storage,
    get_file_for_read,
    serve_stored_file,
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


@router.get("/{file_id}")
async def files_show(
    file_id: uuid.UUID,
    request: Request,
    principal: AccountReadyPrincipal,
    db: Session,
    storage: FileStorageDep,
    size: ImageVariant | None = None,
) -> Response:
    # Authorisation first, always: `serve_stored_file` can answer a 304 without
    # touching the object store, so a permission check below it would turn
    # `If-None-Match` into a way to confirm another tenant's file.
    row = await get_file_for_read(db, principal=principal, file_id=file_id)
    return await serve_stored_file(
        row=row,
        storage=storage,
        if_none_match=request.headers.get("if-none-match"),
        size=size,
        # Lets a file uploaded before renditions existed render itself on its
        # first sized read instead of serving the original to a list forever.
        db=db,
    )
