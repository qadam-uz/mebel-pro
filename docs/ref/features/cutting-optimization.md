---
title: Cutting optimization
status: stable
owner: shape
updated: 2026-05-11
order: 30
related:
  - docs/spec/cutting.md
  - docs/spec/orders.md
  - docs/ref/entities/cutting/cutting-result.md
  - docs/ref/features/material-catalog.md
  - docs/ref/features/order-placement.md
---

# Cutting optimization

## Problem

A customer has a list of panels they need cut to size. Today they describe these over the phone and
the workshop figures out the layout, the number of sheets, and the price — and the customer can't see
any of it. They can't try variations ("what if I make this part 20mm smaller?") without another phone
call. They need to enter the parts themselves, get an optimized cutting layout, see the waste and the
sheet count, get a PDF the shop floor can cut from, and iterate — then carry that result into an
order.

## User stories

- As a **client**, I want to pick a material and enter my parts list (dimensions, quantity, grain,
  edge banding) and run an optimizer so I get a cutting layout and the metrics.
- As a **client**, I want to see the layout visually, per sheet, with the waste %, sheet count, total
  cut length, and edge-banding length by thickness — and download a PDF.
- As a **client**, I want to tweak my parts and re-run to compare, with each run saved as a draft.
- As a **client**, I want my recent drafts listed so I can come back to one, and to delete ones I
  don't need.
- As **workshop staff** handling an order, I want to view the order's confirmed cutting result and
  open its PDF for the saw operator.

## Requirements

1. `optimize-cutting` (client, authenticated): input `{ branch_id, material_id, material_source
   (own/shop), parts[] }` where each part is `{ part_ref (client-supplied id), length_mm, width_mm,
   quantity (≥1), grain (any/required), edge_top/bottom/left/right (thickness mm or null) }`.
   Validates dimensions (50 mm min, ≤ sheet − 2×trim max), grain feasibility, counts (≤ 100 parts).
   Runs FFD + recursive guillotine splitting, **synchronous, 5 s hard timeout**. Produces a `draft`
   `cutting_result` (≤ 20 sheets) with `sheet_layouts`, `waste_percentage`, `sheets_used`,
   `total_cut_length_mm`, `total_edge_length_mm`, `edge_length_by_thickness`, and the stamped
   `algorithm_version`. ≤ 50 open drafts per client. Every call is audited. Full rules: [`docs/spec/cutting.md`](../../spec/cutting.md).
2. `get-cutting-result` (client owns it; workshop staff in scope for `confirmed` results): the result
   JSON, including the layouts.
3. `get-cutting-pdf` (same access): a PDF cutting map — title page (material, sheet size, kerf,
   waste %, sheets, totals), one page per sheet (scaled drawing, part coords, part_ref + quantity
   index, grain arrow), a summary page (edge banding by thickness). Generated server-side, in-process.
4. `list-my-drafts` (client): the client's `draft` results (last 7 days — older ones are auto-deleted
   by the daily job).
5. `delete-my-draft` (client): delete one's own `draft` (only `draft`, only the owner).
6. Lifecycle is system-managed: a draft becomes `confirmed` + bound to an order when the client
   creates an order from it ([`docs/ref/features/order-placement.md`](order-placement.md)); a
   confirmed result becomes `invalidated` when the order's items are modified ([`docs/ref/features/order-modification.md`](order-modification.md)); a daily job deletes drafts older than 7 days; `confirm-cutting-result` / `invalidate-cutting-result` are internal operations the `orders` module calls.

## UX

In the **client app**, the **Cutting wizard** (`/cutting/new`) — a 3-step stepper, mobile-first:

1. **Material** — a branch-context chip (with "change" → branch picker); a material-source toggle
   ("from the shop" / "my own material"); a searchable grid of the branch's active materials (price
   shown only for `shop`); single-select. Empty: "this branch has no materials yet — pick another".
2. **Parts** — a two-pane layout (single column on mobile): left, a parts editor (a table of rows —
   №, length mm, width mm, quantity, grain (any/required), edge per side (0.4 / 2.0 / none); add /
   remove / duplicate row; min 1 row; a `part_ref` UUID hidden per row); a bulk-paste textarea
   accepting `LxWxQty` per line. Right, a live summary: parts count, total area, the material's sheet
   size, a kerf/edge-trim note. Inline validation against the bounds. A "Run optimization" CTA
   (disabled while running; respects the 5 s timeout; on error, highlights the offending part(s) and
   maps `error.code` — `part_too_large`, `part_too_small`, `impossible_grain`, `too_many_parts`,
   `too_many_sheets_needed`, `optimization_timeout`, `draft_limit_exceeded`).
