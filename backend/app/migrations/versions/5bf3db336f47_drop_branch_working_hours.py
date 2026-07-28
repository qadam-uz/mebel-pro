"""drop branch working hours

Revision ID: 5bf3db336f47
Revises: a7c3f1b90d24
Create Date: 2026-07-27 02:50:28.066418
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5bf3db336f47"
down_revision: str | None = "c5e1a0f3b782"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # QAD-179: working hours were display-only and unmaintained; availability is
    # owned by branches.status / closed_reason. Dropping the column destroys any
    # configured schedule — deliberate, and irreversible in practice.
    op.drop_column("branches", "working_hours")


def downgrade() -> None:
    # Recreates the column shape only. The schedules themselves are gone;
    # every branch comes back with an empty map.
    op.add_column(
        "branches",
        sa.Column(
            "working_hours",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
