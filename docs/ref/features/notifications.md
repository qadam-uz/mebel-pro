---
title: Notifications inbox
status: draft
owner: shape
updated: 2026-05-13
order: 60
---

# Notifications inbox

v1's only notification channel is an **in-app inbox** per principal. Producing modules (`orders`,
`inventory`, `identity`, `workshop`, `platform`) call the `notifications` module on a notifiable
event, asking it to fan out one row per recipient with the producer's scope rules applied (it
doesn't broadcast). The cross-cutting model is in [`architecture.md`](../../architecture.md)
→ *Cross-cutting concerns → Notifications*.

## Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `list-notifications` | current principal | paginated, newest first; optional `unread=true` and `since=<ts>`; each item: `id`, `event_code`, `entity_type`, `entity_id`, `payload` (small denormalized render fields — order_number, branch_name, amount, …), `created_at`, `read_at` |
| `notifications-unread-count` | current principal | the count of unread items — drives the bell badge |
| `mark-notification-read` / `mark-all-read` | current principal | |

Delivery is **pull**: the apps poll `unread-count` every ~30–60 s and `list-notifications` on
demand. No WebSocket/SSE in v1.

## UX

In **all three apps** (client / workshop / superadmin), in the top bar:

- **Bell** — badge with the unread count (capped display, e.g. "9+"); polled. Clicking opens a
  **dropdown** listing the last ~10 notifications: an icon per event family, a one-line summary
  built from `payload`, a relative timestamp; clicking an item navigates to the linked entity
  and marks it read; a "mark all as read" action; a "see all" link to a full **notifications
  page** (paginated, with read/unread filter).
- **Toasts** — critical events also fire a toast (in addition to the badge): for the client, an
  order status change; for workshop staff, a new order or a pending refund; for the owner, a
  stale refund or low stock; for the platform operator, an error spike or a failed job.
- States: bell with zero unread (no badge); dropdown loading; dropdown empty ("Nothing new");
  notifications page empty/loading/error. The bell degrades gracefully if the endpoint is down
  (no badge; the underlying data is still on the order/refund pages).
- Accessibility: the bell is a labelled button announcing the unread count; the dropdown is a
  proper menu/listbox with keyboard navigation; toasts are announced and dismissible and don't
  trap focus; notification items have descriptive accessible names (not just icons).

Component specs in [`web/DESIGN.md`](../../../web/DESIGN.md).

## Edge cases

- **Notifications endpoint down** — the bell shows no badge; nothing breaks; the data is
  reachable on the relevant pages.
- **A blocked principal** — their notification rows stay (history); they can't see them until
  unblocked.
- **A workshop-wide event** (e.g. workshop blocked) — fans out one row per staff member; each
  has their own unread count.
- **A flood of low-stock notifications** — coalesced (one per material per day from the daily
  job; live changes still produce one each).
- **A notification linking to an entity the principal can no longer see** (scope changed) — the
  link resolves to a "not available" state rather than leaking; rare.
