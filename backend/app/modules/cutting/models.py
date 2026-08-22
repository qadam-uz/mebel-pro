"""Cutting draft/result foundation models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey, utcnow
from app.models.enums import CuttingResultSource, CuttingResultStatus, DecorType, enum_type


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
            "branch_material_id",
            "panel_index",
            name="uq_cutting_panels_result_material_index",
        ),
        # The same rule for the other material namespace. Two constraints rather
        # than one over a COALESCE because NULLs are distinct in a unique index:
        # with `branch_material_id` nullable, the constraint above stops
        # policing customer-board panels entirely.
        UniqueConstraint(
            "cutting_result_id",
            "customer_board_id",
            "panel_index",
            name="uq_cutting_panels_result_board_index",
        ),
        CheckConstraint("panel_index >= 1", name="ck_cutting_panels_index_positive"),
        CheckConstraint("waste_area_mm2 >= 0", name="ck_cutting_panels_waste_nonnegative"),
        CheckConstraint("cut_count IS NULL OR cut_count >= 0", name="ck_cutting_panels_cut_count"),
        CheckConstraint(
            "cut_length_mm IS NULL OR cut_length_mm >= 0",
            name="ck_cutting_panels_cut_length",
        ),
        CheckConstraint(
            "(branch_material_id IS NOT NULL) <> (customer_board_id IS NOT NULL)",
            name="ck_cutting_panels_material_exactly_one",
        ),
    )

    cutting_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cutting_results.id"), nullable=False
    )
    # Exactly one of the two is set. A panel is cut either from a sheet the
    # branch carries or from one the walk-in brought in; those are disjoint
    # namespaces with different owners, and the CHECK above is what keeps a row
    # from claiming both or neither.
    branch_material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch_materials.id"))
    customer_board_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_boards.id"))
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


class CustomerBoard(UUIDPrimaryKey, Base):
    """A sheet the walk-in carried in — theirs, not the branch's.

    Typed in the cutting editor's «Mijoz materiali» tab, claimed in the draft's
    `own_panel_counts`, priced through a substitute the branch does carry, and
    consumed into an order. **Never listed in any catalog, never stocked, never
    offered to another client.**

    It used to be a `branch_materials` row flagged `customer_supplied`, which
    forced the branch catalog, the attach uniqueness index and every catalog
    listing to carry an exclusion for something that was never an offer. The id
    space is unchanged by the move: `own_panel_counts`, `material_snapshots`,
    `pricing_overrides.material_prices` and the optimizer's panel spec all key
    on a UUID string, and a board id and a branch-material id come from disjoint
    namespaces.
    """

    __tablename__ = "customer_boards"
    __table_args__ = (
        CheckConstraint("thickness_mm > 0", name="ck_customer_boards_thickness_positive"),
        CheckConstraint(
            "length_mm > 0 AND width_mm > 0 AND length_mm >= width_mm",
            name="ck_customer_boards_panel_size",
        ),
        # Panel-shaped only. A customer does not bring their own edge tape: the
        # service rejects `kromka` before the row is built, and this is the
        # backstop.
        CheckConstraint("type <> 'kromka'", name="ck_customer_boards_panel_type"),
        CheckConstraint("price_tiyin >= 0", name="ck_customer_boards_price_nonnegative"),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    # The operator-typed board name; NULL when they did not name it, and then
    # the label falls back to «Mijoz materiali» plus the dimensions.
    name: Mapped[str | None]
    type: Mapped[DecorType] = mapped_column(enum_type(DecorType, "decor_type"), nullable=False)
    thickness_mm: Mapped[Decimal] = mapped_column(nullable=False)
    length_mm: Mapped[int] = mapped_column(nullable=False)
    width_mm: Mapped[int] = mapped_column(nullable=False)
    has_grain: Mapped[bool] = mapped_column(nullable=False, default=False)
    # The substitute's price per sheet, frozen when the board was recorded. Not
    # a price the branch charges for this board — it charges for the SHORTAGE,
    # and the quote's demand is already `needed - brought`, so a per-sheet price
    # here bills only the sheets the customer did not bring and bills nothing
    # when they brought enough. 0 means the branch carries nothing of this size
    # and the operator prices the shortfall by hand.
    price_tiyin: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"), default=0
    )
    # The branch material the SHORTAGE is sold from when the layout needs more
    # sheets than the customer brought. NULL means the branch carries nothing of
    # this size — then the shortfall stays unpriced and the operator prices it.
    stock_material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch_materials.id"))
    # Provenance, never the discriminator: the draft is deleted when the order is
    # placed, so scoping on this would un-scope the board mid-placement.
    source_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cutting_drafts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
