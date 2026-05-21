"""ORM models.

Every model module must be imported here so SQLAlchemy's metadata is complete
(Alembic autogenerate + ``metadata.create_all`` in tests both rely on it).
"""

from app.models.base import Base
from app.models.catalog import BranchMaterial, BranchPricing, Material
from app.models.cutting import (
    CuttingDraft,
    CuttingPlacement,
    CuttingResult,
    CuttingSheet,
)
from app.models.finance import Expense, Income
from app.models.identity import (
    Client,
    PermissionGrant,
    PlatformUser,
    Session,
    WorkshopUser,
)
from app.models.inventory import StockItem, StockTransaction, Supplier
from app.models.platform import ErrorEvent, ErrorGroup, JobRun
from app.models.sales import Order, OrderCancellation, OrderItem, OrderStatusEvent
from app.models.support import ActionLog, File, Notification, StatusChangeLog
from app.models.workshop import Branch, Workshop

__all__ = [
    "ActionLog",
    "Base",
    "Branch",
    "BranchMaterial",
    "BranchPricing",
    "Client",
    "CuttingDraft",
    "CuttingPlacement",
    "CuttingResult",
    "CuttingSheet",
    "ErrorEvent",
    "ErrorGroup",
    "Expense",
    "File",
    "Income",
    "JobRun",
    "Material",
    "Notification",
    "Order",
    "OrderCancellation",
    "OrderItem",
    "OrderStatusEvent",
    "PermissionGrant",
    "PlatformUser",
    "Session",
    "StatusChangeLog",
    "StockItem",
    "StockTransaction",
    "Supplier",
    "Workshop",
    "WorkshopUser",
]
