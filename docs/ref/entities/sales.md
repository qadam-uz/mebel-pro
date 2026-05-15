---
title: Sales
status: draft
owner: shape
updated: 2026-05-16
order: 50
---

# Sales

The order header + its items, payments, refunds, status events, and the single cancel event.
Lifecycle rules, pricing, the state machine, and the warehouse contract are in
[`orders.md`](../features/orders.md).

## Order

A client's request for panels cut to size at a branch — the header that owns the items,
payments, status history, cancellation, refunds, and the production stamps that feed
payroll. Created only by a client, from a cutting draft with a chosen algorithm result.
Carries a **snapshot** of its pricing and a reference to its confirmed cutting result.
Material source is **per item** — see [Order item](#order-item).

**Identity & lifecycle**

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_number` | text | human-readable, `ORD-2026-000123` (per-year sequence); unique |
| `client_id` | UUID | the client who placed it |
| `workshop_id` / `branch_id` | UUID | required (branch in the workshop) |
| `cutting_result_id` | UUID | the confirmed (current) cutting result |
| `delivery_type` | enum | `pickup` / `delivery` |
| `delivery_address` | json? | `{ street, city, lat, lng, note }`; required if `delivery` |
| `delivery_zone_id` | UUID? | the resolved static zone; required if `delivery` |
| `status` | enum | `new` / `pending_payment` / `confirmed` / `cutting` / `edge_banding` / `ready` / `in_delivery` / `completed` / `cancelled`; default `new` |
| `version` | int | optimistic-lock counter for status transitions |
| `priority_score` | int | manager-controlled queue priority (higher = sooner); default 0; used in the cutter / edger / driver queues |
| `pay_later_approved` / `pay_later_approved_by_user_id` / `pay_later_reason` | bool / UUID? / text? | the second / third required if the first is true |
| `reserve_status` | enum? | `ok` / `failed` — set when reserve is attempted after a money-already-moved confirm; null otherwise |
| `note_client` / `note_workshop` | text? | client and staff notes |
| `created_at` / `updated_at` / `confirmed_at` / `completed_at` / `cancelled_at` | timestamps | as the lifecycle moves |

**Pricing snapshot** (frozen at creation and at re-pricing on modify; later catalog / pricing
changes never reach the order)

| Field | Type | Notes |
|---|---|---|
| `subtotal_cutting_tiyin` / `subtotal_materials_tiyin` / `subtotal_edge_banding_tiyin` / `delivery_fee_tiyin` | bigint | snapshot subtotals (materials = 0 unless `shop`; delivery = 0 unless `delivery`); each ≥ 0 |
| `discount_tiyin` | bigint | applied by staff; ≥ 0; ≤ pre-discount total |
| `discount_reason` / `discount_applied_by_user_id` | text? / UUID? | required if `discount_tiyin > 0` |
| `total_tiyin` | bigint | `cutting + materials + edge banding + delivery − discount`; ≥ 0 |
| `currency` | enum | `UZS` (only value in v1) |

**Worker pre-assignment (optional hints; set by the office)**

| Field | Type | Notes |
|---|---|---|
| `assigned_cutter_user_id` | UUID? | optional pre-assignment; pins the order to that cutter's queue; nullable |
| `assigned_edger_user_id` | UUID? | same for edge banding |
| `assigned_driver_user_id` | UUID? | same for delivery |

**Production stamps (immutable once set; what payroll reads — see
[`finance.md`](../features/finance.md))**

| Field | Type | Set at | Notes |
|---|---|---|---|
| `cutter_user_id` | UUID? | `confirmed → cutting` | the workshop user who claimed (or was acted on behalf of); must hold `process_production` on the branch and have `home_branch_id = order.branch_id` |
| `cut_started_at` | timestamp? | `confirmed → cutting` | |
| `cut_completed_at` | timestamp? | `cutting → next` | |
| `sheets_used_snapshot` | int? | `cutting → next` | from the cutting result; `per_sheet` payroll input |
| `cut_count_snapshot` | int? | `cutting → next` | from the cutting result; `per_cut` payroll input |
| `edger_user_id` | UUID? | `cutting → edge_banding` | nullable — set only when the order has banded parts; same grant / home_branch rules |
| `edge_started_at` | timestamp? | `cutting → edge_banding` | |
| `edge_completed_at` | timestamp? | `edge_banding → ready` | |
| `edge_length_snapshot` | json? | `edge_banding → ready` | `{ "0.4": 12500, "2.0": 4800 }` metres-of-banding by thickness; `per_metre_banding` payroll input |
| `driver_user_id` | UUID? | `ready → in_delivery` | nullable — set only on delivery orders; holds `process_delivery` on the branch |
| `driver_started_at` | timestamp? | `ready → in_delivery` | |
| `delivered_at` | timestamp? | `in_delivery → completed` | |
| `picked_up_at` | timestamp? | `ready → completed` (pickup) | |

Invariants: created only by a client, from a cutting draft with a `chosen` result (which
becomes `confirmed` and bound); all money fields are integer tiyin; `total_tiyin` follows
the formula and can't go negative; pricing fields are a snapshot at creation / re-pricing
(later catalog or pricing changes don't reach the order); status transitions follow the
state machine only; concurrent transitions serialize by `version`; `cutter_user_id`,
`edger_user_id`, `driver_user_id` reference workshop users whose `home_branch_id =
order.branch_id` and who hold the matching `process_production` / `process_delivery` grant;
production stamps are immutable once set (set in the same atomic transaction as the
relevant transition); stock actions apply per `shop`-source item — reserved on
`→ confirmed`, consumed on `cutting → next`, released on `confirmed → cancelled` or
`cutting → cancelled`; an order with no `shop` items touches stock not at all; a
`completed` order is terminal; never deleted (goes `cancelled`).

## Order item

One part line of an order — a panel of given dimensions, in some quantity, with optional edge
banding and a grain requirement, plus a frozen snapshot of the material it's cut from and the
prices used. Items mirror the parts the client entered into the cutting wizard for that order.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `material_id` | UUID | logical reference (the snapshot is authoritative for the order) |
| `material_source` | enum | `shop` / `own` — per-item; an order can mix sources |
| `material_snapshot` | json | `{ name, type, thickness_mm, color, decor_code, sheet_length_mm, sheet_width_mm, price_tiyin }` as of order creation |
| `part_ref` | text | the part's id (matches the cutting result's parts snapshot / placements) |
| `length_mm` / `width_mm` | int | within material/cutting bounds |
| `quantity` | int | ≥ 1 |
| `edge_top_mm` / `edge_bottom_mm` / `edge_left_mm` / `edge_right_mm` | numeric? | edge-banding thickness per side, or null |
| `unit_cutting_price_tiyin` | bigint | snapshot, ≥ 0 |
| `unit_material_price_tiyin` | bigint | snapshot; 0 when `material_source = own`; ≥ 0 |
| `edge_cost_tiyin` | bigint | snapshot for this line; ≥ 0 |
| `line_total_tiyin` | bigint | `(unit_cutting + unit_material) × quantity + edge_cost`; ≥ 0 |

On order modification, items are replaced (and the order re-priced); the old items aren't kept
(the old cutting result is, with its `parts_snapshot`). Invariants: snapshot fields never
updated to reflect later catalog changes; `part_ref` corresponds to a part in the order's
cutting result; grain is a property of the item's material (read from `material_snapshot`);
parts on a grained material aren't rotated at cutting time.

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
| `is_owner_force_cancel` | bool | `true` if owner force-cancel from `cutting` / `edge_banding` / `ready` / `in_delivery`; default `false` |
| `reason` | text | mandatory; non-trivially short |
| `refund_required` | bool | whether the order had a completed payment |
| `cancelled_at` | timestamp | |

Invariants: exactly one cancellation per order (DB unique); `reason` mandatory; the
cancelling party must be allowed at the order's status per the eligibility matrix; a
cancellation from `cutting` or later requires `is_owner_force_cancel = true` and the owner;
if `refund_required`, a `pending` order refund is created in the same operation; for a
`shop` order cancelled from `confirmed` or `cutting`, the reservation is released in the
same operation (and the cancel dialog optionally records an `adjust-stock` waste write-off
for any sheets the cutter physically used).

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
