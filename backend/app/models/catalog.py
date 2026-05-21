"""Catalog models — platform materials, branch selections, branch pricing.

Spec: docs/ref/entities/catalog.md.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import CatalogStatus, CuttingModel, MaterialKind, MaterialType


class Material(UUIDPrimaryKey, Timestamped, Base):
    """Platform-wide master record: a cuttable ``sheet`` or edge-banding ``edge``."""

    __tablename__ = "material"

    kind: Mapped[MaterialKind] = mapped_column(Enum(MaterialKind, native_enum=False, length=8))
    type: Mapped[MaterialType | None] = mapped_column(
        Enum(MaterialType, native_enum=False, length=16)
    )
    name: Mapped[str] = mapped_column(String(200))
    thickness_mm: Mapped[float] = mapped_column(Numeric(6, 2))
    color: Mapped[str] = mapped_column(String(80))
    decor_code: Mapped[str | None] = mapped_column(String(80))
    # sheet-only; null for edges
    sheet_length_mm: Mapped[int | None] = mapped_column(Integer)
    sheet_width_mm: Mapped[int | None] = mapped_column(Integer)
    grain_direction: Mapped[bool | None] = mapped_column()
    image_file_id: Mapped[uuid.UUID | None] = mapped_column()
    status: Mapped[CatalogStatus] = mapped_column(
        Enum(CatalogStatus, native_enum=False, length=16), default=CatalogStatus.ACTIVE
    )


class BranchMaterial(UUIDPrimaryKey, Timestamped, Base):
    """A branch's selection of a platform material: its price + visibility."""

    __tablename__ = "branch_material"
    __table_args__ = (UniqueConstraint("branch_id", "material_id", name="uq_branch_material"),)

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), index=True)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material.id"), index=True)
    price_tiyin: Mapped[int] = mapped_column(BigInteger)  # per stock unit (sheet/metre)
    min_stock: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[CatalogStatus] = mapped_column(
        Enum(CatalogStatus, native_enum=False, length=16), default=CatalogStatus.ACTIVE
    )


class BranchPricing(Base):
    """A branch's cutting + edge-banding pricing. One row per branch (PK = branch_id)."""

    __tablename__ = "branch_pricing"

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), primary_key=True)
    cutting_model: Mapped[CuttingModel | None] = mapped_column(
        Enum(CuttingModel, native_enum=False, length=16)
    )
    cutting_rate_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    # map "thickness_mm" -> rate_tiyin per metre, e.g. {"0.4": 300000, "2.0": 500000}
    edge_banding_rates: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column()
