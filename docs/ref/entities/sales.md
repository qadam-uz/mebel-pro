---
title: Sales
status: draft
owner: shape
updated: 2026-05-13
order: 50
---

# Sales

The order header + its items, payments, refunds, status events, and the single cancel event.
Lifecycle rules, pricing, and the warehouse contract are in [`orders.md`](../features/orders.md).

## Order

A client's request for panels cut to size at a branch — the header that owns the items,
payments, status history, cancellation, and refunds. Created only by a client, from a confirmed
cutting draft. Carries a **snapshot** of its pricing and a reference to its confirmed cutting
result.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_number` | text | human-readable, `ORD-2026-000123` (per-year sequence); unique |
| `client_id` | UUID | the client who placed it |
| `workshop_id` / `branch_id` | UUID | required (branch in the workshop) |
| `material_source` | enum | `own` / `shop` |
| `delivery_type` | enum | `pickup` / `delivery` |
| `delivery_address` | json? | `{ street, city, lat, lng, note }`; required if `delivery` |
| `delivery_zone_id` | UUID? | the resolved static zone; required if `delivery` |
| `status` | enum | `new` / `pending_payment` / `confirmed` / `in_production` / `ready` / `in_delivery` / `completed` / `cancelled`; default `new` |
| `cutting_result_id` | UUID | the confirmed (current) cutting result |
| `subtotal_cutting_tiyin` / `subtotal_materials_tiyin` / `subtotal_edge_banding_tiyin` / `delivery_fee_tiyin` | bigint | snapshot subtotals (materials = 0 unless `shop`; delivery = 0 unless `delivery`); each ≥ 0 |
| `discount_tiyin` | bigint | applied by staff; ≥ 0; ≤ pre-discount total |
| `discount_reason` / `discount_applied_by_user_id` | text? / UUID? | required if `discount_tiyin > 0` |
| `total_tiyin` | bigint | `cutting + materials + edge banding + delivery − discount`; ≥ 0 |
| `currency` | enum | `UZS` (only value in v1) |
| `cutter_worker_id` | UUID? | assigned when `→ in_production`; worker in the branch |
| `driver_worker_id` | UUID? | assigned when `→ in_delivery`; worker in the branch |
| `pay_later_approved` / `pay_later_approved_by_user_id` / `pay_later_reason` | bool / UUID? / text? | the second/third required if the first is true |
| `reserve_status` | enum? | `ok` / `failed` — set when reserve is attempted after a money-already-moved confirm; null otherwise |
| `version` | int | optimistic-lock counter for status transitions |
| `note_client` / `note_workshop` | text? | client and staff notes |
| `created_at` / `updated_at` / `confirmed_at` / `completed_at` / `cancelled_at` | timestamps | as the lifecycle moves |

Invariants: created only by a client, only from a `draft` cutting result (which becomes
`confirmed` and bound); all money fields are integer tiyin; `total_tiyin` follows the formula
and can't go negative; pricing fields are a **snapshot** at creation/re-pricing time (later
catalog/pricing changes don't reach the order); status transitions follow the state machine
only; concurrent transitions serialize by `version`; `cutter_worker_id` / `driver_worker_id`
belong to the order's branch; a `completed` order is terminal; never deleted (goes
`cancelled`); for `shop`, stock is reserved on `→ confirmed`, consumed on `→ ready`, released on
cancel-before-production.

## Order item

One part line of an order — a panel of given dimensions, in some quantity, with optional edge
banding and a grain requirement, plus a frozen snapshot of the material it's cut from and the
prices used. Items mirror the parts the client entered into the cutting wizard for that order.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `material_id` | UUID | logical reference (the snapshot is authoritative for the order) |
| `material_snapshot` | json | `{ name, type, thickness_mm, color, decor_code, sheet_length_mm, sheet_width_mm, price_tiyin }` as of order creation |
| `part_ref` | text | the part's id (matches the cutting result's `parts_snapshot` / placements) |
| `length_mm` / `width_mm` | int | within material/cutting bounds |
| `quantity` | int | ≥ 1 |
| `grain_direction` | enum | `any` / `required` |
| `edge_top_mm` / `edge_bottom_mm` / `edge_left_mm` / `edge_right_mm` | numeric? | edge-banding thickness per side, or null |
| `unit_cutting_price_tiyin` | bigint | snapshot, ≥ 0 |
| `unit_material_price_tiyin` | bigint | snapshot; 0 unless `shop`; ≥ 0 |
| `edge_cost_tiyin` | bigint | snapshot for this line; ≥ 0 |
| `line_total_tiyin` | bigint | `(unit_cutting + unit_material) × quantity + edge_cost`; ≥ 0 |

On order modification, items are replaced (and the order re-priced); the old items aren't kept
(the old cutting result is, with its `parts_snapshot`). Invariants: snapshot fields never
updated to reflect later catalog changes; `part_ref` corresponds to a part in the order's
cutting result; a `grain = required` part can't be rotated by the cutter.

## Order payment

A payment record against an order. An order can have several — typically an advance plus a
balance, or a single full payment, or a pay-later settlement. In v1 there is no payment gateway:
workshop staff **record** payments the client made at the counter (cash / bank transfer);
recording one that covers the order (or the advance) transitions the order to `confirmed`. The
gateway methods are reserved for later.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `payment_type` | enum | `full` / `advance` / `balance` / `pay_later_settlement` (`bnpl` reserved for later) |
| `amount_tiyin` | bigint | > 0; ≤ the order's outstanding amount |
| `method` | enum | `cash` / `bank_transfer` (`payme` / `click` / `uzum` / `uzum_nasiya` / `alif_nasiya` reserved for later) |
| `status` | enum | `pending` / `completed` / `failed` / `refunded`; in v1, recording a payment creates it `completed` |
| `external_ref` | text? | gateway/BNPL reference (post-v1); in v1 a bank-transfer reference if useful |
| `paid_at` | timestamp? | when the money actually changed hands |
| `received_by_user_id` | UUID? | the staff user who recorded a cash/bank payment; required for `cash` / `bank_transfer` |
| `receipt_file_id` | UUID? | → [file](support.md#file) — optional receipt scan |
| `note` | text? | |
| `created_at` / `updated_at` | timestamp | |

Invariants: `amount_tiyin > 0`; the sum of completed payments never exceeds the order's
`total_tiyin` (modulo a difference-payment after a price increase); cash/bank payments carry a
`received_by_user_id` + `paid_at`; recording a payment that covers the order (or the advance)
is the trigger that moves it to `confirmed` (and reserves stock if `shop`); the balance payment
must be recorded before handover for `advance` orders; goes `refunded` when an
[order refund](#order-refund) against it completes.

## Order status event

One row per status transition of an order — who made it, from which state to which, why (a
reason, when one is required), and any context. The order's own audit trail; also mirrored into
the global [status change log](support.md#status-change-log). Append-only; the order timeline
in the UI is built from this.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `from_status` | enum? | null for the creation event |
| `to_status` | enum | required; a valid transition target |
| `actor_type` | enum | `client` / `workshop_user` / `system` |
| `actor_user_id` / `actor_client_id` | UUID? / UUID? | mutually exclusive (or both null if `system`) |
| `reason` | text? | required for cancellations and exceptional transitions |
| `metadata` | json? | optional context (e.g. which payment triggered a confirm) |
| `changed_at` | timestamp | |

Invariants: written for **every** status transition in the same atomic operation; `to_status`
is a legal transition from `from_status` per the state machine; cancellation, force-cancel, and
other exceptional transitions carry a `reason`; never updated or deleted.

## Order cancellation

The single cancel event for an order: who cancelled, in what capacity, why, and whether a refund
is owed. An order is cancelled at most once (it's terminal afterwards).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required; **unique** (one cancellation per order) |
| `cancelled_by_type` | enum | `client` / `workshop_user` |
| `cancelled_by_user_id` / `cancelled_by_client_id` | UUID? / UUID? | mutually exclusive |
| `is_owner_force_cancel` | bool | `true` if owner force-cancel of an `in_production`+ order; default `false` |
| `reason` | text | mandatory; non-trivially short |
| `refund_required` | bool | whether the order had a completed payment |
| `cancelled_at` | timestamp | |

Invariants: exactly one cancellation per order (DB unique); `reason` mandatory; the cancelling
party must be allowed at the order's status per the eligibility matrix; an `in_production`+
cancellation requires `is_owner_force_cancel = true` and the owner; if `refund_required`, a
`pending` order refund is created in the same operation; for a `shop` order cancelled before
production, the reserved stock is released in the same operation.

## Order refund

A refund record against an order payment. In v1 refunds are **manual**: the system creates a
`pending` refund when a paid order is cancelled (or down-modified); workshop staff move the
money offline (bank/cash) and **record** the refund with a mandatory bank-reference / receipt
note; the record flips to `completed` and the payment to `refunded`. The owner can revert a
completed refund on dispute. No automatic gateway refunds in v1.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` / `order_payment_id` | UUID | required |
| `amount_tiyin` | bigint | > 0; ≤ the payment's completed amount |
| `method` | enum | `cash` / `bank_transfer` / `payme_manual` / `click_manual` / `other` (required when completing) |
| `status` | enum | `pending` / `completed` / `failed`; created `pending` |
| `note` | text? | **mandatory when completing** — bank reference / receipt id |
| `receipt_file_id` | UUID? | → [file](support.md#file) — optional receipt scan |
| `processed_by_user_id` | UUID? | required when `completed`/`failed` |
| `created_at` / `completed_at` | timestamp / timestamp? | |

Invariants: `amount_tiyin > 0` and ≤ the referenced payment's completed amount; a payment may
have several partial refunds summing to ≤ that amount; completing **requires a `note`** + a
`processed_by_user_id`; all amounts integer tiyin; only the owner can revert a completed
refund; never deleted. A `pending` refund older than 7 days is flagged stale (dashboard + owner
notification).
