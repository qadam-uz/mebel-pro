---
title: Order payment
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/sales/order.md
  - docs/ref/entities/sales/order-refund.md
  - docs/spec/orders.md
  - docs/spec/scope-v1.md
---

# Order payment

## What it is

A payment record against an [order](order.md). An order can have several — typically an advance plus
a balance, or a single full payment, or a pay-later settlement. In v1 there is no payment gateway:
workshop staff **record** payments the client made at the counter (cash / bank transfer); recording
one that covers the order (or the advance) transitions the order to `confirmed`. The gateway methods
are reserved for v1.1. See [`docs/spec/scope-v1.md`](../../../spec/scope-v1.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `order_id` | UUID | the order | required; → order |
| `payment_type` | enum | `full` / `advance` / `balance` / `pay_later_settlement` (`bnpl` reserved for v1.1) | required |
| `amount_tiyin` | bigint | the amount | > 0; ≤ the order's outstanding amount |
| `method` | enum | `cash` / `bank_transfer` (`payme` / `click` / `uzum` / `uzum_nasiya` / `alif_nasiya` reserved for v1.1) | required |
| `status` | enum | `pending` / `completed` / `failed` / `refunded` | in v1, recording a payment creates it `completed` |
| `external_ref` | text? | gateway/BNPL reference — v1.1; in v1 a bank-transfer reference if useful | |
| `paid_at` | timestamp? | when the money actually changed hands | |
| `received_by_user_id` | UUID? | the staff user who recorded a cash/bank payment | required for `cash` / `bank_transfer` |
| `receipt_file_id` | UUID? | → [`file`](../support/file.md) — optional receipt scan | |
| `note` | text? | | |
| `created_at` / `updated_at` | timestamp | | |

## States / lifecycle

In v1: a payment is **created `completed`** when staff record it (the money already moved). The
v1.1 path would create it `pending` (gateway redirect) → `completed` (webhook) / `failed` (timeout).
A payment goes `refunded` when an [order refund](order-refund.md) against it completes.

## Invariants

- `amount_tiyin > 0`; the sum of completed payments never exceeds the order's `total_tiyin` (modulo
  a difference-payment after a price increase) — service rules.
- `cash` / `bank_transfer` payments carry a `received_by_user_id` (the recorder) and a `paid_at` —
  service rule.
- All amounts are integer tiyin — invariant.
- Recording a payment that covers the order (or the advance) is the trigger that moves the order to
  `confirmed` (and reserves stock if `shop`) — service rule ([`docs/spec/orders.md`](../../../spec/orders.md)).
- The balance payment must be recorded before handover for `advance` orders — service rule.

## Relationships

- belongs to → [`docs/ref/entities/sales/order.md`](order.md) (many-to-one)
- recorded by → [`docs/ref/entities/identity/workshop-user.md`](../identity/workshop-user.md) (cash/bank)
- refunded via → [`docs/ref/entities/sales/order-refund.md`](order-refund.md) (zero-to-many)
- receipt → [`docs/ref/entities/support/file.md`](../support/file.md)

## Owner

[`docs/ref/features/order-fulfillment.md`](../../features/order-fulfillment.md) (recording payments); the order-flow rules are in [`docs/spec/orders.md`](../../../spec/orders.md).
