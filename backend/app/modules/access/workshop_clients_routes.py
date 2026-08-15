"""Workshop walk-in client routes (staff resolve + checkout re-fetch)."""

import uuid

from fastapi import APIRouter

from app.api.deps import AccountReadyPrincipal, Session
from app.modules.access.clients import normalize_uz_phone
from app.modules.access.schemas import (
    WorkshopClientLookupResponse,
    WorkshopClientResolveRequest,
    WorkshopClientResolveResponse,
    WorkshopClientResponse,
)
from app.modules.access.workshop_clients import (
    get_workshop_client,
    lookup_walk_in_client,
    resolve_walk_in_client,
)

router = APIRouter(prefix="/workshop/clients", tags=["workshop-clients"])


# Declared BEFORE `/{client_id}` so the literal segment is not captured as a uuid.
@router.get("/lookup", response_model=WorkshopClientLookupResponse)
async def workshop_clients_lookup(
    phone: str,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopClientLookupResponse:
    client = await lookup_walk_in_client(db, principal=principal, phone=phone)
    if client is None:
        return WorkshopClientLookupResponse(found=False, phone=normalize_uz_phone(phone))
    return WorkshopClientLookupResponse(
        found=True,
        phone=client.phone,
        id=client.id,
        name=client.name,
    )


@router.post("/resolve", response_model=WorkshopClientResolveResponse)
async def workshop_clients_resolve(
    payload: WorkshopClientResolveRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopClientResolveResponse:
    resolution = await resolve_walk_in_client(
        db,
        principal=principal,
        phone=payload.phone,
        name=payload.name,
    )
    return WorkshopClientResolveResponse(
        id=resolution.client.id,
        name=resolution.client.name,
        phone=resolution.client.phone,
        created=resolution.created,
    )


@router.get("/{client_id}", response_model=WorkshopClientResponse)
async def workshop_clients_show(
    client_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopClientResponse:
    client = await get_workshop_client(db, principal=principal, client_id=client_id)
    return WorkshopClientResponse(id=client.id, name=client.name, phone=client.phone)
