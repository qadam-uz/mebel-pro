---
title: Order refund
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/sales/order.md
  - docs/ref/entities/sales/order-payment.md
  - docs/ref/entities/sales/order-cancellation.md
  - docs/spec/orders.md
  - docs/spec/scope-v1.md
  - docs/ref/features/order-cancellation-and-refunds.md
---

# Order refund

## What it is

A refund record against an [order payment](order-payment.md). In v1 refunds are **manual**: the
system creates a `pending` refund when a paid order is cancelled (or down-modified); workshop staff
move the money offline (bank / cash) and **record** the refund with a mandatory bank-reference /
receipt note; the record flips to `completed` and the payment to `refunded`. The owner can revert a
completed refund on dispute. No automatic gateway refunds in v1 — [`docs/spec/scope-v1.md`](../../../spec/scope-v1.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `order_id` | UUID | the order | required; → order |
| `order_payment_id` | UUID | which payment is being refunded | required; → order payment |
| `amount_tiyin` | bigint | refund amount (full or partial) | > 0; ≤ the payment's completed amount |
| `method` | enum | `cash` / `bank_transfer` / `payme_manual` / `click_manual` / `other` | required when completing |
| `status` | enum | `pending` / `completed` / `failed` | created `pending` |
| `note` | text? | **mandatory when completing** — bank reference / receipt id | |
| `receipt_file_id` | UUID? | → [`file`](../support/file.md) — optional receipt scan | |
| `processed_by_user_id` | UUID? | the staff user who completed it | required when `completed`/`failed` |
| `created_at` | timestamp | | |
| `completed_at` | timestamp? | | |

## States / lifecycle

`pending` (created automatically on cancel / down-modify of a paid order) → `completed` (staff record
the offline refund: method + mandatory note → payment goes `refunded`, client notified) or `failed`
(staff couldn't complete it — rare). A `completed` refund can be **reverted** by the owner
(exceptional, audited) — it goes back to `failed` with a note. A `pending` refund older than 7 days
is flagged stale (dashboard + owner notification).

## Invariants

- `amount_tiyin > 0` and ≤ the referenced payment's completed amount; a payment may have several
  partial refunds, summing to ≤ that amount — service rules.
- Completing a refund **requires a `note`** (bank ref / receipt) and records `processed_by_user_id` —
  service rule ([`docs/spec/orders.md`](../../../spec/orders.md)).
- All amounts are integer tiyin — invariant.
- Only the owner can revert a completed refund — service rule ([`docs/spec/access.md`](../../../spec/access.md)).
- A refund record is never deleted — soft state only.

## Relationships

- belongs to → [`docs/ref/entities/sales/order.md`](order.md) (many-to-one)
- refunds → [`docs/ref/entities/sales/order-payment.md`](order-payment.md) (many-to-one)
- created by → [`docs/ref/entities/sales/order-cancellation.md`](order-cancellation.md) (or a down-modify of the order)
- processed by → [`docs/ref/entities/identity/workshop-user.md`](../identity/workshop-user.md)
- receipt → [`docs/ref/entities/support/file.md`](../support/file.md)

## Owner

[`docs/ref/features/order-cancellation-and-refunds.md`](../../features/order-cancellation-and-refunds.md); v1 manual-refund policy in [`docs/spec/scope-v1.md`](../../../spec/scope-v1.md).
