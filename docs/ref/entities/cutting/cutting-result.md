---
title: Cutting result
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/cutting.md
  - docs/spec/orders.md
  - docs/ref/entities/cutting/cutting-sheet.md
  - docs/ref/entities/cutting/cutting-placement.md
  - docs/ref/entities/sales/order.md
  - docs/ref/features/cutting-optimization.md
---

# Cutting result

## What it is

The output of one 2D guillotine optimization run: which sheets to use, where each part sits on them,
the waste %, and the metrics the order's pricing needs. Written once and never mutated — only its
status flips. The algorithm version is stamped on it, so replacing the algorithm doesn't disturb
past results. See [`docs/spec/cutting.md`](../../../spec/cutting.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `branch_id` | UUID | the branch context | required; → branch |
| `material_id` | UUID | the material | required; → material |
| `material_source` | enum | `shop` / `own` | required |
| `status` | enum | `draft` / `confirmed` / `invalidated` | default `draft` |
| `algorithm_version` | text | e.g. `ffd-guillotine-1.0` — stamped at run time | required |
| `sheet_length_mm` / `sheet_width_mm` | int | the sheet size used (snapshot from the material) | |
| `kerf_mm` | int | kerf used (snapshot of the global constant) | |
| `edge_trim_mm` | int | edge trim per side (snapshot) | |
| `waste_percentage` | numeric | 0.0–1.0 | |
| `sheets_used` | int | total sheets | ≤ 20 |
| `total_cut_length_mm` | int | total saw travel — feeds `per_cut`-ish metrics | |
| `total_edge_length_mm` | int | total edge-banding length | |
| `edge_length_by_thickness` | json | `{ "0.4": 12500, "2.0": 4800 }` — for per-thickness pricing | |
| `parts_snapshot` | json | the input parts (each with its `part_ref`, dimensions, qty, grain, edges) | |
| `created_by_client_id` | UUID | the client who ran it | required; → client |
| `order_id` | UUID? | the order it's bound to, once confirmed | null while `draft` |
| `created_at` | timestamp | | |
| `confirmed_at` | timestamp? | when an order was created from it | |
| `invalidated_at` | timestamp? | when superseded by a re-optimization | |

## States / lifecycle

`draft` (on `optimize`; `order_id` null) → `confirmed` (an order is created from it; `order_id` set,
`confirmed_at` set) → `invalidated` (the order's items were modified; a fresh result is bound; the
old one is kept for audit). `confirmed` and `invalidated` results are kept forever; `draft`s older
than 7 days are deleted (with their sheets/placements) by a daily job.

## Invariants

- Immutable after creation — only `status`, `order_id`, `confirmed_at`, `invalidated_at` change; the
  layout, metrics, and `parts_snapshot` never change — invariant ([`docs/spec/architecture.md`](../../../spec/architecture.md)).
- A draft has `order_id = NULL`; a confirmed/invalidated result has a non-null `order_id` — service rule.
- `sheets_used ≤ 20`; ≤ 100 input parts; part sizes within bounds (50 mm min, sheet − 2×trim max) —
  enforced at run time; otherwise the run errors instead of producing a result ([`docs/spec/cutting.md`](../../../spec/cutting.md)).
- A client may have ≤ 50 open drafts — service rule (anti-abuse).
- Visible only to its creator (drafts) or to workshop staff in scope (confirmed) — service rule.

## Relationships

- created by → [`docs/ref/entities/identity/client.md`](../identity/client.md) (many-to-one)
- in → [`docs/ref/entities/workshop/branch.md`](../workshop/branch.md), for → [`docs/ref/entities/catalog/material.md`](../catalog/material.md)
- has → [`docs/ref/entities/cutting/cutting-sheet.md`](cutting-sheet.md) (one-to-many) → [`docs/ref/entities/cutting/cutting-placement.md`](cutting-placement.md)
- bound to → [`docs/ref/entities/sales/order.md`](../sales/order.md) (zero-or-one; one current per order)
- PDF → [`docs/ref/entities/support/file.md`](../support/file.md) (generated on demand)

## Owner

[`docs/ref/features/cutting-optimization.md`](../../features/cutting-optimization.md); rules in [`docs/spec/cutting.md`](../../../spec/cutting.md).
