"""Client app API schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import BranchStatus, DekorType, UserStatus
from app.schemas.common import APIModel


class ClientProfileResponse(APIModel):
    id: uuid.UUID
    phone: str
    name: str
    preferred_branch_id: uuid.UUID | None
    status: UserStatus


class ClientContact(APIModel):
    """Public name+phone lookup for an arbitrary client id — for cross-module
    identity displays (e.g. the cutting PDF header) that need a client's
    contact info without the "current authenticated principal" framing that
    `get_client_profile` requires."""

    id: uuid.UUID
    name: str
    phone: str


class ClientProfilePatchRequest(BaseModel):
    name: str | None = None
    preferred_branch_id: uuid.UUID | None = None


class ClientBranchOption(APIModel):
    branch_id: uuid.UUID
    workshop_id: uuid.UUID
    workshop_name: str
    branch_name: str
    address: str
    status: BranchStatus
    closed_reason: str | None
    kerf_mm: int
    edge_trim_mm: int


class ClientBranchMaterialPreview(APIModel):
    id: uuid.UUID
    manufacturer_name: str
    name: str
    price_tiyin: int
    display_unit: str


class ClientBranchResponse(APIModel):
    branch_id: uuid.UUID
    workshop_id: uuid.UUID
    workshop_name: str
    workshop_logo_file_id: uuid.UUID | None
    branch_name: str
    address: str
    # The primary number first, then the branch's extras in display order.
    phone: str
    additional_phones: list[str]
    latitude: Decimal | None
    longitude: Decimal | None
    status: BranchStatus
    closed_reason: str | None
    # Inline material preview so the branches list needs ONE request, not 1+N
    # (CB-13). materials_total is the full carried-material count for the "+N".
    materials_preview: list[ClientBranchMaterialPreview]
    materials_total: int


class ClientBranchMaterialResponse(APIModel):
    """One format a branch carries, as a client sees it.

    `id` is the branch material — the thing that gets ordered. Identity (tur,
    kod, nomi, tolali, image) comes from the dekor, dimensions from the branch's
    own format. There is no `name`: the client composes the label, or reads the
    preview's precomposed one.
    """

    id: uuid.UUID
    tur: DekorType
    manufacturer_name: str
    kod: str | None
    nomi: str
    tolali: bool
    image_file_id: uuid.UUID | None
    qalinlik_mm: Decimal
    uzunlik_mm: int | None
    eni_mm: int | None
    kromka_eni_mm: int | None
    price_tiyin: int
    display_unit: str
