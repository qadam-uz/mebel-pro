---
title: Cutting optimization
status: draft
owner: shape
updated: 2026-05-13
order: 80
---

# Cutting optimization

The 2D guillotine cutting-stock solver: in, a list of parts; out, a sheet-layout scheme, a waste %,
and the metrics the order needs for pricing. The single home for everything cutting — rules,
algorithm, lifecycle, API, UX. The order integration is in [`orders.md`](orders.md).

## What it is

Cutting is its own module — no pricing/payment/stock logic in it; it does geometry and exposes
results. The **client** is the only caller of `optimize`. **Workshop staff** view the confirmed
result + PDF for the saw operator (they cannot edit or re-run). The **system** runs the algorithm
within budget, snapshots the result, manages lifecycle, and cleans up stale drafts.

## Rules

- **Guillotine cuts only.** A cut runs straight through a rectangle edge-to-edge; the algorithm
  recursively splits the sheet into smaller rectangles. Non-guillotine / L-shaped / CNC-router
  paths are out of scope.
- **Algorithm (v1):** First-Fit-Decreasing + recursive guillotine splitting, pure Python, in-process.
  Parts sorted by area descending; each placed in the smallest fitting free rectangle; the leftover
  split by a guillotine cut. The algorithm version is **stamped on the result** — replacing the
  algorithm later doesn't touch past results.
- **Non-deterministic results are allowed.** The same input may yield a slightly different layout on
  re-run — not a problem; each run is its own immutable `cutting_result_id`.
- **Single best result.** The algorithm returns one result optimizing for **waste % minimized** —
  no alternatives in v1. Unhappy → change parts → run again (new draft).
