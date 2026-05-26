---
title: Cutting
status: draft
owner: shape
updated: 2026-05-25
order: 40
---

# Cutting

The client's cutting workspace (a draft) and the output of optimisation runs (one result per
algorithm). Drafts are mutable while the client iterates; results are immutable. Rules are in
[`cutting.md`](../features/cutting.md).

## Cutting draft

The client's editable workspace for one set of parts. Holds the parts list, the most recent
optimisation run's results (one per algorithm — see below), the client's chosen result, and
an optional intended-branch pre-filter. Private to the client. Persists indefinitely (no
expiry); a client may have at most 50 drafts open at once.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `client_id` | UUID | the client who owns it |
| `preferred_branch_id` | UUID? | optional — when set, the material picker is pre-filtered to this branch's selection; the order step defaults to it. Seeded from the client's `preferred_branch_id` on draft create; the client can clear or change it on the draft without affecting the profile default. Never enforces destructively (rows referencing materials this branch doesn't carry stay editable with inline recovery affordances — see [`cutting.md`](../features/cutting.md)). |
| `parts_snapshot` | json | the parts list as the client has edited it — each part has `part_ref` (UUID), `material_id` (a `panel`), `material_source` (`shop` / `own`), `length_mm`, `width_mm`, `quantity`, and per-side `edge_<top\|bottom\|left\|right>` — each either `null` (no banding on that side) or `{ "material_id": <edge-material>, "source": "shop" \| "own" }`. Grain is derived from the panel material (not stored on the part); edge thickness/colour are derived from each side's edge material. |
| `chosen_result_id` | UUID? | the result the client picked from the latest run; null between edits and the next optimise |
| `created_at` / `updated_at` | timestamps | |

Invariants: created by a client, owned by them, never shared; `parts_snapshot` has 1..100
parts; every referenced `material_id` is a `panel`-kind material; every side's `edge_*` (when
non-null) references an `edge`-kind material; on each optimise the previous run's results
are replaced and `chosen_result_id` re-points (defaulting to the lowest-waste algorithm); a
draft has at most one `chosen` at a time; on order placement the chosen result transitions
to `confirmed` (bound to the order) and the draft + the unchosen results are deleted;
deletable by the client at any time (cascades to results, panels, placements).

## Cutting result

The output of **one algorithm** on a draft's parts. A single optimise call produces N
results (one per available algorithm); all are kept until the next optimise call replaces
them, and the client picks one as `chosen`. On order placement the chosen result becomes
`confirmed` and bound; the others are discarded. The algorithm version is stamped — replacing
the algorithm later doesn't touch past results.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `draft_id` | UUID? | the draft this result came from; null once `confirmed` (the draft is gone, the result outlives it via `order_id`) |
| `algorithm_name` / `algorithm_version` | text | e.g. `ffd-guillotine` / `1.0` — stamped at run time |
| `status` | enum | `candidate` (one of N from an optimise run) · `confirmed` (chosen and bound to an order) · `invalidated` (was confirmed; an order modify produced a fresher result) |
| `kerf_mm` / `edge_trim_mm` | int | snapshot of the global constants at run time |
| `panels_used_by_material` | json | `{ "<material_id>": 3, "<material_id>": 1 }` — total panels needed per `panel` material in this result (≤ 20 per material) |
| `waste_percentage` | numeric | 0.0–1.0; weighted across all panel materials in the result |
| `total_cut_length_mm` / `total_edge_length_mm` | int | feed pricing metrics |
| `edge_length_by_material` | json | `{ "<edge-material_id>": 12500, "<edge-material_id>": 4800 }` — per-edge-material pricing input (only `shop`-source edge metres count toward stock decrement; see [`sales.md`](sales.md)). Thickness is derived from the material at read time. |
| `order_id` | UUID? | the order it's bound to, once `confirmed` |
| `created_at` / `confirmed_at` / `invalidated_at` | timestamps | as the lifecycle moves |

Lifecycle: `candidate` on optimise → `confirmed` on order placement (`order_id` set,
`confirmed_at`, `draft_id` cleared) → `invalidated` when the order is modified in a way that
needs a fresh result (the new result is bound; this one is kept). `confirmed` and
`invalidated` are kept forever; `candidate` results are short-lived (deleted on the next
optimise call, on order placement when they weren't chosen, or with the draft).

Invariants: **immutable** after creation — only `status`, `order_id`, `confirmed_at`,
`invalidated_at`, and `draft_id` (cleared on confirm) change; layout, metrics, and the
per-panel rows never change. A `confirmed` / `invalidated` result has a non-null `order_id`;
a `candidate` has a non-null `draft_id`. For each material in `panels_used_by_material`, the
count is ≤ 20; the result has placements covering every part-instance from the source
parts list. Visible only to its draft's creator while `candidate`; to workshop staff in
scope and the client once `confirmed` / `invalidated`.

## Cutting panel

One physical panel within a result — its material, its index within that material, and how
much waste it has.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_result_id` | UUID | required |
| `material_id` | UUID | required — which `panel` material this panel is, and which panel-size + grain rules govern its placements |
| `panel_index` | int | 1, 2, 3, … **within the result's panels of this material**; unique per (result, material); 1..the material's count in `panels_used_by_material` |
| `waste_area_mm2` | bigint | ≥ 0 |

Invariants: `panel_index` contiguous from 1 to the material's count for that result;
immutable; deleted with its parent result.

## Cutting placement

One placed part on one panel: which input part it is, where it sits (origin from the
bottom-left), the dimensions as placed (which differ from the part's nominal dimensions if it
was rotated), and whether it was rotated 90°.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_panel_id` | UUID | required |
| `part_ref` | text | the part id from the draft's `parts_snapshot` |
| `part_quantity_index` | int | 1..quantity, when the part has quantity > 1; ≥ 1 |
| `x_mm` / `y_mm` | int | origin (bottom-left corner) on the panel; within the usable area |
| `length_mm` / `width_mm` | int | dimensions as placed |
| `rotated` | bool | `true` if rotated 90° from the part's nominal orientation |

Invariants: every input part-instance (each `part_ref` × each quantity index) in the source
parts list appears exactly once across the result's placements; the placement sits on a
panel whose `material_id` matches the part's panel material; a part on a grained material is
never `rotated`; placements don't overlap and stay within `panel − 2× edge_trim`; immutable.
