"""Declarative base and shared column mixins."""

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import Connection, DateTime, MetaData, event, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base. All models inherit from this."""

    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


# `pg_trgm` ships the `gin_trgm_ops` opclass that the `ix_decors_search_key_trgm`
# index is declared with, so on Postgres the extension has to exist *before* any
# `create_all` — otherwise the very first table build fails on a missing operator
# class. Registering it on the metadata keeps every `create_all` self-contained
# (tests, throwaway databases) instead of asking each caller to remember. The
# migration installs the extension in its own right: production upgrades run
# Alembic, never `create_all`.
@event.listens_for(Base.metadata, "before_create")
def _install_pg_trgm(target: MetaData, connection: Connection, **kw: Any) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp for Python-side defaults."""
    return datetime.now(UTC)
