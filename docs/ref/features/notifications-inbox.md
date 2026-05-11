---
title: Notifications inbox
status: stable
owner: shape
updated: 2026-05-11
order: 42
related:
  - docs/spec/architecture.md
  - docs/ref/entities/support/notification.md
  - docs/ref/features/order-fulfillment.md
  - docs/ref/features/platform-ops.md
---

# Notifications inbox

## Problem

Things happen that a principal needs to know about — your order moved to `ready`; a refund's been
pending too long; a material is low on stock; your workshop was blocked. v1 has one channel: an
in-app inbox. Each of the three apps needs a notification bell with an unread count and a dropdown of
recent items linking to the relevant order/refund/branch — and critical events should also toast so
they're not missed. (SMS, email, and a Telegram bot are v1.1 — see [`docs/spec/scope-v1.md`](../../spec/scope-v1.md); the system-level notification policy is in [`docs/spec/architecture.md`](../../spec/architecture.md) → *Cross-cutting concerns*.)

## User stories

- As a **client**, I want to be told when my order's status changes, when a payment is recorded, when
  it's cancelled, when a refund completes — without having to keep checking.
- As **workshop staff**, I want to be told about new orders, pending refunds, orders ready without a
  driver, low stock — for my branch(es).
- As a **workshop owner**, I want stale-refund and low-stock alerts for my workshop.
- As a **platform operator**, I want alerts about error spikes and failed scheduled jobs.
- As any principal, I want a bell with an unread count and a way to mark items read.

## Requirements

1. `list-notifications` (current principal): paginated, newest first; optionally `unread=true` and
   `since=<ts>`; each item: id, `event_code`, `entity_type`, `entity_id`, `payload` (the small
   denormalized fields to render the line — order number, branch name, amount, …), `created_at`,
   `read_at`. Scoped by the producing module's rules ([`docs/spec/architecture.md`](../../spec/architecture.md)).
2. `notifications-unread-count` (current principal): the count of unread items — drives the bell badge.
3. `mark-notification-read` / `mark-all-read` (current principal).
4. Producing modules (`orders`, `inventory`, `identity`, `workshop`, `platform`) call the
   `notifications` module on a notifiable event, fanning out one row per recipient with the right
   scope; the daily background jobs (stale refunds, low stock, pay-later overdue) also produce
   notifications.
5. Delivery is **pull**: the apps poll `unread-count` every ~30–60 s and `list-notifications` on
   demand. No WebSocket/SSE in v1.

## UX

In **all three apps** (client / seh / superadmin), in the top bar:

- **Bell** — a badge with the unread count (capped display, e.g. "9+"); polled. Clicking opens a
  **dropdown** listing the last ~10 notifications: an icon per event family, a one-line summary built
  from `payload`, a relative timestamp; clicking an item navigates to the linked entity (the order
  detail, the refund queue, the branch detail, the error monitor) and marks it read; a "mark all as
  read" action; a "see all" link to a full **notifications page** (paginated, with read/unread
  filter).
- **Toasts** — critical events also fire a toast (in addition to the badge): for the client, an order
  status change; for workshop staff, a new order or a pending refund; for the owner, a stale refund or
  low stock; for the platform operator, an error spike or a failed job.
- States: bell with zero unread (no badge); dropdown loading; dropdown empty ("Nothing new");
  notifications page empty/loading/error. The bell degrades gracefully if the endpoint is down (no
  badge; the underlying data is still on the order/refund pages).
- Accessibility: the bell is a labelled button announcing the unread count; the dropdown is a proper
  menu/listbox with keyboard navigation; toasts are announced and dismissible and don't trap focus;
  notification items have descriptive accessible names (not just icons).

Shared components (notification bell + dropdown, toast, data table): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/support/notification.md`](../entities/support/notification.md) — listed, counted, marked read.
- (referenced via `entity_type`/`entity_id` for deep links) [`docs/ref/entities/sales/order.md`](../entities/sales/order.md), [`docs/ref/entities/sales/order-refund.md`](../entities/sales/order-refund.md), [`docs/ref/entities/inventory/stock-item.md`](../entities/inventory/stock-item.md), [`docs/ref/entities/workshop/branch.md`](../entities/workshop/branch.md).

## Edge cases

- **Notifications endpoint down** — the bell shows no badge; nothing breaks; the data is reachable on
  the relevant pages.
- **A blocked principal** — their notification rows stay (history); they can't see them until
  unblocked.
- **A workshop-wide event** (e.g. workshop blocked) — fans out one row per staff member; each has
  their own unread count.
- **A flood of low-stock notifications** — coalesced sensibly (one per material per day from the
  daily job; live changes still produce one each).
- **A notification linking to an entity the principal can no longer see** (scope changed) — the link
  resolves to a "not available" state rather than leaking; rare.

## Out of scope

- SMS / email channels and a Telegram notification bot — v1.1 ([`docs/spec/open-questions.md`](../../spec/open-questions.md) Q5).
- WebSocket / SSE push — v1 is polling.
- User-configurable notification preferences (mute categories) — future.
- Notification retention / purge — none in v1.

## Open questions

- Whether producing modules should emit domain events the `notifications` module subscribes to vs.
  calling it directly — owner: build — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q11.
