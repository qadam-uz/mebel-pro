"""branch production mode

Revision ID: d3f5a9c1e846
Revises: a2f6b91c73de
Create Date: 2026-08-31 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f5a9c1e846"
down_revision: str | None = "a2f6b91c73de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    mode_enum = sa.Enum("simple", "full", name="production_mode")
    mode_enum.create(op.get_bind(), checkfirst=True)
    # `simple` for every row, provisioned and future alike — there is no backfill.
    # The collapsed two-tap flow is the adoption default (orders.md), and at the
    # time this shipped no branch had orders mid-spine: the shops that exist run
    # on paper and never tapped the per-stage choreography, which is the whole
    # reason the mode exists. A shop that wants stations opts into `full` on the
    # branch form.
    op.add_column(
        "branches",
        sa.Column(
            "production_mode",
            mode_enum,
            server_default="simple",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "production_mode")
    sa.Enum(name="production_mode").drop(op.get_bind(), checkfirst=True)
