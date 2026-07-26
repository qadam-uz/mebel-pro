"""workshop login globally unique

Revision ID: a7b3c9d1e2f4
Revises: 37ee5335706c
Create Date: 2026-07-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b3c9d1e2f4"
down_revision: str | None = "37ee5335706c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_INDEX = "uq_workshop_users_workshop_login_ci"
NEW_INDEX = "uq_workshop_users_login_ci"


def upgrade() -> None:
    bind = op.get_bind()
    _assert_no_cross_workshop_duplicates(bind)

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("workshop_users")}
    if OLD_INDEX in indexes:
        op.drop_index(OLD_INDEX, table_name="workshop_users")
    if NEW_INDEX not in indexes:
        op.create_index(NEW_INDEX, "workshop_users", [sa.text("lower(login)")], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("workshop_users")}
    if NEW_INDEX in indexes:
        op.drop_index(NEW_INDEX, table_name="workshop_users")
    if OLD_INDEX not in indexes:
        op.create_index(
            OLD_INDEX,
            "workshop_users",
            ["workshop_id", sa.text("lower(login)")],
            unique=True,
        )


def _assert_no_cross_workshop_duplicates(bind: sa.engine.Connection) -> None:
    """Refuse the index swap while two workshops still share a login.

    Creating the unique index on a table that violates it fails halfway with a
    driver-level error that names one arbitrary row. Fail first instead, listing
    every colliding login, so the renames can be planned as an explicit
    production operation before the migration is retried.
    """
    duplicates = bind.execute(
        sa.text(
            "SELECT lower(login) AS login, count(*) AS total "
            "FROM workshop_users GROUP BY lower(login) HAVING count(*) > 1 "
            "ORDER BY lower(login)"
        )
    ).all()
    if not duplicates:
        return
    listed = ", ".join(f"{row.login} ({row.total} accounts)" for row in duplicates)
    raise RuntimeError(
        "Cannot make workshop logins globally unique: these logins are used by more "
        f"than one workshop user — {listed}. Rename the duplicates (an explicit "
        "production operation, each affected user needs their new login) and re-run "
        "this migration."
    )
