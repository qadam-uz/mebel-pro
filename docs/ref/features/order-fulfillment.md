---
title: Order fulfillment
status: stable
owner: shape
updated: 2026-05-11
order: 36
related:
  - docs/spec/orders.md
  - docs/spec/access.md
  - docs/ref/entities/sales/order.md
  - docs/ref/entities/sales/order-payment.md
  - docs/ref/features/inventory-management.md
  - docs/ref/features/order-cancellation-and-refunds.md
---

# Order fulfillment

## Problem

Once a customer places an order, the workshop has to run it: confirm it (by recording the payment, or
approving pay-later), put it into production with a cutter assigned, mark it ready, hand it over (pickup
or via a driver), and close it — recording payments along the way, applying a discount when needed.
Today this is whiteboards and phone calls; nothing records who advanced the order, who took the cash,
who cut it, who delivered it. The workflow must also respect the state machine (no skipping steps) and
gate handover on the balance being paid for advance orders.

## User stories

- As **staff with `manage_orders`**, I want to see the orders for my branch(es) in a queue, filterable
  by status and payment, so I know what to work on.
- As the same, I want to record a cash/bank payment a customer made so the order confirms (and stock
  is reserved for `shop` orders).
- As the same, I want to move an order to production (assigning a cutter), to ready, and to completed
  — and to assign a driver for delivery.
- As the same, I want to apply a discount with a reason when the situation calls for it.
- As the **workshop owner**, I want to approve pay-later for a trusted customer (with a mandatory
  reason), and to force-cancel an in-production+ order in exceptional cases.

## Requirements

