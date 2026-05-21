"""Declarative base, shared column mixins, and cross-dialect type aliases."""

import uuid
from datetime import date, datetime
from typing import Annotated

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry

# --- Cross-dialect typed-column aliases ------------------------------------
# Postgres in prod, SQLite in tests — these render correctly on both.
uuid_pk = Annotated[uuid.UUID, mapped_column(Uuid, primary_key=True, default=uuid.uuid4)]
uuid_fk = Annotated[uuid.UUID, mapped_column(Uuid)]
tiyin = Annotated[int, mapped_column(BigInteger)]  # integer money, never float
ts = Annotated[datetime, mapped_column(DateTime(timezone=True))]


class Base(DeclarativeBase):
    """Project-wide declarative base. All models inherit from this."""

    registry = registry(
        type_annotation_map={
            datetime: DateTime(timezone=True),
            date: Date,
            str: String,
            uuid.UUID: Uuid,
            # numeric domain values (thickness, lat/lng, waste %) — exact, not float
            float: Numeric,
        }
    )


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
