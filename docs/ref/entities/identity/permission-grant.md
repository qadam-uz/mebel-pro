---
title: Permission grant
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/access.md
  - docs/ref/entities/identity/workshop-user.md
  - docs/ref/entities/workshop/branch.md
  - docs/ref/features/workshop-user-management.md
---

# Permission grant

## What it is

One row that grants a [workshop user](workshop-user.md) one coarse permission, scoped to one
[branch](../workshop/branch.md). A staff user's capability is the set of these rows; the workshop
owner needs none (they hold everything implicitly). The grantable catalog and the owner-only
exceptions are defined in [`docs/spec/access.md`](../../../spec/access.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `workshop_user_id` | UUID | the staff user | required; → workshop user; must not be an owner |
| `permission` | enum | one of `view_dashboard` / `manage_orders` / `manage_catalog` / `manage_inventory` / `manage_workers` (v1 catalog) | required |
| `branch_id` | UUID | the branch this grant applies to | required (all v1 permissions are branch-scoped); → branch in the same workshop |
| `granted_by_user_id` | UUID | the owner who created it | required; → workshop user with `is_owner` |
| `granted_at` | timestamp | | |

## States / lifecycle

No lifecycle states — a grant exists or it doesn't. Editing a user's grants adds/removes rows
atomically; the change takes effect on the user's next request (no session revoke).

## Invariants

- `(workshop_user_id, permission, branch_id)` is unique — DB constraint.
- `branch_id` belongs to the same workshop as `workshop_user_id` — service rule (validated at grant time).
- Grants are only created for non-owner workshop users (owners don't need them) — service rule.
- A grant on an `inactive` branch is inert (the branch isn't shown; the grant becomes live again on reactivation) — service/UI rule.
- Only the workshop owner creates/removes grants — service rule ([`docs/spec/access.md`](../../../spec/access.md)).

## Relationships

- belongs to → [`docs/ref/entities/identity/workshop-user.md`](workshop-user.md) (many-to-one)
- scoped to → [`docs/ref/entities/workshop/branch.md`](../workshop/branch.md) (many-to-one)
- granted by → [`docs/ref/entities/identity/workshop-user.md`](workshop-user.md) (the owner)

## Owner

[`docs/spec/access.md`](../../../spec/access.md) defines the rules; [`docs/ref/features/workshop-user-management.md`](../../features/workshop-user-management.md) owns the grant-editing flow.
