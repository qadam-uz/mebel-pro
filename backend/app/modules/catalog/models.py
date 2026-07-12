"""Platform material catalog and branch pricing models."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import MaterialKind, MaterialStatus, PanelMaterialType, enum_type


class Manufacturer(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "manufacturers"
    __table_args__ = (Index("uq_manufacturers_name_ci", func.lower(text("name")), unique=True),)

    name: Mapped[str] = mapped_column(nullable=False)
    country: Mapped[str | None]
    note: Mapped[str | None]
    status: Mapped[MaterialStatus] = mapped_column(
        enum_type(MaterialStatus, "material_status"),
        default=MaterialStatus.ACTIVE,
        nullable=False,
    )


class Material(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "materials"
    __table_args__ = (
        CheckConstraint("thickness_mm > 0", name="ck_materials_thickness_positive"),
        CheckConstraint(
            "edge_width_mm IS NULL OR edge_width_mm > 0",
            name="ck_materials_edge_width_positive",
        ),
        CheckConstraint(
            "(kind = 'panel' AND type IS NOT NULL "
            "AND panel_length_mm IS NOT NULL AND panel_width_mm IS NOT NULL "
            "AND panel_length_mm >= panel_width_mm AND grain_direction IS NOT NULL "
            "AND edge_width_mm IS NULL) "
            "OR (kind = 'edge' AND type IS NULL "
            "AND panel_length_mm IS NULL AND panel_width_mm IS NULL "
            "AND grain_direction IS NULL AND edge_width_mm IS NOT NULL)",
            name="ck_materials_kind_shape",
        ),
    )

    kind: Mapped[MaterialKind] = mapped_column(
        enum_type(MaterialKind, "material_kind"), nullable=False
    )
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manufacturers.id"), nullable=False
    )
    type: Mapped[PanelMaterialType | None] = mapped_column(
        enum_type(PanelMaterialType, "panel_material_type")
    )
    name: Mapped[str] = mapped_column(nullable=False)
    thickness_mm: Mapped[Decimal] = mapped_column(nullable=False)
    color: Mapped[str] = mapped_column(nullable=False)
    decor_code: Mapped[str | None]
    panel_length_mm: Mapped[int | None]
    panel_width_mm: Mapped[int | None]
    grain_direction: Mapped[bool | None]
    edge_width_mm: Mapped[int | None]
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    status: Mapped[MaterialStatus] = mapped_column(
        enum_type(MaterialStatus, "material_status"),
        default=MaterialStatus.ACTIVE,
        nullable=False,
    )


class BranchMaterial(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "branch_materials"
    __table_args__ = (
        UniqueConstraint("branch_id", "material_id", name="uq_branch_materials_branch_material"),
        CheckConstraint("price_tiyin >= 0", name="ck_branch_materials_price_nonnegative"),
        CheckConstraint("min_stock >= 0", name="ck_branch_materials_min_stock_nonnegative"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False)
    price_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_stock: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[MaterialStatus] = mapped_column(
        enum_type(MaterialStatus, "material_status"),
        default=MaterialStatus.ACTIVE,
        nullable=False,
    )


class BranchPricing(Base):
    __tablename__ = "branch_pricing"
    __table_args__ = (
        CheckConstraint(
            "cutting_rate_tiyin IS NULL OR cutting_rate_tiyin >= 0",
            name="ck_branch_pricing_cutting_nonnegative",
        ),
        CheckConstraint(
            "edge_banding_rate_tiyin IS NULL OR edge_banding_rate_tiyin >= 0",
            name="ck_branch_pricing_edge_nonnegative",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), primary_key=True)
    cutting_rate_tiyin: Mapped[int | None] = mapped_column(BigInteger)
    edge_banding_rate_tiyin: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime | None]
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
