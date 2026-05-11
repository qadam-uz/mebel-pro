---
title: Branch
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/access.md
  - docs/ref/entities/workshop/workshop.md
  - docs/ref/entities/catalog/material.md
  - docs/ref/entities/workshop/worker.md
  - docs/ref/entities/catalog/branch-pricing.md
  - docs/ref/features/branch-management.md
---

# Branch

## What it is

A physical location of a workshop where panels are cut. Owns its own material catalog, warehouse
stock, workers, and pricing. Its status governs whether clients can see it and order from it. See
[`docs/spec/access.md`](../../../spec/access.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `workshop_id` | UUID | owning workshop | required; → workshop |
| `name` | text | branch name | required |
| `address` | text | street address (text) | required |
| `phone` | text | `+998XXXXXXXXX` | required |
| `latitude` / `longitude` | numeric | geo location (manual entry in v1 — no geocoder) | required |
| `working_hours` | json | per weekday `{ open, close }` | required |
| `status` | enum | `active` / `temporarily_closed` / `inactive` | default `active` |
| `closed_reason` | text? | shown when `temporarily_closed` | optional |
| `created_at` / `updated_at` | timestamp | | |

## States / lifecycle

- `active` — visible to clients; accepts new orders & cutting.
- `temporarily_closed` — visible to clients (shown as closed, with `closed_reason`); no new orders.
- `inactive` — invisible to clients; no new orders; existing orders complete normally.

Transitions `active ↔ temporarily_closed ↔ inactive`, owner-only. Never deleted (soft delete).
Changing status does **not** revoke staff sessions or grants.

## Invariants

- `workshop_id` is the branch's tenant; everything under the branch (materials, stock, workers,
  pricing) belongs to the same workshop — invariant.
- A branch with active orders can be set `inactive` (those orders finish), but the UI warns — service/UI rule.
- Only the workshop owner creates branches / changes status — service rule ([`docs/spec/access.md`](../../../spec/access.md)).
- A branch is never deleted — [`docs/spec/architecture.md`](../../../spec/architecture.md).

## Relationships

- belongs to → [`docs/ref/entities/workshop/workshop.md`](workshop.md) (many-to-one)
- stocks → [`docs/ref/entities/catalog/material.md`](../catalog/material.md) (one-to-many)
- has → [`docs/ref/entities/catalog/branch-pricing.md`](../catalog/branch-pricing.md) (one-to-one)
- employs → [`docs/ref/entities/workshop/worker.md`](worker.md) (one-to-many)
- holds → [`docs/ref/entities/inventory/stock-item.md`](../inventory/stock-item.md) (one per material)
- scope of → [`docs/ref/entities/identity/permission-grant.md`](../identity/permission-grant.md)
- referenced by → [`docs/ref/entities/sales/order.md`](../sales/order.md), [`docs/ref/entities/cutting/cutting-result.md`](../cutting/cutting-result.md)

## Owner

[`docs/ref/features/branch-management.md`](../../features/branch-management.md); [`docs/spec/access.md`](../../../spec/access.md).
