---
title: Stock item
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/catalog/material.md
  - docs/ref/entities/inventory/stock-transaction.md
  - docs/ref/features/inventory-management.md
  - docs/spec/orders.md
---

# Stock item

## What it is

A branch's warehouse balance for one material — how many sheets are on hand, how many are reserved
for orders, and the low-stock threshold. One stock item per material per branch. The order flow
drives the reserved/on-hand changes automatically (reserve on `confirmed`, consume on `ready`,
release on cancel-before-production) for `shop`-source orders; staff drive `stock_in`, `adjust`, and
`transfer`. Every change is recorded as a [stock transaction](stock-transaction.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `branch_id` | UUID | the branch | required; → branch |
| `material_id` | UUID | the material | required; → material in the same branch; `(branch_id, material_id)` unique |
| `on_hand` | int | sheets physically in the warehouse | ≥ 0 |
| `reserved` | int | sheets committed to confirmed orders, not yet consumed | 0 ≤ reserved ≤ on_hand |
| `available` | int | derived: `on_hand − reserved` | ≥ 0 |
| `min_stock` | int | low-stock alert threshold | ≥ 0 |
| `updated_at` | timestamp | | |

## States / lifecycle

No lifecycle states — a balance that goes up and down. A stock item exists for the life of its
material (which is soft-deleted, not removed).

## Invariants

- `0 ≤ reserved ≤ on_hand`; `available = on_hand − reserved` — DB checks / computed.
- `(branch_id, material_id)` unique — DB constraint.
- Reserve/consume/release are **atomic** — the stock row is locked (`FOR UPDATE`) for the duration —
  partial states are impossible — service rule ([`docs/spec/orders.md`](../../../spec/orders.md)).
- `reserve(qty)` fails (`insufficient_stock`) if `qty > available`.
- `consume(qty)`: `reserved −= qty`, `on_hand −= qty`. `release(qty)`: `reserved −= qty` (available
  goes back up). `stock_in(qty)`: `on_hand += qty`. `adjust(delta)`: `on_hand += delta` (may correct
  errors; bounded by invariants). `transfer(qty)`: `on_hand` down on the source, up on the
  destination.
- When `available ≤ min_stock`, a low-stock notification fires to the branch's `manage_inventory`
  grantees + the owner — service rule.
- Stock changes only via the inventory module's operations (never raw SQL from elsewhere) — invariant.

## Relationships

- belongs to → [`docs/ref/entities/workshop/branch.md`](../workshop/branch.md) and [`docs/ref/entities/catalog/material.md`](../catalog/material.md)
- audited by → [`docs/ref/entities/inventory/stock-transaction.md`](stock-transaction.md) (one-to-many)
- driven by (logical) → [`docs/ref/entities/sales/order.md`](../sales/order.md) (reserve/consume/release for `shop` orders)

## Owner

[`docs/ref/features/inventory-management.md`](../../features/inventory-management.md); the reserve/consume/release contract is in [`docs/spec/orders.md`](../../../spec/orders.md).
