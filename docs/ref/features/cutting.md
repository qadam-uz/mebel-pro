---
title: Cutting optimization
status: draft
owner: shape
updated: 2026-05-14
order: 80
---

# Cutting optimization

The 2D guillotine cutting-stock solver: in, a list of parts; out, a sheet-layout scheme, a
waste %, and the metrics the order needs for pricing. Cutting is its own module — no pricing,
payment, or stock logic in it; it does geometry and exposes results. The order integration is
in [`orders.md`](orders.md).

## Who does what

- **Client** — the only caller of the optimization.
- **Workshop staff** — view the confirmed result + PDF. The cutter sees it on their tablet
  in the cutter workspace (`process_production` on the branch); the office sees it on the
  order detail page. None can edit or re-run.
- **System** — runs the algorithm within budget, snapshots the result, manages lifecycle,
  cleans up stale drafts.

## Rules

- **Guillotine cuts only.** A cut runs straight through a rectangle edge-to-edge; the
  algorithm recursively splits the sheet into smaller rectangles. Non-guillotine, L-shaped,
  and CNC-router paths are out of scope.
- **Algorithm (v1).** First-Fit-Decreasing + recursive guillotine splitting, pure Python,
  in-process. Parts are sorted by area descending; each goes in the smallest fitting free
  rectangle; the leftover is split by a guillotine cut. **The algorithm version is stamped on
  the result** — replacing the algorithm later doesn't touch past results.
- **Non-deterministic results are allowed.** The same input may yield a slightly different
  layout on re-run; each run is its own immutable cutting result.
- **Single best result, optimised for waste %.** No alternatives in v1. Unhappy → change parts
  → run again (a new draft).
- **Grain.** Two modes: `any` (the algorithm may rotate the part 90°) and `required` (the
  part's length must run parallel to the sheet's grain direction = its long side; no
  rotation). A `required` part that can't fit in its forced orientation → `impossible_grain`.
- **Sheet handling.** One material → one standard sheet size (from the platform catalog), for
  both `own` and `shop` sources. `own` means the client brings the material, but the type /
  thickness is still chosen from the catalog (for pricing and edge data); custom sheet sizes
  are future.
- **Global constants.** Kerf 4 mm; edge trim 10 mm per side (usable area = sheet − 2× edge
  trim).
- **Edge-banding length is computed here.** For each part edge with a banding thickness set,
  the edge length is the part's length (top / bottom) or width (left / right); totals are
  grouped by thickness (`edge_length_by_thickness`). The order's pricing reads this.
- **No stock check at cutting time.** Cutting says only "N sheets needed"; the real
  availability check is `reserve` at order confirmation ([`orders.md`](orders.md) →
  *Warehouse contract*).
- **Limits.**

  | Constraint | Value |
  |---|---|
  | Part minimum | 50 mm × 50 mm |
  | Part maximum | sheet − 2× edge trim |
  | Parts per optimization | ≤ 100 (more → rejected, not queued, in v1) |
  | Sheets per result | ≤ 20 (bigger jobs must be split) |
  | Open drafts per client | ≤ 50 (anti-abuse; cleanup prunes) |
  | Hard timeout | 5 s → `optimization_timeout` |

- **Lifecycle.** `draft` on optimization (not bound to an order; `order_id = NULL`) →
  `confirmed` when an order is created from it (`order_id` set, `confirmed_at`) →
  `invalidated` when the order is modified in a way that requires a fresh result (the new
  result is bound; the old one is kept for audit). Confirmed and invalidated results are kept
  forever; **drafts older than 7 days are deleted** (with their sheets and placements) by a
  daily job — see [`platform.md`](platform.md).
- **Access.** A client sees only their own drafts and confirmed results; workshop staff and
  the owner see confirmed results for orders in their scope; the PDF download is gated the
  same way. Every optimization run is audited.

## Operations

