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


# The *faced* board types — the ones that arrive with a laminate on one or both
# sides, so how many faces are finished is a product fact rather than a constant.
# Narrowed to LDSP + LMDF on 2026-09-08: `dsp` and `mdf` are the bare substrates,
# and asking "1 or 2 faces?" about a raw chipboard sheet was a question with no
# answer — every such row was entered as the meaningless «2». Mirrors the
# `finished_sides` half of the DB shape CHECK; the migration nulled the rows.
FINISHED_SIDES_TYPES = frozenset({DecorType.LDSP, DecorType.LMDF})


def requires_finished_sides(type_: DecorType) -> bool:
    """True when a format of this type must record how many faces are finished.

    False for every other type, and there it is not merely optional: the value
    must be absent (`finished_sides IS NULL`), which is what the CHECK enforces.
    """
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
