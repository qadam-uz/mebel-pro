---
title: Inventory
status: draft
owner: shape
updated: 2026-07-26
order: 30
---

# Inventory

A branch's warehouse balance per material, the append-only transaction log, and the
suppliers stock arrives from. There is **no reservation** in v1: the order state machine
**consumes** stock as production completes and a revert **restores** it — the contract is in
[`orders.md`](../features/orders.md) → *The stock seam*.

## Stock item

A branch's balance for one material — a single on-hand quantity in the material's stock
unit (panel count for a `panel` material, integer millimetres for an `edge`) and a
low-stock threshold in the same unit. The UI displays edge balances as metres. One per
material per branch.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `material_id` | UUID | required; `(branch_id, material_id)` unique |
| `on_hand` | int | the branch's book balance for the material, in its stock unit; **may be negative** — see below |
| `min_stock` | int | low-stock alert threshold in the same unit; ≥ 0 |
| `updated_at` | timestamp | |

Operations (all atomic; the row is locked `FOR UPDATE` for the duration):

- `stock_in(qty)`: `on_hand += qty` (warehouseman; from a supplier).
- `adjust(delta)`: `on_hand += delta` (stock-take / write-off; a *decrease* is bounded ≥ 0;
  reason note required).
- `consume(qty)`: `on_hand -= qty` — system, driven by the order state machine; **not**
  bounded at 0.
- `restore(qty)`: `on_hand += qty` — system, an operator revert of a consumed step.

**A negative balance is legal, and only `consume` can create one.** `consume` records
material that physically already moved: if a worker cut 20 panels and only 5 were ever
booked in, the branch *is* at −15, and that is a true statement about the books. Refusing
the consume would block a worker over bookkeeping, and skipping it would leave stock
permanently too high — silently wrong inventory is the worse failure. The state is
self-healing: recording the missing arrival (+20) lands the balance at 5 with no manual
correction. Every human-facing path that *lowers* a balance keeps the ≥ 0 guard — a typed
stock-out that would go negative is almost certainly a typo. Movements that *raise* a
balance are always allowed, so a revert works from below zero too.

Invariants: `(branch_id, material_id)` unique; stock changes only via the inventory
module's operations (never raw SQL from elsewhere); `consume` / `restore` carry the
`order_id` and no actor (system); `stock_in` / `adjust` carry an actor. When
`on_hand ≤ min_stock` after a change, a low-stock notification fires to the branch's
`manage_inventory` grantees and the owner — a balance that ran *past* the threshold into
negative still qualifies, so the alert never goes quiet. A `consume` that leaves `on_hand`
below zero additionally fires a negative-balance notification to the same recipients.
The verify-time "projected balance" warning
([`catalog-inventory.md`](../features/catalog-inventory.md)) is a read-time computation,
not a stored field.

Edge `consume` / `restore` is keyed by **edge material id** (not by thickness): an
`edge_banding → ready` transition fires one `consume` per `shop` edge material that the
order's `edge_length_snapshot` carries, each for the millimetres of that exact material. A
revert fires one `restore` per material, mirroring the consume.

## Stock transaction

One audit row for one change to a stock item. Append-only.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `stock_item_id` | UUID | required |
| `type` | enum | `stock_in` / `consume` / `restore` / `adjust` |
| `quantity` | int | signed change, non-zero, in the material's stock unit |
| `balance_after` | int | `on_hand` after the change; may be negative on a `consume` row |
| `unit_price_tiyin` | bigint? | purchase price per display unit (per panel / per metre), integer tiyin, ≥ 0; `stock_in` only, null otherwise |
| `total_price_tiyin` | bigint? | authoritative purchase total for the row; panels `quantity × unit price`, edges `quantity_mm × unit price // 1000` (the sale-side per-metre mirror); `stock_in` only |
| `order_id` | UUID? | for `consume` / `restore`; null otherwise |
| `supplier_id` | UUID? | for `stock_in`; null otherwise |
| `actor_user_id` | UUID? | for `stock_in` / `adjust`; null when the system did it (`consume` / `restore`) |
| `note` | text? | supplier note, adjustment reason (required for `adjust`) |
| `created_at` | timestamp | |

Invariants: matches the change applied in the same atomic operation; `consume` / `restore`
carry an `order_id` and no `actor_user_id`; `stock_in` carries a `supplier_id`, an
`actor_user_id`, and a purchase price (rows recorded before pricing shipped stay unpriced —
they are valid history, not backfilled); only `stock_in` rows ever carry a price (DB CHECK);
`adjust` requires a `note` and never carries money — a stock-take fixes quantity, nothing else;
never updated or deleted. There is no stored "latest price" anywhere: the stock-in form's
prefill is derived from this ledger at read time
([`catalog-inventory.md`](../features/catalog-inventory.md)).

## Supplier

Where a branch's stock came from — a lightweight, workshop-scoped record, created on
demand from the stock-in form. No purchase-order flow in v1, but the supplier is a **debt
counterparty**: priced stock-ins, supplier-linked expenses, and signed adjustments fold
into a derived balance ([`finance.md`](../features/finance.md) → *Debts*). A supplier is
the workshop's buying counterparty; the material's **manufacturer**
([`catalog.md`](catalog.md)) is who made it — distinct concepts (a single supplier may
carry materials from several manufacturers, and vice versa).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `name` | text | required |
| `phone` | text? | optional |
| `note` | text? | optional |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_by_user_id` | UUID | the `manage_inventory` user who added it |
| `created_at` / `updated_at` | timestamp | |

Invariants: `name` required; workshop-scoped (a supplier belongs to one workshop); created
by a user with `manage_inventory`; never deleted (deactivated if unused).

## Next

- [`catalog-inventory.md`](../features/catalog-inventory.md) — stock-in, adjust,
  the projected-balance warning, and the order seam mechanics.
- [`sales.md`](sales.md) — the order whose state machine consumes and restores stock.
