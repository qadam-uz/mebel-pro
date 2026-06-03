"""Client app API schemas."""

import uuid

from pydantic import BaseModel

from app.models.enums import BranchStatus, UserStatus
from app.schemas.common import APIModel


class ClientProfileResponse(APIModel):
    id: uuid.UUID
    phone: str
    name: str
    preferred_branch_id: uuid.UUID | None
    status: UserStatus


class ClientProfilePatchRequest(BaseModel):
    name: str | None = None
    preferred_branch_id: uuid.UUID | None = None


class ClientBranchOption(APIModel):
    branch_id: uuid.UUID
    workshop_id: uuid.UUID
    workshop_name: str
    branch_name: str
    status: BranchStatus
    closed_reason: str | None
