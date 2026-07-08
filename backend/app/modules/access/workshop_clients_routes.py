"""Workshop walk-in client routes (staff resolve + checkout re-fetch)."""

import uuid

from fastapi import APIRouter

from app.api.deps import AccountReadyPrincipal, Session
from app.modules.access.schemas import (
    WorkshopClientResolveRequest,
    WorkshopClientResolveResponse,
    WorkshopClientResponse,
)
from app.modules.access.workshop_clients import get_workshop_client, resolve_walk_in_client

router = APIRouter(prefix="/workshop/clients", tags=["workshop-clients"])


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
