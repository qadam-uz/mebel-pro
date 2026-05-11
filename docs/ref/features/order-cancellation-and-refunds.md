---
title: Order cancellation & refunds
status: stable
owner: shape
updated: 2026-05-11
order: 40
related:
  - docs/spec/orders.md
  - docs/spec/scope-v1.md
  - docs/ref/entities/sales/order-cancellation.md
  - docs/ref/entities/sales/order-refund.md
  - docs/ref/features/order-fulfillment.md
---

# Order cancellation & refunds

## Problem

Orders fall through — the customer changes their mind, a `pending_payment` order times out, a defect
turns up in production, a delivery goes wrong. Whoever cancels must give a reason, the order must
never just disappear (it goes `cancelled`, and reserved material is released if it can be), and if the
customer had paid, the money owed back must be tracked through to a recorded, bank-referenced refund —
because in v1 the system doesn't move money, it records that the workshop did. Stale pending refunds
need to be visible so they don't get forgotten.

## User stories

- As a **client**, while my order is `new` or `pending_payment`, I want to cancel it with a reason.
- As **staff with `manage_orders`**, I want to cancel an order (with a reason) up to `confirmed`,
  releasing reserved material, and have a refund record created if the customer had paid.
- As the **workshop owner**, I want to force-cancel an order that's already `in_production` / `ready` /
  `in_delivery` in exceptional cases (with a longer reason).
- As **staff with `manage_orders`**, I want a queue of pending refunds, with stale ones flagged, and
  to record a refund (method, amount, mandatory bank reference / receipt note, optional receipt scan).
- As the **workshop owner**, I want to revert a completed refund on a dispute (with a reason).
- As a **client**, I want to see my refunds and their status.

## Requirements

1. **Cancellation eligibility** ([`docs/spec/orders.md`](../../spec/orders.md)):
   `new`/`pending_payment` — client / staff / owner; `confirmed` — staff / owner (not the client);
   `in_production`/`ready`/`in_delivery` — **owner only** (force-cancel, exceptional); `completed`
   /`cancelled` — nobody.
2. `cancel-my-order` (client) / `cancel-order` (staff/owner) / `force-cancel-order` (owner, for
   `in_production`+): writes the single `order_cancellation` (who, capacity, mandatory `reason`,
   `is_owner_force_cancel` flag, `refund_required` = whether a payment was completed), moves the order
   `→ cancelled`, writes an `order_status_event`. For a `shop` order not yet in production, releases
   the reserved stock (`inventory.release`). If `refund_required`, creates a `pending` `order_refund`
   against the relevant payment for the amount owed. Audited; client + workshop staff notified.
3. **Refund lifecycle is manual** ([`docs/spec/scope-v1.md`](../../spec/scope-v1.md)): the system creates the `pending` refund (on cancel, or on a down-modify difference — [`docs/ref/features/order-modification.md`](order-modification.md)); the workshop moves the money offline; staff record it.
4. `list-pending-refunds` (owner; staff with `manage_orders` for their branches): the pending refunds,
   filterable by branch, stale-only, min amount; sorted oldest-first; stale = `pending` for > 7 days
   (also surfaces in the dashboard and a daily notification to the owner).
