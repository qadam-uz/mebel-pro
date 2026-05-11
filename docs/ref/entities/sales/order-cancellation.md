---
title: Order cancellation
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/sales/order.md
  - docs/ref/entities/sales/order-refund.md
  - docs/spec/orders.md
  - docs/ref/features/order-cancellation-and-refunds.md
---

# Order cancellation

## What it is

The single cancel event for an [order](order.md): who cancelled, in what capacity, why, and whether a
refund is owed. An order is cancelled at most once (it's terminal afterwards). If a payment had been
made, cancellation triggers the creation of a `pending` [order refund](order-refund.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `order_id` | UUID | the order | required; → order; **unique** (one cancellation per order) |
| `cancelled_by_type` | enum | `client` / `workshop_user` | required |
| `cancelled_by_user_id` | UUID? | the workshop user, if applicable | |
| `cancelled_by_client_id` | UUID? | the client, if applicable | |
| `is_owner_force_cancel` | bool | `true` if this was an owner force-cancel of an `in_production`+ order | default `false` |
| `reason` | text | mandatory cancellation reason | required (non-trivially short) |
| `refund_required` | bool | whether the order had a completed payment | |
| `cancelled_at` | timestamp | | |

## States / lifecycle

No lifecycle — write once when the order is cancelled.

## Invariants

- Exactly one cancellation per order — DB constraint (unique `order_id`).
- `reason` is mandatory — service rule.
- The cancelling party must be allowed to cancel at the order's status per the eligibility matrix —
  service rule ([`docs/spec/orders.md`](../../../spec/orders.md)); an `in_production`+ cancellation requires `is_owner_force_cancel` and the owner.
- If `refund_required`, a `pending` order refund is created in the same operation — service rule.
- For a `shop` order cancelled before production, the reserved stock is released in the same
  operation — service rule.

## Relationships

- belongs to → [`docs/ref/entities/sales/order.md`](order.md) (one-to-one)
- triggers → [`docs/ref/entities/sales/order-refund.md`](order-refund.md) (zero-or-one `pending` on creation)
- cancelled by → [`docs/ref/entities/identity/workshop-user.md`](../identity/workshop-user.md) or [`docs/ref/entities/identity/client.md`](../identity/client.md)

## Owner

[`docs/ref/features/order-cancellation-and-refunds.md`](../../features/order-cancellation-and-refunds.md); rules in [`docs/spec/orders.md`](../../../spec/orders.md).
