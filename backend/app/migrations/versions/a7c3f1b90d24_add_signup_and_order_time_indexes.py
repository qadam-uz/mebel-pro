"""add signup and order time indexes

Revision ID: a7c3f1b90d24
Revises: 37ee5335706c
Create Date: 2026-07-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3f1b90d24"
down_revision: str | None = "1a7b3c9d2e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_orders_created_at", "orders", ["created_at"], unique=False)
    op.create_index("ix_workshops_created_at", "workshops", ["created_at"], unique=False)
    op.create_index("ix_clients_created_at", "clients", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clients_created_at", table_name="clients")
    op.drop_index("ix_workshops_created_at", table_name="workshops")
    op.drop_index("ix_orders_created_at", table_name="orders")
