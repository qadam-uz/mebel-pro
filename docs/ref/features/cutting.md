---
title: Cutting optimization
status: draft
owner: shape
updated: 2026-06-26
order: 80
---

# Cutting optimization

The 2D guillotine cutting-stock solver: in, a list of parts where each part picks its own
panel material and per-side edge materials; out, a per-material panel layout, a weighted
waste %, and the structural metrics the order needs for pricing. Cutting is its own module —
no pricing, no payment, no stock logic — and exposes results to the order flow in
[`orders.md`](orders.md).

## Problem

Customers describe parts over the phone; the workshop optimises by hand or with a desktop
tool. The customer can't see the layout, the waste, or the price until the shop tells them.
And a real job — a wardrobe, a kitchen — uses several materials at once: DSP shelves, MDF
backs, plywood drawer bottoms, plus a leftover panel the customer brings from a previous job
and PVC edge tape in different colours and thicknesses for different visible faces. A
single-material flow rejects half the work; forcing one cutting per material rejects the
other half (the user has to reconcile panels and prices across runs); a flow that only
picks edge *thickness* without naming the actual tape forces the workshop to guess which
manufacturer's spool to load and surprises clients at the counter.

## Domain rules

### What's in a cutting

A **cutting draft** is the working surface a client edits and re-optimises until they place an
order. It's private to the client and persists indefinitely (no expiry; cap at 50 open
drafts). The draft becomes a server entity on the **first optimise** — the editor opens local
and unsaved, so abandoned/empty editors never mint a draft (see *Lifecycle*).

A draft owns:

- **An optional `preferred_branch_id`.** Seeded from the client's stored
  [profile default](../entities/identity.md#client) when one exists; the current profile UI does
  not expose setting that default. The client can still change or clear it on the draft without
  touching the profile. When set, the material picker is **pre-filtered**
  to materials this branch carries and the order step defaults to this branch — but the
  filter is a help, never a data operation: parts already in the list stay editable even
  when their materials aren't carried at the new branch (see *Recovery affordances*).
- **Parts.** Each part picks its own **panel** material from the platform catalog, its own
  source (`shop` / `own`), dimensions (length × width × quantity), and a per-side **edge**
  material (top, bottom, left, right — each `null` for no banding, or a catalog edge
  material with its own source). Grain is **not** a per-part choice — it's a property of
  the chosen panel material. Edge thickness and colour are properties of the chosen edge
  material — the user picks the tape, not a thickness.
- **Algorithm results.** Re-running the optimiser produces one result per available
  algorithm in a single call against the same input. All N results are kept on the draft until
  the next run replaces them. The client picks one as the **chosen** result; the chosen one is
  what binds to an order.

Each algorithm result records: `algorithm_name`, `algorithm_version`, per-material panels
and their placements, weighted `waste_percentage`, `panels_used_by_material`,
`total_cut_length_mm`, `total_edge_length_mm`, `edge_length_by_material` (integer millimetres
per edge material; UI/pricing displays metres; only the `shop`-source length feeds the order's
billed and consumed totals; `own` length is tracked separately for the cutting plan).

### Lifecycle

```mermaid
stateDiagram-v2
    [*] --> editing : client opens "New cutting" (local, unsaved)
    editing --> editing : edit parts · pick branch
    editing --> draft : client runs the optimiser → draft created & persisted
    draft --> draft : edit parts · re-optimise · pick algorithm
    draft --> confirmed : client places an order with the chosen result
    confirmed --> [*]
```

- `editing` is **local and unsaved** — the editor before the first optimise. No server draft
  exists yet, so navigating away discards the entry (the editor warns first). The draft is
  created and persisted on the **first optimise**, which is also when autosave begins.
- `draft` is mutable. `confirmed` is immutable and kept forever — it is the historical
  record an order points at.
- Re-running the optimiser on a `draft` replaces all algorithm results in-place. No
  intermediate-run history.
- On order placement, the **chosen** algorithm result becomes the draft's frozen snapshot and
  the draft flips to `confirmed`. Other algorithm results from the same run are discarded at
  this point.

**Why create lazily.** Minting the draft only on the first optimise keeps abandoned and empty
editors out of the drafts list and the 50-draft cap; the accepted cost is that input before
the first optimise isn't autosaved (the editor warns before discarding it). Revisit if clients
report losing pre-optimise work — then back the unsaved editor with local storage, or restore
eager creation.

### Parts and materials

- A part's panel material is a reference to the **platform catalog** (the shared list
  curated by platform operators). All catalog `panel` materials are pickable in the editor
  regardless of branch availability; the branch indicator (below) flags where this
  composition can be fulfilled.
