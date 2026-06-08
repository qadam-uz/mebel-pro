"""Cross-cutting file, notification, audit, and status-log models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import ActorType, AuthenticatedPrincipalType, FileStorageStatus, enum_type


class File(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_files_size_nonnegative"),
        CheckConstraint("sort_order IS NULL OR sort_order >= 0", name="ck_files_sort_order"),
    )

    storage_key: Mapped[str] = mapped_column(nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(nullable=False)
    content_type: Mapped[str] = mapped_column(nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    storage_status: Mapped[FileStorageStatus] = mapped_column(
        enum_type(FileStorageStatus, "file_storage_status"),
        default=FileStorageStatus.PENDING,
        nullable=False,
    )
    entity_type: Mapped[str | None]
    entity_id: Mapped[uuid.UUID | None]
    sort_order: Mapped[int | None]
    uploaded_by_type: Mapped[AuthenticatedPrincipalType] = mapped_column(
        enum_type(AuthenticatedPrincipalType, "authenticated_principal_type"),
        nullable=False,
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(nullable=False)


class Notification(UUIDPrimaryKey, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_unread", "recipient_type", "recipient_id", "read_at"),
    )

    recipient_type: Mapped[AuthenticatedPrincipalType] = mapped_column(
        enum_type(AuthenticatedPrincipalType, "authenticated_principal_type"),
        nullable=False,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_code: Mapped[str] = mapped_column(nullable=False)
    entity_type: Mapped[str | None]
    entity_id: Mapped[uuid.UUID | None]
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    read_at: Mapped[datetime | None]


class ActionLog(UUIDPrimaryKey, Base):
    __tablename__ = "action_logs"
    __table_args__ = (
        Index("ix_action_logs_workshop_branch", "workshop_id", "branch_id"),
        Index("ix_action_logs_entity", "entity_type", "entity_id"),
    )

    actor_type: Mapped[ActorType] = mapped_column(
        enum_type(ActorType, "actor_type"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None]
    actor_client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))
    workshop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshops.id"))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    action: Mapped[str] = mapped_column(nullable=False)
    entity_type: Mapped[str | None]
    entity_id: Mapped[uuid.UUID | None]
    summary: Mapped[str | None]
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    trace_id: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class StatusChangeLog(UUIDPrimaryKey, Base):
    __tablename__ = "status_change_logs"
    __table_args__ = (
        Index("ix_status_change_logs_entity", "entity_type", "entity_id"),
        Index("ix_status_change_logs_workshop_branch", "workshop_id", "branch_id"),
    )

    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    workshop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshops.id"))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    from_status: Mapped[str | None]
    to_status: Mapped[str] = mapped_column(nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(
        enum_type(ActorType, "actor_type"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None]
    actor_client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))
    reason: Mapped[str | None]
    action_log_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("action_logs.id"))
    changed_at: Mapped[datetime] = mapped_column(nullable=False)
