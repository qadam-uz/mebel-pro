---
title: Branch pricing
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/orders.md
  - docs/ref/entities/workshop/branch.md
  - docs/ref/features/branch-pricing.md
---

# Branch pricing

## What it is

A branch's pricing configuration for the cutting service and edge banding. There is one per branch.
Order pricing reads it at order creation / re-pricing time and snapshots the values onto the order;
later changes don't reach existing orders. See [`docs/spec/orders.md`](../../../spec/orders.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `branch_id` | UUID | the branch (also the PK) | required; → branch; 1:1 |
| `cutting_model` | enum | `per_sheet` or `per_cut` — which way cutting is charged | required |
| `cutting_rate_tiyin` | bigint | the rate: per sheet, or per cut, depending on `cutting_model` | required, ≥ 0 |
| `edge_banding_rates` | json | map of `thickness_mm → rate_tiyin per metre`, e.g. `{ "0.4": 300000, "2.0": 500000 }` | a rate for every banding thickness offered |
| `updated_at` | timestamp | | |
| `updated_by_user_id` | UUID | the owner who last set it | → workshop user with `is_owner` |

## States / lifecycle

No lifecycle states. Edited by the owner; each edit is audited; an order priced before an edit is
unaffected (it has a snapshot).

## Invariants

- Exactly one `branch_pricing` row per branch — DB constraint (PK).
- `cutting_model` is one of `per_sheet` / `per_cut` — a branch picks one — DB check.
- All rates are integer tiyin — invariant.
- A part using an edge-banding thickness with no rate in `edge_banding_rates` makes order pricing
  fail (operational setup gap) — service rule ([`docs/spec/orders.md`](../../../spec/orders.md)).
- Only the workshop owner edits branch pricing (not delegable in v1) — service rule ([`docs/spec/access.md`](../../../spec/access.md)).

## Relationships

- belongs to → [`docs/ref/entities/workshop/branch.md`](../workshop/branch.md) (one-to-one)
- consumed by → [`docs/ref/entities/sales/order.md`](../sales/order.md) (snapshots the rates at pricing time)

## Owner

[`docs/ref/features/branch-pricing.md`](../../features/branch-pricing.md); rules in [`docs/spec/orders.md`](../../../spec/orders.md).
