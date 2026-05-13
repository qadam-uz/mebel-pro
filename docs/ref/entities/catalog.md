---
title: Catalog
status: draft
owner: shape
updated: 2026-05-13
order: 25
---

# Catalog

The platform's material catalog, each branch's selection from it, and each branch's pricing.
Materials are **platform-wide master records** — defined once by platform operators; each
branch picks which it carries and sets its own per-sheet price. Branch pricing (cutting model +
edge-banding rates) drives every order's price. Snapshot semantics (a price change never
reaches an existing order) live in [`architecture.md`](../../architecture.md) → *Data model
invariants*.

## Material

A cuttable sheet product — type, thickness, colour, sheet size, grain. Defined once at the
platform level (one master record per spec). A client picks a material when starting a cutting;
the optimizer reads its sheet size and grain; the order snapshots the material's details and
the branch's price.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `type` | enum | `dsp` / `mdf` / `plywood` / `natural_wood` / `other` |
| `name` | text | required, e.g. "Kronospan DSP White 18mm" |
| `thickness_mm` | int | required (e.g. 8/10/16/18/22/25) |
| `color` / `decor_code` | text / text? | required / optional |
| `sheet_length_mm` / `sheet_width_mm` | int | required; `length ≥ width` (long side = grain direction) |
| `grain_direction` | bool | `true` if the board has a grain |
| `image_file_id` | UUID? | → [file](support.md#file) — sample image |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Invariants: one standard sheet size per material (v1); `length ≥ width`; created and edited
only by a platform operator (platform users have full platform scope; no workshop-side
permission grants this); `inactive` invisible to new branch selections and to clients; existing
branch selections of an `inactive` master keep referencing it (history preserved); never
deleted; editing a master never affects existing orders (snapshots).

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
| `price_tiyin` | bigint | per sheet, integer tiyin, ≥ 0 — the branch's price for this material |
| `status` | enum | `active` / `inactive` at the branch level (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

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
