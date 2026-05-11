---
title: Order modification
status: stable
owner: shape
updated: 2026-05-11
order: 38
related:
  - docs/spec/orders.md
  - docs/spec/cutting.md
  - docs/ref/entities/sales/order.md
  - docs/ref/features/order-placement.md
  - docs/ref/features/order-fulfillment.md
---

# Order modification

## Problem

Things change after an order is placed — the customer realizes a part should be a different size,
wants more of something, switches from pickup to delivery, or updates the address. How much can change
depends on how far the order has advanced (you can't re-cut parts that are already being cut). When
parts change, the cutting has to be re-optimized and the order re-priced — and the customer (or staff)
needs to see the price difference *before* committing, then have the payment difference handled
cleanly.

## User stories

- As a **client**, while my order is `new` or `pending_payment`, I want to change my parts, delivery
  type, address, or note — and see the new price before I confirm.
- As **staff with `manage_orders`**, I want to modify an order's parts/delivery/note within what the
  order's status allows, with the price difference shown.
- As either, I want a clear outcome when the price changes: pay the extra (the order goes back to
  awaiting payment) or get the difference refunded.

## Requirements

1. **Modifiable fields by status** ([`docs/spec/orders.md`](../../spec/orders.md)):
   - `new` — client & staff: items, delivery type, delivery address, note.
   - `pending_payment` — staff: items, delivery type; client: delivery address, note.
   - `confirmed` — staff only: items (limited), delivery type, delivery address, note.
   - `in_production` — staff only: delivery address, note.
   - `ready` and later — staff only: delivery address (before dispatch), note.
   Anything outside the matrix → `order_not_modifiable`.
2. `modify-order-preview` (the modifying party): same body as the modify, returns `{ pricing_before,
   pricing_after, requires_additional_payment, refund_amount }` **without persisting** — for the
   confirmation dialog. (If items changed, this runs a fresh cutting optimization to compute
   `pricing_after`.)
3. `modify-my-order` (client; `new`/`pending_payment` only) / `modify-order` (staff; per the matrix):
   applies the change. If **items changed**: re-run `cutting.optimize` → a new `draft` cutting result
   → bind it to the order (`→ confirmed`) and **invalidate** the old one ([`docs/spec/cutting.md`](../../spec/cutting.md)); rebuild the `order_item`s; **re-price** against the *current* branch pricing/material prices → a fresh snapshot ([`docs/spec/orders.md`](../../spec/orders.md)). If **delivery type/address changed**: re-resolve the delivery zone + fee. Then:
   - price went **up** and the order had a completed payment → the order returns to `pending_payment`
     (the difference is now outstanding; staff record it when paid).
   - price went **down** and the order had a completed payment → a `pending` `order_refund` for the
     difference is created ([`docs/ref/features/order-cancellation-and-refunds.md`](order-cancellation-and-refunds.md)).
   - price unchanged → no payment side-effect.
   Writes an `order_status_event` if the status changed (e.g. `confirmed → pending_payment`); audited.
4. The modify never bypasses the state machine — it only edits the allowed fields and triggers the
   above; it can't, e.g., un-cancel an order or skip a status.

## UX

- **Client modify** (`/c/orders/:id/modify`) — reuses the **order create wizard** with the order's
  current values prefilled. If the client edits parts, step 1 routes back into the cutting wizard
  (parts prefilled) → on the next optimize a new draft is produced; returning to the modify wizard
  carries that draft. Before submitting, `modify-order-preview` runs and a **confirmation modal**
  shows: "Price changed: was {X} → now {Y}. {You'll need to pay {diff} / We'll refund {diff} / No
  change.} Continue?" Confirm → `modify-my-order`. On `order_not_modifiable` (status moved on) →
  toast + back to detail.
- **Staff modify** (`/seh/orders/:id` → "Modify") — the same wizard, scoped to the fields the order's
  status permits, with the price-diff modal showing "Additional payment needed" / "Refund will be
  created" / "No change". On out-of-zone delivery address → step 2 inline error (the modify is
  rejected for delivery; switch to pickup). On the optimistic-lock conflict → "this order changed —
  refresh and retry".
- After a successful modify that bounced the order to `pending_payment`, the detail header reflects
  it and the "Record payment" action becomes available (staff side); the client's detail shows
  "awaiting the additional payment".
- States: the preview call has a loading state (it runs an optimization for parts changes — within
  the 5 s budget); the wizard validates each step; the diff modal is the commit point.
- Accessibility: the diff modal states the numbers plainly (not color-only); focus moves into it and
  back; the wizard steps are labelled; the "this can't be modified now" path is explained, not just
  errored.

Shared components (`Stepper`, `CuttingLayoutSVG`, sticky summary, confirm-with-diff modal): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/sales/order.md`](../entities/sales/order.md) — fields changed; status possibly bounced; re-priced snapshot.
- [`docs/ref/entities/sales/order-item.md`](../entities/sales/order-item.md) — rebuilt when items change.
- [`docs/ref/entities/cutting/cutting-result.md`](../entities/cutting/cutting-result.md) — old → `invalidated`; new bound.
- [`docs/ref/entities/sales/order-payment.md`](../entities/sales/order-payment.md), [`docs/ref/entities/sales/order-refund.md`](../entities/sales/order-refund.md) — difference payment / refund.
- [`docs/ref/entities/sales/order-status-event.md`](../entities/sales/order-status-event.md) — if the status changed.
- [`docs/ref/entities/catalog/branch-pricing.md`](../entities/catalog/branch-pricing.md), [`docs/ref/entities/catalog/material.md`](../entities/catalog/material.md) — re-read for re-pricing.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md), [`docs/ref/entities/support/notification.md`](../entities/support/notification.md).

## Edge cases

- **Status advanced between opening the modify and submitting** → `order_not_modifiable`; the UI
  refetches and shows what's now allowed (or nothing).
- **Items changed but the new optimization fails** (e.g. a part too large) → the modify is rejected
  with the cutting error; the order is unchanged; fix the parts and retry.
- **Re-price lands exactly equal** → no `pending_payment` bounce, no refund.
- **Delivery address now out of zone** → modify rejected for delivery; switch to pickup.
- **Branch pricing changed since the order was placed** → the modify re-prices at the *current*
  rates (that's the point — the snapshot is refreshed by the modify).
- **Concurrent modifies** → optimistic-lock conflict on the second; refresh and retry.

## Out of scope

- Modifying a `completed` or `cancelled` order — terminal.
- Client-side modify after `confirmed` — staff only past that point.
- Partial fulfilment (cut some parts now, the rest later) — future.
- A standalone "split this order" operation — out.

## Open questions

- A backend modify-preview endpoint is assumed here (`modify-order-preview`); confirmed in scope. No
  open question specific to this feature.
