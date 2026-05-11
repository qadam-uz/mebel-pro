---
title: Orders
status: stable
owner: shape
updated: 2026-05-11
order: 76
related:
  - docs/spec/cutting.md
  - docs/spec/access.md
  - docs/spec/architecture.md
  - docs/spec/scope-v1.md
  - docs/ref/entities/sales/order.md
  - docs/ref/features/order-placement.md
  - docs/ref/features/order-fulfillment.md
---

# Orders

The single home for the order lifecycle, pricing, payments, refunds, and the warehouse contract.
Per-feature behaviour and screens are the `ref/features/order-*` docs; the cutting it depends on is
[`docs/spec/cutting.md`](cutting.md); who-may-do-what is [`docs/spec/access.md`](access.md); the
cross-cutting invariants it relies on (integer tiyin, snapshots, append-only history, optimistic
lock, atomic stock) are in [`docs/spec/architecture.md`](architecture.md) → *Data model invariants*.

## What an order is

A **client's request for panels cut to size at a branch** — the header that owns the items,
payments, status history, cancellation, and refunds. Created **only by a client**, **only from a
confirmed cutting draft** (no order without one — the draft becomes `confirmed` and bound on
creation; [`docs/spec/cutting.md`](cutting.md)). It carries a **snapshot** of its pricing and a
reference to its current cutting result. Entity detail: [`docs/ref/entities/sales/order.md`](../ref/entities/sales/order.md) and the other `ref/entities/sales/` pages.

Two axes set at creation:

- **Material source** — `own` (the client brings the material; cutting service only — no stock
  movement) or `shop` (the workshop supplies the material — stock reserved / consumed / released as
  the order moves).
- **Delivery type** — `pickup` (free) or `delivery` (a **fixed fee** from a static zone resolved
  from `(branch, lat, lng)` — workshop-entered, no geocoder in v1; out-of-zone ⇒ the client must
  switch to pickup or another branch).

## The state machine

States: `new` → `pending_payment` → `confirmed` → `in_production` → `ready` → (`in_delivery`) →
`completed`; any pre-`completed` state can reach `cancelled` per the matrix below.

```
[client places order]──▶ new
   new ──(client redirected to a gateway, v1.1)──▶ pending_payment
   new ──(staff record a covering payment)─────────▶ confirmed
   new ──(owner/staff approve pay-later + reason)──▶ confirmed
   new ──(client/staff/owner cancel + reason)──────▶ cancelled
   pending_payment ──(payment confirmed)───────────▶ confirmed
   pending_payment ──(payment failed/timeout)──────▶ new
   pending_payment ──(BNPL rejected, v1.1)─────────▶ cancelled
   pending_payment ──(cancel + reason)─────────────▶ cancelled
   confirmed ──(staff start production)────────────▶ in_production   [+ reserve stock if shop]
   confirmed ──(staff/owner cancel + reason)───────▶ cancelled       [release stock if shop & not yet in production; create refund if paid]
   in_production ──(staff mark ready)──────────────▶ ready           [+ consume stock if shop]
   ready ──(staff assign driver; balance recorded)─▶ in_delivery
   ready ──(staff mark picked up; balance recorded)▶ completed
   in_delivery ──(staff mark delivered)────────────▶ completed
   ready / in_delivery ──(owner force-cancel + reason)▶ cancelled    [stock already consumed if shop]
   completed ──(terminal)        cancelled ──(terminal)  [if paid: a pending refund was created]
```

Rules:

- **Every transition is recorded** as an `order_status_event` (who, from→to, reason, metadata) —
  append-only ([`docs/ref/entities/sales/order-status-event.md`](../ref/entities/sales/order-status-event.md)) and mirrored into the audit `status_change_log`.
- **Optimistic locking** on transitions (a `version` column) — concurrent staff edits serialize; the
  loser is told to refresh and retry.
- **Advance-balance gate** — for `advance` orders, the balance payment must be **recorded** before
  `ready → in_delivery` (delivery) or `ready → completed` (pickup).
- A **`completed`** order is terminal — no modify, no cancel (a complaint/return flow is v1.1). An
  order is **never deleted** — it goes `cancelled`.
- **Cancellation requires a reason** (always). Cancelling a *paid* order creates a `pending` refund.

**Cancellation eligibility & refund:**

| Status when cancelled | Who may cancel | Refund |
|---|---|---|
| `new` | client / staff / owner | no payment yet → none |
| `pending_payment` | client / staff / owner | full refund if a payment was completed |
| `confirmed` | staff / owner (not the client) | full or partial — staff/owner decision; stock released if `shop` and not yet in production |
| `in_production` | **owner only** (force-cancel, exceptional) | partial — material is cut; cost stays with the client |
| `ready` | **owner only** (force-cancel, exceptional) | full refund or rework — product defect |
| `in_delivery` | **owner only** (force-cancel, exceptional) | negotiated |
| `completed` | nobody | — |

Force-cancel of an `in_production`+ order, and reverting a completed refund, are **owner-only**
(carve-outs of `manage_orders` — [`docs/spec/access.md`](access.md)); the owner force-cancel takes a
longer mandatory reason.

