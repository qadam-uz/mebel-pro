---
title: Sales
status: draft
owner: shape
updated: 2026-09-05
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
| `order_number` | text | the client–workshop handle: **six random decimal digits**, no leading zero (`100000`–`999999`), e.g. `482917`; globally unique. Displayed as `№ 482 917` |
| `client_id` | UUID | the client the order belongs to — its placer, or the walk-in it was placed for |
| `workshop_id` / `branch_id` | UUID | required (branch in the workshop) |
| `cutting_result_id` | UUID | the confirmed (current) cutting result |
| `status` | enum | `new` / `confirmed` / `cutting` / `edge_banding` / `ready` / `completed` / `cancelled`; default `new` |
| `version` | int | optimistic-lock counter for status transitions |
| `contact_name` / `contact_phone` | text | the checkout contact shared with the workshop; copied from the client profile by default but frozen from the checkout form |
| `note_client` / `note_workshop` | text? | client and staff notes |
| `created_at` / `updated_at` / `confirmed_at` / `completed_at` / `cancelled_at` | timestamps | as the lifecycle moves |

**Order number** — the number is dictated over the phone, printed on the cutting PDF and typed
into a staff search box on a numeric keypad. That is the whole brief: short, digits only, no
meaning. Letters would need the lookalike normalisation the workshop code already carries;
six digits are short enough to say in two breaths.

*Why random, and why no branch or year segment.* A global **sequence** would let every
workshop — and every client — read the platform's volume off the gaps between their own
numbers. The number was `#26-14-0003` until 2026-09 — the third 2026 order of branch 14 —
which made it a small report as well as an identifier; but "the branch's Nth order this
year" is a finance-report question, answered off the report's own columns, so the segments
bought nothing and were parsed by app code that had no business parsing an identifier.

*Collisions.* The space is 900 000. At the operating envelope in
[`architecture.md`](../../architecture.md) — a few workshops, thousands of orders a year — a
retry on the `order_number` unique constraint is the whole collision strategy: no reservation
table, no sequence, no advisory lock. Creation redraws up to five times, then fails loudly
with `order_number_unavailable` rather than issuing a wrong number. Revisit at roughly
100 000 live orders, where a birthday-style collision stops being rare: widen to seven
digits, and nothing else moves, because the display groups from the right.

*Display.* Rendered everywhere as the numero sign, then groups of three from the right,
**U+2009 thin space separated — after the sign as well as between the groups**, one rule and
no other separator: **`№ 482 917`**. The prefix is not copy — it is emitted in every locale, by
`format_order_number` on the backend (which the cutting PDF also uses) and `formatOrderNumber`
on the web; the two emit byte-identical strings, and the vendored DejaVu pair carries U+2009 so
the PDF prints the thin space rather than a box. Search normalises the query by stripping `№`,
`#` and whitespace, so `№ 482 917`, `482 917` and `482917` are one number said three ways.

