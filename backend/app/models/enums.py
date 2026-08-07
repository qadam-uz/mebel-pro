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
    # Read-only access to the branch's orders. Named for what it actually
    # admits (QAD-166) — it used to be `view_dashboard`, which read as a
    # dashboard toggle while granting order reads.
    VIEW_ORDERS = "view_orders"
    MANAGE_ORDERS = "manage_orders"
    PROCESS_PRODUCTION = "process_production"
    MANAGE_CATALOG = "manage_catalog"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_FINANCE = "manage_finance"
    VIEW_FINANCE_REPORTS = "view_finance_reports"


class MaterialStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class DekorType(StrEnum):
    """What a dekor *is* — the single axis that replaced kind + panel type.

    The old model split this in two: `MaterialKind` (panel vs. edge) decided the
    shape, `PanelMaterialType` (dsp/mdf/...) the substrate. Kromka was never a
    substrate, only a shape, so the two enums were never independent. One value
    carries both facts now: `kromka` is tape-shaped, everything else is
    panel-shaped.
    """

    LDSP = "ldsp"
    DSP = "dsp"
    MDF = "mdf"
    FANERA = "fanera"
    YOGOCH = "yogoch"
    KROMKA = "kromka"
    BOSHQA = "boshqa"

    @property
    def tape_shaped(self) -> bool:
        """True when the format is a tape (length only, no panel dimensions)."""
        return self is DekorType.KROMKA

    @property
    def panel_shaped(self) -> bool:
        """True when the format is a sheet (length x width, no tape width)."""
        return not self.tape_shaped


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