- A part's `material_source = shop` means the workshop supplies the panel; `own` means the
  client brings it, and only the cutting service is purchased for that part. Different
  parts can have different sources — including parts of the same material (some from shop,
  some brought).
- An `own` part still picks a catalog material — the entry supplies panel dimensions,
  thickness, kerf-relevant data, and the grain rule. Non-catalog materials are out of
  scope for v1.
- **Edge tape is a catalog material too.** Each side of a part is either `null` (no banding)
  or `(edge material, source)`. The picker UX pins decor-matching edges at the top of one
  material list so the common case ("match the panel decor in 0.4 mm") is a single tap
  without hiding the rest of the catalog (see *UX*). Like panels, edges can be `shop`
  (workshop supplies) or `own` (client brings their own spool); a side's source is
  independent of the panel's source on the same part and of other sides' sources.

### The optimiser

- **One run, multiple materials, multiple algorithms.** A run takes all parts, groups them
  by panel material, and produces an independent layout per material (panels aren't shared
  across materials — different thicknesses, colours). Every available algorithm runs against
  the same input in the same request; all results are returned.
- **Winner = lowest weighted waste %.** Pre-selected as the chosen result; the client may
  switch to a different algorithm's result if the trade favours fewer panels or different
  cut topology.
- **Guillotine cuts only.** A cut runs edge-to-edge; the algorithm recursively splits the
  panel into smaller rectangles. Non-guillotine, L-shaped, and CNC paths are out of scope.
- **Grain — a property of the panel material, not the part.** Each catalog `panel` material
  declares whether it has a visible grain direction. For a **grained material**, every part
  on it has its length aligned with the panel's grain (the long side); the algorithm may
  not rotate the part 90°. For a **non-grained material**, the algorithm is free to rotate
  parts. If a part on a grained material can't fit in its forced orientation, the run fails
  with `impossible_grain`. The user is never asked to set grain on a part.
- **One catalog material → one standard panel size.** The same spec in another size is a
  separate catalog material (size is part of its identity and name); custom panel sizes
  per run are future.
- **Global constants.** Kerf 4 mm. Edge trim 10 mm per side (usable area = panel − 2× edge
  trim).
