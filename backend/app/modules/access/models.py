"""Identity, permission, Telegram sign-in, and session models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import (
    AuthenticatedPrincipalType,
    Permission,
    TelegramLoginTokenStatus,
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
        # Globally unique, not per workshop: the login alone must name exactly one
        # account, so sign-in is a single lookup and the per-account lockout holds.
        Index("uq_workshop_users_login_ci", func.lower(text("login")), unique=True),
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
    home_branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id"),
        nullable=False,
    )
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
        # AB-119: signup-rate counters on the platform dashboard scan by date.
        Index("ix_clients_created_at", "created_at"),
        UniqueConstraint("phone", name="uq_clients_phone"),
        CheckConstraint("length(name) >= 1 AND length(name) <= 80", name="ck_clients_name_len"),
        # Partial: one Telegram account signs in as at most one client, but the
        # many staff-created rows that have never signed in stay unconstrained.
        Index(
            "uq_clients_telegram_user_id",
            "telegram_user_id",
            unique=True,
            postgresql_where=text("telegram_user_id IS NOT NULL"),
            sqlite_where=text("telegram_user_id IS NOT NULL"),
        ),
    )

    phone: Mapped[str] = mapped_column(nullable=False)
    # The Telegram account that signs in as this client. Private-chat id equals
    # user id, so bot messages go straight to it.
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    # Set when a bot send bounces with 403 (the client blocked the bot); cleared
    # on their next `/start`. While set, Telegram delivery is skipped — the
    # inbox is unaffected.
    telegram_unreachable_at: Mapped[datetime | None]
    name: Mapped[str] = mapped_column(nullable=False)
    preferred_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    status: Mapped[UserStatus] = mapped_column(
        enum_type(UserStatus, "user_status"),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    last_login_at: Mapped[datetime | None]


class TelegramLoginToken(UUIDPrimaryKey, Base):
    """One browser↔bot sign-in handshake.

    Two secrets, deliberately: the deep-link token rides in the QR and is
    therefore public to anyone who can photograph the screen, while the poll
    secret never leaves the browser that requested it. A session is released
    only against the poll secret — see
    `docs/ref/features/access-management.md#the-handshake`.
    """

    __tablename__ = "telegram_login_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_telegram_login_tokens_token_hash"),
        UniqueConstraint("poll_secret_hash", name="uq_telegram_login_tokens_poll_secret_hash"),
        # The per-IP creation budget counts rows in a window.
        Index("ix_telegram_login_tokens_ip_created", "request_ip", "created_at"),
        Index("ix_telegram_login_tokens_telegram_user_id", "telegram_user_id"),
    )

    token_hash: Mapped[str] = mapped_column(nullable=False)
    poll_secret_hash: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[TelegramLoginTokenStatus] = mapped_column(
        enum_type(TelegramLoginTokenStatus, "telegram_login_token_status"),
        default=TelegramLoginTokenStatus.PENDING,
        nullable=False,
    )
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))
    request_ip: Mapped[str] = mapped_column(nullable=False)
    device_info: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    confirmed_at: Mapped[datetime | None]
    used_at: Mapped[datetime | None]


class TelegramLoginCode(UUIDPrimaryKey, Base):
    """The fallback path: a short code the bot shows an identified client.

    The code travels *from* Telegram to the site, so nothing is ever sent to a
    typed number. Its low entropy is covered by the redeem throttle, the
    5-minute TTL, and burn-on-redeem — not by per-row attempt counters, since no
    row is addressable before a correct guess.
    """

    __tablename__ = "telegram_login_codes"
    __table_args__ = (Index("ix_telegram_login_codes_code_hash", "code_hash"),)

    code_hash: Mapped[str] = mapped_column(nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
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
