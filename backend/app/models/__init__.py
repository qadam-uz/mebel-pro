"""SQLAlchemy ORM models.

Import every model module here so Alembic's autogenerate sees the full
metadata. Add new models as: ``from app.models.foo import Foo  # noqa: F401``
"""

from app.models.base import Base

__all__ = ["Base"]
