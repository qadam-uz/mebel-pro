"""SQLAlchemy ORM metadata bootstrap."""

from app.models.base import Base

_MODEL_MODULES = (
    "app.modules.access.models",
    "app.modules.catalog.models",
    "app.modules.cutting.models",
    "app.modules.finance.models",
    "app.modules.inventory.models",
    "app.modules.platform.models",
    "app.modules.sales.models",
    "app.modules.support.models",
    "app.modules.workshop.models",
)


def import_all_models() -> None:
    """Import every module-owned model so Base.metadata is complete."""
    for module_name in _MODEL_MODULES:
        __import__(module_name)


__all__ = [
    "Base",
    "import_all_models",
]
