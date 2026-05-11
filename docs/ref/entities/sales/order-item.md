---
title: Order item
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/sales/order.md
  - docs/ref/entities/catalog/material.md
  - docs/spec/orders.md
---

# Order item

## What it is

One part line of an [order](order.md) — a panel of given dimensions, in some quantity, with optional
edge banding and a grain requirement, plus a frozen snapshot of the material it's cut from and the
prices used. Items mirror the parts the client entered into the cutting wizard for that order.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `order_id` | UUID | the order | required; → order |
| `material_id` | UUID | the material chosen (logical reference; the snapshot is authoritative for the order) | → material |
| `material_snapshot` | json | `{ name, type, thickness_mm, color, decor_code, sheet_length_mm, sheet_width_mm, price_tiyin }` as of order creation | |
| `part_ref` | text | the part's id (matches the cutting result's `parts_snapshot` / placements) | |
| `length_mm` / `width_mm` | int | part dimensions | within material/cutting bounds |
| `quantity` | int | how many | ≥ 1 |
| `grain_direction` | enum | `any` / `required` | required |
| `edge_top_mm` / `edge_bottom_mm` / `edge_left_mm` / `edge_right_mm` | numeric? | edge-banding thickness per side, or null | |
| `unit_cutting_price_tiyin` | bigint | cutting price per unit (snapshot) | ≥ 0 |
| `unit_material_price_tiyin` | bigint | material price per unit (snapshot; 0 unless `shop`) | ≥ 0 |
| `edge_cost_tiyin` | bigint | edge-banding cost for this line (snapshot) | ≥ 0 |
| `line_total_tiyin` | bigint | `(unit_cutting + unit_material) × quantity + edge_cost` | ≥ 0 |

## States / lifecycle

No lifecycle states. On order modification, the items are replaced (and the order re-priced); the
old items aren't kept (the old cutting result is, with its `parts_snapshot`).

## Invariants

- `quantity ≥ 1`; dimensions within the material's usable bounds — service/DB rules.
- `material_snapshot` and the unit prices are a snapshot — never updated to reflect later catalog
  changes ([`docs/spec/architecture.md`](../../../spec/architecture.md)).
- `line_total_tiyin` equals the formula above; all money is integer tiyin — invariant.
- `part_ref` corresponds to a part in the order's cutting result — service rule.
- A `grain = required` part can't be rotated by the cutter (and the cutting result respects that) — invariant.

## Relationships

- belongs to → [`docs/ref/entities/sales/order.md`](order.md) (many-to-one)
- snapshots → [`docs/ref/entities/catalog/material.md`](../catalog/material.md)
- aligns with → entries in [`docs/ref/entities/cutting/cutting-result.md`](../cutting/cutting-result.md)'s `parts_snapshot`

## Owner

[`docs/ref/features/order-placement.md`](../../features/order-placement.md) (creation) and [`docs/ref/features/order-modification.md`](../../features/order-modification.md); pricing in [`docs/spec/orders.md`](../../../spec/orders.md).
