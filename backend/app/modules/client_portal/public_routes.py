"""Unauthenticated client-facing routes.

Two endpoints, one job between them: turn the code on a workshop's QR into the
slim identity its landing page shows — the name and branches, and the logo that
goes beside them. Everything past that point needs a session.

Both are scoped by the **code**, which is the only capability either accepts:
neither takes a branch id, a file id, or anything else the caller could aim
somewhere the code does not name.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.api.deps import Session
from app.core.config import settings
from app.modules.access.api import resolve_client_ip
from app.modules.client_portal.api import (
    resolve_workshop_link,
    workshop_link_logo,
    workshop_link_throttle,
)
from app.modules.client_portal.schemas import WorkshopLinkResponse
from app.modules.support.api import FileStorage, file_storage

router = APIRouter(prefix="/public", tags=["public"])

FileStorageDep = Annotated[FileStorage, Depends(file_storage)]


def _charge_lookup(request: Request) -> None:
    """One budget for the whole landing, charged per request.

    Every lookup counts, hit or miss — a budget that only counted misses would
    be no budget at all for whoever already holds a valid code. The logo shares
    the resolve's bucket because a landing makes both calls: two buckets would
    double what a walk of the code space is allowed.
    """
    ip = resolve_client_ip(
        peer_host=request.client.host if request.client else None,
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        trusted_proxy_cidrs=settings.TRUSTED_PROXY_CIDRS,
    )
    workshop_link_throttle.check(ip)
    workshop_link_throttle.record(ip)


@router.get("/workshop-links/{code}", response_model=WorkshopLinkResponse)
async def workshop_link_resolve(
    code: str,
    request: Request,
    db: Session,
    branch_no: int | None = None,
) -> WorkshopLinkResponse:
    _charge_lookup(request)
    return await resolve_workshop_link(db, code=code, branch_no=branch_no)


@router.get("/workshop-links/{code}/logo", response_class=Response)
async def workshop_link_logo_show(
    code: str,
    request: Request,
    db: Session,
    storage: FileStorageDep,
) -> Response:
    """The one file a signed-out scan may read — and only through its code."""
    _charge_lookup(request)
    return await workshop_link_logo(
        db,
        storage=storage,
        code=code,
        if_none_match=request.headers.get("if-none-match"),
    )
