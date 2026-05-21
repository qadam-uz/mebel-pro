"""Top-level API router. Mount feature routers here."""

from fastapi import APIRouter

from app.api.routes import (
    admin_materials,
    admin_workshops,
    auth,
    branches,
    catalog,
    cutting,
    files,
    finance,
    health,
    inventory,
    notifications,
    orders,
    platform_ops,
    platform_users,
    workshop_settings,
    workshop_users,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["meta"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# --- shared (any authenticated principal) ----------------------------------
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])

# --- platform / superadmin app ---------------------------------------------
api_router.include_router(platform_users.router, prefix="/platform/users", tags=["platform-users"])
api_router.include_router(
    admin_workshops.router, prefix="/admin/workshops", tags=["admin-workshops"]
)
api_router.include_router(
    admin_materials.router, prefix="/admin/materials", tags=["admin-materials"]
)
api_router.include_router(
    platform_ops.jobs_router, prefix="/admin/platform/jobs", tags=["platform-ops"]
)
api_router.include_router(
    platform_ops.errors_router, prefix="/admin/platform/errors", tags=["platform-ops"]
)
api_router.include_router(platform_ops.audit_router, prefix="/admin/audit", tags=["platform-ops"])
api_router.include_router(
    platform_ops.dashboard_router, prefix="/admin/dashboard", tags=["platform-ops"]
)

# --- workshop app -----------------------------------------------------------
api_router.include_router(workshop_users.router, prefix="/workshop/users", tags=["workshop-users"])
api_router.include_router(workshop_settings.router, prefix="/workshop/settings", tags=["workshop"])
api_router.include_router(branches.router, prefix="/workshop/branches", tags=["branches"])
api_router.include_router(catalog.picker_router, prefix="/workshop/materials", tags=["catalog"])
api_router.include_router(
    catalog.materials_router,
    prefix="/workshop/branches/{branch_id}/materials",
    tags=["catalog"],
)
api_router.include_router(
    catalog.pricing_router,
    prefix="/workshop/branches/{branch_id}/pricing",
    tags=["catalog"],
)
api_router.include_router(
    inventory.stock_router,
    prefix="/workshop/branches/{branch_id}/stock",
    tags=["inventory"],
)
api_router.include_router(
    inventory.suppliers_router, prefix="/workshop/suppliers", tags=["inventory"]
)
api_router.include_router(
    cutting.workshop_router, prefix="/workshop/cutting-results", tags=["cutting"]
)
api_router.include_router(orders.workshop_router, prefix="/workshop/orders", tags=["orders"])
api_router.include_router(orders.cutter_router, prefix="/workshop/cutting", tags=["orders"])
api_router.include_router(orders.edger_router, prefix="/workshop/banding", tags=["orders"])
api_router.include_router(
    finance.income_router, prefix="/workshop/finance/income", tags=["finance"]
)
api_router.include_router(
    finance.expense_router, prefix="/workshop/finance/expenses", tags=["finance"]
)
api_router.include_router(finance.report_router, prefix="/workshop/finance", tags=["finance"])

# --- client app -------------------------------------------------------------
api_router.include_router(cutting.client_router, prefix="/c/cutting", tags=["cutting"])
api_router.include_router(orders.client_router, prefix="/c/orders", tags=["orders"])
api_router.include_router(catalog.client_picker_router, prefix="/c/materials", tags=["catalog"])
