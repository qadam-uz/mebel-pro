"""Shared enum values used by the foundation schema."""

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class ActorType(StrEnum):
    PLATFORM_USER = "platform_user"
    WORKSHOP_USER = "workshop_user"
    CLIENT = "client"
    SYSTEM = "system"


class AuthenticatedPrincipalType(StrEnum):
    PLATFORM_USER = "platform_user"
    WORKSHOP_USER = "workshop_user"
    CLIENT = "client"


class UserStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class WorkshopStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class BranchStatus(StrEnum):
    ACTIVE = "active"
    TEMPORARILY_CLOSED = "temporarily_closed"
    INACTIVE = "inactive"


class Permission(StrEnum):
    VIEW_DASHBOARD = "view_dashboard"
    MANAGE_ORDERS = "manage_orders"
    PROCESS_PRODUCTION = "process_production"
    MANAGE_CATALOG = "manage_catalog"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_FINANCE = "manage_finance"
    VIEW_FINANCE_REPORTS = "view_finance_reports"


class MaterialStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MaterialKind(StrEnum):
    PANEL = "panel"
    EDGE = "edge"


class PanelMaterialType(StrEnum):
    DSP = "dsp"
    MDF = "mdf"
    PLYWOOD = "plywood"
    NATURAL_WOOD = "natural_wood"
    OTHER = "other"


class StockTransactionType(StrEnum):
    STOCK_IN = "stock_in"
    CONSUME = "consume"
    RESTORE = "restore"
    ADJUST = "adjust"


class SupplierStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MaterialSource(StrEnum):
    SHOP = "shop"
    OWN = "own"


class CuttingResultStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"


class CuttingResultSource(StrEnum):
    OPTIMIZER = "optimizer"
    IMPORTED_MAP = "imported_map"


class OrderStatus(StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    CUTTING = "cutting"
    EDGE_BANDING = "edge_banding"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Currency(StrEnum):
    UZS = "UZS"


class IncomeType(StrEnum):
    ORDER_PAYMENT = "order_payment"
    OTHER = "other"


class MoneyMethod(StrEnum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class LedgerStatus(StrEnum):
    RECORDED = "recorded"
    VOIDED = "voided"


class InvoicePaymentStatus(StrEnum):
    """How far a supplier invoice is settled — derived at read time, never stored."""

    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class ExpenseCategory(StrEnum):
    RENT = "rent"
    UTILITIES = "utilities"
    RAW_MATERIALS = "raw_materials"
    SUPPLIES = "supplies"
    TRANSPORT = "transport"
    EQUIPMENT = "equipment"
    MARKETING = "marketing"
    TAXES_AND_FEES = "taxes_and_fees"
    SALARY = "salary"
    OTHER = "other"


class FileStorageStatus(StrEnum):
    PENDING = "pending"
    STORED = "stored"
    DELETED = "deleted"


class JobRunStatus(StrEnum):
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


class ErrorRecordStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


def enum_type(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Return a SQLAlchemy enum using stable string values."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
        native_enum=True,
        create_constraint=True,
        validate_strings=True,
    )
