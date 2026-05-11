---
title: Worker
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/ref/entities/workshop/branch.md
  - docs/ref/entities/sales/order.md
  - docs/ref/features/worker-management.md
---

# Worker

## What it is

A physical employee of a branch — a saw operator (cutter), a delivery driver, an assembler, etc.
**Not a system user** (no login, no auth): a worker is registered only so an order can be assigned to
one (a cutter when production starts, a driver when delivery starts).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `branch_id` | UUID | the branch this worker belongs to | required; → branch |
| `full_name` | text | name | required |
| `phone` | text | `+998XXXXXXXXX` | required |
| `position` | enum | `cutter` / `driver` / `assembler` / `other` | required |
| `status` | enum | `active` / `inactive` | default `active` |
| `created_at` / `updated_at` | timestamp | | |

## States / lifecycle

`active` ↔ `inactive` (soft delete only). An `inactive` worker can't be assigned to new orders;
their in-progress orders should be reassigned.

## Invariants

- A worker belongs to exactly one branch — invariant.
- Only workers of an order's branch can be assigned to it (as cutter on `→ in_production` or driver
  on `→ in_delivery`) — service rule.
- Managed by users with `manage_workers` on the branch (or the owner) — service rule ([`docs/spec/access.md`](../../../spec/access.md)).
- Never deleted — [`docs/spec/architecture.md`](../../../spec/architecture.md).

## Relationships

- belongs to → [`docs/ref/entities/workshop/branch.md`](branch.md) (many-to-one)
- assigned to (logical) → [`docs/ref/entities/sales/order.md`](../sales/order.md) (a cutter and/or a driver per order)

## Owner

[`docs/ref/features/worker-management.md`](../../features/worker-management.md).
