"""add the record_order_payment permission

Taking money at the counter and correcting the books are different jobs. The
cashier who hands a receipt over needs to *record* an order payment; letting the
same grant *void* one is the classic till fraud — take the cash, erase the row.
`manage_finance` keeps every other ledger write, including edit and void.

Adding an enum value is not emitted by autogenerate, so it is written by hand.
Postgres cannot drop a value from an enum type, so the downgrade removes the
grants that use it and leaves the (now unused) value in place — recorded here so
nobody reads the asymmetry as an oversight.

Revision ID: b3c9f7d21a48
Revises: e7a2c4d19b60
Create Date: 2026-08-21 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c9f7d21a48"
down_revision: str | None = "e7a2c4d19b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF NOT EXISTS so a database already carrying the value (a re-run, or a
    # branch merged twice) upgrades instead of failing.
    op.execute("ALTER TYPE permission ADD VALUE IF NOT EXISTS 'record_order_payment'")


def downgrade() -> None:
    op.execute("DELETE FROM permission_grants WHERE permission = 'record_order_payment'")
