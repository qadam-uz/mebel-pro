---
title: Workshop
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/domain-model.md
  - docs/spec/access.md
  - docs/ref/entities/workshop/branch.md
  - docs/ref/entities/identity/workshop-user.md
  - docs/ref/features/workshop-provisioning.md
---

# Workshop

## What it is

The tenant — one furniture-cutting business (the old codebase called it "organization"). Has exactly
one owner, many branches, many workshop users, and a settings bundle. Provisioned by a platform
operator. See [`docs/spec/access.md`](../../../spec/access.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `name` | text | workshop name | required |
| `logo_file_id` | UUID? | → [`file`](../support/file.md) | optional |
| `phone` | text | main contact, `+998XXXXXXXXX` | required |
| `address` | text? | legal/postal address | |
| `owner_user_id` | UUID | the `is_owner` workshop user | required, 1:1 |
| `status` | enum | `active` / `blocked` | default `active` |
| `created_at` / `updated_at` | timestamp | | |
| **Settings (embedded — one bundle per workshop):** | | | |
| `settings.delivery_enabled` | bool | whether delivery is offered at all | default `false` |
| `settings.delivery_zones` | json | list of `{ id, name, polygon_or_label, fee_tiyin }` — static, admin-entered (v1) | |
| `settings.default_advance_percent` | int | default advance % for `advance` orders | 0–100 |
| `settings.currency` | enum | `UZS` (only value in v1) | |
| `settings.payment_channels` | json | per-channel `{ enabled: bool, credentials: {...} }` for Payme/Click/Uzum/BNPL — **stored, inert in v1** ([`docs/spec/scope-v1.md`](../../../spec/scope-v1.md)) | credentials owner-visible only |

## States / lifecycle

`active` ↔ `blocked` (soft delete only). Blocking cascades: the owner's + staff's sessions are
revoked immediately; open orders freeze (no automatic transitions); clients are unaffected.
Unblocking does not restore sessions. See [`docs/spec/access.md`](../../../spec/access.md), [`docs/spec/access.md`](../../../spec/access.md).

## Invariants

- Exactly one workshop user with `is_owner = true` per workshop — DB/service rule.
- `owner_user_id` references that user — invariant kept by provisioning + ownership-change.
- `settings.payment_channels` credentials are visible only to the workshop owner — service rule ([`docs/spec/access.md`](../../../spec/access.md)).
- `default_advance_percent` ∈ [0, 100] — DB check.
- A workshop is never deleted — soft delete ([`docs/spec/architecture.md`](../../../spec/architecture.md)).
- Only a platform operator creates or blocks/unblocks a workshop — service rule.

## Relationships

- owned by (logical) → [`docs/ref/entities/identity/platform-user.md`](../identity/platform-user.md) provisions it
- has → [`docs/ref/entities/identity/workshop-user.md`](../identity/workshop-user.md) (one owner + many staff)
- owns → [`docs/ref/entities/workshop/branch.md`](branch.md) (one-to-many)
- referenced by (snapshot) → [`docs/ref/entities/sales/order.md`](../sales/order.md) (`workshop_id`)
- logo → [`docs/ref/entities/support/file.md`](../support/file.md)

## Owner

[`docs/ref/features/workshop-provisioning.md`](../../features/workshop-provisioning.md) (create, settings, block/unblock); [`docs/spec/access.md`](../../../spec/access.md).
