"""Cross-cutting models — files, notifications, and the two audit logs.

Spec: docs/ref/entities/support.md.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import ActorType, FileStorageStatus, PrincipalType


class File(UUIDPrimaryKey, Timestamped, Base):
    """A stored blob (MinIO/S3) with metadata, optionally attached to an entity."""

    __tablename__ = "file"

    storage_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    storage_status: Mapped[FileStorageStatus] = mapped_column(
        Enum(FileStorageStatus, native_enum=False, length=16),
        default=FileStorageStatus.PENDING,
    )
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    sort_order: Mapped[int | None] = mapped_column(Integer)
    uploaded_by_type: Mapped[PrincipalType] = mapped_column(
        Enum(PrincipalType, native_enum=False, length=16)
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column()


class Notification(UUIDPrimaryKey, Base):
    """One in-app inbox item for one principal."""

    __tablename__ = "notification"
    __table_args__ = (
        Index("ix_notification_recipient", "recipient_type", "recipient_id", "read_at"),
    )

    recipient_type: Mapped[PrincipalType] = mapped_column(
        Enum(PrincipalType, native_enum=False, length=16)
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column()
    event_code: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionLog(UUIDPrimaryKey, Base):
    """One append-only row per mutating action — the "who did what" audit half."""

    __tablename__ = "action_log"
    __table_args__ = (
        Index("ix_action_log_workshop", "workshop_id", "created_at"),
        Index("ix_action_log_entity", "entity_type", "entity_id"),
    )

    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, native_enum=False, length=16))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column()
    actor_client_id: Mapped[uuid.UUID | None] = mapped_column()
    workshop_id: Mapped[uuid.UUID | None] = mapped_column()
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    summary: Mapped[str | None] = mapped_column(String(400))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    trace_id: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class StatusChangeLog(UUIDPrimaryKey, Base):
    """One append-only row per state transition of any audited entity."""

    __tablename__ = "status_change_log"
    __table_args__ = (
        Index("ix_status_change_entity", "entity_type", "entity_id"),
        Index("ix_status_change_workshop", "workshop_id", "changed_at"),
    )

    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID] = mapped_column()
    workshop_id: Mapped[uuid.UUID | None] = mapped_column()
    branch_id: Mapped[uuid.UUID | None] = mapped_column()
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, native_enum=False, length=16))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column()
    actor_client_id: Mapped[uuid.UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String(500))
    action_log_id: Mapped[uuid.UUID | None] = mapped_column()
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
