"""Unauthenticated client-facing routes.

One endpoint, one job: turn the code on a workshop's QR into the slim identity
its landing page shows. Everything past that point needs a session.
"""

from fastapi import APIRouter, Request

from app.api.deps import Session
from app.core.config import settings
from app.modules.access.api import resolve_client_ip
from app.modules.client_portal.api import resolve_workshop_link, workshop_link_throttle
from app.modules.client_portal.schemas import WorkshopLinkResponse

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/workshop-links/{code}", response_model=WorkshopLinkResponse)
async def workshop_link_resolve(
    code: str,
    request: Request,
    db: Session,
    branch_no: int | None = None,
) -> WorkshopLinkResponse:
    ip = resolve_client_ip(
        peer_host=request.client.host if request.client else None,
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        trusted_proxy_cidrs=settings.TRUSTED_PROXY_CIDRS,
    )
    # Every lookup counts, hit or miss — a budget that only counted misses would
    # be no budget at all for whoever already holds a valid code.
    workshop_link_throttle.check(ip)
    workshop_link_throttle.record(ip)
    return await resolve_workshop_link(db, code=code, branch_no=branch_no)
