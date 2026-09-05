"""Client app API schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import BranchStatus, DecorType, UserStatus
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


class WorkshopLinkBranch(APIModel):
    """One visible branch behind a workshop link.

    Pickup information only — what a client needs to choose a counter and call
    it. Deliberately nothing about prices, catalog, staff or volumes: the
    landing is a trust cue, not a storefront (spec §1.3).
    """

    id: uuid.UUID
    branch_no: int
    name: str
    address: str
    phone: str
    status: BranchStatus
    closed_reason: str | None


class WorkshopLinkResponse(APIModel):
    """The public resolve payload behind `/w/{code}` and `/w/{code}/{branch_no}`."""

    # Echoed in canonical form so the landing posts back exactly what resolved.
    code: str
    workshop_name: str
    workshop_logo_file_id: uuid.UUID | None
    branches: list[WorkshopLinkBranch]
    # Set when the link named a branch that resolved — the landing then skips
    # the choice step entirely.
    requested_branch_id: uuid.UUID | None
    # True when a `branch_no` was asked for and did NOT resolve (renumbered,
    # retired, or made invisible). The link falls back to workshop-level
    # behavior instead of dying, because a printed QR outlives branch
    # reshuffles (spec §8) — the flag is how the landing knows to show the
    # choice step it was about to skip.
    branch_no_fallback: bool


class ClientEntryRequest(BaseModel):
    """Applying a scanned link. The code — never a bare branch id — is the
    capability that names the workshop; the server re-resolves both.

    `branch_id` is present only when the link itself named a branch
    (`/w/{code}/{branch_no}`). Left out, the server pins the workshop's single
    visible branch if it has one and pins nothing otherwise — it never guesses
    which counter of a multi-branch workshop the client stood at.
    """

    code: str
    branch_id: uuid.UUID | None = None


class ClientEntryResponse(APIModel):
    """What the entry wrote. The branch pair is null when the link left the
    branch undecided — the workshop is on Ustaxonalarim either way."""

    workshop_id: uuid.UUID
    workshop_name: str
    branch_id: uuid.UUID | None
    branch_name: str | None


class ClientWorkshopBranch(APIModel):
    id: uuid.UUID
    branch_no: int
    name: str
    address: str
    # Every published number, primary first: the client calls the counter, and
    # a branch that publishes three lines has three because the first two are
    # busy. `ClientBranchResponse` has carried the pair since checkout needed
    # it; Ustaxonalarim and the home card were the surfaces still showing one.
    phone: str
    additional_phones: list[str]
    # For the «Xaritada ko'rish» link; null on a branch nobody has placed on
    # the map yet, and the link is then simply absent.
    latitude: Decimal | None
    longitude: Decimal | None
    status: BranchStatus
    closed_reason: str | None
    is_pinned: bool


class ClientWorkshopResponse(APIModel):
    """One workshop on Ustaxonalarim — the pinned one plus every workshop the
    client has an order or a draft with (spec §2). `public_code` travels so
    "Asosiy qilish" can re-pin through the same entry endpoint a scan uses."""

    workshop_id: uuid.UUID
    name: str
    logo_file_id: uuid.UUID | None
    public_code: str
    is_pinned: bool
    branches: list[ClientWorkshopBranch]


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

    `id` is the branch material — the thing that gets ordered. The pattern
    (code, name, has_grain, image) comes from the decor; the substrate and every
    dimension come from the platform's decor format. There is no composed label:
    the client builds one, or reads the preview's precomposed one.
    """

    id: uuid.UUID
    type: DecorType
    manufacturer_name: str
    code: str | None
    name: str
    has_grain: bool
    image_file_id: uuid.UUID | None
    thickness_mm: Decimal
    length_mm: int | None
    width_mm: int | None
    tape_width_mm: int | None
    # 1 or 2 for the board types, null otherwise. A one-sided sheet is a
    # different product at a different price, so the client has to see it.
    finished_sides: int | None
    price_tiyin: int
    display_unit: str
