---
title: Inventory
status: draft
owner: shape
updated: 2026-05-13
order: 30
---

# Inventory

A branch's warehouse balance per material, plus the append-only transaction log that records
every change. The reserve/consume/release contract driven by the order state machine is in
[`orders.md`](../features/orders.md) → *Warehouse contract*.

## Stock item

A branch's balance for one material — on hand, reserved, the low-stock threshold. One stock item
per material per branch. The order flow drives reserved/on-hand changes automatically for
`shop`-source orders; staff drive `stock_in`, `adjust`, and `transfer`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `material_id` | UUID | required; `(branch_id, material_id)` unique |
| `on_hand` | int | sheets physically in the warehouse; ≥ 0 |
| `reserved` | int | sheets committed to confirmed orders, not yet consumed; `0 ≤ reserved ≤ on_hand` |
| `available` | int | derived: `on_hand − reserved` |
| `min_stock` | int | low-stock alert threshold; ≥ 0 |
| `updated_at` | timestamp | |

Invariants: `0 ≤ reserved ≤ on_hand`; `available = on_hand − reserved`; `(branch_id,
material_id)` unique; reserve/consume/release are **atomic** — the row is locked (`FOR UPDATE`)
for the duration; `reserve(qty)` fails (`insufficient_stock`) if `qty > available`. Stock
changes only via the `inventory` module's operations (never raw SQL from elsewhere).

Operations (all atomic):

- `stock_in(qty)`: `on_hand += qty`.
- `adjust(delta)`: `on_hand += delta` (may correct errors; bounded — can't go below `reserved`
  or 0; requires a reason note).
- `reserve(qty)`: `reserved += qty` (rejects if `qty > available`).
- `consume(qty)`: `reserved -= qty`, `on_hand -= qty`.
- `release(qty)`: `reserved -= qty` (available goes back up).
- `transfer(qty)`: `on_hand` down on source, up on destination (paired transactions; owner-only).

When `available ≤ min_stock`, a low-stock notification fires to the branch's `manage_inventory`
grantees + the owner.

## Stock transaction

One audit row for one change to a stock item. Append-only.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `stock_item_id` | UUID | required |
| `type` | enum | `stock_in` / `reserve` / `release` / `consume` / `transfer_in` / `transfer_out` / `adjust` |
| `quantity` | int | signed change in sheets (or in `reserved`, for reserve/release); non-zero |
| `balance_after` | json | snapshot `{ on_hand, reserved, available }` after the change |
| `order_id` | UUID? | for `reserve` / `release` / `consume`; null otherwise |
| `transfer_id` | UUID? | groups the `transfer_out` + `transfer_in` legs of one transfer |
| `actor_user_id` | UUID? | for `stock_in` / `adjust` / `transfer_*`; null when the system did it (reserve/release/consume) |
| `note` | text? | supplier note, transfer reason, adjustment reason (required for `adjust`) |
| `created_at` | timestamp | |

Invariants: matches the change applied in the same atomic operation; `reserve` / `release` /
`consume` carry an `order_id` and no `actor_user_id` (system); `stock_in` / `adjust` /
`transfer_*` carry an `actor_user_id`; the two legs of a transfer share a `transfer_id` and net
to zero across branches; `adjust` requires a `note`; never updated or deleted.