- **Optimise** (client) — submits a branch, a material, the material source (`shop` / `own`),
  and a list of parts. The system validates against the limits above, runs the algorithm
  within budget, and returns a `draft` result with `algorithm_version`, sheet size,
  `waste_percentage`, `sheets_used`, `total_cut_length_mm`, `total_edge_length_mm`,
  `edge_length_by_thickness`, and per-sheet layouts (placements with `part_ref`, position,
  dimensions, rotation, plus per-sheet waste area).
- **Fetch a result** — anyone whose scope covers it can read the result JSON or download the
  generated cutting-map PDF.
- **Manage drafts** (client) — list one's drafts from the last 7 days; delete a `draft` one
  still owns.
- **Confirm / invalidate** — internal operations called from the order flow when an order
  binds a draft or modifies its parts.

The PDF is rendered server-side, in-process, on demand — no async job.

## UX — the cutting wizard (client app)

A 3-step stepper at `/c/cutting/new`, mobile-first:

1. **Material** — a branch-context chip (with "change" → branch picker); a material-source
   toggle ("from the shop" / "my own material"); a searchable grid of the branch's `active`
   materials (price shown only for `shop`); single-select. Empty: "this branch has no
   materials yet — pick another."
2. **Parts** — a two-pane layout (single column on mobile). Left: a parts editor (table of
   rows — №, length mm, width mm, quantity, grain `any` / `required`, edge per side
   `0.4` / `2.0` / none; add / remove / duplicate row; min 1 row; a hidden `part_ref` UUID per
   row); a bulk-paste textarea accepting `LxWxQty` per line. Right: a live summary — parts
   count, total area, the material's sheet size, a kerf / edge-trim note. Inline validation
   against the bounds. A "Run optimization" CTA (disabled while running; respects the 5 s
   timeout; on error highlights the offending part(s) and maps the error code).
3. **Result** — a big interactive SVG of the sheet layouts with sheet tabs (Sheet 1, 2, …);
   pan / zoom; hovering a placement highlights the originating part in a side legend
   (№, dimensions, quantity index). A metric strip: waste %, sheets used, total cut length
   (m), edge banding by thickness. Actions: **Download PDF** · **Edit parts** (→ step 2,
   creating a new draft on the next run) · **Order with this cutting** (→ order create wizard,
   in [`orders.md`](orders.md)). A subtle footer note: "drafts are kept 7 days."

Other surfaces:

- **My drafts** (`/c/cutting/drafts`) — table / cards: branch, material, parts count,
  waste %, sheets, created (relative), `draft` chip; row actions Open / Delete (confirm).
  Empty: "No saved cuttings — start a new one."
- **Draft / result view** (`/c/cutting/:id`) — the step-3 view, read-only, with an "Order with
  this cutting" CTA (or a note if it's already `confirmed` / `invalidated`).
- **Workshop app**: an order's **Cutting** tab embeds the SVG of the order's confirmed
  result + a PDF link (and, if `invalidated`, shows it with a flag).

States: every step has loading / empty / error; the optimize call has a running state and a
timeout / error path (no infinite spinner); the SVG remains scrollable / zoomable on a small
phone. Accessibility: the SVG layout has a text-equivalent legend (the per-sheet placement
list); hover-to-highlight has a keyboard / tap equivalent; the parts table is fully
keyboard-editable with labelled cells; errors are announced and the offending row gets focus.

## Edge cases

- **`material_not_found`** — bad or foreign material id → 404.
- **`part_too_large` / `part_too_small`** — outside the size bounds → 400; the wizard names
  the offending part and the max size.
- **`impossible_grain`** — a `required` part can't fit in its forced orientation → 400.
- **`too_many_parts` / `too_many_sheets_needed`** — over the caps → 400; split the job.
- **`optimization_timeout`** — no solution within 5 s → 504; retry or simplify.
- **`branch_not_accessible`** — branch inactive or another workshop's → 403.
- **`draft_limit_exceeded`** — > 50 open drafts → delete some first.
- **Algorithm replaced later** — old results, PDFs, and the prices computed from them stay
  exactly as they were (stamped algorithm version + immutable rows).

## Next

[`orders.md`](orders.md) — how a confirmed result is consumed, when it's invalidated, which
cutting metrics drive which price component.
