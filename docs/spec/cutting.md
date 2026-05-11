---
title: Cutting optimization
status: stable
owner: shape
updated: 2026-05-11
order: 80
related:
  - docs/spec/orders.md
  - docs/spec/architecture.md
  - docs/spec/envelope.md
  - docs/ref/entities/cutting/cutting-result.md
  - docs/ref/features/cutting-optimization.md
---

# Cutting optimization

## Purpose

The 2D guillotine cutting-stock solver: in, a list of parts; out, a sheet-layout scheme, a waste %,
and the metrics the order needs for pricing. Cutting is its own module — no pricing/payment/stock
logic in it; it does geometry and exposes results. This page is the canonical behaviour; the
client-facing wizard and screens are [`docs/ref/features/cutting-optimization.md`](../ref/features/cutting-optimization.md); the order integration is [`docs/spec/orders.md`](orders.md).

## Actors

- **Client** — enters parts, runs `optimize`, views the result (SVG layout, metrics, PDF), iterates.
  The *only* caller of `optimize`.
- **Workshop staff** (`manage_orders`) — view the confirmed result + open the PDF for the saw
  operator; cannot run `optimize` or edit the layout.
- **System** — runs the algorithm within its budget, stores the result as a snapshot, manages the
  draft → confirmed → invalidated lifecycle, runs the draft-cleanup job.

## Rules

- **Guillotine cuts only.** A cut runs straight through a rectangle edge-to-edge; the algorithm
  recursively splits the sheet into smaller rectangles. Non-guillotine / L-shaped / CNC-router
  paths are out of scope.
- **Algorithm (v1):** First-Fit-Decreasing + recursive guillotine splitting, pure Python, in-process.
  Parts sorted by area descending; each placed in the smallest fitting free rectangle; the leftover
  split by a guillotine cut. The algorithm version is **stamped on the result**; replacing the
  algorithm doesn't touch past results ([`docs/spec/architecture.md`](architecture.md) context — immutable snapshots).
- **Non-deterministic results are allowed.** The same input may yield a slightly different layout on
  re-run — not a problem; each run is its own immutable `cutting_result_id`.
- **Single best result.** The algorithm returns one result optimizing for **waste % minimized** —
  no alternatives in v1. Unhappy with it → change parts → run again (new draft).
- **Grain:** two modes — `any` (algorithm may rotate the part 90°) and `required` (part length must
  run parallel to the sheet's grain direction = its long side; no rotation). A `required` part that
  can't fit in its forced orientation → `impossible_grain` error.
- **Sheet handling:** one material → one standard sheet size (from the material catalog), for both
  `own` and `shop` sources. `own` means the client brings the material, but the type/thickness is
  still chosen from the catalog (for pricing & edge data); custom sheet sizes are a future option.
- **Global constants:** kerf 4 mm, edge trim 10 mm per side (usable area = sheet − 2× edge trim).
  These are global config; per-branch/per-material overrides are future.
- **Edge-banding length is computed here** (the order's pricing uses it): for each part edge that
  has a banding thickness set, the edge length is the part's length (top/bottom) or width
  (left/right); totals are grouped by thickness (`edge_length_by_thickness`).
- **No stock check at cutting time.** Cutting just says "N sheets needed"; the real availability
  check is `inventory.reserve` at order confirmation ([`docs/spec/orders.md`](orders.md)).
- **Limits:** part 50 mm × 50 mm minimum; max part = sheet − 2× edge trim; ≤ 100 parts per
  `optimize` (more → rejected, not queued, in v1); ≤ 20 sheets per result (a bigger job must be
  split); ≤ 50 open drafts per client (anti-abuse; the cleanup job prunes). 5 s hard timeout on the
  request → `optimization_timeout`.
- **Lifecycle:** `draft` on `optimize` (not bound to an order, `order_id = NULL`) → `confirmed` when
  an order is created from it (`order_id` set, `confirmed_at`) → `invalidated` when the order is
  modified (a fresh result is bound; the old one is kept for audit). Confirmed and invalidated
  results are kept forever; drafts older than 7 days are deleted (with their sheets/placements) by a
  daily job.
- **Access:** a client sees only their own drafts and confirmed results; workshop staff/owner see
  confirmed results for orders in their scope; the PDF download is gated the same way (UUID ids, no
  enumeration). Every `optimize` call is audited.

## Flow

```
client → POST /api/v1/cutting/optimize { branch_id, material_id, material_source, parts[] }
         validate dimensions / grain / counts → error if any
         run FFD + guillotine splitting, ≤ 5 s
   ← { cutting_result_id, status: draft, algorithm_version, sheet_size,
       waste_percentage, sheets_used, total_cut_length_mm, total_edge_length_mm,
       edge_length_by_thickness, sheet_layouts[ { sheet_index, placements[ {part_ref, x, y, length, width, rotated} ], waste_area } ] }
   → client renders SVG, may download PDF (GET /cutting/results/:id/pdf), may re-run

client creates an order from a draft → cutting result → confirmed, bound to the order
client modifies the order's items → re-run → new draft → confirmed & bound; old result → invalidated
daily job → delete drafts older than 7 days
```

## Edge cases & failure paths

- **`material_not_found`** — bad/foreign material id → 404.
- **`part_too_large` / `part_too_small`** — outside the size bounds → 400; the wizard highlights the
  offending part.
- **`impossible_grain`** — `required` part can't fit in its forced orientation → 400.
- **`too_many_parts` / `too_many_sheets_needed`** — over the caps → 400; split the job.
- **`optimization_timeout`** — no solution within 5 s → 504; retry or simplify.
- **`branch_not_accessible`** — branch inactive or another workshop's → 403.
- **`draft_limit_exceeded`** — > 50 open drafts → the client must delete some first.
- **Algorithm replaced** later — fine: old results are immutable and stamped with their version; the
  PDF and metrics still match what the order was priced on.

## See also

- [`docs/spec/orders.md`](orders.md) — how a confirmed result is consumed, when it's invalidated, and which cutting metrics drive which price component.
- [`docs/spec/architecture.md`](architecture.md) — the immutable-snapshot invariant (and why the algorithm can be replaced without disturbing past results).
- [`docs/spec/envelope.md`](envelope.md) — the latency/correctness budget that justifies "synchronous, ≤ 100 parts".
- [`docs/ref/entities/cutting/cutting-result.md`](../ref/entities/cutting/cutting-result.md), [`docs/ref/entities/cutting/cutting-sheet.md`](../ref/entities/cutting/cutting-sheet.md), [`docs/ref/entities/cutting/cutting-placement.md`](../ref/entities/cutting/cutting-placement.md).
- [`docs/ref/features/cutting-optimization.md`](../ref/features/cutting-optimization.md).
