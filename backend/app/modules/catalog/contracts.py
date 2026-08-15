"""Stable catalog contracts."""

import uuid

from app.models.enums import DekorType
from app.modules.catalog.models import BranchMaterial, BranchPricing, Dekor, Manufacturer


def is_tape(tur: DekorType) -> bool:
    """True for kromka — the format carries a tape width, no panel dimensions.

    The single home for the panel/tape test. Cutting, inventory and sales all
    branch on it; re-deriving `tur == KROMKA` in each of them is how the old
    `MaterialKind` checks drifted apart.
    """
    return tur.tape_shaped


def is_panel(tur: DekorType) -> bool:
    """True for every non-kromka dekor — the format carries length x width."""
    return tur.panel_shaped


__all__ = [
    "BranchMaterial",
    "BranchPricing",
    "Dekor",
    "DekorType",
    "Manufacturer",
    "is_panel",
    "is_tape",
]

# ── The seeded identity every customer-supplied board points at ──────────────
# Written by migration d4b18e6c07a9 at these exact ids. A board cannot mint its
# own dekor: dekor writes are platform-operator-only, and one dekor per board
# would collide on the name index and grow the admin catalog without bound.
# The migration carries its own copies of these literals on purpose — a frozen
# revision must not import code that can move under it.
CUSTOMER_MANUFACTURER_ID = uuid.UUID("00000000-0000-0000-0000-00000000c001")
CUSTOMER_DEKOR_ID = uuid.UUID("00000000-0000-0000-0000-00000000c002")
