"""Catalog, decor format and branch material API schemas.

Two surfaces, deliberately disjoint:

- **Platform (decors + decor formats)** — the product. Identity (manufacturer,
  code, name, image, grain) and every concrete format it is made in (substrate,
  thickness, size or tape width, finished sides). No price: a platform operator
  does not set a workshop's prices.
- **Workshop (branch materials)** — the decision to carry one platform format,
  with this branch's own price and reorder threshold. No dimensions: a branch
  does not invent formats.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import DecorType, MaterialStatus
from app.schemas.common import APIModel


class ManufacturerCreateRequest(BaseModel):
    name: str
    country: str | None = None
    note: str | None = None


class ManufacturerPatchRequest(BaseModel):
    name: str | None = None
    country: str | None = None
    note: str | None = None


class ManufacturerResponse(APIModel):
    id: uuid.UUID
    name: str
    country: str | None
    note: str | None
    status: MaterialStatus
    created_at: datetime
    updated_at: datetime


class DecorCreateRequest(BaseModel):
    manufacturer_id: uuid.UUID
    code: str | None = None
    name: str
    has_grain: bool = False
    image_file_id: uuid.UUID | None = None


class DecorPatchRequest(BaseModel):
    manufacturer_id: uuid.UUID | None = None
    code: str | None = None
    name: str | None = None
    has_grain: bool | None = None
    image_file_id: uuid.UUID | None = None


class DecorResponse(APIModel):
    id: uuid.UUID
    manufacturer_id: uuid.UUID
    manufacturer_name: str
    code: str | None
    name: str
    has_grain: bool
    image_file_id: uuid.UUID | None
    status: MaterialStatus
    # There is no stored display name: the string is composed from the identity
    # fields by app/core/material_label.py so every surface (admin, picker, PDF,
    # order history) reads the same shape. It carries no substrate and no
    # dimensions — a decor has neither.
    label: str
    # AB-22: how many distinct branches carry any format of this decor. Populated
    # on the platform list; 0 on responses that don't compute it.
    branch_usage_count: int = 0
    # Active formats. A decor with none is a name nobody can attach anything of.
    format_count: int = 0
    created_at: datetime
    updated_at: datetime


class DecorFormatCreateRequest(BaseModel):
    """One concrete product of a decor. Platform-only; immutable once written.

    Which fields are required follows `type`: `kromka` carries `tape_width_mm`
    and nothing else; every other type carries `length_mm`/`width_mm`, and the
    board types (`ldsp`/`dsp`/`mdf`) additionally carry `finished_sides`. The
    service enforces the whole rule with `decor_format_shape_mismatch`, and the
    DB backs it with a CHECK.
    """

    type: DecorType
    thickness_mm: Decimal
    length_mm: int | None = None
    width_mm: int | None = None
    tape_width_mm: int | None = None
    finished_sides: int | None = None


class DecorFormatResponse(APIModel):
    id: uuid.UUID
    decor_id: uuid.UUID
    type: DecorType
    thickness_mm: Decimal
    length_mm: int | None
    width_mm: int | None
    tape_width_mm: int | None
    finished_sides: int | None
    status: MaterialStatus
    label: str
    created_at: datetime
    updated_at: datetime


class BranchCatalogFormatOption(APIModel):
    """One active format in step two of the attach sheet.

    `carried` rows stay in the list, disabled: hiding them would make the branch
    wonder whether the size exists at all, which is the exact question the sheet
    is there to answer.
    """

    decor_format: DecorFormatResponse
    carried: bool


class BranchMaterialAttachItem(BaseModel):
    """One platform format the branch wants to carry, with its own numbers."""

    decor_format_id: uuid.UUID
    # Both optional: a branch routinely registers its whole list before it knows
    # prices. 0 means "not priced yet" and hides the row from clients.
    price_tiyin: int = 0
    min_stock: int = 0


class BranchMaterialAttachRequest(BaseModel):
    """Carry several platform formats in ONE transaction.

    A flat list of formats rather than decor-then-formats: the attach sheet
    walks one decor at a time, but a batch that spans decors is still one save,
    and a format id already identifies its decor.
    """

    items: list[BranchMaterialAttachItem]


class BranchMaterialPatchRequest(BaseModel):
    """Price and threshold only — the format is this row's identity."""

    price_tiyin: int | None = None
    min_stock: int | None = None


class BranchMaterialResponse(APIModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    decor_format_id: uuid.UUID
    # One nesting level each, not flattened: `decor_format.thickness_mm` says
    # where the number is owned, which is the whole point of the reshape.
    decor_format: DecorFormatResponse
    decor: DecorResponse
    price_tiyin: int
    # price_tiyin == 0 means unpriced, not free. Client-facing listings drop these
    # rows; workshop-facing ones flag them so the gap is visible where it is fixable.
    price_unset: bool
    min_stock: int
    status: MaterialStatus
    label: str
    created_at: datetime
    updated_at: datetime


class BranchMaterialAttachResponse(APIModel):
    created: list[BranchMaterialResponse]
    # Formats a concurrent attach already registered for this branch. The picker
    # shows what is already carried, so a duplicate here is a race, not user
    # error — skipped, not rejected.
    skipped: list[uuid.UUID]


class BranchCatalogDecorOption(APIModel):
    decor: DecorResponse
    # What the branch carries against what the platform offers. A decor is never
    # hidden from the picker: carrying 18 mm does not stop you adding 16 mm.
    carried_format_count: int
    available_format_count: int


class BranchCatalogOptionsPage(APIModel):
    """QAD-159: the attach picker needs an honest `Filtrdagi hammasi (N)` count, so
    this endpoint breaks the house bare-list convention and returns the page plus
    the total number of decors matching the same filters."""

    items: list[BranchCatalogDecorOption]
    total: int


class BranchCatalogManufacturerOption(APIModel):
    id: uuid.UUID
    name: str


class BranchCatalogFiltersResponse(APIModel):
    """Facet values for a branch catalog surface's dropdowns.

    Manufacturers only. Thickness is not a facet: it belongs to a format, and
    step two of the attach sheet lists those in full. `type` is a fixed enum the
    client renders without asking — on this surface it means "has an active
    format of this substrate".

    Which manufacturers depends on `scope`: the attach sheet asks about what the
    platform offers, the branch's own table about what the branch already
    carries. Sending the first set to the second surface means options that
    return nothing.
    """

    manufacturers: list[BranchCatalogManufacturerOption]
