---
title: Cutting sheet
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/cutting/cutting-result.md
  - docs/ref/entities/cutting/cutting-placement.md
  - docs/spec/cutting.md
---

# Cutting sheet

## What it is

One physical sheet within a [cutting result](cutting-result.md) — its index in the layout and how
much of it ends up as waste. The result has `sheets_used` of these; each has a list of
[placements](cutting-placement.md) on it.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `cutting_result_id` | UUID | the parent result | required; → cutting result |
| `sheet_index` | int | 1, 2, 3, … within the result | unique per result; 1..`sheets_used` |
| `waste_area_mm2` | bigint | waste area on this sheet | ≥ 0 |

## States / lifecycle

No lifecycle — written once as part of an immutable cutting result.

## Invariants

- `sheet_index` is contiguous from 1 to the result's `sheets_used` — service rule.
- Immutable (part of an immutable result) — invariant.
- Deleted only when its (draft) parent result is cleaned up after 7 days — service rule.

## Relationships

- belongs to → [`docs/ref/entities/cutting/cutting-result.md`](cutting-result.md) (many-to-one)
- has → [`docs/ref/entities/cutting/cutting-placement.md`](cutting-placement.md) (one-to-many)

## Owner

[`docs/ref/features/cutting-optimization.md`](../../features/cutting-optimization.md).
