"""Workshop-scoped client entry: link resolve, the pin, and Ustaxonalarim.

A client enters through a workshop's door, not through a market. A scanned
`/w/{code}` link resolves here, and applying it writes **two** things
(client-entry.md):

- always a row in `client_workshop_entries` — the relationship itself, which is
  what puts the workshop on Ustaxonalarim even before the client draws
  anything;
- the **pin** (`Client.preferred_branch_id`) only when the branch is *certain*:
  a branch link, or a workshop link to a workshop with exactly one visible
  branch. A multi-branch workshop link leaves the pin alone — the client is
  pinned to a branch, never to a workshop, and nothing may guess which counter
  they stood at.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import BranchStatus, WorkshopStatus
from app.modules.access.api import SlidingWindowIpThrottle
from app.modules.client_portal.models import ClientWorkshopEntry
from app.modules.client_portal.schemas import (
    ClientEntryResponse,
    ClientWorkshopBranch,
    ClientWorkshopResponse,
    WorkshopLinkBranch,
    WorkshopLinkResponse,
)
from app.modules.client_portal.service import get_client_profile
from app.modules.cutting.contracts import CuttingDraft
from app.modules.sales.contracts import Order
from app.modules.support.api import (
    FileStorage,
    ImageVariant,
    get_stored_file,
    record_action,
    serve_stored_file,
)
from app.modules.workshop.api import normalize_public_code
from app.modules.workshop.contracts import Branch, Workshop

# What a client may see and pick: the two statuses that mean "this counter
# exists". `temporarily_closed` stays choosable and renders its reason;
# ordering from it is gated later, exactly as today.
VISIBLE_BRANCH_STATUSES = (BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED)

WORKSHOP_LINK_NOT_FOUND = "workshop_link_not_found"

# The public resolve endpoint is unauthenticated, so this is what stands
# between the code space and a walk. Process-local, like the sign-in budgets.
workshop_link_throttle = SlidingWindowIpThrottle(
    error_code="workshop_link_rate_limited",
    message="Too many workshop link lookups",
    enabled=lambda: settings.PUBLIC_LINK_THROTTLE_ENABLED,
    budget=lambda: settings.PUBLIC_LINK_LOOKUPS_PER_IP,
    window_seconds=lambda: settings.PUBLIC_LINK_WINDOW_SECONDS,
)


def _link_not_found() -> APIError:
    """One 404 for every dead-link cause.

    Never existed, blocked workshop, zero visible branches — the endpoint
    refuses to distinguish them (spec §1.3/§8). A dead link explains nothing
    about why, to a scanner or to a scraper.
    """
    return APIError(
        WORKSHOP_LINK_NOT_FOUND,
        "Workshop link not found",
        status_code=status.HTTP_404_NOT_FOUND,
    )


async def _resolve_link(db: AsyncSession, code: str) -> tuple[Workshop, str, Sequence[Branch]]:
    normalized = normalize_public_code(code)
    if normalized is None:
        # Malformed input can never match a row — refused without a query.
        raise _link_not_found()
    workshop = await db.scalar(
        select(Workshop).where(
            Workshop.public_code == normalized,
            Workshop.status == WorkshopStatus.ACTIVE,
        )
    )
    if workshop is None:
        raise _link_not_found()
    branches = (
        await db.scalars(
            select(Branch)
            .where(
                Branch.workshop_id == workshop.id,
                Branch.status.in_(VISIBLE_BRANCH_STATUSES),
            )
            .order_by(Branch.name)
        )
    ).all()
    if not branches:
        raise _link_not_found()
    return workshop, normalized, branches


async def resolve_workshop_link(
    db: AsyncSession,
    *,
    code: str,
    branch_no: int | None = None,
) -> WorkshopLinkResponse:
    """Everything the `/w/...` landing needs, and nothing else."""
    workshop, normalized, branches = await _resolve_link(db, code)
    requested = None
    if branch_no is not None:
        requested = next((branch for branch in branches if branch.branch_no == branch_no), None)
    return WorkshopLinkResponse(
        code=normalized,
        workshop_name=workshop.name,
        workshop_logo_file_id=workshop.logo_file_id,
        branches=[
            WorkshopLinkBranch(
                id=branch.id,
                branch_no=branch.branch_no,
                name=branch.name,
                address=branch.address,
                phone=branch.phone,
                status=branch.status,
                closed_reason=branch.closed_reason,
            )
            for branch in branches
        ],
        requested_branch_id=requested.id if requested is not None else None,
        branch_no_fallback=branch_no is not None and requested is None,
    )


async def workshop_link_logo(
    db: AsyncSession,
    *,
    storage: FileStorage,
    code: str,
    if_none_match: str | None = None,
) -> Response:
    """The workshop's logo, for a landing that has no session yet.

    The **code is the capability**, exactly as it is for the resolve: it names
    one workshop, and the only file this route can ever reach is that
    workshop's `logo_file_id`. No file id crosses the boundary, so nothing else
    in the store becomes addressable — the general `/files/{id}` route stays
    authenticated.

    Every dead end answers the resolve's one 404: unknown code, blocked
    workshop, no visible branch, and a workshop that simply has no logo. A
    landing that gets nothing here falls back to the name monogram it already
    drew before this route existed.
    """
    workshop, _, _ = await _resolve_link(db, code)
    if workshop.logo_file_id is None:
        raise _link_not_found()
    row = await get_stored_file(db, file_id=workshop.logo_file_id)
    if row is None:
        raise _link_not_found()
    # `sm` (160px): the landing draws it at 56px, and this is the one request a
    # signed-out scan makes for bytes. `db` is passed so a logo that predates
    # renditions renders itself here too rather than shipping the full original.
    return await serve_stored_file(
        row=row,
        storage=storage,
        if_none_match=if_none_match,
        size=ImageVariant.SM,
        db=db,
    )


async def record_workshop_entry(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    workshop_id: uuid.UUID,
    entered_at: datetime | None = None,
) -> ClientWorkshopEntry:
    """Upsert this client's row for this workshop and stamp it.

    One row per pair, so the table records relationships rather than scans; the
    stamp is what orders Ustaxonalarim under the pinned workshop.
    """
    moment = entered_at or datetime.now(UTC)
    entry = await db.scalar(
        select(ClientWorkshopEntry).where(
            ClientWorkshopEntry.client_id == client_id,
            ClientWorkshopEntry.workshop_id == workshop_id,
        )
    )
    if entry is None:
        entry = ClientWorkshopEntry(
            client_id=client_id,
            workshop_id=workshop_id,
            last_entered_at=moment,
        )
        db.add(entry)
        await db.flush()
    else:
        entry.last_entered_at = moment
    return entry


async def apply_entry(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    code: str,
    branch_id: uuid.UUID | None = None,
) -> ClientEntryResponse:
    """Record the entry, and pin the branch when the link settles which one.

    The pair is re-resolved server-side: the code names the workshop, and a
    named branch has to be one of *its* visible branches. Latest entry wins —
    walking through a door is the confirmation.

    Certainty is the whole rule for the pin. A branch link names its counter; a
    one-branch workshop has only one counter to name; a multi-branch workshop
    link names none, so the pin is left exactly as it was and the client is
    asked on Ustaxonalarim instead. The entry row is written either way.
    """
    client = await get_client_profile(db, principal=principal)
    workshop, normalized, branches = await _resolve_link(db, code)
    branch: Branch | None = None
    if branch_id is not None:
        branch = next((row for row in branches if row.id == branch_id), None)
        if branch is None:
            # A branch of another workshop, or one that isn't visible. Same
            # answer either way — the client learns nothing about branches the
            # link does not carry.
            raise APIError(
                "branch_not_found",
                "Branch not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
    elif len(branches) == 1:
        branch = branches[0]

    await record_workshop_entry(db, client_id=client.id, workshop_id=workshop.id)
    if branch is not None:
        client.preferred_branch_id = branch.id
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="client.entry.apply",
        entity_type="client",
        entity_id=client.id,
        workshop_id=workshop.id,
        branch_id=branch.id if branch is not None else None,
        summary=f"Entered {workshop.name} via workshop link",
        details={
            "public_code": normalized,
            "preferred_branch_id": str(branch.id) if branch is not None else None,
        },
    )
    return ClientEntryResponse(
        workshop_id=workshop.id,
        workshop_name=workshop.name,
        branch_id=branch.id if branch is not None else None,
        branch_name=branch.name if branch is not None else None,
    )


async def visible_branch_counts(
    db: AsyncSession,
    workshop_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, int]:
    """How many branches each of these workshops shows a client.

    The system-wide naming rule turns on this one number: a workshop with a
    single visible branch is named by itself and its branch name never appears;
    a workshop with several is «{Workshop} · {Branch}» (client-entry.md). Every
    surface that names a workshop therefore has to count branches the same way
    Ustaxonalarim does, or an order card and the branch list disagree about what
    the same workshop is called — which is why the count travels in the payload
    rather than being guessed client-side, and why it is computed here, beside
    the predicate, rather than re-expressed in the caller.

    Workshops with no visible branch are simply absent from the mapping.
    """

    if not workshop_ids:
        return {}
    rows = (
        await db.execute(
            select(Branch.workshop_id, func.count(Branch.id))
            .where(
                Branch.workshop_id.in_(workshop_ids),
                Branch.status.in_(VISIBLE_BRANCH_STATUSES),
            )
            .group_by(Branch.workshop_id)
        )
    ).all()
    return {workshop_id: int(count) for workshop_id, count in rows}


async def my_workshops(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> list[ClientWorkshopResponse]:
    """The client's related workshops, pinned first (client-entry.md).

    The set is stored plus derived: every workshop the client has *entered*
    through a link, plus the pinned branch's workshop, plus the workshops of
    every branch they have an order or a cutting draft on. The stored half is
    what a link buys — before this table, a client who scanned a workshop's QR
    and drew nothing lost the workshop to the next scan.

    Order is the pinned workshop, then the rest by the most recent thing that
    happened with them — an entry, an order, a drawing — newest first. A
    blocked workshop is off the platform and appears in neither half.
    """
    client = await get_client_profile(db, principal=principal)
    last_seen = await _workshop_activity(db, client_id=client.id)
    branch_ids: set[uuid.UUID] = set()
    if client.preferred_branch_id is not None:
        branch_ids.add(client.preferred_branch_id)

    # History points at branches, which is one hop from what the page groups by.
    # Invisible branches still count for the *derivation* — a workshop whose
    # only branch went inactive stays on the page with its status — they just
    # don't get listed below.
    branch_workshops: dict[uuid.UUID, uuid.UUID] = dict(
        (await db.execute(select(Branch.id, Branch.workshop_id).where(Branch.id.in_(branch_ids))))
        .tuples()
        .all()
    )
    workshop_ids = set(last_seen) | set(branch_workshops.values())
    if not workshop_ids:
        return []
    # A pin whose branch has gone invisible still pins its workshop — the star
    # sits on the branch row, but the workshop it belongs to still leads.
    pinned_workshop_id = (
        branch_workshops.get(client.preferred_branch_id)
        if client.preferred_branch_id is not None
        else None
    )
    rows = (
        await db.execute(
            select(Workshop, Branch)
            .outerjoin(
                Branch,
                (Branch.workshop_id == Workshop.id) & Branch.status.in_(VISIBLE_BRANCH_STATUSES),
            )
            .where(
                Workshop.id.in_(workshop_ids),
                # A blocked workshop is off the platform: no link resolves to
                # it, and it does not appear here either.
                Workshop.status == WorkshopStatus.ACTIVE,
            )
            .order_by(Workshop.name, Branch.name)
        )
    ).all()

    grouped: dict[uuid.UUID, ClientWorkshopResponse] = {}
    for workshop, branch in rows:
        entry = grouped.get(workshop.id)
        if entry is None:
            entry = ClientWorkshopResponse(
                workshop_id=workshop.id,
                name=workshop.name,
                logo_file_id=workshop.logo_file_id,
                public_code=workshop.public_code,
                is_pinned=workshop.id == pinned_workshop_id,
                branches=[],
            )
            grouped[workshop.id] = entry
        if branch is None:
            continue
        pinned = branch.id == client.preferred_branch_id
        entry.branches.append(
            ClientWorkshopBranch(
                id=branch.id,
                branch_no=branch.branch_no,
                name=branch.name,
                address=branch.address,
                phone=branch.phone,
                additional_phones=list(branch.additional_phones or []),
                latitude=branch.latitude,
                longitude=branch.longitude,
                status=branch.status,
                closed_reason=branch.closed_reason,
                is_pinned=pinned,
            )
        )
    return sorted(
        grouped.values(),
        key=lambda item: (
            not item.is_pinned,
            -_activity_rank(last_seen.get(item.workshop_id)),
            item.name,
        ),
    )


# Older than any row this platform can hold, so a workshop with no timestamped
# activity of its own sorts last rather than first.
_NO_ACTIVITY = datetime(1970, 1, 1, tzinfo=UTC)


def _activity_rank(moment: datetime | None) -> float:
    return (moment or _NO_ACTIVITY).timestamp()


async def _workshop_activity(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
) -> dict[uuid.UUID, datetime]:
    """When each workshop last did anything with this client.

    Three sources folded into one map by `max`: the entry stamp, the client's
    latest order, and their latest drawing. They answer the same question —
    "how recently did these two deal with each other" — and the page needs one
    answer per workshop, not three columns.
    """
    latest: dict[uuid.UUID, datetime] = {}

    def _fold(workshop_id: uuid.UUID | None, moment: datetime | None) -> None:
        if workshop_id is None or moment is None:
            return
        current = latest.get(workshop_id)
        if current is None or moment > current:
            latest[workshop_id] = moment

    entries = await db.execute(
        select(ClientWorkshopEntry.workshop_id, ClientWorkshopEntry.last_entered_at).where(
            ClientWorkshopEntry.client_id == client_id
        )
    )
    for workshop_id, entered_at in entries.tuples().all():
        _fold(workshop_id, entered_at)

    orders = await db.execute(
        select(Order.workshop_id, func.max(Order.created_at))
        .where(Order.client_id == client_id)
        .group_by(Order.workshop_id)
    )
    for workshop_id, created_at in orders.tuples().all():
        _fold(workshop_id, created_at)

    drafts = await db.execute(
        select(Branch.workshop_id, func.max(CuttingDraft.created_at))
        .join(Branch, Branch.id == CuttingDraft.preferred_branch_id)
        .where(CuttingDraft.client_id == client_id)
        .group_by(Branch.workshop_id)
    )
    for workshop_id, created_at in drafts.tuples().all():
        _fold(workshop_id, created_at)

    return latest
