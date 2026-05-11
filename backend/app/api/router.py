"""Top-level API router. Mount feature routers here."""

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])
# api_router.include_router(products.router, prefix="/products", tags=["products"])