- **Edge-banding length is computed here.** For each part edge with a banding material set,
  the edge length is the part's length (top/bottom) or width (left/right). Totals roll up
  **by edge material** (`edge_length_by_material`, integer millimetres) — this is the
  **geometric banded length**.
  The metres an order actually **bills and consumes** add a fixed per-side trim overhang
  (masters glue tape long, then trim it flush) — a system constant, the same at every branch
  — so the **consumed** figure is geometry + that trim; see [`orders.md`](orders.md#pricing)
  for the rule. The optimiser emits the geometry, and because the overhang is constant the
  consumed metres are known without a branch.
- **No stock check at cutting time.** The optimiser says only "N panels needed of material
  X" and "L metres needed of edge material Y." Stock is never a gate: the operator sees a
  non-blocking low-stock warning at order verification and the inventory module
  auto-decrements as production completes (see [`orders.md`](orders.md)).
- **No pricing computed here.** Pricing depends on the branch — branches set their own
  per-panel cutting rate and their own per-metre edge price. The optimiser yields
  structural metrics only; price first appears at the order step.

### Limits

| Constraint | Value |
|---|---|
| Part minimum | 50 mm × 50 mm |
| Part maximum | panel − 2× edge trim (for the part's chosen panel material) |
| Parts per optimisation | ≤ 100 (across all materials) |
| Panels per material per result | ≤ 20 (a single material above this must be split into separate orders) |
| Open drafts per client | ≤ 50 (anti-abuse; client deletes to add more) |
| Hard timeout per run | 5 s → `optimization_timeout` |

### Access

A client sees only their own drafts and confirmed results. Workshop staff and the owner see
confirmed results bound to orders in their scope; the PDF download is gated the same way.
Every optimisation run is audited.

## User stories

- As a client, I want all my parts in one cutting even when they need different materials,
  so I don't run multiple cuttings and reconcile panels / prices afterwards.
- As a client, I want to mark some parts or some edges as "I'll bring this material myself,"
  so I can use a leftover I already have.
- As a client, I want to compare algorithm results before committing, so I can pick "fewer
  panels" over "lowest waste" when I care more about cost than offcuts.
- As a client, I want to pre-filter the catalog to one branch's selection so I don't pick
  materials that branch can't fulfil — but I don't want that filter to throw away parts
  I've already entered.
- As a client, I want to filter the catalog by manufacturer so I get the brand the workshop
  near me reliably carries (Egger vs. Kronospan).
- As a client, I want the matching edge for my panel decor offered first so I'm not hunting
  through tens of edge SKUs for the obvious choice.
- As a client, I want the draft saved automatically, so I don't lose it if I close the
  browser.
- As a workshop user (cutter), I want the confirmed layout and PDF on my tablet at the saw,
  so I can cut without translation.

## UX — the cutting wizard (client app)

A single workspace at `/c/cutting/:id` (`/c/cutting/new` before the first optimise; no stepper
— one editing surface above, one results panel below). Entry is the client app's home **New
cutting** button, which opens an empty, unsaved editor; the draft is created and persisted on
the first **Optimise** (see *Lifecycle*). A secondary **My drafts** entry lists unbound drafts.

### Branch pre-filter (top of the editor)

A small affordance under the page header naming the active pre-filter:

- **No pre-filter** → "all branches" + a **Pick a branch** link.
- **Pre-filter set** → just the branch name, e.g. "Yunusobod · Furniture House" + a **Clear**
  button and a **Change** button.

Picking or changing the branch opens a single flat branch list — one row per branch, naming
the branch, its workshop, and today's hours, with a status pill (`temporarily_closed`
branches stay selectable, the row just flags why); a search field appears once the list is
long. One tap selects a branch; **Apply** sets the draft's `preferred_branch_id`. Clearing
removes it. **Neither edits the parts list.** Rows that reference materials the new branch
doesn't carry get a per-row warning + recovery affordances (below).

The **Show all catalog** toggle lives inside this same pre-filter affordance and appears
**only once a branch is selected** — without one the catalog isn't branch-narrowed, so the
toggle has nothing to widen and stays hidden.

### Parts editor (top)

A mode switch at the top: **Manual entry** (default) · **Upload file** (`.bas` / `.xlsx`;
disabled in v1 with a "Coming soon" pill). The page header carries a **Clear parts list**
trash icon, shown only once there are rows. The primary **Optimise** button lives in a
**sticky bottom action bar** — alongside the row / piece count (and, when it's disabled, the
reason shown inline) — so it stays reachable above a long list.

Adding a row follows the content rather than a fixed header control: an empty editor shows a
centred **Add part** call-to-action, and once there are rows a dashed **Add part** tile sits
beneath the last row (there is no separate header add button).

On wide layouts the parts table renders as a dense, scannable grid: a shared column header
and one compact single-line row per part (the panel cell carries a colour swatch, an inline
source toggle, a grain badge, and a leading row checkbox for bulk actions; a trailing
**Delete** trash button removes the row). On narrow screens each row stacks into a labelled
card.

The parts table:

| Column | Behaviour |
| --- | --- |
| **#** | row number |
| **Panel** | searchable dropdown of the platform catalog (`panel` kind); each result shows manufacturer + decor / colour + thickness + size. The picker's own type-to-filter search is the only narrowing inside the parts editor — there is no separate manufacturer / type / thickness / sort bar (it duplicated the search and added clutter). When `preferred_branch_id` is set, the picker is pre-filtered to that branch's selection by default; a toggle "Show all catalog" widens it. Selected row shows the picked panel's short label (e.g. `Egger DSP H1334 18 mm · 2750×1830`) with an inline source chip: `From shop` ↔ `I'll bring it`. A trailing **✕** clears the pick and reopens the list (showing the full set) for a fresh search — re-picking otherwise means manually clearing the typed label first |
| **L mm** | numeric; validated against the part-min / part-max bounds of the chosen panel |
| **W mm** | same |
| **Qty** | integer ≥ 1 |
| **Edges** | per-side summary — a small panel diagram (line weight signals thickness) + a one-line label (e.g. `H1334 · 0.4 mm` · `T·B · H1334 2.0` · `Mixed · 2 edges` · `None`). Tap → edge picker |
| **Delete** | a trash icon button removes the row |

The grain indicator (a small arrow) appears **on the panel chip itself** when the chosen
panel has grain — a passive cue, not a control.

**Edge picker** (opens from the Edges cell — popover on desktop, bottom sheet on mobile):

- **One surface, no modes.** The picker asks two questions first: which sides need edge
  banding, and which tape should be used. There is no separate "match panel" section,
  "browse other materials" section, "customise per side" button, or standalone "apply to
  all" button.
- **The panel diagram is the centerpiece.** Compact quick-pattern chips sit above it
  (**None**, **All sides**, **Top + bottom**, **Left + right**) — each chip carries a mini
  rectangle that draws its banded sides thick so it reads spatially, not just by text — and
  the diagram below shows
  the part with all four sides **labelled** (top / bottom / left / right) — tap a side to
  toggle its banding; banded sides fill (shop vs. "I'll bring it" read as distinct fills).
  Choosing a tape applies it only to the **currently banded** sides; with **no** side
  selected the tape is just remembered (highlighted in the list) and used by the next side
  toggled on — picking a tape never auto-bands all four sides.
- **The ranked tape list is revealed on demand.** Once a tape is chosen the list collapses
  to a one-line summary (swatch + tape + thickness + how many sides) with a **Change**
  toggle; opening it — or arriving at a part with no banding yet — shows the full list.
  Edges with the same `decor_code` as the panel are pinned first with a **Recommended**
  marker; same-`color` matches follow; all other active edge materials continue in the same
  list, filtered by search + a thickness dropdown. If no panel is selected, matching appears
  once the panel is picked but catalog search still works.
- **Source is quiet by default.** `shop` is the default. A segmented source control
  (`Workshop supplies` / `I'll bring it`) applies to the currently banded sides; mixed
  per-side source remains possible through the diagram but is not presented as a separate
  step.
- **The edge picker applies to the row it was opened from.** The footer has only **Cancel**
  and **Apply**; **Apply** saves the selected side pattern, tape, and source to the row whose
  **Edges** cell opened the picker, and never edits sibling rows from inside the picker.
  **Bulk edge apply** is instead an explicit **list-level** action (see _Bulk row actions_
  below) — the picker stays single-purpose, exactly as foreseen here.

**Bulk row actions (desktop).** On wide layouts the parts table gains a leading checkbox
column (and a select-all in the header). Selecting one or more rows reveals a bulk bar with
**Apply edges** (opens the edge picker seeded from the first selected row and writes the
applied side pattern / tape / source to every selected row), **Change material** (a small
picker that sets one panel material on every selected row), and **Delete**. This is the
list-level path for re-banding or re-materialing many identical parts without N picker
round-trips — a desktop power feature; on mobile each row is edited individually (its own
fields plus the per-row delete button).

Per-row inline validation; when something blocks the optimiser the reason is shown inline
next to the (disabled) **Optimise** button in the sticky bar — there is no separate roll-up
banner under the table.

### Recovery affordances — when materials aren't carried at the preferred branch

When `preferred_branch_id` is set and a row references materials the branch doesn't carry,
the row is **not** disabled, **not** dropped, **not** moved. It stays in place, editable,
with a **per-row warning** on each affected row (there is no separate top-level roll-up
banner — the warning lives on the row that has the issue):

- The warning reads *"Not at <branch>."* with two inline buttons:
  - **I'll bring my own** — flips the row's panel source (or for an affected edge side,
    that side's source) to `own`. The branch no longer needs to carry it.
  - **Pick a different material** — opens the picker pre-filtered to the new branch (panel
    swap on the panel cell; edge swap inside the edge picker with the affected side
    already active and the same inline note visible).
- The row's **Delete** (trash) button still works; removal is opt-in and never automatic.

For a row whose **own**-source panel is referenced (i.e. the client already brings the
panel), there's no warning — `own` doesn't care which branch carries it. Same for `own`
edge sides.

### Clearing the parts list (deliberate)

A **Clear parts list** trash icon next to the page header runs a danger-styled action
(confirmation: *"Remove all N parts? This can't be undone."*). This is the only way to wipe
parts wholesale; the branch pre-filter never invokes it.

### Run and the result panel

A primary **Optimise** button in the sticky bottom action bar. Disabled while running (5 s
cap), then disabled until any row changes (so re-tapping doesn't re-run a stale layout); the
disable reason is shown inline next to it. On a brand-new
(unsaved) editor the first **Optimise** also creates and saves the draft before running, after
which the URL becomes `/c/cutting/:id` and autosave takes over.

The result panel only renders once an optimise has produced a result (or an error to surface);
before the first run there is **no empty placeholder** — the parts editor and the sticky
Optimise button are all there is to see.

On success, the panel scrolls into view with three regions:

1. **Headline metrics.**
   - Weighted **waste %** (across all panel materials).
   - **Panels used** total and per-material breakdown.
   - **Edge tape** total length — the **consumed** metres (geometric banding + the fixed
     30 mm trim overhang per banded side), with a breakdown listing each edge material
     that has metres (e.g. `Rehau H1334 0.4 — 8.4 m · Rehau H1334 2.0 — 3.2 m`). When some
     sides are `own`, the breakdown splits shop and own metres per material. The metric
     carries a compact split such as `edge sides 12.8 m + trim overhang 0.6 m`; no long
     explanatory message is shown in the flow. Because the trim overhang is a fixed system constant,
     this is the real figure from the cutting result onward; only price waits on the
     branch's rates ([`orders.md`](orders.md#pricing)).
   - **Cut length total** (m), informational.
   - **Parts placed** count, e.g. `24 / 24` ✓ (red with a per-part list if any didn't fit).
   - The chosen **algorithm** name plus a **Compare algorithms** link → expander with one
     row per algorithm (name, waste %, panels, cut length) and a **Use this one** button
     per row to swap the visualisation.

2. **Panel layout visualiser.**
   - A material tab strip (`DSP H1334 18mm · 2750×1830 · 3 panels` ·
     `MDF Qum 16mm · 2800×2070 · 1 panel`). Within a material, panel tabs
     (`Panel 1 / 2 / 3`).
   - The active panel renders as an interactive SVG (pan / zoom on mobile); each placed
     part is labelled with its **dimensions** — length along the top edge, width down the
     left edge — rather than an opaque part id. Selecting a placement highlights it in the
     side legend, which leads with the dimensions (+ quantity index, rotation indicator).
   - **Banded sides** are flagged by a short, centred accent tick set just inside the
     placed rectangle, on each banded side only (not a full-length frame) — so the cutter
     sees which edges take tape at a glance. The side mapping follows the part's own edges;
     a rotated placement maps them 90° clockwise. Tick inset, length and weight are
     normalised, so banding reads the same on a large and a small panel.

3. **Actions.**
   - **Place order with this cutting** → routes into the order wizard
     (see [`orders.md`](orders.md)).
   - **Download PDF** — the print-ready cutting map for the saw operator (one page per
     panel, header with material + panel index + waste, footer with the algorithm stamp).
   - **Edit parts** scrolls back to the editor; any row change marks the result stale; the
     next **Optimise** replaces it.

Pricing is **not** shown on this screen — totals depend on the branch and surface at the
order step.

### My drafts (`/c/cutting/drafts`)

A list of unbound drafts. Each row: a short label (`14 parts · 6 panels`), the dominant
panel material, last-edited time (relative), the preferred branch chip when set, a Delete
action. Empty: "No saved cuttings — start a new one." No expiry chip — drafts persist until
the client deletes them or hits the cap.

### Read-only view (`/c/cutting/:id` when `confirmed`)

Same workspace, editing disabled, with a banner naming the bound order.

### Workshop side

An order's **Cutting** tab embeds the SVG of the order's confirmed result and a PDF link.

## Edge cases

- **`material_not_found`** — a part references a catalog id that's missing or removed → the
  editor flags the row; the optimiser refuses to run.
- **`part_too_large` / `part_too_small`** — outside the bounds for the chosen panel
  material → the wizard names the offending part and the max size.
- **`impossible_grain`** — a part on a grained material can't fit rotated-locked → the row
  is flagged.
- **`too_many_parts` / `too_many_panels_needed`** — over the caps → reject; split the job.
- **`optimization_timeout`** — no result within 5 s → retry or simplify.
- **`draft_limit_exceeded`** — > 50 open drafts → delete some first.
- **All-`own` cutting** — no `shop` materials at all; the order step accepts any active
  branch with a saw.
- **Edges all `own`** — the order's `edge_length_by_material` still records the total
  metres per material (informational for the cutting plan / PDF), but stock decrement skips
  every side at `edge_banding → ready` because no side is `shop`.
- **Catalog change while a draft sits** — if a material a part references is later removed
  from the catalog, the draft is flagged on next open with that row highlighted; the
  client picks a replacement before re-running.
- **`preferred_branch_id` set but the branch later goes `inactive`** — the pre-filter is
  treated as "no carried materials" for that branch; the wizard surfaces the same
  not-carried recovery affordances on every row, plus a banner pointing at the branch's
  status; the client clears or changes the pre-filter to unlock.
- **`cutting_result_not_usable`** — the order step finds the draft is already `confirmed`
  (concurrent placement, or back-navigation after placing) → redirect to its detail.
- **Algorithm replaced later** — old `confirmed` results stay exactly as they were,
  stamped with the old algorithm version; their PDFs are not regenerated.
- **A workshop deactivates an edge material that's set as a per-side preference on an
  in-flight draft** — same handling as a deactivated panel: row flagged on next open, edge
  side cleared with a one-tap "pick replacement" affordance that opens the edge picker with
  that side active.

## Next

- [`orders.md`](orders.md) — how a chosen cutting result becomes a placed order and which
  cutting metrics drive which price component.
- [`catalog-inventory.md`](catalog-inventory.md) — the platform catalog (manufacturers,
  panels, edges) the wizard reads from, and the branch's selection that drives the
  pre-filter.
