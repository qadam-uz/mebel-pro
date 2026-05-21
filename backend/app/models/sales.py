"""Sales models — order header, items, status events, cancellation.

Spec: docs/ref/entities/sales.md. State machine: docs/ref/features/orders.md.
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import (
    ActorType,
    CancelledByType,
    Currency,
    MaterialSource,
    OrderStatus,
)


class Order(UUIDPrimaryKey, Timestamped, Base):
    """A client's request for panels cut at a branch — the production spine."""

    __tablename__ = "order"
    __table_args__ = ()

    order_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client.id"), index=True)
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop.id"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), index=True)
    cutting_result_id: Mapped[uuid.UUID] = mapped_column()
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=16),
        default=OrderStatus.NEW,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic lock
    note_client: Mapped[str | None] = mapped_column(String(1000))
    note_workshop: Mapped[str | None] = mapped_column(String(1000))
    # contact captured at checkout (shared with the workshop)
    contact_name: Mapped[str] = mapped_column(String(120))
    contact_phone: Mapped[str] = mapped_column(String(20))

    # --- pricing snapshot (frozen at creation) ---
    subtotal_cutting_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    subtotal_materials_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    subtotal_edge_banding_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    discount_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    discount_reason: Mapped[str | None] = mapped_column(String(300))
    discount_applied_by_user_id: Mapped[uuid.UUID | None] = mapped_column()
    total_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[Currency] = mapped_column(
        Enum(Currency, native_enum=False, length=8), default=Currency.UZS
    )

    # --- worker assignment + production stamps ---
    assigned_cutter_user_id: Mapped[uuid.UUID | None] = mapped_column()
    assigned_edger_user_id: Mapped[uuid.UUID | None] = mapped_column()
    cutter_user_id: Mapped[uuid.UUID | None] = mapped_column()
    cut_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sheets_used_snapshot: Mapped[int | None] = mapped_column(Integer)
    cut_count_snapshot: Mapped[int | None] = mapped_column(Integer)
    edger_user_id: Mapped[uuid.UUID | None] = mapped_column()
    edge_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    edge_length_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # lifecycle timestamps
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderItem(UUIDPrimaryKey, Base):
    """One part line of an order, with a frozen material + price snapshot."""

    __tablename__ = "order_item"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order.id"), index=True)
    material_id: Mapped[uuid.UUID] = mapped_column()
    material_source: Mapped[MaterialSource] = mapped_column(
        Enum(MaterialSource, native_enum=False, length=8)
    )
    material_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    part_ref: Mapped[str] = mapped_column(String(64))
    length_mm: Mapped[int] = mapped_column(Integer)
    width_mm: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    edge_top_mm: Mapped[float | None] = mapped_column(Numeric(4, 2))
    edge_bottom_mm: Mapped[float | None] = mapped_column(Numeric(4, 2))
    edge_left_mm: Mapped[float | None] = mapped_column(Numeric(4, 2))
    edge_right_mm: Mapped[float | None] = mapped_column(Numeric(4, 2))
    unit_cutting_price_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    unit_material_price_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    edge_cost_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)
    line_total_tiyin: Mapped[int] = mapped_column(BigInteger, default=0)


class OrderStatusEvent(UUIDPrimaryKey, Base):
    """One append-only row per status transition — the order's audit trail."""

    __tablename__ = "order_status_event"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order.id"), index=True)
    from_status: Mapped[OrderStatus | None] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=16)
    )
    to_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, native_enum=False, length=16))
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, native_enum=False, length=16))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column()
    actor_client_id: Mapped[uuid.UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String(500))
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderCancellation(UUIDPrimaryKey, Base):
    """The single cancel event per order (unique)."""

    __tablename__ = "order_cancellation"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order.id"), unique=True)
    cancelled_by_type: Mapped[CancelledByType] = mapped_column(
        Enum(CancelledByType, native_enum=False, length=16)
    )
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column()
    cancelled_by_client_id: Mapped[uuid.UUID | None] = mapped_column()
    reason: Mapped[str] = mapped_column(String(500))
    cancelled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
