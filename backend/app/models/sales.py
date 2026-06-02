"""Order, item, and status-event foundation models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import ActorType, Currency, MaterialSource, OrderStatus, enum_type


class Order(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_number", name="uq_orders_order_number"),
        UniqueConstraint("cutting_result_id", name="uq_orders_cutting_result"),
        CheckConstraint("version >= 1", name="ck_orders_version_positive"),
        CheckConstraint("subtotal_cutting_tiyin >= 0", name="ck_orders_cutting_nonnegative"),
        CheckConstraint("subtotal_materials_tiyin >= 0", name="ck_orders_materials_nonnegative"),
        CheckConstraint("subtotal_edge_banding_tiyin >= 0", name="ck_orders_edge_nonnegative"),
        CheckConstraint("discount_tiyin >= 0", name="ck_orders_discount_nonnegative"),
        CheckConstraint("total_tiyin >= 0", name="ck_orders_total_nonnegative"),
        CheckConstraint(
            "discount_tiyin <= ("
            "subtotal_cutting_tiyin + subtotal_materials_tiyin + subtotal_edge_banding_tiyin)",
            name="ck_orders_discount_not_above_subtotal",
        ),
        CheckConstraint(
            "total_tiyin = ("
            "subtotal_cutting_tiyin + subtotal_materials_tiyin "
            "+ subtotal_edge_banding_tiyin - discount_tiyin)",
            name="ck_orders_total_formula",
        ),
        CheckConstraint(
            "discount_tiyin = 0 OR ("
            "discount_reason IS NOT NULL AND discount_applied_by_user_id IS NOT NULL)",
            name="ck_orders_discount_metadata_required",
        ),
    )

    order_number: Mapped[str] = mapped_column(nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    cutting_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "cutting_results.id",
            name="fk_orders_cutting_result_id",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=False,
    )
    status: Mapped[OrderStatus] = mapped_column(
        enum_type(OrderStatus, "order_status"),
        default=OrderStatus.NEW,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    note_client: Mapped[str | None]
    note_workshop: Mapped[str | None]
    confirmed_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    subtotal_cutting_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    subtotal_materials_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    subtotal_edge_banding_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    discount_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    discount_reason: Mapped[str | None]
    discount_applied_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workshop_users.id")
    )
    total_tiyin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    currency: Mapped[Currency] = mapped_column(
        enum_type(Currency, "currency"), default=Currency.UZS, nullable=False
    )
    assigned_cutter_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workshop_users.id")
    )
    assigned_edger_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workshop_users.id")
    )
    cutter_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
    cut_completed_at: Mapped[datetime | None]
    panels_used_snapshot: Mapped[int | None]
    cut_count_snapshot: Mapped[int | None]
    edger_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_users.id"))
    edge_completed_at: Mapped[datetime | None]
    edge_length_snapshot: Mapped[dict[str, int] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
    )
    picked_up_at: Mapped[datetime | None]


class OrderItem(UUIDPrimaryKey, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("length_mm > 0 AND width_mm > 0", name="ck_order_items_dimensions"),
        CheckConstraint("quantity >= 1", name="ck_order_items_quantity"),
        CheckConstraint("unit_cutting_price_tiyin >= 0", name="ck_order_items_cutting_price"),
        CheckConstraint("unit_material_price_tiyin >= 0", name="ck_order_items_material_price"),
        CheckConstraint("edge_cost_tiyin >= 0", name="ck_order_items_edge_cost"),
        CheckConstraint("line_total_tiyin >= 0", name="ck_order_items_line_total"),
        CheckConstraint(
            "line_total_tiyin = ("
            "(unit_cutting_price_tiyin + unit_material_price_tiyin) * quantity "
            "+ edge_cost_tiyin)",
            name="ck_order_items_line_total_formula",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False)
    material_source: Mapped[MaterialSource] = mapped_column(
        enum_type(MaterialSource, "material_source"),
        nullable=False,
    )
    material_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    part_ref: Mapped[str] = mapped_column(nullable=False)
    length_mm: Mapped[int] = mapped_column(nullable=False)
    width_mm: Mapped[int] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    edge_top: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    edge_bottom: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    edge_left: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    edge_right: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    unit_cutting_price_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_material_price_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)
    edge_cost_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_tiyin: Mapped[int] = mapped_column(BigInteger, nullable=False)


class OrderStatusEvent(UUIDPrimaryKey, Base):
    __tablename__ = "order_status_events"
    __table_args__ = (
        CheckConstraint(
            "((actor_type = 'client' AND actor_client_id IS NOT NULL AND actor_user_id IS NULL) OR "
            "(actor_type = 'workshop_user' "
            "AND actor_user_id IS NOT NULL AND actor_client_id IS NULL) OR "
            "(actor_type = 'system' AND actor_user_id IS NULL AND actor_client_id IS NULL))",
            name="ck_order_status_events_actor_shape",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    from_status: Mapped[OrderStatus | None] = mapped_column(enum_type(OrderStatus, "order_status"))
    to_status: Mapped[OrderStatus] = mapped_column(
        enum_type(OrderStatus, "order_status"), nullable=False
    )
    actor_type: Mapped[ActorType] = mapped_column(
        enum_type(ActorType, "actor_type"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None]
    actor_client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))
    reason: Mapped[str | None]
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
    )
    changed_at: Mapped[datetime] = mapped_column(nullable=False)


class OrderCancellation(UUIDPrimaryKey, Base):
    __tablename__ = "order_cancellations"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_order_cancellations_order"),
        CheckConstraint(
            "((cancelled_by_type = 'client' "
            "AND cancelled_by_client_id IS NOT NULL AND cancelled_by_user_id IS NULL) OR "
            "(cancelled_by_type = 'workshop_user' "
            "AND cancelled_by_user_id IS NOT NULL AND cancelled_by_client_id IS NULL))",
            name="ck_order_cancellations_actor_shape",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    cancelled_by_type: Mapped[ActorType] = mapped_column(
        enum_type(ActorType, "actor_type"), nullable=False
    )
    cancelled_by_user_id: Mapped[uuid.UUID | None]
    cancelled_by_client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))
    reason: Mapped[str] = mapped_column(nullable=False)
    cancelled_at: Mapped[datetime] = mapped_column(nullable=False)
