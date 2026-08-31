"""Workshop-scoped client entry: link resolve, the pin, and Ustaxonalarim.

A client enters through a workshop's door, not through a market: a scanned
`/w/{code}` link resolves here, applying it writes `Client.preferred_branch_id`
— the **pin** — and every workshop-scoped read downstream derives from that one
column. There is no new entity behind any of it (spec §2).
"""

import uuid
from collections.abc import Sequence

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import BranchStatus, WorkshopStatus
from app.modules.access.api import SlidingWindowIpThrottle
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
from app.modules.support.api import record_action
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


async def apply_entry(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    code: str,
    branch_id: uuid.UUID,
) -> ClientEntryResponse:
    """Pin the client to the branch a workshop link named.

    The pair is re-resolved server-side: the code names the workshop, and the
    branch has to be one of *its* visible branches. Latest entry wins — walking
    through a door is the confirmation — and re-applying the same link changes
    nothing but the audit trail.
    """
    client = await get_client_profile(db, principal=principal)
    workshop, normalized, branches = await _resolve_link(db, code)
    branch = next((row for row in branches if row.id == branch_id), None)
    if branch is None:
        # A branch of another workshop, or one that isn't visible. Same answer
        # either way — the client learns nothing about branches the link does
        # not carry.
        raise APIError(
            "branch_not_found",
            "Branch not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    client.preferred_branch_id = branch.id
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="client.entry.apply",
        entity_type="client",
        entity_id=client.id,
        workshop_id=workshop.id,
        branch_id=branch.id,
        summary=f"Entered {workshop.name} via workshop link",
        details={"public_code": normalized, "preferred_branch_id": str(branch.id)},
    )
    return ClientEntryResponse(
        workshop_id=workshop.id,
        workshop_name=workshop.name,
        branch_id=branch.id,
        branch_name=branch.name,
    )


async def my_workshops(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> list[ClientWorkshopResponse]:
    """The client's related workshops (spec §2), pinned first.

    Derived at read time, never stored: the pinned branch's workshop, plus the
    workshops of every branch the client has an order or a cutting draft on. A
    client who followed a link and never drew simply loses it to the next link
    — no relationship existed.
    """
    client = await get_client_profile(db, principal=principal)
    branch_ids: set[uuid.UUID] = set()
    if client.preferred_branch_id is not None:
        branch_ids.add(client.preferred_branch_id)
    branch_ids.update(
        (
            await db.scalars(select(Order.branch_id).where(Order.client_id == client.id).distinct())
        ).all()
    )
    draft_branch_ids = (
        await db.scalars(
            select(CuttingDraft.preferred_branch_id)
            .where(
                CuttingDraft.client_id == client.id,
                CuttingDraft.preferred_branch_id.is_not(None),
            )
            .distinct()
        )
    ).all()
    # The column is nullable, so its type stays optional even behind the filter.
    branch_ids.update(row for row in draft_branch_ids if row is not None)
    if not branch_ids:
        return []

    # History points at branches, which is one hop from what the page groups by.
    # Invisible branches still count for the *derivation* — a workshop whose
    # only branch went inactive stays on the page with its status (spec §8) —
    # they just don't get listed below.
    branch_workshops: dict[uuid.UUID, uuid.UUID] = dict(
        (await db.execute(select(Branch.id, Branch.workshop_id).where(Branch.id.in_(branch_ids))))
        .tuples()
        .all()
    )
    workshop_ids = set(branch_workshops.values())
    # A pin whose branch has gone invisible still pins its workshop — the badge
    # follows the workshop, not the branch row.
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
                status=branch.status,
                closed_reason=branch.closed_reason,
                is_pinned=pinned,
            )
        )
    return sorted(grouped.values(), key=lambda item: (not item.is_pinned, item.name))
