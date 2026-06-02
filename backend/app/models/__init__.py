"""SQLAlchemy ORM models.

Import every model module here so Alembic's autogenerate sees the full
metadata. Cross-context references remain scalar FK ids; behavior crosses
module boundaries through services, not ORM relationships.
"""

from app.models.base import Base
from app.models.catalog import BranchMaterial, BranchPricing, Manufacturer, Material
from app.models.cutting import CuttingDraft, CuttingPanel, CuttingPlacement, CuttingResult
from app.models.finance import Expense, Income
from app.models.identity import (
    Client,
    PermissionGrant,
    PhoneVerificationChallenge,
    PlatformUser,
    Session,
    WorkshopUser,
)
from app.models.inventory import StockItem, StockTransaction, Supplier
from app.models.platform import ErrorOccurrence, ErrorRecord, JobDefinition, JobRun
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
    "CuttingPanel",
    "CuttingPlacement",
    "CuttingResult",
    "ErrorOccurrence",
    "ErrorRecord",
    "Expense",
    "File",
    "Income",
    "JobDefinition",
    "JobRun",
    "Manufacturer",
    "Material",
    "Notification",
    "Order",
    "OrderCancellation",
    "OrderItem",
    "OrderStatusEvent",
    "PermissionGrant",
    "PhoneVerificationChallenge",
    "PlatformUser",
    "Session",
    "StatusChangeLog",
    "StockItem",
    "StockTransaction",
    "Supplier",
    "Workshop",
    "WorkshopUser",
]
