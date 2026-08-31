---
title: Notifications inbox
status: draft
owner: shape
updated: 2026-08-31
order: 60
---

# Notifications inbox

v1's only notification channel is an **in-app inbox per principal**. Producing modules
(`orders`, `inventory`, `identity`, `workshop`, `platform`) call the `notifications` module on
a notifiable event and ask it to fan out one row per recipient, applying the producer's scope
rules. The notifications module does not broadcast and does not decide recipients.

## How it works

- **Each principal has their own inbox.** A workshop-wide event fans out one row per affected
  staff member; each has their own unread count.
- **Pull delivery.** Apps poll the unread count every ~30–60 s and pull the list on demand. No
  WebSocket / SSE in v1 — overkill at this scale.
- **Each row carries a denormalized payload** (order number, branch name, amount, …) so the
  dropdown can render without a follow-up fetch; the linked entity is the source of truth.
- **No scheduled digest in v1.** Low-stock conditions may produce live inventory notifications,
  but there is no daily low-stock summary job in v1.
- **Rows persist on block.** A blocked principal's rows stay (history); they reappear on
  unblock.
- **A client's order notifications are four status events** — `order.confirmed`,
  `order.ready`, `order.completed`, `order.cancelled` — plus `order.updated` when staff
  revise a placed order. One per phase of the client's four-phase order track, which is why
  the intermediate `cutting` / `edge_banding` transitions notify nobody, in either
  production mode ([`orders.md`](orders.md#ux-client-app)). Older inbox rows written under
  the previous rule (`order.status_changed`) still render as sentences — the code stays
  mapped — but no new ones are produced.

The principal's own inbox supports: pulling the list (paginated, newest first, optional unread
filter and "since timestamp"), pulling the unread count for the bell, marking one read,
marking all read.

## UX

In all three apps (client / workshop / superadmin), in the header:

- **Bell** — a labelled button that marks unread work, in one of two forms. The **workshop**
  chrome carries an 8px orange **signal dot** ringed in the surface colour: the exact figure is
  not actionable at a glance, so the dense shell stays quiet and the count is spoken instead. The
  **client and superadmin** apps keep the numeric badge — a graphite pill in `on-accent`, ringed
  in the canvas, **capped at `9+`** — because neither chrome is dense enough for the number to
  cost anything. Either way the count is also in the button's accessible name, so no state is
  carried by a mark alone. The bell opens a dropdown listing the last ~10 notifications: an icon
  per event family, a one-line summary built from the payload, a relative timestamp. Clicking a row
  navigates to the linked entity and marks it read. The dropdown has "mark all as read" and a
  "see all" link to a full notifications page (paginated, with a read/unread filter).
- **Toasts** for the critical events, in addition to the bell mark — for the client, an order
  status change; for workshop staff, a new order; for the platform operator, an error spike
  or a failed job.
- **States** — bell with zero unread (bare, no dot and no badge); dropdown loading; dropdown
  empty ("Nothing new"); the notifications page has loading / empty / error. If the notifications
  endpoint is down the bell carries no mark but the underlying data is still reachable on the
  relevant pages.
- **Accessibility** — the bell announces the unread count in every app, which in the workshop is
  the only place the figure appears at all; the dropdown is a proper menu / listbox with keyboard
  navigation; toasts are announced, dismissible, and don't trap focus; rows have descriptive
  accessible names (not just icons).

## Edge cases

- **Notifications endpoint down** — the bell carries no mark; nothing breaks; data is reachable
  on the relevant pages.
- **A workshop-wide event** — fans out one row per staff member; each has their own unread
  count.
- **Low stock does not notify** — it is a state the Ombor row and the dashboard already show,
  not an event; sending it to the bell on every movement past the threshold read as noise. Only
  a balance going *negative* notifies (docs/ref/features/catalog-inventory.md).
- **A notification linking to an entity the principal can no longer see** (scope changed since
  the event) — the link resolves to a "not available" state rather than leaking. Rare.

## Next

[`platform.md`](platform.md) — the jobs that produce failed-job alerts and the error monitor that
notifies operators on an error spike.
