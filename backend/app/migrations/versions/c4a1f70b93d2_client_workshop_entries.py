"""client workshop entries

Ustaxonalarim stops being purely derived. Every successful workshop-link entry
now writes a row here, so a client who scans a link and does not draw anything
that session still keeps the workshop (client-entry.md); the pin
(`clients.preferred_branch_id`) is written only when the branch is certain and
is unchanged by this migration.

Nothing is backfilled: the derived half of the set (pin + order/draft history)
still reads exactly as before, so existing clients lose nothing, and there is no
record of past entries to reconstruct.

Revision ID: c4a1f70b93d2
Revises: 1b8ec08422e9
Create Date: 2026-09-05 10:12:44.318220
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a1f70b93d2"
down_revision: str | None = "1b8ec08422e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_workshop_entries",
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("workshop_id", sa.Uuid(), nullable=False),
        sa.Column("last_entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "workshop_id", name="uq_client_workshop_entries_pair"),
    )
    op.create_index(
        "ix_client_workshop_entries_client",
        "client_workshop_entries",
        ["client_id", "last_entered_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_client_workshop_entries_client", table_name="client_workshop_entries")
    op.drop_table("client_workshop_entries")
