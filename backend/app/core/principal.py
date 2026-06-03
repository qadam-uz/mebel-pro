"""Authenticated-principal and internal actor contexts."""

import uuid
from dataclasses import dataclass

from app.models.enums import ActorType, AuthenticatedPrincipalType, Permission


@dataclass(frozen=True)
class PermissionGrantKey:
    permission: Permission
    branch_id: uuid.UUID


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    principal_type: AuthenticatedPrincipalType
    principal_id: uuid.UUID
    session_id: uuid.UUID
    trace_id: str
    workshop_id: uuid.UUID | None = None
    is_owner: bool = False
    password_reset_required: bool = False
    grants: frozenset[PermissionGrantKey] = frozenset()


@dataclass(frozen=True)
class ActorContext:
    actor_type: ActorType
    trace_id: str
    actor_user_id: uuid.UUID | None = None
    actor_client_id: uuid.UUID | None = None


def actor_from_principal(principal: AuthenticatedPrincipal) -> ActorContext:
    actor_type = ActorType(principal.principal_type.value)
    if principal.principal_type is AuthenticatedPrincipalType.CLIENT:
        return ActorContext(
            actor_type=actor_type,
            actor_client_id=principal.principal_id,
            trace_id=principal.trace_id,
        )
    return ActorContext(
        actor_type=actor_type,
        actor_user_id=principal.principal_id,
        trace_id=principal.trace_id,
    )


def system_actor(trace_id: str) -> ActorContext:
    return ActorContext(actor_type=ActorType.SYSTEM, trace_id=trace_id)
