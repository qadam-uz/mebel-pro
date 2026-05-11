---
title: Cutting placement
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/cutting/cutting-sheet.md
  - docs/ref/entities/cutting/cutting-result.md
  - docs/spec/cutting.md
---

# Cutting placement

## What it is

One placed part on one [cutting sheet](cutting-sheet.md): which input part it is, where it sits
(origin from the bottom-left), the dimensions as placed (which differ from the part's nominal
dimensions if it was rotated), and whether it was rotated 90°. The front-end's SVG layout and the
PDF are rendered from these.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `cutting_sheet_id` | UUID | the sheet it's on | required; → cutting sheet |
| `part_ref` | text | the client-supplied id of the input part (from `parts_snapshot`) | required |
| `part_quantity_index` | int | 1..quantity, when the part has quantity > 1 | ≥ 1 |
| `x_mm` / `y_mm` | int | origin (bottom-left corner) on the sheet | within the usable area |
| `length_mm` / `width_mm` | int | dimensions as placed | |
| `rotated` | bool | `true` if rotated 90° from the part's nominal orientation | |

## States / lifecycle

No lifecycle — written once as part of an immutable cutting result.

## Invariants

- Every input part-instance (each `part_ref` × each quantity index) appears exactly once across the
  result's placements — service rule (a successful run places everything).
- A `grain = required` part is never `rotated` — invariant ([`docs/spec/cutting.md`](../../../spec/cutting.md)).
- Placements don't overlap and stay within `sheet − 2×edge_trim` on each sheet — service rule.
- Immutable — invariant.

## Relationships

- belongs to → [`docs/ref/entities/cutting/cutting-sheet.md`](cutting-sheet.md) (many-to-one)
- refers to (by `part_ref`) → an entry in the parent result's `parts_snapshot` ([`docs/ref/entities/cutting/cutting-result.md`](cutting-result.md))

## Owner

[`docs/ref/features/cutting-optimization.md`](../../features/cutting-optimization.md).
