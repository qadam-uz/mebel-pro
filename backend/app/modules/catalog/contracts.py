"""Stable catalog contracts."""

from app.models.enums import DecorType
from app.modules.catalog.models import (
    DECOR_FORMAT_SHAPE_CHECK,
    BranchMaterial,
    BranchPricing,
    Decor,
    DecorFormat,
    Manufacturer,
)


def is_tape(type_: DecorType) -> bool:
    """True for kromka — the format carries a tape width, no panel dimensions.

    The single home for the panel/tape test. Cutting, inventory and sales all
    branch on it; re-deriving `type == KROMKA` in each of them is how the old
    `MaterialKind` checks drifted apart.
    """
    return type_.tape_shaped


def is_panel(type_: DecorType) -> bool:
    """True for every non-kromka format — it carries length x width."""
    return type_.panel_shaped


# The board types whose finished-face count is a product fact rather than a
# constant. Mirrors the `finished_sides` half of the DB shape CHECK.
FINISHED_SIDES_TYPES = frozenset({DecorType.LDSP, DecorType.DSP, DecorType.MDF})


def requires_finished_sides(type_: DecorType) -> bool:
    """True when a format of this type must record how many faces are finished."""
    return type_ in FINISHED_SIDES_TYPES


__all__ = [
    "DECOR_FORMAT_SHAPE_CHECK",
    "FINISHED_SIDES_TYPES",
    "BranchMaterial",
    "BranchPricing",
    "Decor",
    "DecorFormat",
    "DecorType",
    "Manufacturer",
    "is_panel",
    "is_tape",
    "requires_finished_sides",
]