- **Grain:** two modes — `any` (algorithm may rotate the part 90°) and `required` (part length must
  run parallel to the sheet's grain direction = its long side; no rotation). A `required` part that
  can't fit in its forced orientation → `impossible_grain` error.
- **Sheet handling:** one material → one standard sheet size (from the material catalog), for both
  `own` and `shop` sources. `own` means the client brings the material, but the type/thickness is
  still chosen from the catalog (for pricing & edge data); custom sheet sizes are future.
- **Global constants:** kerf 4 mm, edge trim 10 mm per side (usable area = sheet − 2× edge trim).
- **Edge-banding length is computed here** (the order's pricing uses it): for each part edge with a
  banding thickness set, the edge length = the part's length (top/bottom) or width (left/right);
  totals are grouped by thickness (`edge_length_by_thickness`).
- **No stock check at cutting time.** Cutting just says "N sheets needed"; the real availability
  check is `inventory.reserve` at order confirmation ([`orders.md`](orders.md)).
- **Limits:** part 50 mm × 50 mm minimum; max part = sheet − 2× edge trim; ≤ 100 parts per
  `optimize` (more → rejected, not queued, in v1); ≤ 20 sheets per result (a bigger job must be
  split); ≤ 50 open drafts per client (anti-abuse; cleanup job prunes). 5 s hard timeout on the
  request → `optimization_timeout`.
- **Lifecycle:** `draft` on `optimize` (not bound to an order, `order_id = NULL`) → `confirmed` when
  an order is created from it (`order_id` set, `confirmed_at`) → `invalidated` when the order is
  modified (a fresh result is bound; the old one is kept for audit). Confirmed and invalidated
  results are kept forever; drafts older than 7 days are deleted (with their sheets/placements) by a
  daily job.
- **Access:** a client sees only their own drafts and confirmed results; workshop staff/owner see
  confirmed results for orders in their scope; the PDF download is gated the same way. Every
  `optimize` call is audited.

## API surface

```
client → POST /api/v1/cutting/optimize { branch_id, material_id, material_source, parts[] }
         validate dimensions / grain / counts → error if any
         run FFD + guillotine splitting, ≤ 5 s
   ← { cutting_result_id, status: draft, algorithm_version, sheet_size,
       waste_percentage, sheets_used, total_cut_length_mm, total_edge_length_mm,
       edge_length_by_thickness, sheet_layouts[ { sheet_index, placements[ {part_ref, x, y, length, width, rotated} ], waste_area } ] }
```

- `GET /cutting/results/:id` — the result JSON, including layouts.
- `GET /cutting/results/:id/pdf` — server-generated cutting map (in-process).
- `GET /cutting/drafts` (client) — last 7 days; `DELETE /cutting/drafts/:id` (client; only `draft`,
  only the owner).
- `confirm-cutting-result` / `invalidate-cutting-result` — internal ops the `orders` module calls.

## UX — the cutting wizard (client app)

A 3-step stepper at `/c/cutting/new`, mobile-first:

1. **Material** — a branch-context chip (with "change" → branch picker); a material-source toggle
   ("from the shop" / "my own material"); a searchable grid of the branch's active materials (price
   shown only for `shop`); single-select. Empty: "this branch has no materials yet — pick another."
2. **Parts** — a two-pane layout (single column on mobile). Left: a parts editor (table of rows —
   №, length mm, width mm, quantity, grain `any`/`required`, edge per side `0.4`/`2.0`/none;
   add / remove / duplicate row; min 1 row; a hidden `part_ref` UUID per row); a bulk-paste textarea
   accepting `LxWxQty` per line. Right: a live summary — parts count, total area, the material's
   sheet size, a kerf/edge-trim note. Inline validation against the bounds. A "Run optimization"
   CTA (disabled while running; respects the 5 s timeout; on error highlights the offending part(s)
   and maps `error.code`).
3. **Result** — a big interactive SVG of `sheet_layouts` with sheet tabs (Sheet 1, 2, …); pan/zoom;
   hovering a placement highlights the originating part in a side legend (№, dimensions, quantity
   index). A metric strip: waste %, sheets used, total cut length (m), edge banding by thickness.
   Actions: **Download PDF**, **Edit parts** (→ step 2, creating a new draft on next run), **Order
   with this cutting** (→ order create wizard, [`orders.md`](orders.md)). A subtle footer note:
   "drafts are kept 7 days."

Other surfaces:

- **My drafts** (`/c/cutting/drafts`) — table/cards: branch, material, parts count, waste %, sheets,
  created (relative), `draft` chip; row actions Open / Delete (confirm). Empty: "No saved cuttings
  — start a new one."
- **Draft / result view** (`/c/cutting/:id`) — the step-3 view, read-only, with an "Order with this
  cutting" CTA (or a note if it's already `confirmed`/`invalidated`).
- **Workshop app**: an order's **Cutting** tab embeds the SVG of the order's confirmed result + a PDF
  link (and, if `invalidated`, shows it with a flag).

States: every step has loading / empty / error; the optimize call has a running state and a
timeout/error path (no infinite spinner); the SVG remains scrollable/zoomable on a small phone.
Accessibility: the SVG layout has a text-equivalent legend (the per-sheet placement list);
hover-to-highlight has a keyboard/tap equivalent; the parts table is fully keyboard-editable with
labelled cells; errors are announced and the offending row gets focus. Component specs are in
[`web/DESIGN.md`](../../../web/DESIGN.md).

## Edge cases & failure paths

- **`material_not_found`** — bad/foreign material id → 404.
- **`part_too_large` / `part_too_small`** — outside the size bounds → 400; the wizard names the
  offending part and the max size.
- **`impossible_grain`** — `required` part can't fit in its forced orientation → 400.
- **`too_many_parts` / `too_many_sheets_needed`** — over the caps → 400; split the job.
- **`optimization_timeout`** — no solution within 5 s → 504; retry or simplify.
- **`branch_not_accessible`** — branch inactive or another workshop's → 403.
- **`draft_limit_exceeded`** — > 50 open drafts → delete some first.
- **Algorithm replaced later** — old results, PDFs, and the prices computed from them stay exactly
  as they were (stamped algorithm version + immutable rows).

## Next

[`orders.md`](orders.md) — how a confirmed result is consumed, when it's invalidated, which cutting
metrics drive which price component. The cutting wishlist (alternatives, async, manual edits,
per-branch kerf, multiple sheet sizes, `preferred` grain) is parked in [`open-questions.md`](../../open-questions.md) Q7.
