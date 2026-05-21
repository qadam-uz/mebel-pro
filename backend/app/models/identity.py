"""Identity models — the auth subjects and the session record.

Spec: docs/ref/entities/identity.md. Rules: docs/access-patterns.md.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import Permission, PrincipalType, UserStatus


class PlatformUser(UUIDPrimaryKey, Timestamped, Base):
    """A platform-operating team member ("superadmin"). Full platform scope."""

    __tablename__ = "platform_user"

    # stored lower-cased; uniqueness is case-insensitive
    login: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, length=16), default=UserStatus.ACTIVE
    )
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkshopUser(UUIDPrimaryKey, Timestamped, Base):
    """A workshop's person — including the owner. Capability = owner flag or grants."""

    __tablename__ = "workshop_user"
    __table_args__ = (
        UniqueConstraint("workshop_id", "login", name="uq_workshop_user_login"),
        Index("ix_workshop_user_workshop", "workshop_id"),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop.id"))
    login: Mapped[str] = mapped_column(String(64))  # lower-cased; unique per workshop
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    home_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branch.id"))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, length=16), default=UserStatus.ACTIVE
    )
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PermissionGrant(UUIDPrimaryKey, Base):
    """One ``(workshop user, permission, branch)`` grant. Owners hold all implicitly."""

    __tablename__ = "permission_grant"
    __table_args__ = (
        UniqueConstraint("workshop_user_id", "permission", "branch_id", name="uq_permission_grant"),
    )

    workshop_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop_user.id"), index=True)
    permission: Mapped[Permission] = mapped_column(Enum(Permission, native_enum=False, length=32))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branch.id"), index=True)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop_user.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Client(UUIDPrimaryKey, Timestamped, Base):
    """The customer — Telegram-OAuth identity only, global to the platform."""

    __tablename__ = "client"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20))
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, length=16), default=UserStatus.ACTIVE
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Session(UUIDPrimaryKey, Base):
    """A logged-in device for any principal. Opaque tokens stored hashed (SHA-256)."""

    __tablename__ = "session"
    __table_args__ = (Index("ix_session_principal", "principal_type", "principal_id"),)

    principal_type: Mapped[PrincipalType] = mapped_column(
        Enum(PrincipalType, native_enum=False, length=16)
    )
    principal_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    access_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    device_info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
