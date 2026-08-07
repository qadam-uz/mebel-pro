---
title: Cutting
status: draft
owner: shape
updated: 2026-07-29
order: 40
---

# Cutting

The client's cutting workspace (a draft) and the output of optimisation runs (one chosen result
per run). Drafts are mutable while the client iterates; results are immutable. Rules are in
[`cutting.md`](../features/cutting.md).

## Cutting draft

The client's editable workspace for one set of parts. Holds the parts list, the most recent
optimisation or imported result, the automatically chosen result, and
the branch the cutting is scoped to. Private to the client — or, when minted by workshop
staff for a walk-in, to that workshop's staff until the order is placed. Persists
indefinitely (no expiry); a client may have at most 50 self-made drafts open at once.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `client_id` | UUID | the client who owns it |
| `name` | text? | operator-editable label; `null` until set. The draft a MAP import commits is seeded from the uploaded file's name (extension stripped, e.g. `AFZAL.map` -> `AFZAL`; blank/unusable leaves it `null`) — every other draft (manual, CSV/XML import) starts unnamed until the operator names it. |
| `created_via_workshop_id` | UUID? | null for a client self-made draft. Set to the minting workshop when staff created the draft for a walk-in ([`cutting.md`](../features/cutting.md#access)): staff access is scoped by it (workshop-wide), the draft is hidden from the client until the order is placed, and it is excluded from the 50-draft cap. On such a draft `preferred_branch_id` is the staff flow's fixed branch, frozen at creation. Unfinished ones (no bound order, `revision_of_order_id` null) are listed on the workshop's **Saqlangan chizmalar** surface for resuming. |
| `revision_of_order_id` | UUID? | null except on an order's **revision draft** ([`orders.md`](../features/orders.md#revising-a-placed-order)): staff-minted from the order's confirmed result, branch-locked to the order's branch, unique per order. A revision draft never places a new order — its only exits are apply (back onto its order) or discard — and it is client-invisible like any staff-minted draft. |
| `preferred_branch_id` | UUID? | the branch the cutting is scoped to; the material picker offers only this branch's carried materials and the order step defaults to it. **Required by the editor** — the parts UI is gated until it's set (see [`cutting.md`](../features/cutting.md)) — but the column stays nullable for drafts predating this rule and for the unsaved window before the first branch pick. Seeded from the client's `preferred_branch_id` on draft create; the client can change it on the draft (no clear-to-none) without affecting the profile default. Never enforces destructively (rows referencing materials the branch doesn't carry stay editable with inline recovery affordances). |
| `parts_snapshot` | json | the parts list as the client has edited it — each part has `part_ref` (UUID), optional display `name` (`null` for fallback `D{row}` in the UI), `material_id` (a `panel`), `material_source` (currently normalised to `shop` by the editor), `follow_grain` (bool, default `true` for old snapshots; when true the part is rotation-locked), `thickened` (bool, default `false` for old snapshots — the workshop glues a strip of the same panel under the part; see [`cutting.md`](../features/cutting.md)), `length_mm`, `width_mm`, `quantity`, and per-side `edge_<top\|bottom\|left\|right>` — each either `null` (no banding on that side) or `{ "material_id": <edge-material>, "source": "shop" }`. Edge thickness/colour are derived from each side's edge material. |
| `chosen_result_id` | UUID? | the result the client picked from the latest run; null between edits and the next optimise |
| `created_at` / `updated_at` | timestamps | |

Invariants: owned by the client (`client_id`) whether self-made (`created_via_workshop_id`
null) or staff-minted for a walk-in (set); never visible beyond the access rules in
[`cutting.md`](../features/cutting.md#access); `parts_snapshot` has 1..100
parts; every referenced `material_id` is a `panel`-kind material; every side's `edge_*` (when
non-null) references an `edge`-kind material; each optimise replaces the previous candidate
with one engine-selected result and points `chosen_result_id` to it; an imported MAP result is
the sole chosen result until a geometry-affecting `parts_snapshot` edit
(adding/removing a `part_ref`, or changing quantity, dimensions, panel material, or
`follow_grain`) deletes every candidate result, including imported MAP results; a geometry-neutral
edit (name, thickening, edge bands, or material source) retains candidates and refreshes their edge metrics
and material snapshots while preserving `chosen_result_id`; a draft has at most one `chosen` at a
time; on order placement — or a revision apply — the chosen result transitions to
`confirmed` (bound to the order) and the draft is deleted; a
revision apply also deletes the order's superseded confirmed result (with its panels and
placements); a self-made draft is deletable by the
client at any time, a staff-minted one by the minting workshop's staff (cascades to results,
panels, placements).

