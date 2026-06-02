"""Cutting draft/result foundation models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import CuttingResultStatus, enum_type


class CuttingDraft(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "cutting_drafts"

    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    preferred_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    parts_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    chosen_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "cutting_results.id",
            name="fk_cutting_drafts_chosen_result_id",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        )
    )


class CuttingResult(UUIDPrimaryKey, Base):
    __tablename__ = "cutting_results"
    __table_args__ = (
        CheckConstraint(
            "waste_percentage >= 0 AND waste_percentage <= 1", name="ck_cutting_results_waste"
        ),
        CheckConstraint("total_cut_length_mm >= 0", name="ck_cutting_results_cut_length"),
        CheckConstraint("total_edge_length_mm >= 0", name="ck_cutting_results_edge_length"),
        UniqueConstraint("order_id", name="uq_cutting_results_order"),
    )

    draft_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cutting_drafts.id"))
    algorithm_name: Mapped[str] = mapped_column(nullable=False)
    algorithm_version: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[CuttingResultStatus] = mapped_column(
        enum_type(CuttingResultStatus, "cutting_result_status"),
        default=CuttingResultStatus.CANDIDATE,
        nullable=False,
    )
    kerf_mm: Mapped[int] = mapped_column(nullable=False)
    edge_trim_mm: Mapped[int] = mapped_column(nullable=False)
    panels_used_by_material: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    waste_percentage: Mapped[Decimal] = mapped_column(nullable=False)
    total_cut_length_mm: Mapped[int] = mapped_column(nullable=False)
    total_edge_length_mm: Mapped[int] = mapped_column(nullable=False)
    edge_length_by_material: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "orders.id",
            name="fk_cutting_results_order_id",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        )
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    confirmed_at: Mapped[datetime | None]
    invalidated_at: Mapped[datetime | None]


class CuttingPanel(UUIDPrimaryKey, Base):
    __tablename__ = "cutting_panels"
    __table_args__ = (
        UniqueConstraint(
            "cutting_result_id",
            "material_id",
            "panel_index",
            name="uq_cutting_panels_result_material_index",
        ),
        CheckConstraint("panel_index >= 1", name="ck_cutting_panels_index_positive"),
        CheckConstraint("waste_area_mm2 >= 0", name="ck_cutting_panels_waste_nonnegative"),
    )

    cutting_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cutting_results.id"), nullable=False
    )
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False)
    panel_index: Mapped[int] = mapped_column(nullable=False)
    waste_area_mm2: Mapped[int] = mapped_column(nullable=False)


class CuttingPlacement(UUIDPrimaryKey, Base):
    __tablename__ = "cutting_placements"
    __table_args__ = (
        CheckConstraint("part_quantity_index >= 1", name="ck_cutting_placements_quantity_index"),
        CheckConstraint("x_mm >= 0 AND y_mm >= 0", name="ck_cutting_placements_origin"),
        CheckConstraint("length_mm > 0 AND width_mm > 0", name="ck_cutting_placements_size"),
    )

    cutting_panel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cutting_panels.id"), nullable=False
    )
    part_ref: Mapped[str] = mapped_column(nullable=False)
    part_quantity_index: Mapped[int] = mapped_column(nullable=False)
    x_mm: Mapped[int] = mapped_column(nullable=False)
    y_mm: Mapped[int] = mapped_column(nullable=False)
    length_mm: Mapped[int] = mapped_column(nullable=False)
    width_mm: Mapped[int] = mapped_column(nullable=False)
    rotated: Mapped[bool] = mapped_column(default=False, nullable=False)
