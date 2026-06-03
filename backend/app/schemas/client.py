"""Client app API schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import BranchStatus, MaterialKind, PanelMaterialType, UserStatus
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


class ClientBranchResponse(APIModel):
    branch_id: uuid.UUID
    workshop_id: uuid.UUID
    workshop_name: str
    workshop_logo_file_id: uuid.UUID | None
    branch_name: str
    address: str
    phone: str
    latitude: Decimal
    longitude: Decimal
    working_hours: dict[str, object]
    status: BranchStatus
    closed_reason: str | None


class ClientBranchMaterialResponse(APIModel):
    id: uuid.UUID
    kind: MaterialKind
    manufacturer_name: str
    type: PanelMaterialType | None
    name: str
    thickness_mm: Decimal
    color: str
    decor_code: str | None
    panel_length_mm: int | None
    panel_width_mm: int | None
    grain_direction: bool | None
    image_file_id: uuid.UUID | None
    price_tiyin: int
    display_unit: str
