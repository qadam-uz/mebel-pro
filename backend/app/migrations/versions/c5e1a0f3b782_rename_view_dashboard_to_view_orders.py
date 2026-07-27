"""rename the view_dashboard permission to view_orders

The grant was labelled as a dashboard toggle but its only effect is admitting
the holder to workshop order reads (QAD-166). Renaming the enum *value* keeps
every existing `permission_grants` row pointing at the same enum member — the
value is stored by OID, so nothing has to be rewritten and no grant is orphaned.

Revision ID: c5e1a0f3b782
Revises: a7c3f1b90d24
Create Date: 2026-07-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e1a0f3b782"
down_revision: str | None = "a7c3f1b90d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE permission RENAME VALUE 'view_dashboard' TO 'view_orders'")


def downgrade() -> None:
    op.execute("ALTER TYPE permission RENAME VALUE 'view_orders' TO 'view_dashboard'")
