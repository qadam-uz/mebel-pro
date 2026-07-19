"""Workshop-side cutting draft/result use cases (staff acting for a walk-in).

Mirrors the client cutting surface for workshop staff with ``manage_orders``.
Drafts stay client-owned (``client_id``) but are stamped
``created_via_workshop_id`` so staff access is scoped to their own workshop and
the drafts stay invisible on the client's own surface until an order is placed.
The heavy lifting (validation, optimise, response shaping) is the shared core in
``service.py`` — this module only differs in how the draft is scoped/authorized
and how the branch is validated (workshop tenancy, not public browsability).
"""

import uuid

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    CuttingResultStatus,
    MaterialKind,
    Permission,
    UserStatus,
)
from app.modules.access.api import (
    require_manage_orders_workshop,
    resolve_branch_scope,
)
from app.modules.access.contracts import Client
from app.modules.cutting.contracts import CuttingDraft, CuttingResult
from app.modules.cutting.schemas import (
    ClientCatalogMaterialOption,
    CuttingDraftResponse,
    CuttingPart,
    CuttingResultResponse,
)
from app.modules.cutting.service import (
    _apply_choose,
    _apply_delete,
    _apply_optimize,
    _apply_update,
    _catalog_materials,
    _draft_response,
    _result_response,
)
from app.modules.sales.contracts import Order
from app.modules.support.api import record_action


async def create_workshop_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    client_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> CuttingDraftResponse:
    workshop_id = require_manage_orders_workshop(principal)
    # The branch must belong to this workshop and the staffer must hold
    # manage_orders on it (owner bypass inside resolve_branch_scope).
    scope = await resolve_branch_scope(
        db, principal, branch_id=branch_id, permission=Permission.MANAGE_ORDERS
    )
    client = await db.get(Client, client_id)
    if client is None:
        raise APIError(
            "client_not_found", "Client not found", status_code=status.HTTP_404_NOT_FOUND
        )
    if client.status is not UserStatus.ACTIVE:
        raise APIError(
            "account_blocked", "Account is blocked", status_code=status.HTTP_403_FORBIDDEN
        )
    draft = CuttingDraft(
        client_id=client.id,
        preferred_branch_id=scope.branch_id,
        created_via_workshop_id=workshop_id,
        parts_snapshot=[],
    )
    db.add(draft)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="cutting_draft.create",
        entity_type="cutting_draft",
        entity_id=draft.id,
        workshop_id=workshop_id,
        summary="Created cutting draft for walk-in client",
        details={"client_id": str(client.id), "on_behalf": True},
    )
    return await _draft_response(db, draft)


async def get_workshop_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
) -> CuttingDraftResponse:
    draft = await _workshop_draft(db, principal=principal, draft_id=draft_id)
    return await _draft_response(db, draft)


async def update_workshop_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
    name_set: bool,
    name: str | None,
    preferred_branch_id_set: bool,
    preferred_branch_id: uuid.UUID | None,
    parts_snapshot: list[CuttingPart] | None,
) -> CuttingDraftResponse:
    draft = await _workshop_draft(db, principal=principal, draft_id=draft_id)
    resolved_branch_id = preferred_branch_id
    if preferred_branch_id_set and draft.revision_of_order_id is not None:
        # A revision draft is branch-locked to its order (orders.md: "Revising a
        # placed order") — same branch, same client, always.
        if preferred_branch_id != draft.preferred_branch_id:
            raise APIError(
                "order_revision_branch_locked",
                "An order revision stays on the order's branch",
            )
    elif preferred_branch_id_set and preferred_branch_id is not None:
        # A branch change on the staff path must still be a workshop branch the
        # staffer can act on — tenancy, not public browsability.
        scope = await resolve_branch_scope(
            db, principal, branch_id=preferred_branch_id, permission=Permission.MANAGE_ORDERS
        )
        resolved_branch_id = scope.branch_id
    return await _apply_update(
        db,
        draft=draft,
        principal=principal,
        name_set=name_set,
        name=name,
        preferred_branch_id_set=preferred_branch_id_set,
        preferred_branch_id=resolved_branch_id,
        parts_snapshot=parts_snapshot,
    )


async def delete_workshop_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
) -> None:
    draft = await _workshop_draft(db, principal=principal, draft_id=draft_id)
    await _apply_delete(db, draft=draft, principal=principal)


async def optimize_workshop_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
) -> CuttingDraftResponse:
    draft = await _workshop_draft(db, principal=principal, draft_id=draft_id)
    return await _apply_optimize(db, draft=draft, principal=principal)


async def choose_workshop_result(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
    result_id: uuid.UUID,
) -> CuttingDraftResponse:
    draft = await _workshop_draft(db, principal=principal, draft_id=draft_id)
    return await _apply_choose(db, draft=draft, principal=principal, result_id=result_id)


async def get_workshop_result(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    result_id: uuid.UUID,
) -> CuttingResultResponse:
    """A cutting result visible to this workshop: a candidate of a staff-minted
    draft of this workshop, or a confirmed result bound to an order of it."""
    workshop_id = require_manage_orders_workshop(principal)
    result = await db.get(CuttingResult, result_id)
    if result is None:
        raise APIError(
            "cutting_result_not_found",
            "Cutting result not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if result.status is CuttingResultStatus.CANDIDATE:
        draft = await db.get(CuttingDraft, result.draft_id) if result.draft_id else None
        if draft is None or draft.created_via_workshop_id != workshop_id:
            raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    else:
        order = await db.get(Order, result.order_id) if result.order_id else None
        if order is None or order.workshop_id != workshop_id:
            raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return await _result_response(db, result)


async def workshop_catalog_materials(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    kind: MaterialKind,
    branch_id: uuid.UUID,
    search: str | None = None,
    manufacturer_id: uuid.UUID | None = None,
    carried_only: bool = False,
    limit: int | None = None,
) -> list[ClientCatalogMaterialOption]:
    # A staff draft is always branch-scoped — the branch must belong to the
    # workshop and the staffer must hold manage_orders on it.
    await resolve_branch_scope(
        db, principal, branch_id=branch_id, permission=Permission.MANAGE_ORDERS
    )
    return await _catalog_materials(
        db,
        kind=kind,
        branch_id=branch_id,
        search=search,
        manufacturer_id=manufacturer_id,
        carried_only=carried_only,
        limit=limit,
    )


async def _workshop_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
) -> CuttingDraft:
    workshop_id = require_manage_orders_workshop(principal)
    draft = await db.get(CuttingDraft, draft_id)
    # A draft not minted via THIS workshop (a client's own, or another
    # workshop's) is a 404 — same shape a foreign draft gets on the client path.
    if draft is None or draft.created_via_workshop_id != workshop_id:
        raise APIError(
            "cutting_draft_not_found",
            "Cutting draft not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return draft