5. `process-refund` (`manage_orders` on the order's branch, or owner): for a `pending` refund, set
   `method` (`cash` / `bank_transfer` / `payme_manual` / `click_manual` / `other`), `amount` (≤ the
   payment's completed amount; partials allowed, summing to ≤ that amount), a **mandatory `note`**
   (bank reference / receipt id), an optional receipt scan; → refund `completed`, the payment
   `refunded`, `processed_by_user_id` recorded, `completed_at` set; client notified. (Or `failed` if
   the workshop couldn't complete it — rare.)
6. `revert-refund` (**owner only**): for a `completed` refund (a dispute), set it back to `failed`
   with a mandatory reason; audited.
7. Every action audited; status changes write status-change-log rows.

## UX

- **Client** — on the order detail, `new`/`pending_payment` shows a "Cancel" action → a confirm
  dialog with a **mandatory reason** textarea → `cancel-my-order`; on success the status flips to
  `cancelled` and the reason shows on the timeline. A **Refunds** section appears if any refund
  exists: per refund — amount, method (once recorded), status; `pending` shows "Being refunded by the
  workshop — need help?" with a support placeholder.
- **Staff** (`/seh/orders/:id`) — the cancel action per status (see [`docs/ref/features/order-fulfillment.md`](order-fulfillment.md)'s action table): a confirm dialog with a mandatory reason (longer for force-cancel) and a warning when `shop` material is reserved (it'll be released). After a paid order is cancelled, the **Refunds** tab shows the auto-created `pending` refund row with a "Complete refund" action → a modal: method select, amount (defaults to the owed amount, validated), mandatory note (bank ref / receipt), optional receipt-scan upload → `process-refund`; a stale row is highlighted (amber/danger + a "stale" chip, not color alone).
- **Refund queue** (`/seh/refunds`) — table: refund id (short), order #, client, amount, payment ref
  (external_ref + method), days pending, branch, action menu ("Complete refund" → the same modal).
  Toolbar: stale-only toggle (with a count badge), branch filter, min-amount filter, sorted
  oldest-first. Owner-only: a "Revert refund" action on `completed` refunds (in the order detail's
  Refunds tab) → a dialog with a mandatory reason. Empty: "No pending refunds."
- States: list/detail loading/empty/error; the confirm and process modals show a busy state and end
  in success or a recoverable error; the optimistic-lock conflict on cancel surfaces as "this order
  changed — refresh and retry"; no infinite spinners.
- Accessibility: the reason textareas are required and labelled; destructive/danger styling on cancel,
  force-cancel, and revert, each naming the consequence; the stale flag is chip + color, not color
  alone; modal focus management; the first invalid field gets focus on a failed submit.

Shared components (confirm-with-reason, data table, filter bar, file uploader, status badge): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/sales/order-cancellation.md`](../entities/sales/order-cancellation.md) — the one cancel event per order.
- [`docs/ref/entities/sales/order-refund.md`](../entities/sales/order-refund.md) — created `pending`, processed `completed`/`failed`, reverted.
- [`docs/ref/entities/sales/order.md`](../entities/sales/order.md) — `→ cancelled`; `cancelled_at`.
- [`docs/ref/entities/sales/order-payment.md`](../entities/sales/order-payment.md) — `→ refunded` on refund completion.
- [`docs/ref/entities/sales/order-status-event.md`](../entities/sales/order-status-event.md) — the cancel transition.
- [`docs/ref/entities/inventory/stock-item.md`](../entities/inventory/stock-item.md) — `release` on cancel before production (`shop`).
- [`docs/ref/entities/support/file.md`](../entities/support/file.md) — refund receipt scan.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md), [`docs/ref/entities/support/notification.md`](../entities/support/notification.md).

## Edge cases

- **Cancelling a `shop` order in production** — no stock release (material already consumed); the
  cancellation records `refund_required` per whether a payment exists.
- **Force-cancelling a `ready`/`in_delivery` order** — owner only; the reason is mandatory and longer;
  the customer's situation (defect, delivery failure) is noted.
- **Partial refunds** — a payment can have several `completed` refunds; their amounts sum to ≤ the
  payment amount; each needs its own note.
- **Refund left `pending` > 7 days** — flagged stale; the dashboard counts it; the owner gets a daily
  notification; it doesn't auto-resolve.
- **Reverting a refund** — owner-only; goes to `failed` with a reason; the dispute is now visible in
  audit; what happens next (re-issue, escalate) is offline.
- **An `in_production`+ cancellation by a staff member without owner rights** — `forbidden`; the
  control isn't shown.
- **Concurrent cancel** — optimistic-lock conflict; the second one refreshes.

## Out of scope

- Automatic gateway refunds (Payme/Click reverse webhooks) — v1.1 ([`docs/spec/open-questions.md`](../../spec/open-questions.md) Q4); v1 is manual + recorded.
- A formal dispute-resolution workflow / escalation queue — future; v1 has audit + the owner's revert.
- Complaint / return after `completed` — future.
- Refund of an `own`-material order's cutting service beyond what was paid — same rules apply
  (refund ≤ the payment).

## Open questions

- Making force-cancel / refund-revert a delegable permission — owner: shape — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q12.