1. `list-branch-orders` / `get-order` (owner; staff with `manage_orders` on the order's branch):
   the orders for the in-scope branch(es); list filters — status (groups + individual), payment status
   (paid / unpaid / partial / pay-later-pending), has-pending-refund, search (order # or client name),
   date range; sortable. Detail with items (snapshots), pricing breakdown, delivery info, the cutting
   summary + PDF, payments, refunds, the status timeline, the internal note.
2. `record-payment` (`manage_orders` on the branch, or owner): for an order, record a payment — type
   (`full` / `advance` / `balance`), method (`cash` / `bank_transfer`), amount (defaults to the
   outstanding, validated ≤ outstanding), optional receipt scan. Creates an `order_payment` (status
   `completed`, `received_by_user_id` = the actor, `paid_at`). If the recorded payment covers the
   order (or the advance), the order goes `→ confirmed` (and `inventory.reserve` runs for a `shop`
   order — atomic; on a money-already-moved confirm a reserve failure leaves the order `confirmed`
   with `reserve_status = failed` + an owner alert; see [`docs/spec/orders.md`](../../spec/orders.md)).
3. `mark-pay-later` (owner; covered by `manage_orders` in v1 with the mandatory reason as the control):
   sets `pay_later_approved` + `pay_later_approved_by_user_id` + `pay_later_reason`, moves the order
   `→ confirmed` (reserve runs; this is a *no-money* confirm — a reserve failure rolls the whole thing
   back with `insufficient_stock`).
4. `change-order-status` (`manage_orders` on the branch, or owner): the allowed transitions only —
   `confirmed → in_production` (optionally assign a `cutter_worker_id` of the branch),
   `in_production → ready` (runs `inventory.consume` for a `shop` order), `ready → completed` (pickup —
   gated: the balance must have been recorded for an `advance` order), `ready → in_delivery` (delivery —
   requires a `driver_worker_id` of the branch + balance recorded), `in_delivery → completed`. Each
   writes an `order_status_event` and serializes via the order's `version` (optimistic lock).
5. `assign-driver` (`manage_orders` on the branch, or owner): set `driver_worker_id` (a branch worker,
   position driver typically) — part of `ready → in_delivery`.
6. `apply-discount` (`manage_orders` on the branch, or owner): percent or fixed sum, **mandatory
   reason**; recomputes `total_tiyin` (can't go negative), records `discount_applied_by_user_id`,
   flags the order; audited; surfaced in the dashboard.
7. `cancel-order` / `force-cancel-order` / `revert-refund` — see [`docs/ref/features/order-cancellation-and-refunds.md`](order-cancellation-and-refunds.md) (force-cancel of `in_production`+ and refund-revert are owner-only).
8. Dashboard (`view_dashboard`): KPIs (orders, revenue completed, avg order value, completed/cancelled
   ratio, pending refunds + stale subcount), an order-status distribution, a simple timeseries, the
   refund-SLA panel, a low-stock summary, recent audit highlights — scoped to the in-scope branch(es)
   (owner: the workshop).
9. Every action audited; status changes write status-change-log rows; the client (and relevant
   workshop staff) get notifications on status changes, payment recorded, discount, etc.

## UX

In the **seh app**:

- **Orders** (`/seh/orders`) — a branch-scoped queue, two modes (toggle in the toolbar):
  - **Board** — columns `new` / `pending_payment` / `confirmed` / `in_production` / `ready` /
    `in_delivery` (no `completed` / `cancelled`); each column header has a count; cards: order #,
    client name + phone, total, payment chip (paid/unpaid/partial/pay-later), delivery icon, item
    count, age, a pending-refund flag. **No drag-and-drop** — status changes go through the card's
    action menu (the state machine is restricted).
  - **Table** — columns: order #, branch (if multi-branch), client, status, payment status, total,
    items, created, action menu; sortable headers. Filter strip: status chips, payment-status chips,
    has-pending-refund toggle, search, date range. Branch filter dropdown for multi-branch users.
    Empty: "No orders in your branch(es)." If the user has zero branches: "No branches assigned —
    ask your workshop owner."
- **Order detail** (`/seh/orders/:id`) — header (order #, branch chip, client (link to a mini-card),
  status badge, total) with the status-appropriate action set:

  | Status | Actions |
  |---|---|
  | `new` | Cancel (reason) · Modify · Mark pay-later (owner; reason) · Record payment |
  | `pending_payment` | Cancel (reason) · Modify · Record payment |
  | `confirmed` | Start production (→ `in_production`; optional cutter) · Cancel (reason) |
  | `in_production` | Mark ready (→ `ready`) · Apply discount (reason) · Force-cancel (owner; reason) |
  | `ready` (pickup) | Mark picked up (→ `completed`; blocked until balance recorded for advance) · Record payment · Force-cancel (owner) |
  | `ready` (delivery) | Assign driver (→ `in_delivery`; blocked until balance recorded) · Record payment · Force-cancel (owner) |
  | `in_delivery` | Mark delivered (→ `completed`) · Force-cancel (owner) |
  | `completed` | (read-only) |
  | `cancelled` | Complete refund (if a pending refund exists) |

  Tabs: Overview (items snapshots, pricing breakdown, delivery info, the internal note — inline
  editable), Cutting (the SVG + PDF link; invalidated note if applicable), Payments (the
  `order_payment` list; "Record payment" inline → modal with amount/method/receipt), Refunds (only if
  any; "Complete refund" → modal — see [`docs/ref/features/order-cancellation-and-refunds.md`](order-cancellation-and-refunds.md)), Timeline (status events + audit), Notes (the internal note).
  Discount dialog: percent or fixed sum + reason, with a live new-total preview. Pay-later dialog:
  reason + confirms the client name. Cancel dialog: reason + a warning if `shop` material is reserved
  (stock will be released).
- **Dashboard** (`/seh/dashboard`, `view_dashboard`) — date-range + branch filter; KPI cards; status
  donut; orders/revenue timeseries (client zero-filled); refund-SLA panel ("N stale, oldest age" →
  link to refunds); top branches (owner); recent critical audit entries. Empty for an empty period:
  "No orders in this period."
- States: list/detail/dashboard each have loading/empty/error; actions show a busy state and end in
  success or a recoverable error; the optimistic-lock conflict surfaces as "this order changed —
  refresh and try again"; no infinite spinners.
- Accessibility: the board is keyboard-navigable (focus a card, open via Enter); status actions are
  in a labelled menu, not drag targets; destructive actions (cancel, force-cancel) are danger-styled
  and name their effect; modal focus management; the balance-gate is explained when an action is
  disabled.

Shared components (`KanbanBoard`, data table, filter bar, order timeline, status badge, money input,
confirm-with-reason, charts): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/sales/order.md`](../entities/sales/order.md) — status transitions, discount, pay-later, worker assignments.
- [`docs/ref/entities/sales/order-payment.md`](../entities/sales/order-payment.md) — recorded payments.
- [`docs/ref/entities/sales/order-status-event.md`](../entities/sales/order-status-event.md) — one per transition.
- [`docs/ref/entities/sales/order-refund.md`](../entities/sales/order-refund.md), [`docs/ref/entities/sales/order-cancellation.md`](../entities/sales/order-cancellation.md) — via cancellation.
- [`docs/ref/entities/inventory/stock-item.md`](../entities/inventory/stock-item.md) — reserve on confirm, consume on ready, release on early cancel (`shop`).
- [`docs/ref/entities/workshop/worker.md`](../entities/workshop/worker.md) — cutter/driver assignment.
- [`docs/ref/entities/cutting/cutting-result.md`](../entities/cutting/cutting-result.md) — viewed/PDF.
- [`docs/ref/entities/support/file.md`](../entities/support/file.md), [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md), [`docs/ref/entities/support/notification.md`](../entities/support/notification.md).

## Edge cases

- **Recording a payment larger than the outstanding amount** — rejected.
- **Reserve fails on a money-already-recorded confirm** — order stays `confirmed`, `reserve_status =
  failed`, owner alerted, manual resolution (retry the reserve, or cancel + refund). On a pay-later
  (no-money) confirm, the reserve failure rolls it back (`insufficient_stock`).
- **Advancing past `ready` with the balance unrecorded** (advance order) — the action is disabled
  with an explanation; record the balance first.
- **Two staff advance the same order at once** — the second hits the optimistic-lock conflict and is
  told to refresh.
- **Assigning a worker from another branch / an inactive worker** — rejected.
- **Pay-later order never paid past the handover deadline** — staff cancel it (`reason =
  no_payment`); for `shop`, the material is already consumed (no release); the loss is the workshop's;
  the owner can review it.
- **A staff member without `manage_orders` on the branch hitting an action** — `forbidden`; the seh
  app doesn't show the control.

## Out of scope

- Operator-created orders — never.
- Online payment via a gateway — v1.1; v1 records cash/bank only.
- Drag-and-drop status changes — disallowed (the state machine is restricted).
- Multi-note threads on an order — v1 has a single internal note.
- Real-time delivery (GPS) tracking — future.
- CSV export of the orders list — placeholder (disabled) in v1.

## Open questions

- Whether force-cancel / refund-revert should be a delegable permission rather than owner-only —
  owner: shape — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q12.
