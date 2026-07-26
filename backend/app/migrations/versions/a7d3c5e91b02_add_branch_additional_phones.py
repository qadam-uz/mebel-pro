"""add branch additional phones

Revision ID: a7d3c5e91b02
Revises: 37ee5335706c
Create Date: 2026-07-26 10:12:44.118203
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "a7d3c5e91b02"
down_revision: str | None = "37ee5335706c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # An empty-array server default backfills every existing branch, so the
    # column can be NOT NULL from the start (QAD-158).
    op.add_column(
        "branches",
        sa.Column(
            "additional_phones",
            sa.JSON().with_variant(JSONB, "postgresql"),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "additional_phones")