## Cutting result

The single output selected by the cutting engine for a draft's parts. A run may evaluate several
providers internally, but persists only their validated, engine-scored winner and chooses it
automatically. On order placement it becomes `confirmed` and bound. The engine/provider version
is stamped for audit; replacing a solver later doesn't touch past results.

| Field                                                              | Type       | Notes                                                                                                                                                                                |
| ------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `id`                                                               | UUID       | PK                                                                                                                                                                                   |
| `draft_id`                                                         | UUID?      | the draft this result came from; null once `confirmed` (the draft is gone, the result outlives it via `order_id`)                                                                    |
| `algorithm_name` / `algorithm_version`                             | text       | internal audit stamp: `cutting-engine/native`, `cutting-engine/packingsolver`, or `cutting-engine/hybrid` plus engine/provider version; `imported-2dplace-map` / `map-1` for MAP imports. Not a client-visible choice |
| `source`                                                           | enum       | `optimizer` for generated layouts · `imported_map` for a 2D-Place MAP layout committed from import                                                                                   |
| `status`                                                           | enum       | `candidate` (the draft's current result) · `confirmed` (chosen and bound to an order)                                                                                                |
| `kerf_mm` / `edge_trim_mm`                                         | int        | snapshot of the draft's branch settings (or the platform defaults for a branch-less draft) at run time; an imported MAP result instead derives both from the imported layout's own geometry (the dominant gap between adjacent parts, the dominant part inset from a sheet edge — [`cutting.md`](../features/cutting.md#imports)) and falls back to `0` / `0` when the layout gives no evidence |
| `panels_used_by_material`                                          | json       | `{ "<material_id>": 3, "<material_id>": 1 }` — total panels needed per `panel` material in this result (≤ 20 per material)                                                           |
| `waste_percentage`                                                 | numeric    | 0.0–1.0; weighted across all panel materials in the result                                                                                                                           |
| `total_cut_length_mm` / `total_edge_length_mm`                     | int        | feed pricing metrics                                                                                                                                                                 |
| `edge_length_by_material`                                          | json       | `{ "<edge-material_id>": 12500, "<edge-material_id>": 4800 }` — per-edge-material geometric length in integer millimetres; UI/pricing displays metres.                               |
| `parts_snapshot`                                                   | json       | source parts copied from the draft at optimise time, including each part's `name`, `follow_grain` and `thickened`, so the result remains renderable after the draft is deleted on order placement |
| `material_snapshots`                                               | json       | material display/spec facts copied at optimise time for every panel/edge material referenced by the result; used for labels and PDFs after catalog edits                             |
| `edge_length_shop_by_material` / `edge_length_own_by_material`     | json       | source-split geometric edge length, keyed by edge material id, in integer millimetres                                                                                                |
| `edge_consumed_shop_by_material` / `edge_consumed_own_by_material` | json       | source-split edge consumption, keyed by edge material id, in integer millimetres; includes the fixed 30 mm overhang per banded side                                                  |
| `edge_banded_sides_by_material`                                    | json       | `{ "<edge-material_id>": { "shop": 4, "own": 2 } }` — source-split count of banded sides feeding consumption and Phase 5 stock math                                                  |
| `order_id`                                                         | UUID?      | the order it's bound to, once `confirmed`                                                                                                                                            |
| `created_at` / `confirmed_at`                                      | timestamps | as the lifecycle moves                                                                                                                                                               |

Lifecycle: `candidate` on optimise → `confirmed` on order placement (`order_id` set,
`confirmed_at`, `draft_id` cleared). `confirmed` results are kept forever; `candidate`
results are short-lived (replaced on the next optimise call or deleted with the draft).

Invariants: **immutable** after creation — only `status`, `order_id`, `confirmed_at`,
and `draft_id` (cleared on confirm) change; layout, metrics, snapshots, and the per-panel
rows never change. A result carries enough source/material snapshots to render a confirmed
plan after the draft is deleted or catalog display facts change. A `confirmed` result has a
non-null `order_id`; a `candidate` has a non-null `draft_id`. For
each material in `panels_used_by_material`, the count is ≤ 20; the result has placements
covering every part-instance from the source parts list. Visible only to its draft's creator
while `candidate`; to workshop staff in scope and the client once `confirmed`. An imported MAP
candidate is never offered beside an optimizer candidate. A geometry-affecting parts edit deletes
the imported layout and the next run replaces it with one optimizer result; geometry-neutral name,
edge-band, and material-source edits retain the external placement and refresh its edge metrics
and material snapshots.

## Cutting panel

One physical panel within a result — its material, its index within that material, and how
much waste it has.

| Field               | Type   | Notes                                                                                                                                                                                                                                                        |
| ------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `id`                | UUID   | PK                                                                                                                                                                                                                                                           |
| `cutting_result_id` | UUID   | required                                                                                                                                                                                                                                                     |
| `material_id`       | UUID   | required — which `panel` material this panel is, and which panel-size + grain rules govern its placements                                                                                                                                                    |
| `panel_index`       | int    | 1, 2, 3, … **within the result's panels of this material**; unique per (result, material); 1..the material's count in `panels_used_by_material`                                                                                                              |
| `waste_area_mm2`    | bigint | ≥ 0                                                                                                                                                                                                                                                          |
| `cut_count`         | int?   | exact number of engine cuts on this sheet; ≥ 0 when known. `null` for imported MAP and legacy rows, whose cut path is not known.                                                                                                                          |
| `cut_length_mm`     | int?   | exact Manhattan sum of the engine cuts on this sheet; ≥ 0 when known. `null` for imported MAP and legacy rows.                                                                                                                                            |
| `offcuts`           | json?  | display-only rectangles left by the optimiser or imported MAP layout: `{ x_mm, y_mm, length_mm, width_mm, usable }`. Old rows may store null; API responses expose `[]`. Usable offcuts are shown as customer-retained remainders, non-usable ones as waste. |

Invariants: `panel_index` contiguous from 1 to the material's count for that result;
immutable; deleted with its parent result.

## Cutting placement

One placed part on one panel: which input part it is, where it sits (origin from the
bottom-left), the dimensions as placed (which differ from the part's nominal dimensions if it
was rotated), and whether it was rotated 90°.

| Field                    | Type | Notes                                                            |
| ------------------------ | ---- | ---------------------------------------------------------------- |
| `id`                     | UUID | PK                                                               |
| `cutting_panel_id`       | UUID | required                                                         |
| `part_ref`               | text | the part id from the draft's `parts_snapshot`                    |
| `part_quantity_index`    | int  | 1..quantity, when the part has quantity > 1; ≥ 1                 |
| `x_mm` / `y_mm`          | int  | origin (bottom-left corner) on the panel; within the usable area |
| `length_mm` / `width_mm` | int  | dimensions as placed                                             |
| `rotated`                | bool | `true` if rotated 90° from the part's nominal orientation        |

Invariants: every input part-instance (each `part_ref` × each quantity index) in the source
parts list appears exactly once across the result's placements; the placement sits on a
panel whose `material_id` matches the part's panel material; a locked part (grained material
and `follow_grain=true`) is never `rotated`; placements don't overlap and stay within
`panel − 2× edge_trim`; immutable.

## Next

- [`../features/cutting.md`](../features/cutting.md) — cutting behavior and lifecycle.
- [PackingSolver provider spec](https://github.com/BerdiyorovAbrorjon/cutting-engine/blob/main/docs/PACKINGSOLVER_PROVIDER_SPEC.md)
  — internal solver orchestration and audit stamps.
