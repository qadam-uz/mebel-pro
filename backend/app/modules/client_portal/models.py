"""Client-portal ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey, utcnow


class ClientWorkshopEntry(UUIDPrimaryKey, Timestamped, Base):
    """One workshop this client has walked into, and when they last did.

    Ustaxonalarim used to be derived from the pin plus order/draft history
    alone, which meant a client who scanned a workshop's link and did not draw
    anything that session lost the workshop again — the relationship existed in
    the world and nowhere in the data. Entry now writes a row here every time,
    whether or not the branch was certain enough to pin (client-entry.md).

    The pair is the identity: one row per client per workshop, upserted, so the
    table stays the size of the relationships it records rather than of the
    scans that made them.
    """

    __tablename__ = "client_workshop_entries"
    __table_args__ = (
        UniqueConstraint("client_id", "workshop_id", name="uq_client_workshop_entries_pair"),
        # Ustaxonalarim reads one client's rows, newest first.
        Index("ix_client_workshop_entries_client", "client_id", "last_entered_at"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    # Ordering key for the page. Separate from `updated_at` because that column
    # would also move for a schema backfill, and this one means one thing: the
    # last time the client came through this workshop's door.
    last_entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
