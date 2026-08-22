"""Stable inventory contracts."""

from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement

from app.modules.catalog.contracts import BranchMaterial
from app.modules.inventory.models import StockItem, StockTransaction, Supplier, SupplierInvoice


def low_stock_condition() -> ColumnElement[bool]:
    """ "Is this material running out?" in SQL, over `StockItem` joined to `BranchMaterial`.

    The single home for the predicate, because it is asked from both sides of
    the branch material: Ombor's «Kam qolgan materiallar» reads it off the stock
    list, and the catalog's own chip reads it off the material list — the screen
    where the threshold behind it is set. Two copies would drift the moment one
    of the two arms was reconsidered.

    Kept in `contracts` rather than `inventory.service` so the catalog can ask it
    without importing the inventory use cases (which import the catalog).

    Mirrors `inventory.service.is_low_stock`, which answers the same question for
    one already-loaded row. `min_stock = 0` means monitoring is off; the
    `on_hand < 0` arm is independent of it, because a negative balance is an
    unrecorded arrival (QAD-150) and has to stay visible either way.
    """

    return or_(
        StockItem.on_hand < 0,
        and_(BranchMaterial.min_stock > 0, StockItem.on_hand <= BranchMaterial.min_stock),
    )


__all__ = [
    "StockItem",
    "StockTransaction",
    "Supplier",
    "SupplierInvoice",
    "low_stock_condition",
]
