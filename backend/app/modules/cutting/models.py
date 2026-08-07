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
from app.models.enums import CuttingResultSource, CuttingResultStatus, enum_type


class CuttingDraft(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "cutting_drafts"
    __table_args__ = (
        UniqueConstraint("revision_of_order_id", name="uq_cutting_drafts_revision_order"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(nullable=True)
    preferred_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    # Set when workshop staff minted this draft for a walk-in client; such
    # drafts are hidden from the client's own draft surface until ordered and
    # do not count toward the client's draft limit.
    created_via_workshop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshops.id"))
    # Set when this draft is an order's revision scratchpad (orders.md: "Revising
    # a placed order"): seeded from the order's confirmed result, branch-locked,
    # one per order; it applies back onto its order and never places a new one.
    revision_of_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "orders.id",
            name="fk_cutting_drafts_revision_of_order_id",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        )
    )
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
    # Client-supplied material (cutting.md, "Own material"). Sheets are counted
    # per catalog material rather than flagged per part: a part cannot say which
    # physical sheet carried it, because parts of one material share one layout
    # that does not exist until the optimiser has run. The stored number is the
    # client's claim, not a cap — `min(claim, panels_used)` decides what a given
    # result actually charges, so a claim that outruns today's layout survives
    # for the edit that needs it.
    own_panel_counts: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    # Edge tape is brought by the roll, so ownership is per tape material and the
    # per-side `source` on each part is stamped from this list on every write.
    own_edge_material_ids: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default="[]",
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
    source: Mapped[CuttingResultSource] = mapped_column(
        enum_type(CuttingResultSource, "cutting_result_source"),
        default=CuttingResultSource.OPTIMIZER,
        server_default=CuttingResultSource.OPTIMIZER.value,
        nullable=False,
    )
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
    # The draft's own-material claim projected onto *this* layout —
    # `min(claim, panels_used)` per material. The claim itself stays on the draft
    # so it survives a re-optimise; what a result charges is frozen here, which
    # is what lets a confirmed order reprice identically years later without
    # reaching back to a draft that has since moved on.
    own_panel_counts: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    waste_percentage: Mapped[Decimal] = mapped_column(nullable=False)
    total_cut_length_mm: Mapped[int] = mapped_column(nullable=False)
    total_edge_length_mm: Mapped[int] = mapped_column(nullable=False)
    edge_length_by_material: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    parts_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    material_snapshots: Mapped[dict[str, dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    edge_length_shop_by_material: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    edge_length_own_by_material: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    edge_consumed_shop_by_material: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    edge_consumed_own_by_material: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    edge_banded_sides_by_material: Mapped[dict[str, dict[str, int]]] = mapped_column(
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
        CheckConstraint("cut_count IS NULL OR cut_count >= 0", name="ck_cutting_panels_cut_count"),
        CheckConstraint(
            "cut_length_mm IS NULL OR cut_length_mm >= 0",
            name="ck_cutting_panels_cut_length",
        ),
    )

    cutting_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cutting_results.id"), nullable=False
    )
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False)
    panel_index: Mapped[int] = mapped_column(nullable=False)
    waste_area_mm2: Mapped[int] = mapped_column(nullable=False)
    # Imported MAP and pre-migration rows deliberately retain unknown cut metrics.
    cut_count: Mapped[int | None]
    cut_length_mm: Mapped[int | None]
    offcuts: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )


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
