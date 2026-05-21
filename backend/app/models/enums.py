"""Domain enumerations shared across modules.

All enums are ``StrEnum`` so they serialise to readable strings in the API and
store as VARCHAR (``native_enum=False``) for cross-dialect portability — the
same definition runs on Postgres (prod) and SQLite (tests) without native enum
types or Alembic enum gymnastics.
"""

from enum import StrEnum


class PrincipalType(StrEnum):
    """The three authenticatable principal kinds — one per front-end app."""

    PLATFORM_USER = "platform_user"
    WORKSHOP_USER = "workshop_user"
    CLIENT = "client"


class ActorType(StrEnum):
    """Who performed an audited action / status transition (``system`` = the app)."""

    PLATFORM_USER = "platform_user"
    WORKSHOP_USER = "workshop_user"
    CLIENT = "client"
    SYSTEM = "system"


class UserStatus(StrEnum):
    """Soft-delete-only lifecycle for platform/workshop users and clients."""

    ACTIVE = "active"
    BLOCKED = "blocked"


class Permission(StrEnum):
    """The v1 coarse-grained, branch-scoped permission catalog.

    ``process_delivery`` is gated out of v1 with delivery and is intentionally
    absent.
    """

    VIEW_DASHBOARD = "view_dashboard"
    MANAGE_ORDERS = "manage_orders"
    PROCESS_PRODUCTION = "process_production"
    MANAGE_CATALOG = "manage_catalog"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_FINANCE = "manage_finance"
    VIEW_FINANCE_REPORTS = "view_finance_reports"


class WorkshopStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class BranchStatus(StrEnum):
    ACTIVE = "active"
    TEMPORARILY_CLOSED = "temporarily_closed"
    INACTIVE = "inactive"


class MaterialKind(StrEnum):
    SHEET = "sheet"
    EDGE = "edge"


class MaterialType(StrEnum):
    """Sheet-only sub-type; null for edges."""

    DSP = "dsp"
    MDF = "mdf"
    PLYWOOD = "plywood"
    NATURAL_WOOD = "natural_wood"
    OTHER = "other"


class CatalogStatus(StrEnum):
    """Shared active/inactive lifecycle for materials and branch selections."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class CuttingModel(StrEnum):
    PER_SHEET = "per_sheet"
    PER_CUT = "per_cut"


class StockTransactionType(StrEnum):
    STOCK_IN = "stock_in"
    CONSUME = "consume"
    RESTORE = "restore"
    ADJUST = "adjust"


class SupplierStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CuttingResultStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"


class MaterialSource(StrEnum):
    SHOP = "shop"
    OWN = "own"


class OrderStatus(StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    CUTTING = "cutting"
    EDGE_BANDING = "edge_banding"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CancelledByType(StrEnum):
    CLIENT = "client"
    WORKSHOP_USER = "workshop_user"


class IncomeType(StrEnum):
    ORDER_PAYMENT = "order_payment"
    OTHER = "other"


class PaymentMethod(StrEnum):
    """Card/terminal ("karta") is recorded as ``bank_transfer`` — no ``card``."""

    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class LedgerStatus(StrEnum):
    RECORDED = "recorded"
    VOIDED = "voided"


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


class Currency(StrEnum):
    UZS = "UZS"


class JobRunResult(StrEnum):
    OK = "ok"
    FAILED = "failed"
    RUNNING = "running"


class ErrorGroupStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
