---
title: Inventory
status: draft
owner: shape
updated: 2026-08-20
order: 30
---

# Inventory

A branch's warehouse balance per material, the append-only transaction log, and the
suppliers stock arrives from. There is **no reservation** in v1: the order state machine
**consumes** stock as production completes and a revert **restores** it — the contract is in
[`orders.md`](../features/orders.md) → *The stock seam*.

## Stock item

A branch's balance for one **branch material** — one platform format the branch carries
([`catalog.md`](catalog.md#branch-material)) — as a single on-hand quantity in that
material's stock unit (sheet count for a panel-shaped format, integer millimetres for
`kromka`) and a low-stock threshold in the same unit. The UI displays tape balances as
metres. One per branch material, so 16 mm and 18 mm of the same decor are separate rows.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `branch_material_id` | UUID | required; unique — one stock row per branch material. Kept alongside `branch_id` because every inventory read is branch-scoped |
| `on_hand` | int | the branch's book balance for the material, in its stock unit; **may be negative** — see below |
| `updated_at` | timestamp | |

There is deliberately **no `min_stock` here**. The low-stock threshold is a property of
what the branch carries, so it lives once on
[`branch_material.min_stock`](catalog.md#branch-material) and every reader joins to it.
It used to be mirrored onto this row so the low-stock filter could be a single-table
predicate, kept in step by an explicit sync call — which is how two copies drift: a write
path that forgets the call leaves the alert comparing against a stale number, silently.
`stock_item` is only the balance.

Operations (all atomic; the row is locked `FOR UPDATE` for the duration):

- `stock_in(qty)`: `on_hand += qty` (warehouseman; from a supplier).
- `stock_in_void(qty)`: `on_hand -= qty` — one per line of a voided supplier invoice; **not**
  bounded at 0.
- `adjust(delta)`: `on_hand += delta` (stock-take / write-off; a *decrease* is bounded ≥ 0;
  reason note required).
- `consume(qty)`: `on_hand -= qty` — system, driven by the order state machine; **not**
  bounded at 0.
- `restore(qty)`: `on_hand += qty` — system, an operator revert of a consumed step.

**A negative balance is legal, and only the two system-driven subtractions —
`consume` and `stock_in_void` — can create one.** `consume` records
material that physically already moved: if a worker cut 20 panels and only 5 were ever
booked in, the branch *is* at −15, and that is a true statement about the books. Refusing
the consume would block a worker over bookkeeping, and skipping it would leave stock
permanently too high — silently wrong inventory is the worse failure. The state is
self-healing: recording the missing arrival (+20) lands the balance at 5 with no manual
correction. `stock_in_void` is the same argument from the other end: the paper was wrong, but
the goods either never arrived or have already left, so refusing the reversal would leave the
books permanently too high. Every human-facing path that *lowers* a balance keeps the ≥ 0
guard — a typed stock-out that would go negative is almost certainly a typo. Movements that
*raise* a balance are always allowed, so a revert works from below zero too.

**`on_hand == Σ quantity` over the item's transactions, always.** Every operation above only
*appends*, where maintaining the balance by delta arithmetic is correct and cheap. Editing a
supplier invoice's lines is the one path that rewrites movements which already have later
movements behind them, and no delta can repair the `balance_after` snapshots those later rows
carry — so that path **replays the chain** instead: read the item's transactions in
`(created_at, id)` order, run the sum, rewrite every `balance_after`, land `on_hand` on the
total. A voided invoice's `stock_in` rows are not skipped, because its `stock_in_void` rows
cancel them. The replay is what promotes this invariant from true-by-construction to enforced;
it may land the balance negative, on the same argument as `consume`.

Invariants: `branch_material_id` unique; stock changes only via the inventory
module's operations (never raw SQL from elsewhere); `consume` / `restore` carry the
`order_id` and no actor (system); `stock_in` / `stock_in_void` / `adjust` carry an actor.
**Low stock raises no notification** — it is a state on the row, read by the Ombor list and
its filter, and the alert that used to fire on every movement past the threshold was removed
as noise (QAD-182). A row is low when `on_hand < 0`, **or** when the branch set a real
threshold and the balance reached it (`branch_material.min_stock > 0 AND on_hand ≤
min_stock`). A `min_stock` of `0` means monitoring is **off**: attaching a format mints a
zero-balance row, so the unconditional `on_hand ≤ min_stock` marked every never-stocked row
low and the warning stopped meaning anything. Going **negative**
is a discrete event rather than a level, so a `consume` or a `stock_in_void` that leaves
`on_hand` below zero fires a negative-balance notification to the branch's `manage_inventory`
grantees and the owner. The verify-time "projected balance" warning
([`catalog-inventory.md`](../features/catalog-inventory.md)) is a read-time computation,
not a stored field.

Edge `consume` / `restore` is keyed by **kromka branch material id** (not by thickness): an
`edge_banding → ready` transition fires one `consume` per `shop` edge material that the
order's `edge_length_snapshot` carries, each for the millimetres of that exact format. A
revert fires one `restore` per material, mirroring the consume.

## Stock transaction

One audit row for one change to a stock item. Append-only.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `stock_item_id` | UUID | required |
| `type` | enum | `stock_in` / `stock_in_void` / `consume` / `restore` / `adjust` |
| `quantity` | int | signed change, non-zero, in the branch material's stock unit |
| `balance_after` | int | `on_hand` after the change; may be negative on a `consume` row |
| `unit_price_tiyin` | bigint? | purchase price per display unit (per panel / per metre), integer tiyin, ≥ 0; `stock_in` only, null otherwise |
| `total_price_tiyin` | bigint? | authoritative purchase total for the row; panels `quantity × unit price`, edges `quantity_mm × unit price // 1000` (the sale-side per-metre mirror); `stock_in` only |
| `order_id` | UUID? | for `consume` / `restore`; null otherwise |
| `supplier_id` | UUID? | for `stock_in`; null otherwise |
| `invoice_id` | UUID? | the arrival document this row belongs to; `stock_in` / `stock_in_void` only (DB CHECK) |
| `actor_user_id` | UUID? | for `stock_in` / `stock_in_void` / `adjust`; null when the system did it (`consume` / `restore`) |
| `note` | text? | supplier note, adjustment reason (required for `adjust`) |
| `created_at` | timestamp | |

Invariants: matches the change applied in the same atomic operation; `consume` / `restore`
carry an `order_id` and no `actor_user_id`; `stock_in` carries a `supplier_id`, an
`actor_user_id`, and a purchase price (rows recorded before pricing shipped stay unpriced —
they are valid history, not backfilled); only `stock_in` rows ever carry a price (DB CHECK);
`adjust` requires a `note` and never carries money — a stock-take fixes quantity, nothing else;
never updated or deleted; every `stock_in` the platform records belongs to exactly one
**supplier invoice** (below). A `stock_in_void` row is the negative of exactly one `stock_in`
row on a voided invoice, carries **no** price and **no** note — the reason lives once, on the
invoice — and is never itself reversed. There is no stored "latest price" anywhere: the
arrival form's prefill is derived from this ledger at read time, skipping rows whose invoice is
voided ([`catalog-inventory.md`](../features/catalog-inventory.md)).

## Supplier invoice

One arrival document — the grain a workshop accountant negotiates in. A supplier quotes a
total for the whole faktura, discount included, so summing raw stock-in line prices can never
reproduce the number on the supplier's paper. The invoice groups the lines and carries the
document-level discount and surcharge, and the payable side of the supplier balance folds over
`total_tiyin` rather than over line prices — which is what makes the two agree.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `branch_id` | UUID | required — stock is per-branch, so one invoice is always one branch |
| `supplier_id` | UUID? | null only for historical arrivals that never had one |
| `invoice_no` | text | `K-0008` — `K-` + 4-digit sequence, unique per workshop, no yearly reset |
| `invoice_date` | date | defaults to today, editable, never in the future |
| `subtotal_tiyin` | bigint | sum of the line totals, ≥ 0 |
| `discount_tiyin` | bigint | ≥ 0 and ≤ `subtotal_tiyin` (DB CHECK); always 0 on anything entered now |
| `surcharge_tiyin` | bigint | ≥ 0 (DB CHECK); always 0 on anything entered now |
| `total_tiyin` | bigint | stored, `= subtotal − discount + surcharge` (DB CHECK) |
| `note` | text? | legacy only — no UI writes one, and the edit operation refuses it |
| `status` | enum | `recorded` / `voided` — the finance `LedgerStatus`, same shape as an [expense](finance.md#expense) |
| `voided_reason` | text? | required when voiding, null while recorded |
| `recorded_by_user_id` | UUID | the `manage_inventory` user who entered it |
| `voided_by_user_id` | UUID? | who voided it |
| `voided_at` | timestamp? | when |
| `created_at` / `updated_at` | timestamp | |

**States.** `recorded` on creation. `recorded → voided` is the only transition, one-way: a
voided document is never reinstated (the corrected arrival is a *new* invoice with its own
`K-…`), and nothing is ever deleted.

Invariants: the invoice and every stock-in line on it are written in one transaction — a
failure on any line leaves no invoice and no stock movement; `invoice_no` is minted per
workshop (not per branch, because the debt view spans branches) under an advisory lock, so
concurrent arrivals never collide. An invoice with no supplier takes no part in any supplier
balance.

Lifecycle invariants (service-enforced, not DB constraints):

- Only a `recorded` invoice may be **edited** — its header (supplier, date)
  and, optionally, its **whole line set**. Changing the supplier rewrites `supplier_id` on the
  invoice's stock-in rows in the same transaction, so that denormalized column never goes
  stale behind the header.
- A line edit **rewrites the lines wholesale**: the invoice's `stock_in` rows are deleted, the
  submitted set is inserted — keeping the arrival's original `created_at` and its original
  recorder as `actor_user_id`, so a typo fix does not push the delivery to the top of the
  ledger — and every touched stock item (the union of the removed and the added materials) has
  its chain replayed. `subtotal_tiyin` and `total_tiyin` are recomputed from the new lines; the
  untouched `discount_tiyin` / `surcharge_tiyin` are carried through, and an edit that would
  leave a legacy discount above the new subtotal is refused rather than breaking the DB CHECK.
- `discount_tiyin` / `surcharge_tiyin` / `note` are **no longer enterable** — always 0 / null
  on anything created now, and the edit operation refuses them outright. The columns stay so
  the fold arithmetic and legacy rows remain valid
  ([`catalog-inventory.md`](../features/catalog-inventory.md) carries the decision and its
  revisit trigger).
- A void is **blocked while a `recorded` expense references the invoice**. Money and goods
  reverse in separate, explicit steps: a void under a live payment would silently turn that
  payment into a dangling advance against the supplier.
- A void writes exactly one `stock_in_void` row per stock-in line, locking the stock rows in
  `branch_material_id` order (the same discipline creation uses).
- **Only `recorded` invoices feed a derived reader** — the supplier debt fold and its
  statement, the payable-invoice set, the last-price prefill, `Ombor qiymati`, and the
  payment-status filter. A voided invoice still appears in the unfiltered list, with its badge.

Discount and surcharge mirror the order's ([`sales.md`](sales.md)) — same non-negative and cap
constraints, same stored-total check — but deliberately carry **no reason or approver**: on an
order staff *grant* a concession and it needs an audit trail, here they would only transcribe
what the supplier already wrote. Nothing writes them today (above); the constraints stand so a
legacy row and the fold arithmetic stay valid.

**Payment status** — `unpaid` / `partial` / `paid` — is derived at read time from the
**recorded** expenses booked against the invoice, never stored: it is the same subtraction as
the supplier balance, one grain finer. Reading one invoice also returns its linked payments —
voided ones included, because a disputed document is read with its whole story.

## Supplier

Where a branch's stock came from — a lightweight, workshop-scoped record, created on
demand from the arrival form. No purchase-order flow in v1, but the supplier is a **debt
counterparty**: supplier invoices, supplier-linked expenses, and signed adjustments fold
into a derived balance ([`finance.md`](../features/finance.md) → *Debts*). A supplier is
the workshop's buying counterparty; the decor's **manufacturer**
([`catalog.md`](catalog.md#manufacturer)) is who made it — distinct concepts (a single supplier may
carry materials from several manufacturers, and vice versa).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `name` | text | required |
| `phone` | text? | optional |
| `note` | text? | legacy only — no UI writes one, and the edit operation refuses it |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_by_user_id` | UUID | the `manage_inventory` user who added it |
| `created_at` / `updated_at` | timestamp | |

Invariants: `name` required; workshop-scoped (a supplier belongs to one workshop); created
by a user with `manage_inventory`; never deleted (deactivated if unused).

## Next

- [`catalog-inventory.md`](../features/catalog-inventory.md) — stock-in, adjust,
  the projected-balance warning, and the order seam mechanics.
- [`sales.md`](sales.md) — the order whose state machine consumes and restores stock.
