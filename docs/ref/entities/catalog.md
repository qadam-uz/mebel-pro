---
title: Catalog
status: draft
owner: shape
updated: 2026-05-22
order: 25
---

# Catalog

The platform's material catalog, each branch's selection from it, and each branch's pricing.
Materials are **platform-wide master records** — defined once by platform operators; each
branch picks which it carries and sets its own price. Branch pricing (cutting model +
edge-banding rates) drives every order's price. Snapshot semantics (a price change never
reaches an existing order) live in [`architecture.md`](../../architecture.md) → *Data model
invariants*.

## Material

A platform master record (one per spec and sheet size), of two **kinds** in v1: a `sheet` (a cuttable
board, stocked and priced per sheet) or an `edge` (edge-banding tape, stocked and measured
per metre). A client picks a sheet when starting a cutting and an edge thickness per side;
the optimizer reads the sheet's size and grain; the order snapshots the material's details
and the branch's price.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `kind` | enum | `sheet` / `edge` |
| `type` | enum? | `sheet` only: `dsp` / `mdf` / `plywood` / `natural_wood` / `other` |
| `name` | text | required, includes the sheet size, e.g. "Kronospan DSP White 18mm · 2750×1830" |
| `thickness_mm` | numeric | required (sheets e.g. 8/16/18; edges e.g. 0.4/2.0) |
| `color` / `decor_code` | text / text? | required / optional |
| `sheet_length_mm` / `sheet_width_mm` | int? | **`sheet` only**, required there; `length ≥ width` (long side = grain direction); null for `edge` |
| `grain_direction` | bool? | **`sheet` only**; `true` if the board has a grain; null for `edge` |
| `image_file_id` | UUID? | → [file](support.md#file) — sample image |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Invariants: `sheet` materials have `type`, sheet size (`length ≥ width`), and grain; `edge`
materials have none of these and are measured in metres; one standard sheet size per `sheet`
material (v1) — a material's identity is its spec **and** that size, so the same spec stocked in
two sheet sizes is two separate materials, each naming its size; created and edited only by a
platform operator (platform users have full
platform scope; no workshop-side permission grants this); `inactive` invisible to new branch
selections and to clients; existing branch selections of an `inactive` master keep
referencing it (history preserved); never deleted; editing a master never affects existing
orders (snapshots).

## Branch material

A branch's selection of a platform material — the (branch, material) link that says "this
branch carries this material at this price." Created when a branch adds a material to its
catalog; holds the per-branch price and the branch-level visibility flag. The branch's
[`stock_item`](inventory.md#stock-item) for the material is created alongside this record.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `material_id` | UUID | required; references a platform [Material](#material) |
| `price_tiyin` | bigint | per stock unit (per **sheet** for a `sheet`, per **metre** for an `edge`), integer tiyin, ≥ 0 |
| `min_stock` | int | low-stock threshold for the branch's stock item; ≥ 0 |
| `status` | enum | `active` / `inactive` at the branch level (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Order pricing uses a `sheet`'s `price_tiyin` (for `shop` parts) and the branch's
[Branch pricing](#branch-pricing) for cutting and edge banding. An `edge` material's
`price_tiyin` is a **cost reference only** — banding is priced from `edge_banding_rates`,
not the per-metre material price (v1).

Invariants: `(branch_id, material_id)` unique; price is integer tiyin (never float); editing
the price never affects existing orders (snapshots); created and edited by the workshop owner or
a `manage_catalog` grantee on the branch; the referenced Material must be `active` at the
platform level when the selection is created (existing selections survive a later platform
deactivation); `inactive` invisible to clients shopping at this branch and not selectable in a
new cutting; a client sees a material at a branch only when **both** the master Material and
the Branch material are `active`; never deleted.

## Branch pricing

A branch's pricing configuration for the cutting service and edge banding. There is one per
branch. Order pricing reads it at order creation / re-pricing time and snapshots the values onto
the order; later changes don't reach existing orders.

| Field | Type | Notes |
|---|---|---|
| `branch_id` | UUID | PK; 1:1 with branch |
| `cutting_model` | enum | `per_sheet` or `per_cut` |
| `cutting_rate_tiyin` | bigint | the rate per the chosen model, ≥ 0 |
| `edge_banding_rates` | json | map `thickness_mm → rate_tiyin per metre`, e.g. `{ "0.4": 300000, "2.0": 500000 }` |
| `updated_at` | timestamp | |
| `updated_by_user_id` | UUID | → workshop user with `is_owner` |

Invariants: exactly one row per branch (DB PK); rates are integer tiyin; a part using a banding
thickness with no rate makes order pricing fail (operational gap; the owner adds it); only the
workshop owner edits (not delegable in v1).
