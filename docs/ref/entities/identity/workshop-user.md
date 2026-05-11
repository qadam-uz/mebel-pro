---
title: Workshop user
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/domain-model.md
  - docs/spec/access.md
  - docs/ref/entities/identity/permission-grant.md
  - docs/ref/entities/workshop/workshop.md
  - docs/ref/entities/identity/session.md
---

# Workshop user

## What it is

A staff member of a workshop — including its **owner**. Logs in with a login + password. Belongs to
exactly one workshop. Capability is the owner flag (everything) or a set of branch-scoped
[permission grants](permission-grant.md) — there is no role taxonomy. Uses the **seh (workshop)
app**. See [`docs/spec/access.md`](../../../spec/access.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `workshop_id` | UUID | the workshop this user belongs to | required; → workshop (logical) |
| `login` | text | login identifier | unique per workshop, case-insensitive |
| `password_hash` | text | argon2/bcrypt hash | never plaintext |
| `full_name` | text | display name | required |
| `phone` | text | contact, `+998XXXXXXXXX` | required |
| `is_owner` | bool | the workshop owner | exactly one `true` per workshop |
| `status` | enum | `active` / `blocked` | default `active` |
| `force_password_change` | bool | must change before using the app | default `true` on creation |
| `failed_login_count` | int | brute-force counter | reset on success |
| `locked_until` | timestamp? | brute-force lock expiry | null when not locked |
| `last_login_at` | timestamp? | | |
| `created_at` / `updated_at` | timestamp | | |

## States / lifecycle

`active` ↔ `blocked` (soft delete only). `force_password_change` clears on first password change.
`is_owner` is set at provisioning (the first user) and only a platform operator can move ownership
to another user.

## Invariants

- Exactly **one** `is_owner = true` workshop user per workshop — DB/service rule.
- `login` unique within a workshop (case-insensitive) — DB constraint.
- Blocking a user, or blocking its workshop, deletes its sessions immediately — service rule ([`docs/spec/access.md`](../../../spec/access.md), [`docs/spec/access.md`](../../../spec/access.md)).
- Owner is created by a platform operator; staff are created by the owner; both with `force_password_change`.
- A staff user with zero grants can log in but has no actionable screens — service/UI rule.
- Password meets complexity — service rule.

## Relationships

- belongs to → [`docs/ref/entities/workshop/workshop.md`](../workshop/workshop.md) (many-to-one)
- has → [`docs/ref/entities/identity/permission-grant.md`](permission-grant.md) (zero-to-many; none if owner)
- has many → [`docs/ref/entities/identity/session.md`](session.md)
- referenced by (logical) → [`docs/ref/entities/sales/order-status-event.md`](../sales/order-status-event.md), [`docs/ref/entities/sales/order-payment.md`](../sales/order-payment.md) (`received_by`), [`docs/ref/entities/sales/order-refund.md`](../sales/order-refund.md) (`processed_by`), [`docs/ref/entities/sales/order-cancellation.md`](../sales/order-cancellation.md), [`docs/ref/entities/inventory/stock-transaction.md`](../inventory/stock-transaction.md) (`actor`)
- receives → [`docs/ref/entities/support/notification.md`](../support/notification.md)

## Owner

[`docs/ref/features/workshop-user-management.md`](../../features/workshop-user-management.md) (creation, grants, reset/block) and [`docs/ref/features/workshop-provisioning.md`](../../features/workshop-provisioning.md) (the owner). Authz model: [`docs/spec/access.md`](../../../spec/access.md).
