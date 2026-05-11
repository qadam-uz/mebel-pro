---
title: Status change log
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/nfr.md
  - docs/ref/entities/support/action-log.md
  - docs/ref/entities/sales/order-status-event.md
  - docs/ref/features/audit-log.md
---

# Status change log

## What it is

One row per state transition of any entity that has a status — primarily orders (mirroring each
[order status event](../sales/order-status-event.md)), but also branches, materials, workers,
workshops, users, refunds going `active`/`blocked`/`inactive`/`completed`/etc. The "what changed
state" half of the audit log (the "who did what" half is the [action log](action-log.md)).
Append-only. See [`docs/spec/nfr.md`](../../../spec/nfr.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `entity_type` | text | the entity whose status changed (`order` / `branch` / `material` / `worker` / `workshop` / `workshop_user` / `client` / `order_refund` / …) | required |
| `entity_id` | UUID | the entity's id | required |
| `workshop_id` | UUID? | for scoping the viewer | |
| `branch_id` | UUID? | when relevant | |
| `from_status` | text? | previous status (null for the first) | |
| `to_status` | text | new status | required |
| `actor_type` | enum | `platform_user` / `workshop_user` / `client` / `system` | required |
| `actor_user_id` / `actor_client_id` | UUID? | the actor | |
| `reason` | text? | when the transition requires one | |
| `action_log_id` | UUID? | the action-log row this transition belongs to (when it was part of a user action) | → action log |
| `changed_at` | timestamp | | |

## States / lifecycle

No lifecycle — write once, never update or delete (append-only).

## Invariants

- Every status transition of an audited entity writes exactly one row, in the same atomic operation —
  invariant ([`docs/spec/nfr.md`](../../../spec/nfr.md)).
- For orders, this row corresponds 1:1 with an [`order_status_event`](../sales/order-status-event.md)
  (the order's own timeline) — service rule; the order-status-event is the order-scoped detail, this
  is the cross-entity audit view.
- Never updated or deleted — append-only.
- Same scoping as the action log (workshop owner/staff: own workshop; platform operator: all).

## Relationships

- subject (logical) → any status-bearing entity, esp. [`docs/ref/entities/sales/order.md`](../sales/order.md)
- companion → [`docs/ref/entities/support/action-log.md`](action-log.md); links via `action_log_id`
- mirrors → [`docs/ref/entities/sales/order-status-event.md`](../sales/order-status-event.md) for orders

## Owner

The `audit` module; viewer in [`docs/ref/features/audit-log.md`](../../features/audit-log.md).
