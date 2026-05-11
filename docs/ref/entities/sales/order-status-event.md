---
title: Order status event
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/sales/order.md
  - docs/spec/orders.md
  - docs/ref/entities/support/status-change-log.md
---

# Order status event

## What it is

One row per status transition of an [order](order.md) — who made it, from which state to which,
why (a reason, when one is required), and any context. The order's own audit trail; also mirrored
into the global [status change log](../support/status-change-log.md). Append-only; it's what the
order timeline in the UI is built from.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `order_id` | UUID | the order | required; → order |
| `from_status` | enum? | the previous status (null for the creation event) | |
| `to_status` | enum | the new status | required; a valid transition target |
| `actor_type` | enum | `client` / `workshop_user` / `system` | required |
| `actor_user_id` | UUID? | the workshop user, if `actor_type = workshop_user` | |
| `actor_client_id` | UUID? | the client, if `actor_type = client` | |
| `reason` | text? | required for cancellations and exceptional transitions | |
| `metadata` | json? | optional context (e.g. which payment triggered a confirm) | |
| `changed_at` | timestamp | | |

## States / lifecycle

No lifecycle — write once, never update (append-only).

## Invariants

- A row is written for **every** status transition, in the same atomic operation — invariant ([`docs/spec/orders.md`](../../../spec/orders.md)).
- `to_status` is a legal transition from `from_status` per the state machine — service rule.
- Cancellation, force-cancellation, and other exceptional transitions carry a `reason` — service rule.
- Exactly one of `actor_user_id` / `actor_client_id` is set unless `actor_type = system` (both null) — service rule.
- Never updated or deleted — append-only ([`docs/spec/architecture.md`](../../../spec/architecture.md)).

## Relationships

- belongs to → [`docs/ref/entities/sales/order.md`](order.md) (many-to-one)
- mirrored into → [`docs/ref/entities/support/status-change-log.md`](../support/status-change-log.md)
- actor → [`docs/ref/entities/identity/workshop-user.md`](../identity/workshop-user.md) or [`docs/ref/entities/identity/client.md`](../identity/client.md)

## Owner

[`docs/spec/orders.md`](../../../spec/orders.md); written by the order workflow features.
