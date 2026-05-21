"""File upload / download routes — any authenticated principal.

Multipart upload stores the bytes in S3 and returns the File metadata; download
streams the blob after a scope check (docs/ref/entities/support.md). Allowed
attach contexts and the size cap are enforced in ``app.services.files``.
"""

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from fastapi import File as FormFile
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentPrincipal, Session
from app.core.errors import forbidden
from app.schemas.files import FileOut
from app.services import files as service

router = APIRouter()


@router.post("", response_model=FileOut, status_code=201)
async def upload_file(
    principal: CurrentPrincipal,
    db: Session,
    upload: Annotated[UploadFile, FormFile()],
    entity_type: Annotated[str | None, Form()] = None,
    entity_id: Annotated[uuid.UUID | None, Form()] = None,
) -> FileOut:
    data = await upload.read()
    row = await service.upload_file(
        db,
        principal=principal,
        data=data,
        original_name=upload.filename or "upload",
        content_type=upload.content_type or "application/octet-stream",
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return FileOut.model_validate(row)


@router.get("/{file_id}")
async def download_file(
    file_id: uuid.UUID, principal: CurrentPrincipal, db: Session
) -> StreamingResponse:
    file = await service.get_file(db, file_id)
    if not service.can_download(file, principal):
        raise forbidden("You do not have access to this file.")
    data = service.download_bytes(file)

    def _iter() -> Iterator[bytes]:
        yield data

    return StreamingResponse(
        _iter(),
        media_type=file.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{file.original_name}"',
            "Content-Length": str(file.size_bytes),
        },
    )
