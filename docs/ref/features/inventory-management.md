---
title: Inventory management
status: stable
owner: shape
updated: 2026-05-11
order: 18
related:
  - docs/spec/orders.md
  - docs/ref/entities/inventory/stock-item.md
  - docs/ref/entities/inventory/stock-transaction.md
  - docs/ref/features/material-catalog.md
  - docs/ref/features/order-fulfillment.md
---

# Inventory management

## Problem

A branch's warehouse holds sheets of each material. Some are free; some are committed to confirmed
orders. Staff need to record incoming stock, correct counting errors, and (the owner) move stock
between branches — and the system needs to reserve/consume/release stock automatically as
`shop`-source orders move, atomically, so two confirmations can't double-spend the last sheet.
Today this lives in a notebook; there's no reliable available-vs-reserved view and no audit of
movements.

## User stories

- As a **workshop owner / staff with `manage_inventory`**, I want to record a stock-in (with a
  supplier note / delivery doc) so the on-hand count goes up.
- As the same, I want to adjust a count (with a mandatory reason) to correct an error.
- As the same, I want to see, per material, on-hand / reserved / available / min-stock and a history
  of movements.
- As a **workshop owner**, I want to transfer stock from one branch to another (within the workshop).
- As the system, I want to reserve stock when a `shop` order is confirmed, consume it when the order
  is ready, and release it if the order is cancelled before production — atomically.
- As anyone with `manage_inventory` or the owner, I want a low-stock alert when available ≤ min-stock.

## Requirements

1. `stock-in` (owner or `manage_inventory` on the branch): material_id (in branch), quantity (> 0),
   note? (supplier), receipt file? → `on_hand += qty`; writes a `stock_in` transaction with the actor.
2. `adjust-stock` (same): material_id, signed delta, **mandatory note** (reason) → `on_hand += delta`
   (bounded by invariants — can't go below `reserved` or below 0); writes an `adjust` transaction.
3. `get-branch-stock` / `list-stock-transactions` (owner or `manage_inventory` on the branch; clients
   never see stock numbers): per-material balances + a filterable transaction log (type, date,
   material).
4. `transfer-stock` (**owner only** — not delegable in v1): from_branch, to_branch (both in the
   workshop), material (must exist in both), quantity (≤ source `available`) → `on_hand` down on
   source, up on destination; writes a paired `transfer_out` + `transfer_in` (same `transfer_id`)
   with the actor and a reason note. Reserved stock cannot be transferred.
5. `reserve` / `consume` / `release` (system, no actor — driven by [`docs/spec/orders.md`](../../spec/orders.md)):
   - `reserve(order_id, items)` on `order → confirmed` for a `shop` order — atomic, row-lock the
     stock rows; `available` must cover it or it fails `insufficient_stock` (caveat: on a
     money-already-moved confirm the failure doesn't roll the order back — see [`docs/spec/orders.md`](../../spec/orders.md)). `reserved += qty`.
   - `consume(order_id)` on `order → ready` — `reserved -= qty`, `on_hand -= qty`.
   - `release(order_id)` on cancel of a `shop` order before production — `reserved -= qty`.
   - Each writes a `reserve` / `consume` / `release` transaction with the `order_id`.
6. Low-stock: when `available ≤ min_stock` after any change, a notification fires to the branch's
   `manage_inventory` grantees + the owner; the daily summary repeats it.
7. Every mutating action writes an audit-log row.

## UX

In the **seh app**, under a branch's **Stock** tab (and an owner-wide view with a branch filter):

- **Current stock** tab — table: material (name + image), on-hand, available, reserved, min-stock,
  last updated; low-stock rows highlighted (danger color + a "low" chip, not color alone). Row click
  → drawer with the last ~30 transactions for that material. Per-row "Record stock-in" → modal
  (qty, supplier note, delivery-doc upload). Set min-stock inline (or in the material form).
- **Transactions** tab — full log: type (`stock_in` / `reserve` / `release` / `consume` /
  `transfer_in` / `transfer_out` / `adjust`), quantity (signed), balance-after, order link (for
  reserve/consume/release), actor, note, date; filters: type, date range, material. Read-only.
- **Transfer** tab — **owner only** (staff see the tab disabled with a "owner only" tooltip): form —
  from-branch, to-branch, material, quantity (validated ≤ source available), reason note. Confirms
  the move.
- **Adjust stock** action — modal with signed delta + a required reason; warns it changes the
  recorded count.
- States: loading (skeletons), empty (no materials → "add materials first" link), error (`trace_id`),
  "insufficient stock" surfaced on a failed transfer/adjust.
- Accessibility: low-stock is signalled by chip + color, not color alone; the transfer tab's
  disabled state has an explanatory tooltip; modals manage focus.

Shared patterns (data table, drawer, filtered log, file uploader, confirm-with-reason): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/inventory/stock-item.md`](../entities/inventory/stock-item.md) — balances mutated by every operation.
- [`docs/ref/entities/inventory/stock-transaction.md`](../entities/inventory/stock-transaction.md) — one row per change.
- [`docs/ref/entities/catalog/material.md`](../entities/catalog/material.md) — the material a stock item tracks; `min_stock` may be edited via the material form.
- [`docs/ref/entities/sales/order.md`](../entities/sales/order.md) — drives reserve/consume/release.
- [`docs/ref/entities/support/file.md`](../entities/support/file.md) — delivery doc on stock-in.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/notification.md`](../entities/support/notification.md).

## Edge cases

- **Reserve loses a race for the last sheet** — the second confirmation gets `insufficient_stock`;
  because cutting doesn't check stock, this is a real (if rare) case — the order stays `new` (or, if
  money already moved, `confirmed` with `reserve_status = failed` and an owner alert). See [`docs/spec/orders.md`](../../spec/orders.md).
- **Cancel a `shop` order in production** — material was already consumed; no release; the loss is
  the workshop's.
- **Adjust below `reserved`** — rejected (can't make committed stock disappear).
- **Transfer reserved stock** — rejected (only `available` can move).
- **Stock-in for an `inactive` material** — allowed (the material still exists); it just won't be
  offered to clients.
- **`own`-source order** — no inventory interaction at all.

## Out of scope

- Stock-aware cutting (the optimizer planning around what's on hand) — v1 doesn't check stock at
  cutting time ([`docs/spec/cutting.md`](../../spec/cutting.md), [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q7).
- Auto purchase orders on low stock — future.
- Offcut / remnant tracking — future.
- Barcode / QR scanning for stock-in/out — future.
- Delegating `transfer-stock` to staff — owner-only in v1.

## Open questions

- Should `transfer-stock` become a delegable permission? — owner: shape — see [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q1/Q12.