## Pricing

The system computes everything; clients and staff never type a price — the **discount is the only
human input**, and it requires a reason. Money is **integer tiyin** throughout (1 UZS = 100 tiyin);
the frontend converts for display only. Per-branch pricing setup is [`docs/ref/features/branch-pricing.md`](../ref/features/branch-pricing.md); the entity is [`docs/ref/entities/catalog/branch-pricing.md`](../ref/entities/catalog/branch-pricing.md).

| Component | When | Source |
|---|---|---|
| Cutting service | always | the branch's cutting model — `per_sheet` (× sheets used) or `per_cut` (× cut count) — applied to the cutting result's metrics |
| Materials | `shop` source only | Σ (the material's snapshot price per sheet × sheets attributable to it), from the cutting result |
| Edge banding | parts with banding | Σ (edge length at thickness × the branch's edge-banding rate for that thickness), from the cutting result's `edge_length_by_thickness` |
| Delivery fee | `delivery` only | the static zone fee resolved from `(branch, lat, lng)` |
| Discount | when staff add one | percent or fixed sum; subtracted; **reason + the staff user id recorded** (audited); no enforced cap in v1 — the reason + audit + a "has discount" flag are the control |

**Total = cutting + materials + edge banding + delivery fee − discount.**

- **Snapshot at creation/re-pricing.** When the order is created (or re-priced on modify), every
  component value, the material details + the unit prices used, and the cutting-result reference are
  **frozen** onto the order/order-items; later changes to the catalog, the branch pricing, or the
  delivery zones do **not** reach existing orders. (Why → [`docs/spec/architecture.md`](architecture.md) → *Data model invariants*.)
- **Recalculation on modify** (below) recomputes against the *current* rates → a fresh snapshot →
  the payment difference handled as described under *Cancellation & refunds → recording payments*.
- **Operational setup gaps fail loudly** — if the branch has no cutting model set, or no
  edge-banding rate for a thickness a part uses, order pricing fails with a clear error (the owner
  must fix it; the client can't work around it).

## Modification

Allowed fields shrink as the order advances ([`docs/ref/features/order-modification.md`](../ref/features/order-modification.md)):

| Status | Modifiable by |
|---|---|
| `new` | client & staff — items, delivery type, delivery address, note |
| `pending_payment` | staff — items, delivery type; client — delivery address, note |
| `confirmed` | staff — items (limited), delivery type, delivery address, note |
| `in_production` | staff — delivery address, note |
| `ready` and later | staff — delivery address (before dispatch), note |

Anything outside the matrix → `order_not_modifiable`. A **modify-preview** (dry-run) returns
`pricing_before` / `pricing_after` / `requires_additional_payment` / `refund_amount` without
persisting — for the confirmation dialog. Applying a modify: if **items changed**, re-run
`cutting.optimize` → a new `draft` cutting result → bind it (`→ confirmed`) and **invalidate** the
old one ([`docs/spec/cutting.md`](cutting.md)), rebuild the `order_item`s, re-price against current
rates → a fresh snapshot; if **delivery type/address changed**, re-resolve the zone + fee. Then:
price **up** on an already-paid order → it returns to `pending_payment` for the difference; price
**down** → a difference `pending` refund is created; unchanged → no payment side-effect.

## Cancellation & refunds

Cancelling a paid order (or down-modifying one) creates a **`pending` refund** against the relevant
payment for the amount owed; for a `shop` order cancelled before production, the reserved stock is
released in the same operation; the single `order_cancellation` row records who, in what capacity,
the mandatory reason, whether `is_owner_force_cancel`, and `refund_required`. Entities:
[`docs/ref/entities/sales/order-cancellation.md`](../ref/entities/sales/order-cancellation.md), [`docs/ref/entities/sales/order-refund.md`](../ref/entities/sales/order-refund.md).

**Refunds are manual in v1** (the *why* — gateways/auto-refund deferred — is in [`docs/spec/scope-v1.md`](scope-v1.md)): the system creates the `pending` refund; the workshop moves the money **offline** (bank / cash); staff **record** it — method (`cash` / `bank_transfer` / `payme_manual` / `click_manual` / `other`), amount (≤ the payment's completed amount; partials allowed, summing to ≤ that amount), a **mandatory `note`** (bank reference / receipt id), an optional receipt scan → the refund goes `completed`, the payment `refunded`, `processed_by_user_id` recorded, the client notified. The **owner** can **revert** a completed refund on dispute (exceptional, audited → `failed` with a reason). A `pending` refund older than **7 days** is flagged stale (dashboard + a daily owner notification).

### Recording payments (v1)

There is **no payment gateway in v1** — no redirect, no `initiate-payment` flow, no automatic
refund (the *why*, and the v1.1 plan, are in [`docs/spec/scope-v1.md`](scope-v1.md)). Instead:

- Workshop staff (`manage_orders` on the branch, or owner) **record** payments the client made at
  the counter — type `full` / `advance` / `balance`, method `cash` / `bank_transfer`, amount
  (validated ≤ the order's outstanding), optional receipt scan; the recording user is logged
  (`received_by_user_id`). Recording a payment that **covers** the order (or the advance)
  transitions it `→ confirmed`. Entity: [`docs/ref/entities/sales/order-payment.md`](../ref/entities/sales/order-payment.md).
- The owner can approve **pay-later** for a trusted customer — mandatory reason → `→ confirmed`
  without a payment (the reason + audit are the control). The client pays before handover (recorded
  as a payment); if they never do, staff cancel the order (`reason = no_payment`) — for `shop`, the
  material is already consumed (no release), the loss is the workshop's, surfaced as a dispute the
  owner can review.
- **Stock on confirm:** for a `shop` order, `inventory.reserve` runs atomically on `→ confirmed`. If
  the payment **already moved** (a recorded `completed` payment) and the reserve fails, the order
  stays `confirmed` with `reserve_status = failed` and the owner is alerted — no rollback after
  money moved (manual resolution: retry, or refund + cancel). If it's a **no-money** confirm
  (pay-later, or recording a payment whose unit-of-work hasn't committed yet), a reserve failure
  rolls the whole thing back with `insufficient_stock`. (The v1.1 gateway path will keep this
  shape — `pending_payment` → an idempotent signed webhook → `confirmed`; the `reserve_status` field
  and the `pending_payment` state are the seams.)

## Warehouse contract (`shop` orders)

Driven entirely by the order state machine; the mechanics are in [`docs/ref/features/inventory-management.md`](../ref/features/inventory-management.md) and the entity in [`docs/ref/entities/inventory/stock-item.md`](../ref/entities/inventory/stock-item.md). On `→ confirmed`: `reserve` (atomic; `reserved += qty`; fails `insufficient_stock` if `available` doesn't cover it — see above for the money-already-moved exception). On `→ ready`: `consume` (`reserved -= qty`, `on_hand -= qty`). On cancel **before production**: `release` (`reserved -= qty`). After production starts, the material is consumed — no release. An `own`-source order never touches stock.

## Who does what

- **Client** — creates the order; cancels or modifies it while `new` / `pending_payment`; sees its
  status & timeline; pays (recorded by staff in v1).
- **Workshop staff with `manage_orders` on the order's branch** — records payments; approves
  pay-later¹; moves the order `confirmed → in_production` (optionally assigning a cutter) → `ready`
  → (`in_delivery`, assigning a driver) → `completed`; applies discounts; processes refunds.
- **Workshop owner** — all of the above on every branch, **plus** force-cancel an `in_production`+
  order and revert a completed refund.
- **System** — auto-transitions on a payment recorded (and, v1.1, on a payment webhook); reserves /
  consumes / releases stock; writes status events; runs the overdue/stale notification jobs.

¹ Pay-later approval is owner-discretion in practice but covered by `manage_orders` in v1, with the
mandatory reason as the control — see [`docs/spec/access.md`](access.md) and [`docs/spec/open-questions.md`](open-questions.md) Q12. Assigned cutters/drivers must belong to the order's branch.

## Edge cases & failure paths

- **Stock reserve fails on a money-already-moved confirm** → order stays `confirmed`,
  `reserve_status = failed`, owner alerted; on a no-money confirm → whole UOW rolls back,
  `insufficient_stock`. (Rare — cutting doesn't check stock, so a race is possible.)
- **Cutting result invalidated mid-flow** (concurrent modify) → the detail shows the prior result
  with a note; the order's bound result is always a single current one.
- **Out-of-zone delivery address at modify time** → modify rejected for delivery; switch to pickup.
- **Pay-later order unpaid past the handover deadline** → staff cancel it (`reason = no_payment`);
  for `shop`, consumed material is the workshop's loss; owner can review.
- **Concurrent staff transitions** → optimistic-lock conflict → the second one refreshes and retries.
- **Branch goes `inactive` while orders are open** → those orders complete normally; the branch just
  accepts no new orders.
- **Branch pricing incomplete** → order creation fails at pricing; the seh app flags the branch.

## See also

- [`docs/spec/cutting.md`](cutting.md) — the cutting-result lifecycle the order depends on; the immutability invariant.
- [`docs/spec/access.md`](access.md) — who may do which transition; the manage_orders carve-outs.
- [`docs/spec/scope-v1.md`](scope-v1.md) — why payments & refunds are manual in v1; the v1.1 gateway plan.
- [`docs/spec/architecture.md`](architecture.md) — the data-model invariants (tiyin, snapshots, append-only, optimistic lock, atomic stock).
- [`docs/ref/entities/sales/`](../ref/entities/sales/), [`docs/ref/entities/inventory/stock-item.md`](../ref/entities/inventory/stock-item.md), [`docs/ref/entities/cutting/cutting-result.md`](../ref/entities/cutting/cutting-result.md).
- [`docs/ref/features/order-placement.md`](../ref/features/order-placement.md), [`docs/ref/features/order-fulfillment.md`](../ref/features/order-fulfillment.md), [`docs/ref/features/order-modification.md`](../ref/features/order-modification.md), [`docs/ref/features/order-cancellation-and-refunds.md`](../ref/features/order-cancellation-and-refunds.md).
