---
title: Catalog
status: draft
owner: shape
updated: 2026-06-02
order: 25
---

# Catalog

The platform's material catalog, the manufacturers behind the catalog, each branch's
selection from it, and each branch's pricing. Materials are **platform-wide master records**
— defined once by platform operators; each branch picks which it carries and sets its own
price. Branch pricing carries the two service rates (per-panel cutting + per-metre edge
banding labour); the branch's per-metre price on each edge selection is the **raw material**
price for that tape. Order pricing combines them: edge cost = material + labour, summed per
metre. Snapshot semantics (a price change never reaches an existing order) live in
[`architecture.md`](../../architecture.md) → *Data model invariants*.

## Manufacturer

Who makes a material — Kronospan, Egger, Rehau, and so on. A platform-scoped master record:
two materials with the same spec but different manufacturers are two separate catalog rows
(identity includes the manufacturer). Created by platform operators on demand from the
material-create form.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `name` | text | required; unique (case-insensitive) |
| `country` | text? | optional — disambiguates similarly-named brands |
| `note` | text? | optional — short free-text |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Invariants: `name` unique; created and edited only by a platform operator; `inactive` invisible
to new material creates and to branch material-selection pickers; existing materials of an
`inactive` manufacturer keep referencing it (history preserved); never deleted.

## Material

A platform master record (one per spec, panel size where applicable, **and manufacturer**), of
two **kinds** in v1: a `panel` (a cuttable board, stocked and priced per panel) or an `edge`
(edge-banding tape, stocked and measured per metre). A client picks a panel when starting a
cutting and an edge material per side; the optimizer reads the panel's size and grain; the
order snapshots the material's details and the branch's price.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `kind` | enum | `panel` / `edge` |
| `manufacturer_id` | UUID | required; references a platform [Manufacturer](#manufacturer) |
| `type` | enum? | `panel` only: `dsp` / `mdf` / `plywood` / `natural_wood` / `other` |
| `name` | text | required; spec + size, e.g. "DSP H1334 ST9 · Dub Sonoma · 18 mm · 2750×1830" — manufacturer rendered separately, not embedded in the name |
| `thickness_mm` | numeric | required (panels e.g. 8/16/18; edges e.g. 0.4/2.0) |
| `color` / `decor_code` | text / text? | required / optional |
| `panel_length_mm` / `panel_width_mm` | int? | **`panel` only**, required there; `length ≥ width` (long side = grain direction); null for `edge` |
| `grain_direction` | bool? | **`panel` only**; `true` if the board has a grain; null for `edge` |
| `image_file_id` | UUID? | → [file](support.md#file) — sample image |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Invariants: `panel` materials have `type`, panel size (`length ≥ width`) and grain; `edge`
materials have none of these and are measured in metres; one standard panel size per `panel`
material (v1) — a material's identity is its spec, that size, **and its manufacturer**, so the
same spec in two manufacturers is two catalog rows and the same spec in two panel sizes is two
more, each naming its specifics; created and edited only by a platform operator (platform
users have platform-ops scope for this; no workshop-side permission grants it); `inactive` invisible
to new branch selections and to clients; existing branch selections of an `inactive` master
keep referencing it (history preserved); never deleted; editing a master never affects
existing orders (snapshots).

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
| `price_tiyin` | bigint | per stock unit (per **panel** for a `panel`, per **metre** for an `edge`), integer tiyin, ≥ 0 |
| `min_stock` | int | low-stock threshold for the branch's stock item; ≥ 0 |
| `status` | enum | `active` / `inactive` at the branch level (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Order pricing reads `price_tiyin` for **both** kinds: a `panel`'s per-panel price for `shop`
panel parts, and an `edge`'s per-metre price for every `shop` edge metre. The per-metre edge
price is the **raw material rate** for that tape — the **edge-banding labour** is a separate
per-metre rate on [Branch pricing](#branch-pricing), added on top of the material. Cutting
service is the per-panel rate, also on Branch pricing.

Invariants: `(branch_id, material_id)` unique; price integer tiyin (never float); editing
the price never affects existing orders (snapshots); created and edited by the workshop owner
or a `manage_catalog` grantee on the branch; the referenced Material must be `active` at the
platform level when the selection is created (existing selections survive a later platform
deactivation); `inactive` invisible to clients shopping at this branch and not selectable in
a new cutting; a client sees a material at a branch only when **both** the master Material
and the Branch material are `active`; never deleted.

## Branch pricing

A branch's service-rate configuration: one rate for cutting a panel, one rate for applying a
metre of edge tape (any thickness). There is one row per branch. Order pricing reads it at
order creation time and snapshots the values onto the order; later changes don't reach
existing orders. Edge **material** cost is separate — it lives on the per-metre `price_tiyin`
of each [Branch material](#branch-material) `edge` selection.

| Field | Type | Notes |
|---|---|---|
| `branch_id` | UUID | PK; 1:1 with branch |
| `cutting_rate_tiyin` | bigint | the rate per panel cut, ≥ 0 |
| `edge_banding_rate_tiyin` | bigint | the labour rate per metre of tape applied, ≥ 0 (one rate; thickness is the material's property and doesn't change the rate in v1) |
| `updated_at` | timestamp | |
| `updated_by_user_id` | UUID | → workshop user with `is_owner` |

Invariants: exactly one row per branch (DB PK); rates are integer tiyin; only the workshop
owner edits (not delegable in v1). A part using an edge material the branch doesn't carry
makes order pricing fail (operational gap; the owner adds the edge to the branch's selection).
