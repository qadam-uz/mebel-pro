---
title: Material
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/cutting.md
  - docs/spec/orders.md
  - docs/ref/entities/workshop/branch.md
  - docs/ref/entities/inventory/stock-item.md
  - docs/ref/features/material-catalog.md
---

# Material

## What it is

A cuttable sheet product in a branch's catalog — a particular board type, thickness, decor, and
standard sheet size, with a price per sheet. Per branch: the same physical product may exist (or not)
in another branch with a different price. A client picks a material when starting a cutting; the
cutting optimizer reads its sheet size and grain; the order snapshots its price.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `branch_id` | UUID | the branch this material belongs to | required; → branch |
| `type` | enum | `dsp` / `mdf` / `plywood` / `natural_wood` / `other` | required |
| `name` | text | full product name, e.g. "Kronospan DSP White 18mm" | required |
| `thickness_mm` | int | board thickness | required (e.g. 8/10/16/18/22/25) |
| `color` | text | color / decor name | required |
| `decor_code` | text? | decor code, e.g. `W1100` | optional |
| `sheet_length_mm` / `sheet_width_mm` | int | the one standard sheet size for this material | required; `length ≥ width` (long side = grain direction) |
| `price_tiyin` | bigint | price per sheet, in tiyin | required, ≥ 0 |
| `grain_direction` | bool | `true` if the board has a grain | required |
| `image_file_id` | UUID? | → [`file`](../support/file.md) sample image | optional |
| `status` | enum | `active` / `inactive` | default `active` |
| `created_at` / `updated_at` | timestamp | | |

## States / lifecycle

`active` ↔ `inactive` (soft delete only — old orders reference it by snapshot anyway). An `inactive`
material is invisible to clients and can't be chosen in a new cutting.

## Invariants

- One material → one standard sheet size (v1) — invariant ([`docs/spec/cutting.md`](../../../spec/cutting.md)).
- `sheet_length_mm ≥ sheet_width_mm` (the long side is the grain direction) — service/DB rule.
- `price_tiyin` is integer tiyin, never a float — invariant.
- Editing the price never affects existing orders (they snapshot it) — [`docs/spec/architecture.md`](../../../spec/architecture.md).
- Managed by users with `manage_catalog` on the branch (or the owner) — service rule.
- Never deleted — soft delete.

## Relationships

- belongs to → [`docs/ref/entities/workshop/branch.md`](../workshop/branch.md) (many-to-one)
- tracked by → [`docs/ref/entities/inventory/stock-item.md`](../inventory/stock-item.md) (one stock item per material per branch)
- referenced by (snapshot) → [`docs/ref/entities/sales/order-item.md`](../sales/order-item.md), [`docs/ref/entities/cutting/cutting-result.md`](../cutting/cutting-result.md)
- image → [`docs/ref/entities/support/file.md`](../support/file.md)

## Owner

[`docs/ref/features/material-catalog.md`](../../features/material-catalog.md).
