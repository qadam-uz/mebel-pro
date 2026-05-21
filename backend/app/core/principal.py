"""The authenticated principal context.

Built by the auth dependency from the bearer token; never from client input.
Authorization (docs/ref/features/access-management.md → *How a request is
authorized*) reduces to: allow if owner, or if ``(permission, branch)`` is in
the grant set; owner-only operations require ``is_owner``.
"""

import uuid
from dataclasses import dataclass, field

from app.models.enums import Permission, PrincipalType, UserStatus


@dataclass(frozen=True)
class Principal:
    type: PrincipalType
    id: uuid.UUID
    session_id: uuid.UUID
    status: UserStatus = UserStatus.ACTIVE
    force_password_change: bool = False
    # workshop-user-only fields
    workshop_id: uuid.UUID | None = None
    is_owner: bool = False
    grants: frozenset[tuple[Permission, uuid.UUID]] = field(default_factory=frozenset)

    @property
    def is_platform_user(self) -> bool:
        return self.type is PrincipalType.PLATFORM_USER

    @property
    def is_workshop_user(self) -> bool:
        return self.type is PrincipalType.WORKSHOP_USER

    @property
    def is_client(self) -> bool:
        return self.type is PrincipalType.CLIENT

    def has_permission(self, permission: Permission, branch_id: uuid.UUID) -> bool:
        """Owner holds every permission on every branch; staff hold their grants."""
        if not self.is_workshop_user:
            return False
        if self.is_owner:
            return True
        return (permission, branch_id) in self.grants

    def branches_with(self, permission: Permission) -> set[uuid.UUID]:
        """Branch ids the principal holds ``permission`` on (empty for the owner —
        owner accessibility is computed from the workshop's branches instead)."""
        return {b for (p, b) in self.grants if p is permission}

    @property
    def accessible_branches(self) -> set[uuid.UUID]:
        """Branch ids reachable by any grant (non-owner). Owner spans all branches,
        resolved by the caller against the workshop."""
        return {b for (_, b) in self.grants}
