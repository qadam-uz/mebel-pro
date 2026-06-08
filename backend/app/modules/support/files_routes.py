"""Authenticated file upload/read routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
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


@router.get("/{file_id}")
async def files_show(
    file_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    storage: FileStorageDep,
) -> Response:
    row = await get_file_for_read(db, principal=principal, file_id=file_id)
    content = storage.open(row.storage_key)
    return Response(content=content, media_type=row.content_type)