*Legacy era:* orders placed before this format keep their `#26-14-0003` and `ORD-2026-000123`
numbers **exactly as stored** — clients hold screenshots and printed cutting maps of them, and
nothing reformats history. Both pass through the formatter unchanged, and stay findable
because search ORs the normalised form beside a raw substring match.

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
| `price_overrides` | json | unit prices staff agreed for this order, replacing the branch rate card: `{cutting_rate_tiyin, edge_banding_rate_tiyin, material_prices: {<material_id>: tiyin}}` (a branch-material or customer-board id). Absent keys mean "use the branch's price". Kept on the order because it re-prices for other reasons too (a revision, a change of who supplies the sheets) and would otherwise fall back to the list price; a revision clears it along with the discount ([`orders.md`](../features/orders.md#pricing)) |
| `total_tiyin` | bigint | `cutting + materials + edge banding − discount + surcharge`; ≥ 0 |
| `currency` | enum | `UZS` (only value in v1) |

**Worker assignment + production stamps** (assignment is mutable until the job is done;
stamps are immutable once set and cleared by a revert of the step that set them — they are
the only input to the worker-production reports in [`finance.md`](../features/finance.md)).
The "set at" column names the **`full`**-mode action; on a `simple`-mode branch the
composite **Tayyor** writes the same columns for the steps it walks, all at one instant, and
its worker ids are optional and may stay `NULL`
([`orders.md`](../features/orders.md#production-mode)).

| Field | Type | Set at | Notes |
|---|---|---|---|
| `assigned_cutter_user_id` | UUID? | operator assigns | pure metadata — assignment does **not** change status; holds `process_production` on the branch; in simple mode set only by a Tayyor worker pick, and cleared by its undo |
| `assigned_edger_user_id` | UUID? | operator assigns | set when the order has banded parts; holds `process_production` on the branch; same simple-mode rule |
| `cutter_assigned_at` / `edger_assigned_at` | timestamp? | operator assigns | restamped on re-assignment; station-queue FIFO key; persists across reverts (except the simple-mode undo, which clears what its composite wrote) |
| `cutting_started_at` | timestamp? | **Start cutting** (`confirmed → cutting`) | cleared by revert `cutting → confirmed`; simple mode stamps it at Tayyor, equal to `cut_completed_at` |
| `banding_started_at` | timestamp? | **Start banding** (within `edge_banding`) | cleared by revert `edge_banding → cutting`; survives `ready → edge_banding`; simple mode stamps it at Tayyor unless a full-mode start had already written it |
| `cutter_user_id` | UUID? | `cutting → next` | the user credited (assignee, or the on-behalf "who did this work?" pick; in simple mode the optional completion-time pick, so it may stay null) |
| `cut_completed_at` | timestamp? | `cutting → next` | |
| `panels_used_snapshot` / `cut_count_snapshot` | int? | `cutting → next` | from the cutting result; production-report inputs |
| `edger_user_id` | UUID? | `edge_banding → ready` | the user credited; null when the order had no banded parts, and nullable in simple mode for the same reason as `cutter_user_id` |
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
machine only, in both production modes, and a status transition is never conditioned on the
mode the branch happens to run — the mode decides only which action writes it;
concurrent transitions serialize by `version`; `cutter_user_id` /
`edger_user_id`, when set, reference workshop users who hold `process_production` on
`branch_id`;
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
| `branch_material_id` | UUID? | logical reference to the panel **branch material** — one branch's carried [decor format](catalog.md#decor-format) (the snapshot is authoritative for the order) |
| `customer_board_id` | UUID? | set instead when the panel was a sheet the client brought — a [customer board](cutting.md#customer-board). **Exactly one of the two id columns is set**, enforced by a CHECK |
| `material_source` | enum | `shop` / `own` — for the panel; per-item; an order can mix |
| `material_snapshot` | json | `{ manufacturer_name, type, code, name, has_grain, thickness_mm, length_mm, width_mm, tape_width_mm, finished_sides, price_tiyin }` as of order creation, plus `customer_supplied` + `stock_material_id` on a customer board. Older rows keep the Uzbek vocabulary (`tur`, `kod`, `nomi`, `tolali`, `qalinlik_mm`, `uzunlik_mm`, `eni_mm`, `kromka_eni_mm`) and the oldest the pre-reshape English one (`color`, `decor_code`, `panel_length_mm`, `panel_width_mm`, `edge_width_mm`) — frozen history is never rewritten, and the label formatter reads all three |
| `part_ref` | text | the part's id (matches the cutting result's parts snapshot / placements) |
| `length_mm` / `width_mm` | int | within material / cutting bounds |
| `quantity` | int | ≥ 1 |
| `edge_top` / `edge_bottom` / `edge_left` / `edge_right` | json? | per side: either null (no banding) or `{ material_id, source, snapshot: { manufacturer_name, type, code, name, thickness_mm, tape_width_mm, price_tiyin } }`, where `material_id` is a `kromka` branch material (the JSON key kept its name; the values were rewritten, and older snapshots keep the vocabulary they were written with) |
| `unit_cutting_price_tiyin` | bigint | snapshot, ≥ 0 |
| `unit_material_price_tiyin` | bigint | snapshot; 0 when panel `material_source = own`; ≥ 0 |
| `edge_cost_tiyin` | bigint | snapshot for this line — sum across the four sides of `shop` edge cost; 0 when every banded side is `own`; ≥ 0 |
| `line_total_tiyin` | bigint | `(unit_cutting + unit_material) × quantity + edge_cost`; ≥ 0 |

Invariants: snapshot fields are never updated to reflect later catalog changes; `part_ref`
corresponds to a part in the order's cutting result; **exactly one** of `branch_material_id` /
`customer_board_id` is set (DB CHECK) — a line is cut either from a sheet the branch carries or
from one the client brought, and a reader that only prints the line never has to branch on
which, because the label and every price come from `material_snapshot` either way; the branch
material, when set, is one of a panel-shaped format; each side's edge `material_id` (when set)
is a `kromka` branch material; grain is a property of the panel's decor (read from
`material_snapshot`); parts on a grained material aren't rotated at cutting time; per-side `source` is independent and may differ across sides
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
`new → confirmed` with the same actor in one operation — as does a `simple`-mode branch's
composite **Tayyor** (and its undo) for the several production events it writes at once
([`orders.md`](../features/orders.md#the-simple-mode-collapse)); `to_status` is a legal transition
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
