"""Top-level API router. Mount module route surfaces here."""

from fastapi import APIRouter

from app.api.routes import health
from app.modules.access import routes as access_routes
from app.modules.access import workshop_clients_routes as access_workshop_clients_routes
from app.modules.catalog import routes as catalog_routes
from app.modules.client_portal import routes as client_portal_routes
from app.modules.cutting import routes as cutting_routes
from app.modules.finance import routes as finance_routes
from app.modules.inventory import routes as inventory_routes
from app.modules.platform import routes as platform_routes
from app.modules.sales import routes as sales_routes
from app.modules.support import files_routes, notifications_routes
from app.modules.workshop import routes as workshop_routes
from app.modules.workshop import setup_routes as workshop_setup_routes

api_router = APIRouter()
api_router.include_router(access_routes.router)
api_router.include_router(access_workshop_clients_routes.router)
api_router.include_router(catalog_routes.router)
api_router.include_router(cutting_routes.router)
api_router.include_router(client_portal_routes.router)
api_router.include_router(finance_routes.router)
api_router.include_router(files_routes.router)
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(inventory_routes.router)
api_router.include_router(notifications_routes.router)
api_router.include_router(platform_routes.router)
api_router.include_router(sales_routes.router)
api_router.include_router(workshop_setup_routes.router)
api_router.include_router(workshop_routes.router)
# api_router.include_router(products.router, prefix="/products", tags=["products"])
