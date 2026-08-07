"""Catalog and branch material API schemas.

Two surfaces, deliberately disjoint:

- **Platform (dekorlar)** — identity only. No thickness, no size, no price: a
  platform operator cannot know what formats a given workshop's supplier sells.
- **Workshop (branch materials)** — a dekor in one concrete format, with the
  branch's own price and reorder threshold.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import DekorType, MaterialStatus
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


class DekorCreateRequest(BaseModel):
    manufacturer_id: uuid.UUID
    tur: DekorType
    kod: str | None = None
    nomi: str
    tolali: bool = False
    image_file_id: uuid.UUID | None = None


class DekorPatchRequest(BaseModel):
    manufacturer_id: uuid.UUID | None = None
    tur: DekorType | None = None
    kod: str | None = None
    nomi: str | None = None
    tolali: bool | None = None
    image_file_id: uuid.UUID | None = None


class DekorResponse(APIModel):
    id: uuid.UUID
    manufacturer_id: uuid.UUID
    manufacturer_name: str
    tur: DekorType
    kod: str | None
    nomi: str
    tolali: bool
    image_file_id: uuid.UUID | None
    holat: MaterialStatus
    # There is no stored name any more: the display string is composed from the
    # identity fields by app/core/material_label.py so every surface (admin,
    # picker, PDF, order history) reads the same shape.
    label: str
    # AB-22: how many distinct branches carry any format of this dekor. Populated
    # on the platform list; 0 on responses that don't compute it.
    branch_usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class BranchMaterialFormatInput(BaseModel):
    """One (thickness + size) combination of a dekor a branch wants to carry.

    Panel-shaped dekorlar carry `uzunlik_mm`/`eni_mm`; kromka carries
    `kromka_eni_mm`. Which pair is required follows the dekor's `tur` and is
    enforced by the service layer — the DB cannot see `tur` from here.
    """

    qalinlik_mm: Decimal
    uzunlik_mm: int | None = None
    eni_mm: int | None = None
    kromka_eni_mm: int | None = None
    # Both optional: a branch routinely registers its whole format list before it
    # knows prices. 0 means "not priced yet" and hides the row from clients.
    price_tiyin: int = 0
    min_stock: int = 0


class BranchMaterialAttachRequest(BaseModel):
    """Attach one dekor in one or more formats — all in a single transaction."""

    dekor_id: uuid.UUID
    formats: list[BranchMaterialFormatInput]


class BranchMaterialFormatKey(APIModel):
    """Identifies a format within a (branch, dekor) pair."""

    qalinlik_mm: Decimal
    uzunlik_mm: int | None
    eni_mm: int | None
    kromka_eni_mm: int | None


class BranchMaterialPatchRequest(BaseModel):
    qalinlik_mm: Decimal | None = None
    uzunlik_mm: int | None = None
    eni_mm: int | None = None
    kromka_eni_mm: int | None = None
    price_tiyin: int | None = None
    min_stock: int | None = None


class BranchMaterialResponse(APIModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    dekor_id: uuid.UUID
    dekor: DekorResponse
    qalinlik_mm: Decimal
    uzunlik_mm: int | None
    eni_mm: int | None
    kromka_eni_mm: int | None
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
    # Formats a concurrent attach already registered for this branch+dekor. The
    # picker shows what is already carried, so a duplicate here is a race, not
    # user error — skipped, not rejected.
    skipped: list[BranchMaterialFormatKey]


class BranchCatalogDekorOption(APIModel):
    dekor: DekorResponse
    # How many formats of this dekor the branch already carries. A dekor is never
    # hidden from the picker: carrying 18 mm does not stop you adding 16 mm.
    carried_format_count: int


class BranchCatalogOptionsPage(APIModel):
    """QAD-159: the attach picker needs an honest `Filtrdagi hammasi (N)` count, so
    this endpoint breaks the house bare-list convention and returns the page plus
    the total number of dekorlar matching the same filters."""

    items: list[BranchCatalogDekorOption]
    total: int


class BranchCatalogManufacturerOption(APIModel):
    id: uuid.UUID
    name: str


class BranchCatalogFiltersResponse(APIModel):
    """Facet values for the attach picker's dropdowns.

    Manufacturers only. Thickness used to be a facet here because it was a
    platform-catalog fact; it is now a per-branch format the operator types in,
    so there is nothing to enumerate. `tur` is a fixed enum the client renders
    without asking.
    """

    manufacturers: list[BranchCatalogManufacturerOption]
