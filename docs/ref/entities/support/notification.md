---
title: Notification
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/architecture.md
  - docs/ref/features/notifications-inbox.md
---

# Notification

## What it is

One in-app inbox item for one principal — "your order moved to `ready`", "this refund is now stale",
"low stock on material X", "your workshop was blocked". Produced by the module where the event
happened, fanned out to the right recipients, polled by the front-end apps. v1's only notification
channel — SMS/email/Telegram-bot are v1.1. See [`docs/spec/architecture.md`](../../../spec/architecture.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `recipient_type` | enum | `platform_user` / `workshop_user` / `client` | required |
| `recipient_id` | UUID | the principal | required; → the matching entity (logical) |
| `event_code` | text | e.g. `order.status_changed`, `refund.stale`, `warehouse.low_stock`, `workshop.blocked` | required |
| `entity_type` | text? | the subject entity type (`order` / `order_refund` / `stock_item` / `branch` / …) | |
| `entity_id` | UUID? | the subject entity's id (for the deep link) | |
| `payload` | json | small denormalized fields needed to render without extra lookups (order_number, branch_name, amount, …) | |
| `created_at` | timestamp | | |
| `read_at` | timestamp? | when the recipient marked it read | null = unread |

## States / lifecycle

`unread` (`read_at` null) → `read` (`read_at` set, via `mark-read` / `read-all`). Not deleted in v1
(no purge job).

## Invariants

- One row per recipient per event (a workshop-wide event fans out to one row per recipient) — service rule.
- A recipient sees only their own notifications, with the producing module's scope rules applied —
  service rule ([`docs/spec/architecture.md`](../../../spec/architecture.md)).
- The unread count (badge) is the count of `read_at IS NULL` rows for the principal — invariant.
- `payload` is small — enough to render the inbox line; the full data lives on the linked entity.

## Relationships

- targets → [`docs/ref/entities/identity/platform-user.md`](../identity/platform-user.md), [`docs/ref/entities/identity/workshop-user.md`](../identity/workshop-user.md), or [`docs/ref/entities/identity/client.md`](../identity/client.md) (via `recipient_type` + `recipient_id`)
- deep-links to (logical, by `entity_type`+`entity_id`) → [`docs/ref/entities/sales/order.md`](../sales/order.md), [`docs/ref/entities/sales/order-refund.md`](../sales/order-refund.md), [`docs/ref/entities/inventory/stock-item.md`](../inventory/stock-item.md), [`docs/ref/entities/workshop/branch.md`](../workshop/branch.md), …

## Owner

The `notifications` module; rules in [`docs/spec/architecture.md`](../../../spec/architecture.md); UI in [`docs/ref/features/notifications-inbox.md`](../../features/notifications-inbox.md).
