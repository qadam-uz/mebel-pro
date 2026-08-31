"""telegram bot client sign-in

Replaces the Telegram Gateway OTP flow with the bot deep-link handshake:
`phone_verification_challenges` goes, the two handshake tables arrive, and the
client row gains its Telegram link.

Forward-only. The challenge table is dropped outright rather than migrated:
its rows are 5-minute transients whose only durable purpose was feeding the
Gateway send budgets, and those budgets no longer exist — nothing downstream
reads a challenge, so there is nothing to carry over. Client rows are
untouched: `phone` stays the identity, and `telegram_user_id` fills in the
first time each client signs in through the bot.

Revision ID: 1b8ec08422e9
Revises: f1c8d3a29b47
Create Date: 2026-08-31 18:11:09.787857
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1b8ec08422e9"
down_revision: str | None = "f1c8d3a29b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TOKEN_STATUS = sa.Enum(
    "pending",
    "started",
    "awaiting_contact",
    "confirmed",
    "used",
    "declined",
    name="telegram_login_token_status",
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "telegram_login_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("poll_secret_hash", sa.String(), nullable=False),
        sa.Column("status", TOKEN_STATUS, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("request_ip", sa.String(), nullable=False),
        sa.Column(
            "device_info",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("poll_secret_hash", name="uq_telegram_login_tokens_poll_secret_hash"),
        sa.UniqueConstraint("token_hash", name="uq_telegram_login_tokens_token_hash"),
    )
    # The per-IP creation budget counts rows in a (request_ip, created_at) window.
    op.create_index(
        "ix_telegram_login_tokens_ip_created",
        "telegram_login_tokens",
        ["request_ip", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_login_tokens_telegram_user_id",
        "telegram_login_tokens",
        ["telegram_user_id"],
        unique=False,
    )

    op.create_table(
        "telegram_login_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telegram_login_codes_code_hash",
        "telegram_login_codes",
        ["code_hash"],
        unique=False,
    )

    op.add_column("clients", sa.Column("telegram_user_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "clients",
        sa.Column("telegram_unreachable_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Partial: one Telegram account signs in as at most one client, while the
    # staff-created rows that have never signed in stay unconstrained.
    op.create_index(
        "uq_clients_telegram_user_id",
        "clients",
        ["telegram_user_id"],
        unique=True,
        postgresql_where=sa.text("telegram_user_id IS NOT NULL"),
        sqlite_where=sa.text("telegram_user_id IS NOT NULL"),
    )

    op.drop_index(
        op.f("ix_phone_verification_challenges_phone"),
        table_name="phone_verification_challenges",
    )
    op.drop_index(
        op.f("ix_phone_verification_challenges_request_ip"),
        table_name="phone_verification_challenges",
    )
    op.drop_table("phone_verification_challenges")


def downgrade() -> None:
    op.create_table(
        "phone_verification_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("request_ip", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 5",
            name="ck_phone_challenges_attempts",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_phone_verification_challenges_phone"),
        "phone_verification_challenges",
        ["phone"],
        unique=False,
    )
    op.create_index(
        op.f("ix_phone_verification_challenges_request_ip"),
        "phone_verification_challenges",
        ["request_ip"],
        unique=False,
    )

    op.drop_index(
        "uq_clients_telegram_user_id",
        table_name="clients",
        postgresql_where=sa.text("telegram_user_id IS NOT NULL"),
        sqlite_where=sa.text("telegram_user_id IS NOT NULL"),
    )
    op.drop_column("clients", "telegram_unreachable_at")
    op.drop_column("clients", "telegram_user_id")

    op.drop_index("ix_telegram_login_codes_code_hash", table_name="telegram_login_codes")
    op.drop_table("telegram_login_codes")
    op.drop_index("ix_telegram_login_tokens_telegram_user_id", table_name="telegram_login_tokens")
    op.drop_index("ix_telegram_login_tokens_ip_created", table_name="telegram_login_tokens")
    op.drop_table("telegram_login_tokens")
    sa.Enum(name="telegram_login_token_status").drop(op.get_bind(), checkfirst=True)
