---
title: Cutting
status: draft
owner: shape
updated: 2026-05-13
order: 40
---

# Cutting

The output of a 2D guillotine optimization run — the result, its sheets, and the placed parts.
Written once and never mutated; only the result's status flips and its `order_id` is set when an
order is created from it. Rules are in [`cutting.md`](../features/cutting.md).

## Cutting result

The output of one optimization run: which sheets to use, where each part sits on them, the waste
%, and the metrics the order's pricing needs. The algorithm version is stamped — replacing the
algorithm later doesn't touch past results.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` / `material_id` | UUID | required; the context |
| `material_source` | enum | `shop` / `own` |
| `status` | enum | `draft` / `confirmed` / `invalidated` (default `draft`) |
| `algorithm_version` | text | e.g. `ffd-guillotine-1.0` — stamped at run time |
| `sheet_length_mm` / `sheet_width_mm` | int | snapshot from the material |
| `kerf_mm` / `edge_trim_mm` | int | snapshot of the global constants |
| `waste_percentage` | numeric | 0.0–1.0 |
| `sheets_used` | int | ≤ 20 |
| `total_cut_length_mm` / `total_edge_length_mm` | int | feed pricing metrics |
| `edge_length_by_thickness` | json | `{ "0.4": 12500, "2.0": 4800 }` — per-thickness pricing input |
| `parts_snapshot` | json | the input parts (each with `part_ref`, dimensions, qty, grain, edges) |
| `created_by_client_id` | UUID | the client who ran it |
| `order_id` | UUID? | the order it's bound to, once confirmed |
| `created_at` / `confirmed_at` / `invalidated_at` | timestamps | as the lifecycle moves |

Lifecycle: `draft` on `optimize` (`order_id = NULL`) → `confirmed` when an order is created
(`order_id` set, `confirmed_at`) → `invalidated` when the order's items are modified (a fresh
result is bound; the old one is kept). `confirmed`/`invalidated` are kept forever; drafts older
than 7 days are deleted by a daily job.

Invariants: **immutable** after creation — only `status`, `order_id`, `confirmed_at`,
`invalidated_at` change; the layout, metrics, and `parts_snapshot` never change. A draft has
`order_id = NULL`; a confirmed/invalidated result has a non-null `order_id`. `sheets_used ≤ 20`;
≤ 100 input parts; sizes within bounds (50 mm min, sheet − 2×trim max). A client may have ≤ 50
open drafts. Visible only to its creator (drafts) or workshop staff in scope (confirmed).

## Cutting sheet

One physical sheet within a result — its index and how much waste it has.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_result_id` | UUID | required |
| `sheet_index` | int | 1, 2, 3, … within the result; unique per result; 1..`sheets_used` |
| `waste_area_mm2` | bigint | ≥ 0 |

Invariants: `sheet_index` contiguous from 1 to the result's `sheets_used`; immutable; deleted
only when its (draft) parent result is cleaned up.

## Cutting placement

One placed part on one sheet: which input part it is, where it sits (origin from the
bottom-left), the dimensions as placed (which differ from the part's nominal dimensions if it
was rotated), and whether it was rotated 90°.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_sheet_id` | UUID | required |
| `part_ref` | text | the client-supplied id of the input part (from `parts_snapshot`) |
| `part_quantity_index` | int | 1..quantity, when the part has quantity > 1; ≥ 1 |
| `x_mm` / `y_mm` | int | origin (bottom-left corner) on the sheet; within the usable area |
| `length_mm` / `width_mm` | int | dimensions as placed |
| `rotated` | bool | `true` if rotated 90° from the part's nominal orientation |

Invariants: every input part-instance (each `part_ref` × each quantity index) appears exactly
once across the result's placements; a `grain = required` part is never `rotated`; placements
don't overlap and stay within `sheet − 2×edge_trim` on each sheet; immutable.
