"""Public inventory API used by routes and other modules."""

from app.modules.inventory.service import (
    StockRecord,
    TransactionRecord,
    consume_order_stock,
    create_supplier,
    display_unit,
    ensure_stock_item_for_branch_material,
    list_stock,
    list_suppliers,
    list_transactions,
    record_adjustment,
    record_stock_in,
    restore_order_stock,
    set_supplier_status,
    stock_unit,
    sync_stock_item_min_stock,
    update_supplier,
)

__all__ = [
    "StockRecord",
    "TransactionRecord",
    "consume_order_stock",
    "create_supplier",
    "display_unit",
    "ensure_stock_item_for_branch_material",
    "list_stock",
    "list_suppliers",
    "list_transactions",
    "record_adjustment",
    "record_stock_in",
    "restore_order_stock",
    "set_supplier_status",
    "stock_unit",
    "sync_stock_item_min_stock",
    "update_supplier",
]
