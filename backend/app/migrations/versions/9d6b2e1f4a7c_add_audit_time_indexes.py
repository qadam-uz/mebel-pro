"""add audit time indexes

Revision ID: 9d6b2e1f4a7c
Revises: 2d7f9d06216e
Create Date: 2026-06-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d6b2e1f4a7c"
down_revision: str | None = "2d7f9d06216e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_action_logs_created_at", "action_logs", ["created_at"], unique=False)
    op.create_index(
        "ix_status_change_logs_changed_at",
        "status_change_logs",
        ["changed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_status_change_logs_changed_at", table_name="status_change_logs")
    op.drop_index("ix_action_logs_created_at", table_name="action_logs")
