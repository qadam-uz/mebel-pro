"""Liveness / readiness endpoints."""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import Session
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness — process is up."""
    return HealthResponse(env=settings.ENV)


@router.get("/readyz", response_model=HealthResponse)
async def readyz(db: Session) -> HealthResponse:
    """Readiness — dependencies (DB) reachable."""
    await db.execute(text("SELECT 1"))
    return HealthResponse(env=settings.ENV)
