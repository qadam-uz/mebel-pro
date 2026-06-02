"""Identity, permission, OTP challenge, and session models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import (
    AuthenticatedPrincipalType,
    Permission,
    UserStatus,
    enum_type,
)


class PlatformUser(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "platform_users"
    __table_args__ = (Index("uq_platform_users_login_ci", func.lower(text("login")), unique=True),)

    login: Mapped[str] = mapped_column(nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    full_name: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        enum_type(UserStatus, "user_status"),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    password_reset_required: Mapped[bool] = mapped_column(default=True, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]


class WorkshopUser(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "workshop_users"
    __table_args__ = (
        Index(
            "uq_workshop_users_workshop_login_ci",
            "workshop_id",
            func.lower(text("login")),
            unique=True,
        ),
        Index(
            "uq_workshop_users_one_owner_per_workshop",
            "workshop_id",
            unique=True,
            postgresql_where=text("is_owner = true"),
            sqlite_where=text("is_owner = 1"),
        ),
        UniqueConstraint("id", "workshop_id", name="uq_workshop_users_id_workshop"),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    login: Mapped[str] = mapped_column(nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    full_name: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str] = mapped_column(nullable=False)
    is_owner: Mapped[bool] = mapped_column(default=False, nullable=False)
    home_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    status: Mapped[UserStatus] = mapped_column(
        enum_type(UserStatus, "user_status"),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    password_reset_required: Mapped[bool] = mapped_column(default=True, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]


class PermissionGrant(UUIDPrimaryKey, Base):
    __tablename__ = "permission_grants"
    __table_args__ = (
        UniqueConstraint(
            "workshop_user_id",
            "permission",
            "branch_id",
            name="uq_permission_grants_user_permission_branch",
        ),
    )

    workshop_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_users.id"),
        nullable=False,
    )
    permission: Mapped[Permission] = mapped_column(
        enum_type(Permission, "permission"),
        nullable=False,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_users.id"),
        nullable=False,
    )
    granted_at: Mapped[datetime] = mapped_column(nullable=False)


class Client(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("phone", name="uq_clients_phone"),
        CheckConstraint("length(name) >= 1 AND length(name) <= 80", name="ck_clients_name_len"),
    )

    phone: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    preferred_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    status: Mapped[UserStatus] = mapped_column(
        enum_type(UserStatus, "user_status"),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    last_login_at: Mapped[datetime | None]


class PhoneVerificationChallenge(UUIDPrimaryKey, Base):
    __tablename__ = "phone_verification_challenges"
    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 5", name="ck_phone_challenges_attempts"
        ),
    )

    phone: Mapped[str] = mapped_column(nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    consumed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class Session(UUIDPrimaryKey, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("access_token_hash", name="uq_sessions_access_token_hash"),
        UniqueConstraint("refresh_token_hash", name="uq_sessions_refresh_token_hash"),
        Index("ix_sessions_principal", "principal_type", "principal_id"),
    )

    principal_type: Mapped[AuthenticatedPrincipalType] = mapped_column(
        enum_type(AuthenticatedPrincipalType, "authenticated_principal_type"),
        nullable=False,
    )
    principal_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    access_token_hash: Mapped[str] = mapped_column(nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(nullable=False)
    access_token_expires_at: Mapped[datetime] = mapped_column(nullable=False)
    refresh_token_expires_at: Mapped[datetime] = mapped_column(nullable=False)
    device_info: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(nullable=False)
