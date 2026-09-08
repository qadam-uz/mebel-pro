"""Catalog, decor format and branch material API schemas.

Three surfaces:

- **Platform (decors + decor formats)** — the *library*. Identity (manufacturer,
  code, name, image, grain) and every concrete format it is made in (substrate,
  thickness, size or tape width, finished sides). No price: a platform operator
  does not set a workshop's prices.
- **Workshop catalog (own decors + own formats)** — the same product shape,
  written by a workshop for itself when the library lacks it, and visible only to
  that workshop. Every product response carries `own` so a list can badge the row
  without a second call.
- **Workshop (branch materials)** — the decision to carry one format, at this
  branch's own price. No dimensions: the branch row is a commercial decision, not
  a product fact.
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
    # True when the reader's own workshop wrote the row (`workshop_id IS NOT
    # NULL`). The owning workshop's id is deliberately absent: a reader either
    # sees a row or does not, so the only fact a screen needs is "mine" vs "the
    # library's". Platform responses are always `false` — they list the library.
    own: bool = False
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
    # This workshop wrote the decor — the «Sizniki» chip. See ManufacturerResponse.
    own: bool = False
    created_at: datetime
    updated_at: datetime


class DecorFormatCreateRequest(BaseModel):
    """One concrete product of a decor. Immutable once written.

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
    # This workshop wrote the format. True on a format of a *library* decor too:
    # "Egger H1145 exists, the 16 mm is ours" is the common case.
    own: bool = False
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
    """One format the branch wants to carry, at its own price.

    A stale client still sending the retired `min_stock` is **ignored**, not
    refused: Pydantic drops unknown fields, and a 422 would break an old tab
    mid-attach over a number nothing reads any more.
    """

    decor_format_id: uuid.UUID
    # Optional: a branch routinely registers its whole list before it knows
    # prices. 0 means "not priced yet" and hides the row from clients.
    price_tiyin: int = 0


class BranchMaterialAttachRequest(BaseModel):
    """Carry several platform formats in ONE transaction.

    A flat list of formats rather than decor-then-formats: the attach sheet
    walks one decor at a time, but a batch that spans decors is still one save,
    and a format id already identifies its decor.
    """

    items: list[BranchMaterialAttachItem]


class BranchMaterialPatchRequest(BaseModel):
    """Price only — the format is this row's identity.

    A stale `min_stock` is ignored for the same reason as on the attach item.
    """

    price_tiyin: int | None = None


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
    # The decor is this workshop's own — the Materiallar table badges the row and
    # offers the edit menu on it. Nested `decor.own` says the same thing; this is
    # the flat read the table's row template wants.
    decor_own: bool = False
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


# --------------------------------------------------------------------------- #
# The workshop's own catalog rows
# --------------------------------------------------------------------------- #


class WorkshopManufacturerOption(APIModel):
    """One row of the create form's manufacturer combobox."""

    id: uuid.UUID
    name: str
    own: bool


class WorkshopDecorCreateRequest(BaseModel):
    """«Yangi dekor» — one decor and its first sizes, in one save.

    `manufacturer_id` **or** `manufacturer_name`, never both and never neither
    (`manufacturer_required`): the combobox either picked a row or offered
    «+ „Kastamonu“ ni qo'shish», and a payload carrying both would make the
    server choose which half of what the operator said to honour.

    There is no `workshop_id`: the owning workshop is the branch's, and a request
    field would be an id one workshop could type to plant a row in another's
    catalog.
    """

    manufacturer_id: uuid.UUID | None = None
    manufacturer_name: str | None = None
    name: str
    code: str | None = None
    has_grain: bool = False
    image_file_id: uuid.UUID | None = None
    # At least one (`decor_formats_required`). A decor with no format is a name
    # nobody can attach anything of, and the form's next step prices these rows.
    formats: list[DecorFormatCreateRequest] = []


class WorkshopDecorPatchRequest(BaseModel):
    """Fix an own decor. Formats are absent on purpose — they stay immutable."""

    manufacturer_id: uuid.UUID | None = None
    manufacturer_name: str | None = None
    code: str | None = None
    name: str | None = None
    has_grain: bool | None = None
    image_file_id: uuid.UUID | None = None


class WorkshopDecorCreateResponse(APIModel):
    """The new decor plus every format it was created with, all active.

    The sheet lands on its price step with exactly these rows ticked, so they
    travel back with the decor rather than costing a second round trip.
    """

    decor: DecorResponse
    formats: list[DecorFormatResponse]
