"""Top-level API router. Mount feature routers here."""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    catalog,
    client,
    files,
    health,
    inventory,
    platform,
    workshop,
    workshop_setup,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(client.router)
api_router.include_router(files.router)
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(inventory.router)
api_router.include_router(platform.router)
api_router.include_router(workshop_setup.router)
api_router.include_router(workshop.router)
# api_router.include_router(products.router, prefix="/products", tags=["products"])