3. **Result** — a big interactive SVG of `sheet_layouts` with sheet tabs (Sheet 1, 2, …); pan/zoom;
   hovering a placement highlights the originating part in a side legend (№, dimensions, quantity
   index). A metric strip: waste %, sheets used, total cut length (m), edge banding by thickness.
   Actions: "Download PDF", "Edit parts" (→ step 2, creating a new draft on next run), "Order with
   this cutting" (→ order create wizard, [`docs/ref/features/order-placement.md`](order-placement.md)). A subtle footer note: "drafts are kept 7 days".

- **My drafts** (`/cutting/drafts`) — table/cards: branch, material, parts count, waste %, sheets,
  created (relative), `draft` chip; row actions Open / Delete (confirm). Empty: "No saved cuttings —
  start a new one."
- **Draft / result view** (`/cutting/:id`) — the step-3 view, read-only from `get-cutting-result`,
  with an "Order with this cutting" CTA (or a note if it's already `confirmed`/`invalidated`).
- In the **seh app**, an order's **Cutting** tab embeds the SVG of the order's confirmed result + a
  PDF link (and, if `invalidated`, shows it with a flag).
- States: every step has loading / empty / error; the optimize call has a running state and a
  timeout/error path (no infinite spinner); the SVG remains scrollable/zoomable on a small phone.
- Accessibility: the SVG layout has a text-equivalent legend (the per-sheet placement list);
  hover-to-highlight has a keyboard/tap equivalent; the parts table is fully keyboard-editable with
  labelled cells; errors are announced and the offending row gets focus.

Shared components (`CuttingLayoutSVG`, `Stepper`, the parts editor, the data table): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/cutting/cutting-result.md`](../entities/cutting/cutting-result.md) — created (draft), bound (confirmed), invalidated, cleaned up.
- [`docs/ref/entities/cutting/cutting-sheet.md`](../entities/cutting/cutting-sheet.md), [`docs/ref/entities/cutting/cutting-placement.md`](../entities/cutting/cutting-placement.md) — the layout detail.
- [`docs/ref/entities/catalog/material.md`](../entities/catalog/material.md) — chosen; provides sheet size & grain.
- [`docs/ref/entities/workshop/branch.md`](../entities/workshop/branch.md) — the branch context.
- [`docs/ref/entities/identity/client.md`](../entities/identity/client.md) — the caller.
- [`docs/ref/entities/support/file.md`](../entities/support/file.md) — the generated PDF.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md) — each `optimize` call.

## Edge cases

- **A part doesn't fit even rotated** → `part_too_large`; the wizard names it and the max size.
- **`required`-grain part can't fit in its forced orientation** → `impossible_grain`.
- **Over the 100-part or 20-sheet cap** → `too_many_parts` / `too_many_sheets_needed`; split the job
  (v1 doesn't queue big jobs).
- **5 s elapses with no solution** → `optimization_timeout`; retry or simplify.
- **Inactive / foreign branch** → `branch_not_accessible`.
- **Over 50 open drafts** → `draft_limit_exceeded`; delete some first.
- **Re-running the same input** may give a slightly different layout — fine; each run is its own
  immutable result.
- **Algorithm replaced later** — old results, PDFs, and the prices computed from them are unchanged.

## Out of scope

- Top-N alternative results — v1 returns the single best ([`docs/spec/open-questions.md`](../../spec/open-questions.md) Q7).
- Async optimization for > 100 parts — v1 rejects them.
- Operator manual layout editing — v1 is algorithm-only.
- Per-branch / per-material kerf & edge-trim — v1 is global.
- Multiple sheet sizes per material; `preferred` grain; custom sheet sizes for `own` material — future.
- 3D nesting, CNC router paths — out of scope entirely.
- A backend SVG endpoint (for share/email) — v1 is PDF + client-side SVG.

## Open questions

- The cutting v1.1 wishlist (alternatives, async, manual edits, overrides, etc.) — owner: shape — see [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q7.
