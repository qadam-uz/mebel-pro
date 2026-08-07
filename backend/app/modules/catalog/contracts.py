"""Stable catalog contracts."""

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
