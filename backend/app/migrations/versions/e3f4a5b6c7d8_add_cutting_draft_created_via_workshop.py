"""add cutting draft created via workshop

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cutting_drafts",
        sa.Column("created_via_workshop_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cutting_drafts_created_via_workshop_id",
        "cutting_drafts",
        "workshops",
        ["created_via_workshop_id"],
        ["id"],
    )


def downgrade() -> None:
    # Forward-only: staff-minted drafts referencing a workshop would silently
    # become client-visible if the column were dropped; a rollback should be a
    # deliberate new migration instead.
    pass
