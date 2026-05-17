---
title: Sales
status: draft
owner: shape
updated: 2026-05-17
order: 50
---

# Sales

The order header, its items, the status events, and the single cancel event. Lifecycle
rules, pricing, the state machine, and the stock / money seams are in
[`orders.md`](../features/orders.md). Money (what the client paid, refunds) lives in the
finance context ([`finance.md`](finance.md)); the order holds **no payment rows**.

## Order

A client's request for panels cut to size at a branch — the header that owns the items, the
status history, the production stamps, and a frozen price snapshot. Created only by a client,
from a cutting draft with a chosen algorithm result. v1 is pickup-only; the order references
its confirmed cutting result. Material source is **per item** — see [Order item](#order-item).

**Identity & lifecycle**

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_number` | text | human-readable, `ORD-2026-000123` (per-year sequence); unique |
| `client_id` | UUID | the client who placed it |
| `workshop_id` / `branch_id` | UUID | required (branch in the workshop) |
| `cutting_result_id` | UUID | the confirmed (current) cutting result |
| `status` | enum | `new` / `confirmed` / `cutting` / `edge_banding` / `ready` / `completed` / `cancelled`; default `new` |
| `version` | int | optimistic-lock counter for status transitions |
| `note_client` / `note_workshop` | text? | client and staff notes |
| `created_at` / `updated_at` / `confirmed_at` / `completed_at` / `cancelled_at` | timestamps | as the lifecycle moves |

**Pricing snapshot** (frozen at creation against the chosen branch's rates; there is no
post-placement modification, so it is never re-priced)

| Field | Type | Notes |
|---|---|---|
| `subtotal_cutting_tiyin` / `subtotal_materials_tiyin` / `subtotal_edge_banding_tiyin` | bigint | snapshot subtotals (materials = 0 unless `shop`); each ≥ 0 |
| `discount_tiyin` | bigint | applied by a `manage_orders` user; ≥ 0; ≤ pre-discount total |
| `discount_reason` / `discount_applied_by_user_id` | text? / UUID? | required if `discount_tiyin > 0` |
| `total_tiyin` | bigint | `cutting + materials + edge banding − discount`; ≥ 0 |
| `currency` | enum | `UZS` (only value in v1) |

**Worker assignment + production stamps** (assignment is mutable until the job is done;
stamps are immutable once set and cleared by a revert of the step that set them — they are
the only input to the worker-production reports in [`finance.md`](../features/finance.md))

| Field | Type | Set at | Notes |
|---|---|---|---|
| `assigned_cutter_user_id` | UUID? | operator assigns | setting it is the `confirmed → cutting` trigger; holds `process_production` on the branch |
| `assigned_edger_user_id` | UUID? | operator assigns | set when the order has banded parts; holds `process_production` on the branch |
| `cutter_user_id` | UUID? | `cutting → next` | the user credited (assignee, or the on-behalf "who did this work?" pick) |
| `cut_completed_at` | timestamp? | `cutting → next` | |
| `sheets_used_snapshot` / `cut_count_snapshot` | int? | `cutting → next` | from the cutting result; production-report inputs |
| `edger_user_id` | UUID? | `edge_banding → ready` | the user credited; null when the order had no banded parts |
| `edge_completed_at` | timestamp? | `edge_banding → ready` | |
| `edge_length_snapshot` | json? | `edge_banding → ready` | `{ "0.4": 12500, "2.0": 4800 }` metres of banding by thickness |
| `picked_up_at` | timestamp? | `ready → completed` | |

Invariants: created only by a client, from a cutting draft with a `chosen` result (which
becomes `confirmed` and bound); all money fields are integer tiyin; `total_tiyin` follows
the formula and can't go negative; the price snapshot is frozen at creation (no
re-pricing — there is no modification); status transitions follow the state machine only;
concurrent transitions serialize by `version`; `cutter_user_id` / `edger_user_id` reference
workshop users who hold `process_production` on `branch_id`; production stamps are set in the
same atomic transaction as their transition and **cleared by a revert** of that step; stock
is auto-decremented per `shop` item by the inventory module (sheets at `cutting →` next,
edges at `edge_banding → ready`) — the order holds no stock balance; `completed` and
`cancelled` are terminal; an order is never deleted (it goes `cancelled`).

## Order item

One part line of an order — a panel of given dimensions and quantity, optional edge banding,
plus a frozen snapshot of the material it's cut from and the prices used. Items mirror the
parts the client entered into the cutting wizard for that order.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `material_id` | UUID | logical reference (the snapshot is authoritative for the order) |
| `material_source` | enum | `shop` / `own` — per-item; an order can mix sources |
| `material_snapshot` | json | `{ name, type, thickness_mm, color, decor_code, sheet_length_mm, sheet_width_mm, price_tiyin }` as of order creation |
| `part_ref` | text | the part's id (matches the cutting result's parts snapshot / placements) |
| `length_mm` / `width_mm` | int | within material / cutting bounds |
| `quantity` | int | ≥ 1 |
| `edge_top_mm` / `edge_bottom_mm` / `edge_left_mm` / `edge_right_mm` | numeric? | edge-banding thickness per side, or null |
| `unit_cutting_price_tiyin` | bigint | snapshot, ≥ 0 |
| `unit_material_price_tiyin` | bigint | snapshot; 0 when `material_source = own`; ≥ 0 |
| `edge_cost_tiyin` | bigint | snapshot for this line; ≥ 0 |
| `line_total_tiyin` | bigint | `(unit_cutting + unit_material) × quantity + edge_cost`; ≥ 0 |

Invariants: snapshot fields are never updated to reflect later catalog changes; `part_ref`
corresponds to a part in the order's cutting result; grain is a property of the item's
material (read from `material_snapshot`); parts on a grained material aren't rotated at
cutting time. There is no modify path — items are created with the order and never replaced.

## Order status event

One row per status transition — who made it, from which state to which, why (when a reason
is required), and any context. The order's audit trail; also mirrored into the global
[status change log](support.md#status-change-log). Append-only; the order timeline is built
from this.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `from_status` | enum? | null for the creation event |
| `to_status` | enum | required; a valid transition target (including a revert step) |
| `actor_type` | enum | `client` / `workshop_user` / `system` |
| `actor_user_id` / `actor_client_id` | UUID? / UUID? | mutually exclusive (or both null if `system`) |
| `reason` | text? | required for cancellations and reverts |
| `metadata` | json? | optional context (e.g. the credited user on an on-behalf completion) |
| `changed_at` | timestamp | |

Invariants: written for **every** transition in the same atomic operation; `to_status` is a
legal transition (or revert) from `from_status` per the state machine; cancellation and
revert carry a `reason`; never updated or deleted.

## Order cancellation

The single cancel event: who cancelled, in what capacity, and why. An order is cancelled at
most once (it's terminal afterwards). Money already paid is returned offline and recorded as
an expense in the finance module — there is no refund entity.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required; **unique** (one cancellation per order) |
| `cancelled_by_type` | enum | `client` (only while `new`) / `workshop_user` |
| `cancelled_by_user_id` / `cancelled_by_client_id` | UUID? / UUID? | mutually exclusive |
| `reason` | text | mandatory; non-trivially short |
| `cancelled_at` | timestamp | |

Invariants: exactly one cancellation per order (DB unique); `reason` mandatory; the
cancelling party is allowed at the order's status per [`orders.md`](../features/orders.md)
(`workshop_user` with `manage_orders` on any pre-`completed` state; `client` only while
`new`); already-decremented material is not restored.

## Next

- [`orders.md`](../features/orders.md) — the state machine, pricing, and the stock / money
  seams that govern these rows.
- [`finance.md`](../features/finance.md) — order income and the worker-production reports
  the stamps feed.
