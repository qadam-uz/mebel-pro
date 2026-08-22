"""retire the record_order_payment permission

The counter cashier is simply given `manage_finance`: they record, edit and void
payments, and the end-of-day question is answered by the ledger's date filter,
its *who recorded* filter and the period total. The narrow grant added in
`b3c9f7d21a48` bought a second authz branch and a checkbox nobody used, so it
goes away again.

Deleting the grants is the whole upgrade, and it has to happen: the `Permission`
StrEnum no longer carries `record_order_payment`, so a surviving row would fail
to load the moment its holder authenticates.

Postgres cannot drop a value from an enum type in place, so the value stays in
the `permission` type — **unused and unreadable by the code**. Rebuilding the
type (new enum, column swap, drop old) would be the only way to be rid of it,
and it buys nothing: no column can hold the value once the grants are gone.
The orphan is the boring choice, recorded here so nobody reads it as an
oversight — the same asymmetry `b3c9f7d21a48` documents for its own downgrade.

`downgrade()` re-adds the enum value (idempotently), which is all it can do:
the deleted grants are not restorable — who held the permission on which branch
is not recoverable from anything this migration leaves behind.

Revision ID: a2f6b91c73de
Revises: c4e91a7b52d0
Create Date: 2026-08-22 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2f6b91c73de"
down_revision: str | None = "c4e91a7b52d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM permission_grants WHERE permission = 'record_order_payment'")


def downgrade() -> None:
    # IF NOT EXISTS so a database that still carries the orphan value — every
    # database that ran the upgrade — downgrades instead of failing.
    op.execute("ALTER TYPE permission ADD VALUE IF NOT EXISTS 'record_order_payment'")
