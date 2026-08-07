---
title: Sales
status: draft
owner: shape
updated: 2026-08-07
order: 50
---

# Sales

The order header, its items, the status events, and the single cancel event. Lifecycle
rules, pricing, the state machine, and the stock / money seams are in
[`orders.md`](../features/orders.md). Money (what the client paid, refunds) lives in the
finance context ([`finance.md`](finance.md)); the order holds **no payment rows**.

## Order

A client's request for panels cut to size at a branch — the header that owns the items, the
status history, the production stamps, and a frozen price snapshot. Created by the client —
or by workshop staff on behalf of a walk-in client — from a cutting draft with a chosen
algorithm result. v1 is pickup-only; the order references its confirmed cutting result.
Material source is **per item** for the panel and **per side** for each edge — see
[Order item](#order-item).

**Identity & lifecycle**

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_number` | text | human-readable, `#26-14-0003` — 2-digit year · the branch's `branch_no` · a per-branch, per-year sequence (4 digits, resets each January); globally unique |
| `client_id` | UUID | the client the order belongs to — its placer, or the walk-in it was placed for |
| `workshop_id` / `branch_id` | UUID | required (branch in the workshop) |
| `cutting_result_id` | UUID | the confirmed (current) cutting result |
| `status` | enum | `new` / `confirmed` / `cutting` / `edge_banding` / `ready` / `completed` / `cancelled`; default `new` |
| `version` | int | optimistic-lock counter for status transitions |
| `contact_name` / `contact_phone` | text | the checkout contact shared with the workshop; copied from the client profile by default but frozen from the checkout form |
| `note_client` / `note_workshop` | text? | client and staff notes |
| `created_at` / `updated_at` / `confirmed_at` / `completed_at` / `cancelled_at` | timestamps | as the lifecycle moves |

**Order number** — `#26-14-0003` is the third 2026 order of branch 14. The sequence is scoped
to the branch because a client orders from a branch, and that is the unit staff count in; the
`branch_no` segment ([`workshop.md`](workshop.md)) carries both the branch's identity and the
number's platform-wide uniqueness, so there is no workshop segment. `branch_no` is never
zero-padded and the prefix keeps its trailing dash, which is what stops branch 1's numbers
from being read as branch 14's. Numbers are minted under an advisory lock and counted from
existing rows — safe only because orders are never deleted.

*Legacy era:* orders placed before this format keep their `ORD-2026-000123` numbers — clients
hold screenshots and printed cutting maps of them. The two formats coexist permanently; order
search is a substring match, so both stay findable.

**Pricing snapshot** (frozen at creation against the chosen branch's rates; there is no
post-placement modification, so it is never re-priced)

| Field | Type | Notes |
|---|---|---|
| `subtotal_cutting_tiyin` | bigint | snapshot subtotal — `Σ panels × cutting_rate_tiyin` at this branch; ≥ 0 |
| `subtotal_materials_tiyin` | bigint | snapshot subtotal — `shop`-source panel cost; ≥ 0 |
| `subtotal_edge_banding_tiyin` | bigint | snapshot subtotal — `shop`-source edge cost; ≥ 0 |
| `discount_tiyin` | bigint | applied by a `manage_orders` user; ≥ 0; ≤ pre-adjustment subtotal (never makes the price negative) |
| `discount_reason` / `discount_applied_by_user_id` | text? / UUID? | required if `discount_tiyin > 0` |
| `surcharge_tiyin` | bigint | applied by a `manage_orders` user; ≥ 0; no cap (reason + audit are the control) |
| `surcharge_reason` / `surcharge_applied_by_user_id` | text? / UUID? | required if `surcharge_tiyin > 0` |
| `total_tiyin` | bigint | `cutting + materials + edge banding − discount + surcharge`; ≥ 0 |
| `currency` | enum | `UZS` (only value in v1) |

**Worker assignment + production stamps** (assignment is mutable until the job is done;
stamps are immutable once set and cleared by a revert of the step that set them — they are
the only input to the worker-production reports in [`finance.md`](../features/finance.md))

| Field | Type | Set at | Notes |
|---|---|---|---|
| `assigned_cutter_user_id` | UUID? | operator assigns | pure metadata — assignment does **not** change status; holds `process_production` on the branch |
| `assigned_edger_user_id` | UUID? | operator assigns | set when the order has banded parts; holds `process_production` on the branch |
| `cutter_assigned_at` / `edger_assigned_at` | timestamp? | operator assigns | restamped on re-assignment; station-queue FIFO key; persists across reverts |
| `cutting_started_at` | timestamp? | **Start cutting** (`confirmed → cutting`) | cleared by revert `cutting → confirmed` |
| `banding_started_at` | timestamp? | **Start banding** (within `edge_banding`) | cleared by revert `edge_banding → cutting`; survives `ready → edge_banding` |
| `cutter_user_id` | UUID? | `cutting → next` | the user credited (assignee, or the on-behalf "who did this work?" pick) |
| `cut_completed_at` | timestamp? | `cutting → next` | |
| `panels_used_snapshot` / `cut_count_snapshot` | int? | `cutting → next` | from the cutting result; production-report inputs |
| `edger_user_id` | UUID? | `edge_banding → ready` | the user credited; null when the order had no banded parts |
| `edge_completed_at` | timestamp? | `edge_banding → ready` | |
| `edge_length_snapshot` | json? | `edge_banding → ready` | `{ "<kromka branch_material_id>": 12500, … }` — consumed banding length in integer millimetres per tape format (only `shop` source). UI/reports display metres. Thickness is part of the format itself. |
| `picked_up_at` | timestamp? | `ready → completed` | |

Invariants: created by the client — or by workshop staff on behalf of a walk-in client
([`orders.md`](../features/orders.md#staff-created-orders-walk-in-clients)) — from a cutting
draft with a `chosen` result (which becomes `confirmed` and bound); a staff-created order
lands `confirmed` with `confirmed_at` set at creation; the checkout contact snapshot is
frozen at creation so later client profile edits do not rewrite the workshop-facing order;
all money fields are integer
tiyin; `total_tiyin` follows the formula and can't go negative; the discount and surcharge
are independent manual adjustments (either, both, or neither), each requiring a reason and
applied-by stamp when non-zero, settable only while `new`/`confirmed` and cleared by a
revision; the price snapshot is otherwise frozen
at creation (no re-pricing — there is no modification); status transitions follow the state
machine only; concurrent transitions serialize by `version`; `cutter_user_id` /
`edger_user_id` reference workshop users who hold `process_production` on `branch_id`;
production stamps are set in the same atomic transaction as their transition and **cleared by
a revert** of that step; stock is auto-decremented per `shop` source by the inventory module
(panels at `cutting →` next, edges at `edge_banding → ready`, per tape format) — the order
holds no stock balance; `completed` and `cancelled` are terminal; an order is never deleted
(it goes `cancelled`).

## Order item

One part line of an order — a panel of given dimensions and quantity, optional edge banding
**per side**, plus frozen snapshots of the panel and each side's edge (the snapshots are
authoritative for the order) and the prices used. Items mirror the parts the client entered
into the cutting wizard for that order.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `branch_material_id` | UUID | logical reference to the panel **branch material** — one dekor in one format (the snapshot is authoritative for the order) |
| `material_source` | enum | `shop` / `own` — for the panel; per-item; an order can mix |
| `material_snapshot` | json | `{ manufacturer_name, tur, kod, nomi, tolali, qalinlik_mm, uzunlik_mm, eni_mm, kromka_eni_mm, price_tiyin }` as of order creation. Pre-reshape rows keep the old vocabulary (`name`, `type`, `color`, `decor_code`, `thickness_mm`, `panel_length_mm`, `panel_width_mm`) — frozen history is never rewritten, and the label formatter reads both |
| `part_ref` | text | the part's id (matches the cutting result's parts snapshot / placements) |
| `length_mm` / `width_mm` | int | within material / cutting bounds |
| `quantity` | int | ≥ 1 |
| `edge_top` / `edge_bottom` / `edge_left` / `edge_right` | json? | per side: either null (no banding) or `{ material_id, source, snapshot: { manufacturer_name, tur, kod, nomi, qalinlik_mm, kromka_eni_mm, price_tiyin } }`, where `material_id` is a `kromka` branch material (the JSON key kept its name; the values were rewritten) |
| `unit_cutting_price_tiyin` | bigint | snapshot, ≥ 0 |
| `unit_material_price_tiyin` | bigint | snapshot; 0 when panel `material_source = own`; ≥ 0 |
| `edge_cost_tiyin` | bigint | snapshot for this line — sum across the four sides of `shop` edge cost; 0 when every banded side is `own`; ≥ 0 |
| `line_total_tiyin` | bigint | `(unit_cutting + unit_material) × quantity + edge_cost`; ≥ 0 |

Invariants: snapshot fields are never updated to reflect later catalog changes; `part_ref`
corresponds to a part in the order's cutting result; `branch_material_id` is a branch material
of a panel-shaped dekor; each side's edge `material_id` (when set) is one of a `kromka` dekor;
grain is a property of the panel's dekor (read from `material_snapshot`); parts on a grained material
aren't rotated at cutting time; per-side `source` is independent and may differ across sides
of the same item. There is no modify path — items are created with the order and never
replaced.

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

Invariants: written for **every** transition in the same atomic operation; the creation
event (`from_status` null) carries the order's creator as actor — `client` on the self-serve
path, `workshop_user` on the staff walk-in path, which writes both `∅ → new` and
`new → confirmed` with the same actor in one operation; `to_status` is a legal transition
(or revert) from `from_status` per the state machine; cancellation and revert carry a
`reason`; never updated or deleted.

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
