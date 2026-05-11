---
title: Order
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/orders.md
  - docs/ref/entities/sales/order-item.md
  - docs/ref/entities/sales/order-payment.md
  - docs/ref/entities/sales/order-status-event.md
  - docs/ref/entities/cutting/cutting-result.md
  - docs/ref/features/order-placement.md
---

# Order

## What it is

A client's request for panels cut to size at a branch — the header that owns the items, payments,
status history, cancellation, and refunds. Created only by a client, from a confirmed cutting draft.
Carries a **snapshot** of its pricing and a reference to its confirmed cutting result. Moves through a
fixed state machine. The full lifecycle and the rules around it are in [`docs/spec/orders.md`](../../../spec/orders.md); pricing in [`docs/spec/orders.md`](../../../spec/orders.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `order_number` | text | human-readable, `ORD-2026-000123` (per-year sequence) | unique |
| `client_id` | UUID | the client who placed it | required; → client |
| `workshop_id` | UUID | snapshot of the branch's workshop | required |
| `branch_id` | UUID | the branch | required; → branch (same workshop) |
| `material_source` | enum | `own` / `shop` | required |
| `delivery_type` | enum | `pickup` / `delivery` | required |
| `delivery_address` | json? | `{ street, city, lat, lng, note }` | required if `delivery` |
| `delivery_zone_id` | UUID? | the resolved static zone (for the fee) | required if `delivery` |
| `status` | enum | `new` / `pending_payment` / `confirmed` / `in_production` / `ready` / `in_delivery` / `completed` / `cancelled` | default `new` |
| `cutting_result_id` | UUID | the confirmed (current) cutting result | required; → cutting result |
| `subtotal_cutting_tiyin` | bigint | cutting-service price (snapshot) | ≥ 0 |
| `subtotal_materials_tiyin` | bigint | material price (snapshot; 0 unless `shop`) | ≥ 0 |
| `subtotal_edge_banding_tiyin` | bigint | edge-banding price (snapshot) | ≥ 0 |
| `delivery_fee_tiyin` | bigint | delivery fee (snapshot; 0 unless `delivery`) | ≥ 0 |
| `discount_tiyin` | bigint | discount applied by staff | ≥ 0; ≤ the pre-discount total |
| `discount_reason` | text? | required if `discount_tiyin` > 0 | |
| `discount_applied_by_user_id` | UUID? | the staff user | required if discount > 0 |
| `total_tiyin` | bigint | `cutting + materials + edge banding + delivery − discount` | ≥ 0 |
| `currency` | enum | `UZS` (only value v1) | |
| `cutter_worker_id` | UUID? | assigned when `→ in_production` | → worker in the branch |
| `driver_worker_id` | UUID? | assigned when `→ in_delivery` | → worker in the branch |
| `pay_later_approved` | bool | owner/staff approved pay-later | default `false` |
| `pay_later_approved_by_user_id` | UUID? | the approver | required if `pay_later_approved` |
| `pay_later_reason` | text? | required if `pay_later_approved` | |
| `reserve_status` | enum? | `ok` / `failed` — set when reserve is attempted after a money-already-moved confirm | null otherwise |
| `version` | int | optimistic-lock counter for status transitions | bumped on transition |
| `note_client` | text? | client's note | |
| `note_workshop` | text? | staff's internal note | |
| `created_at` / `updated_at` | timestamp | | |
| `confirmed_at` / `completed_at` / `cancelled_at` | timestamp? | when the order reached those states | |

## States / lifecycle

`new → pending_payment → confirmed → in_production → ready → (in_delivery) → completed`, with
`cancelled` reachable from any pre-`completed` state per the cancellation matrix. Each transition
writes an [order status event](order-status-event.md). The full diagram, who-may-do-what, the
advance-balance gate, and the modification matrix are in [`docs/spec/orders.md`](../../../spec/orders.md).

## Invariants

- Created only by a client, only from a `draft` cutting result (which becomes `confirmed` and bound) —
  service rule.
- All money fields are integer tiyin; `total_tiyin` equals the formula above; `discount_tiyin` can't
  push the total negative — service/DB rules.
- Pricing fields and the material/pricing references are a **snapshot** at creation/re-pricing time —
  later catalog/pricing changes don't reach the order ([`docs/spec/architecture.md`](../../../spec/architecture.md)).
- Status transitions follow the state machine only; concurrent transitions are serialized by
  `version` (optimistic lock) — service rule.
- `discount_*`, `pay_later_*`, `cutter_worker_id`, `driver_worker_id` are populated only in the
  states that allow them; assigned workers belong to the order's branch — service rules.
- A `completed` order is terminal (no modify, no cancel); an order is never deleted (goes
  `cancelled`) — service rule.
- Stock is reserved on `→ confirmed`, consumed on `→ ready`, released on cancel-before-production —
  only for `shop` source; an `own`-source order never touches stock — service rule ([`docs/spec/orders.md`](../../../spec/orders.md)).

## Relationships

- placed by → [`docs/ref/entities/identity/client.md`](../identity/client.md) (many-to-one)
- at → [`docs/ref/entities/workshop/branch.md`](../workshop/branch.md); in → [`docs/ref/entities/workshop/workshop.md`](../workshop/workshop.md)
- contains → [`docs/ref/entities/sales/order-item.md`](order-item.md) (one-to-many)
- confirms → [`docs/ref/entities/cutting/cutting-result.md`](../cutting/cutting-result.md) (one current)
- has → [`docs/ref/entities/sales/order-payment.md`](order-payment.md), [`docs/ref/entities/sales/order-refund.md`](order-refund.md), [`docs/ref/entities/sales/order-status-event.md`](order-status-event.md) (one-to-many each); [`docs/ref/entities/sales/order-cancellation.md`](order-cancellation.md) (zero-or-one)
- assigned → [`docs/ref/entities/workshop/worker.md`](../workshop/worker.md) (cutter and/or driver)
- drives → [`docs/ref/entities/inventory/stock-item.md`](../inventory/stock-item.md) (reserve/consume/release for `shop`)

## Owner

[`docs/spec/orders.md`](../../../spec/orders.md) and [`docs/spec/orders.md`](../../../spec/orders.md); features [`docs/ref/features/order-placement.md`](../../features/order-placement.md), [`docs/ref/features/order-fulfillment.md`](../../features/order-fulfillment.md), [`docs/ref/features/order-modification.md`](../../features/order-modification.md), [`docs/ref/features/order-cancellation-and-refunds.md`](../../features/order-cancellation-and-refunds.md).
