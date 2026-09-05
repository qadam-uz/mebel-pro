---
title: Orders
status: draft
owner: shape
updated: 2026-09-05
order: 30
---

# Orders

The order lifecycle: a client places an order from a finished cutting — or workshop staff
place it for a walk-in client (see [Staff-created orders](#staff-created-orders-walk-in-clients))
— the workshop verifies it, production runs (step by step, or as one tap — see
[Production mode](#production-mode)), and the client collects it. v1 is **pickup-only**, the order
**never moves money** (the finance module records what the client paid —
[`finance.md`](finance.md)) and **never holds stock balances** (the inventory module
auto-decrements as production completes — [`catalog-inventory.md`](catalog-inventory.md)).
The order is the production spine; money and material are separate modules it triggers.

## Problem

An order today is a phone call, a verbal price, and a whiteboard. The client can't see the
price or the cutting plan, and the workshop can't trace who cut what. v1 makes ordering
self-serve, pricing automatic, the workflow restricted to a small state machine, and every
transition a recorded row.

## What an order is

A **client's request for panels cut to size at one branch** — the header that owns the
items, the status history, the production stamps, and a frozen price snapshot. Created
**by the client — or by workshop staff on behalf of a walk-in client** — from a cutting
**draft** with a **chosen algorithm result** (no order without one — the draft becomes
`confirmed` and is bound on creation; see [`cutting.md`](cutting.md)).

Set at creation:

- **Branch** — the draft's branch, carried straight through. A material *is* a branch's
  format ([`catalog-inventory.md`](catalog-inventory.md)), so the cutting is already bound to
  one branch by the time it has parts; the order step shows that branch and links back to the
  editor to change it, rather than offering a second choice. The branch **freezes pricing**
  against its rates.
- **Material source — per-item for panels, per-side for edges.** Each part is `shop` (the
  workshop supplies the panel; inventory auto-decrements for it) or `own` (the client
  brings the panel; cutting service only, no stock movement for that panel). Each banded
  edge side is independently `shop` (workshop supplies that tape; inventory decrements
  consumed length as integer millimetres internally, shown and priced as metres) or `own`
  (client brings the tape; no stock movement for that side). The data model and pricing
  support mixing sources at every level, but the **client cutting editor no longer offers
  `own`** ([`cutting.md`](cutting.md#parts-and-materials)) — new orders are fully `shop`;
  `own` remains meaningful for historical orders.
- **Handover — pickup only.** The client collects at the branch. Delivery is out of v1
  ([`scope.md`](../../scope.md)).

Post-placement modification is **workshop-side only**, pre-production — a staff **revision**
(see [Revising a placed order](#revising-a-placed-order)). The client's own path stays
cancel-and-reorder while `new`.

## Production mode

How much of production a branch actually operates is a **branch setting** —
`production_mode`, owner-only, alongside kerf and the edge overhang
([`workshop.md`](workshop.md)):

| Mode | What the branch runs |
|---|---|
| **`simple`** — the default | production is **one tap**: a `manage_orders` admin marks the order **Tayyor** when the job is done, and **Olib ketdi** when the client takes it. No assignment, no start taps, no station queues, no worker account required. |
| **`full`** — the owner opts in | the per-stage choreography below: assign a cutter and an edger, the worker starts each job, each stage is completed at its own station. |

**Why simple is the default.** In the shops we visited the floor runs on paper — the saw
operator and the bander never touch a screen; the admin is the only person at one. The
per-stage taps therefore never happened, and since the **stock seam hangs off those taps**,
the warehouse — the module the shops themselves named as their pain — silently died with
them. Simple mode buys the warehouse back at the price of one honest tap. **The paper stays
the floor interface**: the system runs up to the printed cutting map and resumes when the
admin says the job is done. Nothing in simple mode may require a worker account, an
assignment, or a start tap. Every branch is `simple` unless its owner says otherwise —
including branches that predate the setting; `full` is the opt-in for a shop that genuinely
staffs two stations and wants the queues.

**Simple mode is a collapse, not a fork.** The six-status spine below stays authoritative in
both modes, and so does every effect it drives — stock, stamps, events, audit, reports. One
composite action writes the *remaining* spine events in a single transaction, reusing each
step's own effect logic; it is the same pattern the walk-in
[auto-confirm](#staff-created-orders-walk-in-clients) already uses for `∅ → new → confirmed`.

**The mode is read at the moment of the action, never stamped on the order.** Any order is
valid in either mode and switching migrates nothing: a `confirmed` order simply regains its
assignment and start actions on simple → full, and an order caught mid-spine on full →
simple is finished by the composite **Tayyor**, which completes only what is left.

**The two flows' surfaces are exclusive**, so no branch ever has two ways to move the same
order. On a simple branch the per-step production operations — assign, start cutting, start
banding, cutting done, banding done, single-step revert — are refused with
`simple_mode_active`; on a full branch the composite Tayyor and Orqaga are refused with
`full_mode_active`. Both carry the branch's actual mode, and the app refetches on either.
Everything outside production — approve, cancel, mark collected, discount, surcharge, order
prices, own-material, the internal note, and revision — is **mode-independent** and behaves
identically. So is what the client sees ([UX — client app](#ux-client-app)).

## Staff-created orders (walk-in clients)

A walk-in customer at the counter has no app session. Staff holding
`manage_orders` on the branch place the order **for** them, through the **same cutting
editor the client app uses** ([`cutting.md`](cutting.md#workshop-side)) — the walk-in flow
parameterizes the client flow, it doesn't fork it. The flow:

1. **Entry** — the shell's **+ Yangi buyurtma** action in the workshop sidebar, enabled only
   when the staffer holds `manage_orders` on the **currently selected branch** and that branch
   is `active`; otherwise it renders disabled with a hint to switch branch. It lives in the
   sidebar rather than on the Orders screen because it is the app's most-run task and belongs
   to no single list.
2. **Walk-in resolve** — phone-first find-or-create: the phone is looked up as the staffer
   types (a read-only lookup, separate from the create); a match fills the registered name
   into a read-only field with a caption, on the same screen — there is no second confirm
   step; the name is asked only when the number is new; a blocked account reads as a miss. Semantics,
   guardrails, and the decision rationale live in
   [`access-management.md`](access-management.md#staff-resolved-walk-ins-find-or-create).
3. **Shared editor** — the client app's editor in fixed-branch mode: the branch is locked
   to the entry branch and frozen into the draft at creation, and a persistent strip names
   the walk-in (name + phone). Draft visibility and lifecycle rules:
   [`cutting.md`](cutting.md#access).
4. **Checkout** — single-branch: a quote at the locked branch, contact prefilled from the
   resolved client, **Place order**. Pricing setup gaps fail with the same error codes as
   the client path (see [Pricing](#pricing)); the error copy names the branch and that the
   owner sets its pricing.
5. **The order lands `confirmed`** and opens on its detail. From `confirmed` onward a
   staff-created order is indistinguishable from a client-placed one — same state machine,
   same stock and money seams.

**Create + auto-confirm.** A staff-placed order is created and confirmed in one operation:
two append-only status events are written (`∅ → new`, `new → confirmed`), both with
`actor_type = workshop_user` and the acting staffer's id, and **`confirmed_at` is set to
creation time**. The standard `order.confirmed` client notification fires as usual — the
walk-in sees it, along with the order in their history, after they first sign in through
the Telegram bot with the same phone.

**Why auto-confirm.** The `new → confirmed` gate exists so staff verify a *client's*
self-serve order; a staff-placed order is verified by construction — the same staffer just
built it with the client at the counter. Landing it at `new` for a second Approve tap would
be ceremony (two events, same actor, seconds apart), while skipping the `∅ → new` event
would break the append-only spine every timeline and report reads — so both events are
written atomically, by the same actor. Revisit if workshops ask for a second-person review
of staff-placed orders — then drop the auto-confirm and land staff orders at `new` like any
other.

## Revising a placed order

Staff holding `manage_orders` on the order's branch may revise the order's **cutting
content** — parts, dimensions, quantities, materials, per-side edge picks — while the order
is `new` or `confirmed`. From `cutting` onward nothing is editable (material may already be
cut; if the start itself was the mistake, revert first). The client has no self-serve edit —
their path stays cancel-and-reorder while `new`; revisit if workshops field frequent
pre-approval "change one size" calls that a phone-driven staff revision doesn't cover.

The revision is a **scratchpad draft, applied atomically**:

1. **Edit** on the order detail creates — or resumes — the order's **revision draft**: a
   staff-scoped cutting draft seeded from the confirmed result's parts, branch-locked to the
   order's branch, linked back to the order (`revision_of_order_id`,
   [`cutting` entities](../entities/cutting.md)). One revision per order; Edit is
   idempotent. The order itself is untouched — approving, assigning, discounting, and
   cancelling all stay available while a revision sits open.
2. Staff edit in the **same shared cutting editor** as the walk-in flow — parts UI,
   optimise, result pick — with a persistent strip naming the order being revised.
3. **Review & save** shows the current frozen price next to the new quote at the order's
   branch. Saving atomically: rebinds the order to the new chosen result (the superseded
   confirmed result and its panels are deleted), replaces the item snapshots, **re-freezes
   pricing at the branch's current rates**, clears any discount and surcharge, clears the
   edger assignment when no side needs banding any more, bumps the order `version`, appends an `edited`
   status event (same-status, staff actor, old/new totals in metadata), mirrors to the audit
   log, and notifies the client (`order.updated`).
4. **Discard** deletes the revision draft; the order never notices.

Rules:

- **Same branch, same client — always.** A different branch or client is a cancel +
  re-create; keeping both fixed lets one quote path and one carry check serve create and
  revise alike.
- **Re-pricing is whole-snapshot, at current rates.** A revision replaces the frozen price;
  it never patches line items. If catalog prices moved since placement the new freeze
  reflects them — the review screen makes the delta explicit before saving.
- **Neither the discount nor the surcharge survives a revision.** Both were granted against
  the old contents; re-apply either (reason + audit, as always) if still warranted.
- **Save is guarded like a transition**: optimistic `version` check, status re-checked at
  save (`order_edit_not_allowed` once production started or the order went terminal), and
  the same pricing/carry error codes as placement. A revision that outlived its window can
  only be discarded.
- **Status never changes on a revision** — `new` stays `new`, `confirmed` stays `confirmed`.
  The staffer saving the revision has just re-verified the content; forcing a re-approve
  would be the same ceremony the staff-create auto-confirm avoids.
- **A revision draft never places a new order.** Checkout rejects it; its only exit is
  apply or discard. It is invisible to the client like any staff-minted draft.

## The state machine

One straight spine with a single gateway — *does any part need edge banding?* Read it top to
bottom: the solid path is the happy flow and the dashed arrows are the operator **revert**
(one step back, a mistake fix). **Cancellation is not drawn** — it would cross every box:
any non-terminal status can go to `cancelled` (see the table below).

**This spine is authoritative in both [production modes](#production-mode).** It is drawn
here as full mode taps it — one action per arrow; simple mode walks the same arrows and
writes the same events, several at a time
([The simple-mode collapse](#the-simple-mode-collapse)).

```mermaid
flowchart TD
    start([▶ order placed]) --> new[new<br/>placed · awaiting review]
    new -->|operator approves| confirmed[confirmed<br/>verified · assigned · queued]
    confirmed -->|assigned cutter starts| cutting[cutting<br/>cutter at the saw]
    cutting -->|Cutting done| gate{any part<br/>edge-banded?}
    gate -->|yes| edge_banding[edge_banding<br/>edger working]
    gate -->|no| ready[ready<br/>awaiting collection]
    edge_banding -->|Banding done| ready
    ready -->|operator marks collected| done([● completed])

    cutting -. "revert" .-> confirmed
    edge_banding -. "revert" .-> cutting
    ready -. "revert" .-> edge_banding
```

`completed` and `cancelled` are **terminal**. A post-collection problem (return, complaint)
is out of v1 ([`scope.md`](../../scope.md)) — `completed` is final by design.
`edge_banding` is skipped when no part is banded (the gateway's *no* branch).

### Transitions

Who triggers each step (by per-branch grant — there are no fixed roles), and its effects.
The four production rows are how a **`full`**-mode branch taps them; a simple branch reaches
the same rows through one composite action, with the same effects
([below](#the-simple-mode-collapse)).

| From → To | Trigger · who | Effect |
|---|---|---|
| — → `new` | client places the order from a chosen cutting result · or `manage_orders` staff place it for a walk-in ([Staff-created orders](#staff-created-orders-walk-in-clients)) | price snapshot frozen |
| `new → confirmed` | **Approve** · `manage_orders` (reviewed, client called) · automatic on a staff-created order (same staff actor, same operation) | — |
| `new → cancelled` | **Cancel** · client (only while `new`) or `manage_orders` + reason | — |
| `confirmed → cutting` | **Start cutting** · `process_production` (the assigned cutter), or `manage_orders` on-behalf — requires a cutter assigned | stamp `cutting_started_at` |
| `cutting → edge_banding` | **Cutting done** · `process_production`, or `manage_orders` on-behalf — *gateway: a part is banded* | stamp the cutter + snapshot; **decrement panel stock** (`shop` panels) |
| `cutting → ready` | **Cutting done** · same — *gateway: no part is banded* | stamp the cutter + snapshot; **decrement panel stock** (`shop` panels) |
| `edge_banding → ready` | **Banding done** · `process_production`, or `manage_orders` on-behalf | stamp the edger + snapshot; **decrement edge stock per edge material** (`shop` sides only) |
| `ready → completed` | **Mark collected** · `manage_orders` | stamp `picked_up_at` |
| `* → cancelled` | **Cancel** · `manage_orders` + reason (any pre-`completed` status) | already-decremented material stays consumed |
| revert: `cutting→confirmed`, `edge_banding→cutting`, `ready→edge_banding\|cutting` | **Revert** one step · `manage_orders` + reason | clears that step's stamps; **re-increments** the stock it decremented |

### The simple-mode collapse

On a [`simple`](#production-mode) branch the same spine is walked by two composite actions,
both `manage_orders`, both one transaction with the usual optimistic `version` check. The
lifecycle the admin actually sees:

| Step | Trigger | Internal effect |
|---|---|---|
| order placed | client app or the walk-in counter, unchanged | `∅ → new` (walk-in: auto-confirm to `confirmed`) |
| **Tasdiqlash** (client orders only) | `manage_orders` | `new → confirmed`, with the projected-stock warning and the `order_has_unpriced_materials` gate, unchanged |
| **Tayyor** | `manage_orders`, one tap + confirm dialog | every spine event still owed, through to `ready` |
| **Olib ketdi** | `manage_orders` | `ready → completed`, unchanged |
| **Orqaga** | `manage_orders` + reason | composite revert `ready → … → confirmed` |
| **Cancel** | unchanged | any non-terminal + reason |

A walk-in order is therefore **two taps** end to end, a client order three.

**Tayyor** is accepted from `confirmed`, `cutting`, or `edge_banding` — the latter two being
full → simple leftovers. It walks the remaining transitions in order, each guarded by the
status the order has reached *by then* and each **running that step's existing effect
logic**, so no decrement can fire twice: `confirmed → cutting` (event only), then the
cutting completion (cutter + snapshots stamped, **panel stock decremented**) through the
gateway, then, when a side is banded, the banding completion (edger +
`edge_length_snapshot` stamped, **edge stock decremented**). An order already past a step
gets only what remains. Every event is an ordinary `order_status_event` with the acting
staffer as actor — the append-only spine and its audit rows are untouched — and the client
gets exactly one notification, `order.ready`, from the final event.

**Worker credit is optional and picked at completion.** The dialog offers a cutter and (when
a side is banded) an edger from the branch's `process_production` holders, validated exactly
as an assignment is. Picked, the ids land in `cutter_user_id` / `edger_user_id` with
assignment stamps, and the production reports work unchanged — the snapshot counters replace
the cutter's paper tally. Left empty they stay `NULL` and the order still completes: in
simple mode **worker accounts are a reporting dimension, not a gate**. A shop that wants
per-worker figures creates accounts for its workers and never hands them a tablet. This is
the counterpart of full mode's "completion credits the assignee, never a completion-time
pick" ([Rules](#rules)) — that rule presumes an assignment, and simple mode has none, so
completion-time *is* the pick.

**Orqaga** is the whole Tayyor taken back, from `ready` only, reason required. It chains the
existing single-step reverts to `confirmed` — `ready → edge_banding → cutting → confirmed`,
or `ready → cutting` for an unbanded order — so each step re-increments exactly what it
decremented and clears exactly the stamps it wrote, the composite's worker ids and
assignment stamps included. One revert event per step, all carrying the same reason. There
is **no partial undo**: a shop that needs step-level surgery switches the branch to full
mode. Never out of `completed`, as with any revert.

### Rules

Assignment, starts, and per-stage completion are the **`full`**-mode choreography, so the
first five rules below describe that mode; the last three hold in both. Simple mode's
counterparts are in [The simple-mode collapse](#the-simple-mode-collapse).

- **Assignment is metadata, not a trigger.** `manage_orders` staff assign the cutter and
  edger once the order is `confirmed`; assigning stamps `cutter_assigned_at` /
  `edger_assigned_at` and orders the station queue, but the order **stays `confirmed`**
  until the cutter starts. There is **no self-claiming** — a worker only sees and starts
  work already assigned to them. *Why the split:* when assignment itself flipped the
  status, "cutting" meant "a name was typed into a form", the queue/in-progress
  distinction was fake, and job durations were unknowable. **Revisited 2026-08-31 — and
  resolved the other way.** The field visits met that revisit condition and then some: the
  shops were not leaning on on-behalf, they were not tapping at all. Folding start into
  assign would have kept a choreography nobody performs; instead the whole choreography
  became opt-in and [simple mode](#production-mode) is the default. Full mode keeps the
  split, unchanged, for the shops that do staff two stations.
- **The worker starts the job.** **Start cutting** (`confirmed → cutting`) and **Start
  banding** (a stamp within `edge_banding`, no status change) are one-tap actions by the
  assigned worker — or `manage_orders` on-behalf. "In production" therefore means a
  machine is actually running — on the workshop's own screens. The **client's** track does
  not carry that distinction in either mode: it reads *Tayyorlanmoqda* from `confirmed`
  onward ([UX — client app](#ux-client-app)).
- **Each stage gates on its own worker, at its own start.** Start cutting requires only
  the assigned cutter (`cutter_required`); Start banding requires an assigned edger
  (`edger_required`). A banded order may start cutting with the edger slot still open —
  the saw never waits on a later stage's staffing; the office fills the slot while
  cutting runs, and the board and order detail flag the open slot from `cutting` on. An
  order can therefore sit in `edge_banding` unassigned; banding cannot start until the
  slot is filled.
- **One button per job; no per-item work.** Workers don't manage line items. The cutter
  views the cutting plan read-only and marks **Cutting done** once; the edger marks
  **Banding done** once. A `manage_orders` user may complete a job **on behalf** (worker
  absent / system issue) — completion always **credits the assigned worker** in the
  production reports ([`finance.md`](finance.md)); changing who gets credit is a
  deliberate revert → reassign, never a completion-time pick. This is a **full-mode** rule:
  it exists because there *is* an assignment to be faithful to. Simple mode has none, so
  its Tayyor dialog picks the credit at completion — optionally, and it may be left empty.
- **Re-assignment locks when the stage starts.** The cutter can be changed only while the
  order is `confirmed`; the edger until banding is stamped started (so still swappable while
  cutting runs). After the lock the deliberate path is a **revert** — it clears the start
  stamp and reopens assignment — never a silent mid-job swap that would re-credit running
  work.
- **Revert is mistake-correction only** — never out of `completed` or `cancelled`. One step
  at a time in full mode; in simple mode the whole composite comes back at once, because
  there was only ever one action to undo.
- **Every transition is an `order_status_event`** (actor, from → to, reason, metadata),
  append-only, mirrored to the audit log.
- **Optimistic locking** on transitions (a `version` column): concurrent staff actions
  serialize; the loser is told to refresh and retry.

### Production stamps

The cutter and edger are workshop users holding `process_production` on the order's branch,
with `home_branch_id = order.branch_id` — **except the owner**, who holds
`process_production` on every branch implicitly and may be assigned as cutter or edger on
any branch regardless of their `home_branch_id` (a one-person shop's owner floats between
branches; the constraint exists to keep non-owner staff at the branch they physically work
at, and the owner has no such home). No separate worker entity — see
[`access-patterns.md`](../../access-patterns.md). The system stamps the order at each job's
completion; these stamps are the **only** input to the worker-production reports the
accountant uses ([`finance.md`](finance.md)).

| Stamp | Set at | Read by |
|---|---|---|
| `cutter_assigned_at`, `edger_assigned_at` | assignment (re-assignment restamps) | station queue order (FIFO by assignment) |
| `cutting_started_at` | **Start cutting** (`confirmed → cutting`) | station WIP · start→done durations |
| `banding_started_at` | **Start banding** (within `edge_banding`) | station WIP · start→done durations |
| `cutter_user_id`, `cut_completed_at`, `panels_used_snapshot`, `cut_count_snapshot` | `cutting → next` | production report (panels / cuts) |
| `edger_user_id`, `edge_completed_at`, `edge_length_snapshot` (by edge material) | `edge_banding → ready` | production report (metres of banding) |
| `picked_up_at` | `ready → completed` | client notify · audit |

One cutter, one edger per order in v1. Completion stamps are immutable once set, written in
the same atomic transaction as the transition, and **cleared by a revert** of the step that
set them. Start stamps follow the phase: a revert that leaves a phase clears its start
(`cutting → confirmed` clears `cutting_started_at`; `edge_banding → cutting` clears
`banding_started_at`), while `ready → edge_banding` keeps `banding_started_at` — banding had
genuinely started. Assignment stamps persist across reverts.

**Simple-mode stamps carry one instant.** The composite Tayyor writes every start and
completion stamp at the action time, so `cutting_started_at = cut_completed_at` and, for a
banded order, `banding_started_at = edge_completed_at`. The invariant (start ≤ complete)
holds; the durations are zero by construction and render as **"—"** rather than "0 min",
and a zero-duration row is excluded from any average. The admin is recording a finished job,
not driving a stopwatch. A start stamp a **previous full-mode tap already wrote** on a
leftover is left alone — that duration was real. `cutter_user_id` and `edger_user_id` may
also be `NULL` on a completed simple-mode order; the production report groups those under a
**Belgilanmagan** bucket ([`finance.md`](finance.md)) so the accountant still sees the
volume, and such rows never reach a per-worker pay view. Station queues only ever hold
assigned jobs, so simple-mode orders never appear in one.

## The stock seam

Driven entirely by this state machine; the mechanics live in
[`catalog-inventory.md`](catalog-inventory.md). The contract:

- **No reservation.** Verification is **never blocked** by low stock — some workshops buy
  per order. At approval the operator sees a **warning** if a `shop` material's projected
  balance won't cover this order (projected = on-hand minus the not-yet-decremented demand
  of active orders ahead), so they can prompt the warehouseman. It is a warning, not a
  gate.
- **Auto-decrement at job completion.** `shop` panels decrement at the **cutting**
  completion; each `shop` edge material's **consumed length** decrements at the **banding**
  completion (one inventory transaction per edge material the order's `edge_length_snapshot`
  carries with shop millimetres — these are **consumed** metres when displayed/priced, see *Pricing*). A
  revert re-increments exactly what its step decremented. On a **`full`**-mode branch those
  are the two separate **Cutting done** / **Banding done** taps; on a **`simple`** branch the
  composite **Tayyor** runs both completions in one transaction, so panels **and** edges
  decrement together at that single moment ([Production mode](#production-mode)). The
  contract is otherwise identical — same effects, same restores, same figures. Which taps
  the seam hangs off is precisely why the mode exists: hung off taps a paper-run shop never
  makes, the warehouse silently stopped moving. The edge figure stays the **optimiser's
  consumed metres** in both modes, never the bander's actual tape; drift is reconciled by
  ordinary inventory adjustments. Revisit if shops ask to type real metres at Tayyor.
- **Staff set the unit prices, up to production.** A counter negotiates the *rate* — "these
  sheets at 250 000, not 300 000" — so `manage_orders` may replace the branch rate card for
  one order while it is `new` or `confirmed`: the per-sheet price of each panel material, the
  per-metre price of each tape, the cutting rate and the banding rate. **Quantities are never
  editable**: how many sheets a layout needs is the optimiser's answer, and retyping it would
  put the bill and the cutting plan out of step. A discount can reach the same total, but only
  as one lump on the bottom line; the receipt has to show the price the client was quoted per
  sheet, which is why this is its own action rather than a bigger discount.
  The agreement is stored on the order, not only in the item snapshots, because the order
  re-prices for other reasons too — without a home there, the next re-price would quietly
  restore the branch's list price under the agreed one. A **revision** does clear it: that
  re-prices the whole snapshot at current rates by definition, the same rule that already
  clears the discount and the surcharge. Every change appends a same-status event carrying the
  old and new agreement and the old and new total.
- **Staff set it on the order, up to production.** The counter usually hears "I'll bring my
  own" while reading the order back at approval, so `manage_orders` may set the client's
  sheet counts on a `new` or `confirmed` order — the same window as a discount. The layout
  does not move; only who pays for the sheets it uses, so the order re-prices in the same
  transaction and appends a same-status event. A negotiated discount survives, clamped only
  if the smaller subtotal can no longer carry it. Past `confirmed` the sheets may be cut and
  the stock seam has already run, so the claim is frozen with them. **The branch's
  `own_material_allowed` does not gate this** — that setting is about what a client may
  arrange unattended in the app ([`workshop.md`](workshop.md)), not what the shop can take
  in at the counter.
- **The order names what the client owes.** Each price line carries the client's share
  (`own_panels` / `own_mm`) beside the charged figure rather than folded into it, so a
  material the client supplies entirely reads as "you bring 4 sheets" instead of a free
  `0 sheets` line. Both order screens surface the list before anything else: the workshop's
  in the production card, above the cutter picker, because the shop cannot start without it;
  the client's above the tabs, because it is the only thing on that page they must act on.
- **`own` parts and `own` edge sides never touch stock.** An order with no `shop` panels
  and no `shop` edge sides skips this seam entirely. A material the client supplies **every**
  sheet of nets to a zero demand rather than disappearing — pricing still has to check the
  branch carries it — and a zero demand is skipped at the seam rather than written as a
  no-op movement.
- **After decrement, material is spent.** Cancelling an order whose panels/edges were
  already decremented does **not** restore them (they were physically cut); the loss is
  the workshop's, recorded offline.

## The money seam

The order **never holds payments or refunds**. All money lives in the finance module
([`finance.md`](finance.md)): an accountant (`manage_finance`) records an *income* against
the order — the amount the client actually paid (full or partial) and the date — at the
counter. No in-system payment, no gateway, no payment-driven status.

- **One disclosure rule.** Split the order's money into two parts and gate them
  differently:
  - The **frozen total + price breakdown** is visible to the client **from placement
    onward** (the Overview tab) — including any workshop-applied discount (−) and
    surcharge (+) lines, each with its reason. The client already saw the computed
    figures in the order wizard; pricing is frozen at creation and never re-priced, so
    there is nothing to hide and hiding it only confuses ("what will this cost?").
  - The **settlement figures** — recorded-so-far and balance — appear to the client
    **only at `ready` and `completed`** (the Finance tab), the moment they need to settle
    on collection and the receipt afterwards. There is no in-app payment action; a
    discrepancy ("I paid, it's not marked") is resolved out-of-system by calling the
    workshop.
  - **Workshop side.** Staff with `view_finance_reports` or `manage_finance` see a read-only
    settlement summary (total / recorded / balance) on the order detail at **any** status,
    sourced from the finance module — distinct from the client's ready/completed gate.
  - **Taking the money is the one write this page offers.** While a balance is outstanding,
    `manage_finance` gets a **To'lov qabul qilish** action beside the settlement: amount
    (prefilled with the balance, capped by it), method, date, note. It writes an ordinary
    `order_payment` income — the order still holds no money — and the settlement re-reads.
    The counter is one person, and sending them to Moliya to search for the order they
    already have open is four steps and a second search. Everything else about that money —
    editing, voiding, any other row — happens in the finance module
    ([`finance.md`](finance.md)), where a correction carries a reason and an audit trail.
    Several payments may be recorded for one order, at any status, so an advance at the
    counter and the balance at pickup are the same flow twice.
- **Cancellation never creates a refund record.** If money must go back, the accountant
  books an *expense* in the finance module. A cancelled order carries only its reason.

## Pricing

The system computes everything; the **two manual adjustments — a discount and a surcharge —
are the only human inputs**, each needing a reason. Frozen onto the order at creation
against the chosen branch's rates; later catalog or pricing changes never reach an existing
order on their own — the one re-pricing path is a workshop
[revision](#revising-a-placed-order), which replaces the whole freeze at the branch's
current rates.

| Component | When | Source |
|---|---|---|
| Cutting service | always | the branch's `cutting_rate_tiyin` × the chosen result's total panels — one rate, applied per panel cut (v1's only model) |
| Panel materials | parts with `material_source = shop` | Σ (the branch's per-panel price × panels attributable to that material's `shop` parts) |
| Edge materials | per side, when the side has an edge material and `source = shop` | Σ (**consumed metres** of that tape × the branch's per-metre **raw material** price on that `kromka` branch material) |
| Edge banding labour | when any `shop` side has banding | total `shop` **consumed metres** of banding × the branch's `edge_banding_rate_tiyin` (one labour rate, all thicknesses) |
| Discount (chegirma) | when a `manage_orders` user adds one | percent or fixed sum; **subtracted**; capped at the computed subtotal (a discount never makes the price negative); **reason + the user id recorded** (audited) |
| Surcharge (ustama) | when a `manage_orders` user adds one | percent or fixed sum; **added**; no enforced cap in v1 — the reason + audit are the control; **reason + the user id recorded** (audited) |

**Total = cutting + panel materials + edge materials + edge banding labour − discount + surcharge.**

Discount and surcharge are **independent** — an order may carry both (e.g. a rush surcharge
and a loyalty discount), each with its own reason and applied-by stamp. Each is applied on a
`new` or `confirmed` order by a `manage_orders` user; both lock once production starts.
Setting an adjustment to zero clears its reason and stamp. The percent form resolves against
the computed subtotal at apply time and is stored as the resolved sum — the order keeps the
absolute tiyin figure, not the percentage.

**Consumed metres.** A banded side eats more tape than its visible edge: the master glues
it long and trims it flush after. So edge metres — the single figure behind the
edge-material price, the banding labour, the client's tape total, **and** the stock
decrement — are **consumed**, not geometric:

> consumed metres (per edge material) = the cutting result's geometric `edge_length_by_material`
> + the branch's `edge_overhang_mm` × the order's banded `shop` sides for that material

The overhang is a **branch setting** — `edge_overhang_mm` on the branch, default 30 mm, set
by the owner on the branch form ([`workshop.md`](workshop.md)) — because how long a bander
glues and how much they trim back is a property of that shop floor's machine and habit, not
of the platform. It is added **once per banded side**, not once per part: a piece banded on
four sides carries it four times. The banded-side count comes from the order's own per-side
edge picks; `own` sides are neither billed nor decremented, so they don't enter the sum.

The overhang is resolved from the draft's branch at optimisation time, exactly as kerf and
edge trim are, so the consumed figure is known from the **cutting result** onward and the
client sees real metres in the wizard ([`cutting.md`](cutting.md)); only the *price* waits on
the branch's rates. A draft with no branch chosen yet falls back to the platform default,
and switching branch re-optimises against the new one. One figure downstream — no separate
geometric-vs-consumed columns.

**Operational setup gaps fail loudly.** If the branch has no cutting rate set, or has banded
parts but no edge-banding labour rate set, or doesn't carry an edge material a part uses,
order creation fails with a clear error — the owner must fix the branch's rates or attach the
missing format ([`catalog-inventory.md`](catalog-inventory.md)). The relevant error codes:
`missing_cutting_rate`, `missing_edge_banding_rate`, `branch_does_not_carry_panel`,
`branch_does_not_carry_edge`.

**An unpriced material stops the order at confirm, not before.** Both catalogs list formats
the branch carries but has not priced, so an order can arrive selling one. A draft may hold
it and a quote may show it — confirming is the step that turns an order into money owed, so
that is where the line is drawn: `new → confirmed` is refused with
`order_has_unpriced_materials` while any material the order **sells** resolves to zero, and
the error names them. Staff clear it with an order-level price, which prices the material for
this order without touching the branch's rate card. Two cases deliberately pass: a material
the client supplied entirely (the workshop sells none of it, so it needs no price), and a
material deactivated after the order was placed (it still has to be paid for, and re-checking
the catalog here would resurrect the failure the [stock seam](#the-stock-seam) exists to
avoid).

## UX — client app

The client app is **phone-first**: below `md` a five-tab bottom bar (Bosh sahifa · Chizmalar ·
Buyurtmalar · Ustaxona · Profil) replaces the desktop header nav, and the focused screens —
the cutting editor, the result stage, the order confirmation, the entry landing, login — carry
no shell chrome at all, because each already has its own way back.

Home (`/c`) leads with **what needs attention now**, and on every list here **the row or card
is the link** — no per-row **Batafsil** or **Kuzatish** button, and no second tap target
inside a card that is one. The order's branch is the one the draft already carries in its
`preferred_branch_id` — settled before the editor opened, from the client's pin or the branch
row the drawing was started from ([`client-entry.md`](client-entry.md)); placement reads it
rather than asking again.

Order numbers print through the formatter everywhere — `№ 482 917`, or a legacy number
verbatim ([`sales.md`](../entities/sales.md)).

**The client track is four phases, and it is the same in both
[production modes](#production-mode)** — the status pills, the orders-list filter chips and
the four client notifications all run off it. It is a **vocabulary**, not a widget: the phase
strip, the progress fraction and the next-phase line that used to render it were removed from
the client screens in 2026-09 (a bar that jumps between two of four positions measured
nothing the pill did not already say), while the phases themselves are unchanged.

| Phase | Internal statuses | Sub-line |
|---|---|---|
| **Yangi** | `new` | *Ustaxona tasdiqlashi kutilmoqda* |
| **Tayyorlanmoqda** | `confirmed`, `cutting`, `edge_banding` | *Ishlab chiqarish jarayonida* |
| **Tayyor** | `ready` | *Olib ketishingiz mumkin* |
| **Olib ketildi** | `completed` | — |

`cancelled` is terminal and off-track, shown as its own **Bekor qilindi** pill.

*Why one phase for the three production statuses.* The client can act on exactly one thing —
whether the order is collectable — and a queued-vs-sawing distinction is not client value,
it is workshop kitchen. Splitting it also made the track depend on how the workshop is run:
a full-mode order crawled through two extra phases, a simple-mode one would jump them. A
client with orders at two branches in different modes sees the identical track on both; only
the timing differs. **Stability beats fake precision.**

*Why these words.* **Tayyorlanmoqda** says what is happening rather than what the workshop
clicked, and it self-explains against the next phase — *Tayyorlanmoqda → Tayyor* reads as a
progression without a legend. **Olib ketildi** is the truth of the terminal status (a
completed order is a collected order) and mirrors the **Olib ketdi** action that produces
it; that symmetry between the button and the resulting status is deliberate. Both replaced
earlier labels (*Tasdiqlandi* / *Yakunlandi*) on 2026-08-31.

Consequently the client is notified on exactly **four order-status events** —
`order.confirmed`, `order.ready`, `order.completed`, `order.cancelled`. The intermediate
`cutting` / `edge_banding` transitions produce no client notification **in either mode**;
inbox rows written before that (`order.status_changed`) still render
([`notifications.md`](notifications.md)). A revision still notifies separately
(`order.updated`, see [Revising a placed order](#revising-a-placed-order)).

- **Home dashboard** (`/c`) — `Salom, {ism}` alone on the greeting row, then, in order: the
  **Ustaxonangiz** card (the client's pinned branch — logo, name, address, tap-to-call phone,
  a pill only when the branch is `temporarily_closed`; the card body links to the workshop
  profile, [`client-entry.md`](client-entry.md) owns it), the page's one primary
  **+ Yangi chizma** directly under the card and outside it, a **ready-for-pickup** banner for
  the first `ready` order (number, branch, total, a *yana N ta tayyor* hint — and **no
  action**, because «Olib ketdi» is the workshop's mark at the counter, so the banner informs
  and links), **Faol buyurtmalar** (at most four rows, `Barchasi →` to the filtered list) and
  **Davom ettirish** (at most three drafts; a chosen result opens the result stage, otherwise
  the editor). Empty sections are omitted rather than shown empty, and a pinned client with
  nothing active and no drafts gets one first-run prompt under the card.
  **Un-pinned** — no card, no drawing action anywhere on the page: the **Ustaxona tanlang**
  prompt takes the card's place and opens Ustaxonalarim, because a drawing needs a branch.

  *What went, and why.* The pinned line under the greeting read like a staff badge — the
  client is not the workshop's employee — and the three-up count strip beside it overlapped
  itself (Tayyorlanmoqda ⊂ Faol) while being untappable; the per-row progress bars measured
  two of four positions. All three were removed on 2026-09-03/04, and the trust cue they
  carried moved into the Ustaxonangiz card, which is a thing the client can actually use.

- **Cutting wizard** — see [`cutting.md`](cutting.md). Entry point and where the client
  spends most of their time.
- **Order confirmation** (`/c/orders/new/:draftId`) — opens from the cutting result's order
  button. The branch was settled before the drawing opened; this stage never lists or compares
  branches. It pre-checks that the draft still has a chosen result and preferred branch, quotes
  only that branch, and renders one page: the **Ustaxona** block as read-only pickup context, a
  **Mijoz** card, and the price summary with the drawing's four figures (Detallar · Listlar ·
  Kromka · Foydali qoldiq — [`cutting.md`](cutting.md)) under it.

  - **Mijoz** — **Ism** and **Telefon**, prefilled from the profile and editable inline, under
    a muted label-style line, *"Ustaxona siz bilan bog'lanishi uchun"*, rather than an info
    banner; the values are frozen onto the order as the workshop-facing contact snapshot and
    the profile is not overwritten until the order is placed. There is no reset-to-profile
    action — two fields already carry the profile's values, and a link to re-fetch what is
    already in the box was a control for a problem nobody had.
  - **The phone must be an Uzbek number** (`+998` + 9 digits). A Telegram sign-up can bring in
    a foreign number, and a workshop that cannot dial its client cannot serve them, so a
    foreign number is rejected on blur and on submit with *"O'zbekiston raqami kerak:
    +998 XX XXX XX XX"* and the confirm button stays disabled until it is fixed.
  - **Own material is not offered here** — nor anywhere else in the client app in the MVP
    ([`cutting.md`](cutting.md#parts-and-materials)).

  A closed branch, incomplete branch pricing, or material-carrying failure blocks confirmation
  with the branch-specific reason and a retry/back-to-details path; it never falls back to a
  comparison list. The client does not choose a payment plan and pays nothing online — payment is
  recorded by the workshop's accountant at the counter ([`finance.md`](finance.md)). On
  success → `/c/orders/:id` with a banner: *"Buyurtma berildi — ustaxona ko'rib chiqib siz
  bilan bog'lanadi."*

- **My orders** (`/c/orders`) — a segmented chip row (**Hammasi · Faol · Tayyor ·
  Yakunlangan · Bekor**) mirrored into `?status=`, so the home's `Barchasi →` and the browser
  back button both land on the right filter, plus a search icon-button that expands into the
  input (drawing names are searchable too, so the field stays plain text). **The card is the
  link**: left column `№ 482 917` in bold, the draft name as the headline **only when there is
  one** (an untitled drawing shows no headline — a grey "Nomsiz chizma" placeholder was the
  worst thing on the card), the `created_via_workshop` pill after it, then
  `{workshop} · {branch}` and `{n} detal · {m} list · {sana}` as two short lines. Right column,
  top-aligned: the status pill and the **frozen total** beneath it — shown from placement, never
  "price after confirm", since pricing is frozen at creation. No button of any kind, and no
  cancel: cancelling lives on the detail page alone. A filter change keeps the old rows visible
  at reduced opacity while the new page loads instead of blanking the list. Empty: *"Buyurtma
  yo'q"*; filtered-empty offers to clear the filters.
- **Order detail** (`/c/orders/:id`) — four blocks, top to bottom. **Header card**: the number,
  the draft name under it when there is one, the status pill, the total right-aligned under a
  *jami narx* caption, and — only while `new` — a **Bekor qilish** outline-danger action with
  its reason dialog. On phones a full-width **Chizmani PDF ochish** follows the card; desktop
  keeps the PDF link in the Chizma tab head. **Ustaxona card**: workshop and branch by the
  naming rule, address, **Xaritada ko'rish** when the branch has coordinates, phone (a
  cancelled order shows the cancel banner and no Ustaxona card). **Narx card**: one receipt —
  Kesish xizmati, Material, Kromka, any Ustama / Chegirma, then **Jami**; at `ready` and
  `completed` two further rows, **To'langan** and **Qoldiq**, with Qoldiq set larger than Jami
  because it is what the client pays at the counter, and one line saying payment is taken at
  the workshop. Before `ready` there are no payment rows. Then **Detallar** alone on phones,
  **Detallar | Chizma** as tabs on desktop. **No dates, no phase track, no phase text, no
  Tarix and no To'lov tab** — the page answers what this costs, where to collect it and what is
  in it; a timeline of statuses the client was already notified about answered none of those.
- **Ustaxonalarim** (`/c/branches`) and the **workshop profile** (`/c/workshops/:id`) — the
  workshops the client actually deals with, their branches' pickup and contact details, the pin,
  and each branch's read-only catalog. See [`client-entry.md`](client-entry.md), which owns them.

## UX — workshop app

Permission names below are the per-branch grants from
[`access-management.md`](access-management.md); a single user may hold all of them.

**The workshop's status vocabulary follows the order's own branch
[mode](#production-mode).** A **`full`** branch keeps all six internal names — there
`confirmed` genuinely means *queued, not started*, and calling it *Tayyorlanmoqda* would be
a lie, so it stays **Tasdiqlangan**. A **`simple`** branch shows three: `confirmed`,
`cutting` and `edge_banding` are one word, **Tayyorlanmoqda**, and share one pill tone (two
tones under one label read as a defect, not as detail). Independently of mode, `completed`
is labelled **Olib ketildi** everywhere — client and workshop, board, table, timeline and
filters — mirroring the **Olib ketdi** action that produces it; it was *Yakunlandi* before
2026-08-31. A surface with no branch in hand — global search, the finance payable-order
picker — renders the six-status vocabulary rather than guessing a collapse.

- **Nav counters** (`manage_orders`, `process_production`) — the sidebar's **Buyurtmalar** item
  carries a graphite `+N` pill with bone text: how many orders sit in `new` for the selected
  branch, so an arrival is visible from any screen. It is a live count, not an unread marker —
  no read state, no per-user tracking; it falls on its own as staff confirm. Hidden entirely at
  zero, `99+` above 99, and branch-scoped so it always agrees with the list it links to.
  Refreshes on shell load, on a branch switch, when the tab returns to the foreground, and
  after any order mutation; a failed count renders no badge and never disturbs the shell.
  **Kesish** and **Krom** carry the same counter over the signed-in user's **own** queue at that
  station — the number their station page shows, not a branch-wide backlog, because the queue is
  personal for everyone, owner included. Both items are **hidden entirely while the selected
  branch is [`simple`](#production-mode)** — their queues are assignment-fed and a simple
  branch writes no assignment, so they would be permanently empty screens; hiding the items
  takes their counters with them, since the shell derives the counters from the nav list. The
  Buyurtmalar pill is unaffected. A deep link to a station page or a Chizma job sheet on a
  simple branch lands on the existing no-access / empty state — the mode adds no new screens.
- **Orders** (`/workshop/orders`, `manage_orders`; a `view_orders` holder reads individual
  orders by link or search, not this board) —
  branch-scoped, two views:
  - **Board** — one column per active status on a **`full`** branch (`new` / `confirmed` /
    `cutting` / `edge_banding` / `ready`); **three** on a [`simple`](#production-mode) one,
    named as the three statuses that branch has — **Yangi** / **Tayyorlanmoqda** / **Tayyor**
    — where the middle column groups `confirmed` + `cutting` + `edge_banding`, the same
    grouping the client track uses, so a full → simple leftover lands there naturally. There
    is no separate board vocabulary: every header is the status label in the column's own
    mode, which is why cards carry no status pill of their own — the header is the pill. The
    board follows the **sidebar's branch picker**; «Hammasi», which mixes branches, keeps the
    full lifecycle so no branch's orders are folded into a column its own mode lacks.
    Each header has a count; cards: order #, client name + phone, total, item count, age, the
    assigned cutter / edger chip when set — plus a warning chip when a banded order in
    `cutting` / `edge_banding` still has no edger. Both chips are **full-mode only**: a
    simple branch has no assignment to show and no station to stall at, so "kesuvchi yo'q"
    there would name a gap that does not exist. **No drag between status columns** —
    status changes go through the card's action menu.
  - **Table** — sortable; columns: order #, branch (if multi-branch), client, status,
    total, items, created, action menu; each row's status reads in **its own order's branch
    mode**. Filters: a status dropdown of lifecycle buckets
    (active default · completed · cancelled · all) — per-status drill-down is the board's
    columns, not the filter — plus the app-wide
    date-range picker (preset shortcuts + a calendar for custom spans), and a **client
    phone** field — digits-contains against the order's contact phone, so a partial tail
    or a formatted number both match (non-digits in the input are ignored); branch and
    search come from the shell — the sidebar's branch picker and the header's search field.
    The filters apply to both modes.
    Empty: "No orders — nothing matches the selected filters." Zero branches: "No branches
    assigned — ask your workshop owner."
- **New order — walk-in flow** (`manage_orders`) — the sidebar's **+ Yangi buyurtma** action
  starts the [staff-creation flow](#staff-created-orders-walk-in-clients); it's enabled per the
  entry gate there, disabled with a "switch branch" hint otherwise, and the Orders screen does
  not repeat it. Screens:
  - `/workshop/orders/new` — walk-in resolve: a phone field; on a match, a confirm card with
    the registered name; on a new number, a name field; the target (selected) branch named
    throughout.
  - `/workshop/orders/new/cutting?client=` — the shared editor, new-draft mode.
  - `/workshop/orders/cutting/:id` — the shared editor on a saved walk-in draft.
  - `/workshop/orders/new/:draft_id/checkout` — the single-branch checkout (quote at the
    locked branch, contact prefilled from the resolved client, **Place order**). Two columns:
    on the left the client as a heading — name, then `phone · branch`, with one **O'zgartirish**
    link back to step 1 — over the order's contents and the optional note; on the right the
    price. The client was decided on step 1, so this screen only has to let the operator
    recognise it, not re-enter it. Each price line names what it was counted from (`2 list`,
    `26.4 m propil`, `34.3 m lenta`) under its label, so "why this much?" is answerable without
    leaving the screen. The card ends with the total, the commit, the way back and the
    condition it commits to, in that order — the button that gets clicked lives with the number
    it charges.

  Success routes to the order detail, already `confirmed`.
- **Revision — edit a placed order** (`manage_orders`, status `new` / `confirmed`) — **Edit**
  on the order detail opens the shared editor on the order's revision draft
  (`/workshop/orders/cutting/:draft_id`, with a strip naming the order); the editor's
  forward action goes to `/workshop/orders/edit/:draft_id/review` — current vs. new price
  side by side, the discount-reset note when a discount is set, **Save** (applies
  atomically, returns to the detail) and **Discard**. While a revision sits open the order
  detail surfaces it (resume + discard); mechanics and guards:
  [Revising a placed order](#revising-a-placed-order).
- **Order detail** (`/workshop/orders/:id`) — one command header card: order #, status
  pill, client + total on a meta line, the internal workshop note inline beneath it
  (added/edited in place, saved on blur; a quiet "add note" ghost when empty), a compact
  phase strip along the bottom, and exactly **one status-appropriate primary action**;
  the status history opens from a header clock button as a modal timeline; rarer actions
  (edit, discount and surcharge — each a modal, revert, cancel) fold into an overflow menu.

  Everything on this page reads the **order's own branch [mode](#production-mode)**, off the
  payload — never the sidebar's selection, which may be pointing elsewhere. The **phase
  strip** collapses with it: six steps on a full branch (minus `edge_banding` when nothing
  is banded), **four** on a simple one — Yangi → Tayyorlanmoqda → Tayyor → Olib ketildi —
  where a full → simple leftover in `cutting` marks the middle step current rather than
  falling off the strip. A strip listing steps nobody on that branch can move separately
  would describe the machine, not the order. The **history/timeline keeps all six names in
  both modes**: it is the event spine, the composite really did write `confirmed → cutting →
  ready`, and collapsing it there would print "Tayyorlanmoqda → Tayyorlanmoqda".

  The **full**-mode actions:

  | Status | Actions | Permission |
  |---|---|---|
  | `new` | Approve (→ `confirmed`) · Edit ([revision](#revising-a-placed-order)) · Cancel (reason) · Apply discount / surcharge (reason) | `manage_orders` |
  | `confirmed` | Assign / change cutter and edger (metadata) · Edit ([revision](#revising-a-placed-order)) · Start cutting (→ `cutting`) · Apply discount / surcharge · Cancel (reason) | assign/edit/discount/surcharge/cancel: `manage_orders` · start: the assigned cutter (`process_production`) or `manage_orders` on-behalf |
  | `cutting` | Cutting done (→ `edge_banding`/`ready`; decrements panels) · Change edger (metadata; the cutter is locked) · Revert → `confirmed` (reason) · Cancel (reason) | done: `process_production` or `manage_orders` on-behalf · edger/revert/cancel: `manage_orders` |
  | `edge_banding` | Start banding (stamp; requires an assigned edger) · Banding done (→ `ready`; decrements edges per material) · Change edger (until banding starts) · Revert → `cutting` (reason) · Cancel (reason) | start/done: `process_production` or `manage_orders` on-behalf · edger/revert/cancel: `manage_orders` |
  | `ready` | Mark collected (→ `completed`) · Revert → `edge_banding`/`cutting` (reason) · Cancel (reason) | `manage_orders` |
  | `completed` / `cancelled` | (read-only) | — |

  Completion (own or on-behalf) credits the assigned worker. Destructive actions
  (cancel, revert) and "Mark collected" use a danger / confirm dialog that names the
  effect ("client collected everything?").

  On a **simple** branch the assignment selects and the start buttons are simply not there,
  and every forward action is `manage_orders` — there is no assignment, so no worker ever
  holds one:

  | Status | Primary | Also (overflow / secondary) |
  |---|---|---|
  | `new` | **Tasdiqlash** | Edit · discount / surcharge · Cancel |
  | `confirmed` | **Tayyor** | Edit · discount / surcharge · Cancel |
  | `cutting` / `edge_banding` (full → simple leftovers) | **Tayyor** | Cancel |
  | `ready` | **Olib ketdi** | **Orqaga qaytarish** (reason) · Cancel |
  | `completed` / `cancelled` | read-only | — |

  - **The Tayyor dialog** is success-styled, not danger — it confirms a finished job, not a
    destruction — and names the effects before the button: first the stock lines it will
    decrement (each `shop` panel material with its sheets, each `shop` edge material with its
    consumed metres, read from the order's own price lines so the dialog can never disagree
    with the money card beside it), then the two **optional** worker selects — *Kim kesdi?*
    and, only when a side is banded, *Kim kromka yopishtirdi?* Both default to empty and
    offer the branch's last pick as a preselected suggestion, a convenience that stays
    clearable. Confirming runs the composite; the detail comes back at `ready`. An empty
    slot afterwards reads as the reports' own **Belgilanmagan**, not as a "nobody assigned
    yet" nag.
  - **The Orqaga dialog** is danger-styled with a required reason, and names both effects:
    the material returns to the warehouse and the order goes back to *Tayyorlanmoqda*.

  Below the header the page splits into two equal cards that fill the viewport (no page
  scroll at desktop heights; short or narrow windows fall back to normal scrolling): the
  **production card** — on a full branch, instant-apply assignment selects per the lock
  rules, full-width, with the kromka slot always rendered (a quiet disabled box when the
  order has no banding); on a simple branch the selects are absent and the card is its
  completion sub-lines alone. Either way the sub-lines carry the cut snapshot counters, and
  a **"Chizma va tarkib"** button opens a modal with the cutting SVG + PDF, the item snapshots showing
  per-side edge materials, and edge-material consumption — and the **money card**: total,
  the **read-only settlement summary** (recorded / balance, sourced from the finance
  module, shown at any status to staff with `view_finance_reports`/`manage_finance`,
  hidden otherwise), and an always-expanded itemized price breakdown — one line per
  material actually used (each `shop` panel material with its panels, each `shop` kromka
  material with its consumed metres), the services (cutting, banding labour) with their
  quantities, then the surcharge (+) and discount (−) adjustments last. The material lines are rebuilt from order-time snapshots
  (item snapshot prices × cutting-result demands), so they reconcile exactly with the
  frozen subtotals even after later price-list changes. The warehouse warning banner (if
  a `shop` material is short) sits above the cards. There is **no** Payments or Refunds
  surface here — recording and correcting money is the finance module; the summary is a
  read-only mirror.

  **An order the reader may not open is not a loading failure.** The route admits
  `process_production`, but the data rule behind it admits only the assignee, and an order in
  another branch answers 404 rather than confirming it exists. Both land on their own state —
  "Bu buyurtmaga ruxsatingiz yo'q", explaining that the order belongs to another branch, is not
  assigned to this user, or does not exist — with no retry button, because the request that was
  refused will be refused again. The connection-failure state with its retry stays for a
  genuine transport error.

- **Production stations** (`/workshop/cutting` "Kesish", `/workshop/banding` "Krom",
  `process_production`) — **full-mode surfaces**: they are fed by assignments, which a
  [`simple`](#production-mode) branch never writes, so both pages and the home dashboard's
  **Stansiyalar** panel ([`workshop.md`](workshop.md)) are hidden while such a branch is
  selected — a panel reading "0 · hech kim" forever is worse than no panel. That is one rule
  with one carried consequence: the Stansiyalar panel is the only dashboard section a
  `process_production`-only staffer has, so on a simple branch that staffer has none, and
  the page owes them the existing "nothing here for you" empty state rather than a heading
  over blank space. The panel's visibility and the empty state are computed from the same
  flag so they cannot disagree. In full mode the stations are the shop-floor terminal,
  tablet-first, as **two separate sidebar pages** (replacing the tabbed "Ishlarim" workspace, whose URL redirects to Kesish). Each
  station is a priority stack, not columns: the started job pinned on top ("Hozirgi ish"),
  the assigned queue below in **FIFO by assignment
  time** (`cutter_assigned_at` / `edger_assigned_at`), today's completed jobs collapsed at
  the bottom. The page stays fresh on its own (~15 s poll + refresh on focus) — no manual
  refresh button. Cards: order #, part / panel counts (cutting station) or metres of
  tape + parts (banding station), assignment age, and the client's **first name only**
  — material names live on the Chizma sheet, one tap away, and production surfaces
  never show prices, discounts, or client phone numbers; the payload is
  **server-trimmed**, not hidden client-side. The queue is
  **personal for everyone, owner included**: only jobs assigned to the signed-in user,
  scoped to the sidebar's branch picker, and "completed today" is the caller's own tally —
  the server enforces the scope. Owners / `manage_orders` users manage statuses
  **on-behalf from the office order page**, not at the station. **Boshlash** on a queued
  card starts the job and opens its Chizma sheet in one tap. Empty: "Nothing assigned —
  nice."
- **"Chizma" job sheet** (`/workshop/production/:order_id`) — the worker-grade job view
  and the pure-`process_production` replacement for the office order detail: a head of
  **stat chips** (client first name, parts, panels, total tape metres — no material
  text), the cutting plan SVG (zoomable, height-capped so the whole panel fits the
  screen without scrolling; on the banding station a **tape legend** under it names
  each roll with a swatch matching the drawing's edge ticks and its metres) with a
  **panels rail** beside it — panels stacked vertically; on the
  **cutting station only**, each panel carries an icon mark toggle the worker uses as
  their own cut checkpoints (stored on the tablet only, never synced; marking a panel
  advances the drawing to the next unmarked one — the banding view shows the rail
  without marks), the parts list under it (part **names**, never refs; dimensions in
  large tabular figures; a per-part edge glyph marking which sides get banding), and a sticky
  action bar with the single state-appropriate action (**Boshlash** / **Tugatdim**),
  shown **to the assignee only**. The sheet stays fresh like the queues and re-fetches
  right before start / complete so a stale version can't conflict. The PDF lives on the
  office order page, not here.
- **Completion** — a success-styled confirm (not danger) naming the order and what
  happens next ("moves to banding — <edger>'s queue"); the manager-revert-only caveat is
  a quiet secondary line. The terminal credits **the assignee**; the on-behalf "who did
  this work?" choice lives only in the office order page's completion dialog. After
  confirming, the next queued job is highlighted.

States: list / detail each have loading / empty / error; actions show a busy state and end
in success or a recoverable error; the optimistic-lock conflict surfaces as "this order
changed — refresh and try again"; no infinite spinners. Accessibility: the board is
keyboard-navigable; status actions are in a labelled menu, not drag targets; destructive
actions are danger-styled and name their effect; modal focus is managed.

## Edge cases

- **Cutting draft already used / not the client's / not `draft`** →
  `cutting_result_not_usable`; redirect to its detail.
- **Branch went `inactive` / `temporarily_closed` between cutting and order** →
  `branch_closed`; the client picks another branch.
- **Workshop blocked between cutting and order** → `workshop_blocked`.
- **Branch's `cutting_rate_tiyin` not set** → `missing_cutting_rate`; the client sees
  "this branch can't take orders right now"; the workshop app flags the branch.
- **Order has banded parts but the branch's `edge_banding_rate_tiyin` is not set** →
  `missing_edge_banding_rate`; same gating + flag.
- **A `shop` panel the cutting uses is no longer the branch's** — deactivated, or the draft
  moved to another branch → `branch_does_not_carry_panel`. A part names a branch material
  directly now, so this is an id-belongs-to-this-branch-and-is-active test, not a catalog
  lookup; the editor's material swap covers it earlier and the order step is the final gate.
- **A `shop` tape a side uses is no longer the branch's** →
  `branch_does_not_carry_edge`; same test, same recovery.
- **`shop` material short at verification** → approval is **not** blocked; the operator
  sees a warning and prompts the warehouseman
  ([`catalog-inventory.md`](catalog-inventory.md)).
- **Cancel before any decrement** (`new` / `confirmed` / `cutting`) → no stock change.
- **Cancel after a decrement** (`edge_banding` / `ready`) → the cut material is spent,
  not restored; money returned, if any, is an accountant expense
  ([`finance.md`](finance.md)).
- **Revert** → exactly reverses the prior step's stamps and re-increments the stock that
  step decremented (for edges, one restore per edge material the step had consumed);
  never out of `completed`.
- **Order has no banded sides** → `edge_banding` is skipped; the cutting completion goes
  straight to `ready` (the gateway's *no* branch), in either mode.
- **Order has banded sides but every side is `own`** → the `edge_banding` step still
  runs (the edger applies the tape the client brought), but no inventory transactions
  fire at the banding completion — `shop` metres-by-material is empty.
- **Assigned but not started** (full mode) → the order stays `confirmed`: queued in the
  assignee's station, grouped under them in the owner's view, and *Tayyorlanmoqda* to the
  client. No auto-start, no timeout.
- **Start guards** (full mode; in simple mode these endpoints are gated off, so none of
  them can fire) → starting cutting without an assigned cutter (`cutter_required`) is
  rejected — the edger slot never blocks the saw; **Start banding** without an assigned
  edger (`edger_required`) or twice (`banding_already_started`) is rejected; a
  non-assigned `process_production` user starting someone else's job is rejected.
- **One person holds `manage_orders` + `process_production`** → fine; they approve,
  assign themselves, start, and complete the jobs (credited to themselves). v1 assumes
  **no separation of duties**.
- **Concurrent staff transitions / cancel** → optimistic-lock conflict on the second;
  refresh and retry.
- **Cutter / edger from another branch, a blocked user, or one without
  `process_production` on this branch** — rejected at assignment. The **owner is
  exempt** from the same-branch (`home_branch_id = order.branch_id`) check — they hold
  `process_production` everywhere and may self-assign on any branch.
- **No worker available** — the order waits in `confirmed` (or `edge_banding`); the
  board flags the column count; a `manage_orders` user can start and complete
  on-behalf. No auto-timeout.
- **Client disputes a recorded payment** — out-of-system; the client calls the workshop
  and the accountant corrects the income in the finance module.
- **Client re-cuts from the same idea after placing** → the existing order's confirmed
  result stays authoritative. v1 has no client modification path; the workshop can
  [revise pre-production](#revising-a-placed-order), otherwise the client cancels and
  places a new order.
- **Revision saved after production started or the order went terminal** →
  `order_edit_not_allowed`; the leftover revision draft can only be discarded (the order
  detail keeps surfacing it with a discard action at any status).
- **Concurrent revision save and another staff action** → optimistic-lock conflict on the
  loser; refresh and retry.
- **Revision removes every banded side** → the edger assignment is cleared with the save;
  banding added back later re-assigns as usual.
- **Revision applied after the client already paid** → the settlement summary recomputes
  against the new total; an overpayment is corrected by the accountant in the finance
  module, like any recorded-payment dispute.
- **Tayyor on a full → simple leftover** (order already in `cutting` or `edge_banding`) →
  the composite writes only the events still owed and runs only the effects those steps own,
  so nothing decrements twice; a start stamp the earlier full-mode tap wrote is kept. A
  cutter pick is refused on a leftover already past the saw (`cutting_already_started`) —
  that credit is not this tap's to rewrite.
- **Tayyor on an order with no banded side** → the gateway's `ready` branch: two events
  (`confirmed → cutting → ready`), panels decremented, no edger select shown (offering one
  is refused with `edger_not_required`).
- **Tayyor on a fully-`own` order** → the events run and no stock moves; zero `shop` demand
  skips the seam, as the contract already states. Banded-but-all-`own`: the `edge_banding`
  event is still written (the spine is unchanged) with no edge decrement.
- **Tayyor twice** (double tap, or two admins) → the second call finds the order `ready` and
  is refused as an invalid transition; it surfaces as the existing "this order changed —
  refresh" state. A Tayyor racing a revision save, discount, or cancel loses on the
  optimistic-lock check — the composite is one transaction.
- **Orqaga then Tayyor again** → fully supported: new events, new stamps, stock decremented
  again. The spine records the whole story rather than editing it.
- **Branch switched to `simple` mid-order** → nothing is migrated or stranded. An order in
  `cutting` or `edge_banding` reads *Tayyorlanmoqda* on every simple-mode surface and is
  finished by the composite Tayyor. This is why the switch carries **no warning modal** — a
  count of "stranded" orders would warn about a non-event.
- **Branch switched to `full` mid-order** → a `confirmed` order simply regains its
  assignment and start actions; a simple-mode order that was already `ready` is unaffected.
- **Mode switched between page load and action** → the stale surface's call is refused with
  `simple_mode_active` / `full_mode_active`, a toast explains which mode the branch is in,
  and the page refetches.
- **A worker id invalid at Tayyor** (another branch, blocked, no grant) → the existing
  assignment validation errors and nothing is written.
- **A client with orders at two branches in different modes** → the same four-phase track on
  both; only the timing differs.

## Next

- [`cutting.md`](cutting.md) — the cutting-result lifecycle the order binds and depends
  on.
- [`catalog-inventory.md`](catalog-inventory.md) — materials, the warehouse, and the
  auto-decrement contract this state machine drives.
- [`finance.md`](finance.md) — order income, the worker-production reports, and
  expenses.
