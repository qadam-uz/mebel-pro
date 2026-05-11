---
title: Platform user
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/domain-model.md
  - docs/spec/access.md
  - docs/ref/entities/identity/session.md
  - docs/ref/entities/identity/workshop-user.md
---

# Platform user

## What it is

A person on the platform-operating team ("superadmin"). Not bound to any workshop; has no permission
model — full platform scope. Provisions workshops and their owners, blocks/unblocks workshops,
investigates incidents across workshops, operates platform tooling. Uses the **superadmin app**.

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `login` | text | login identifier | unique, case-insensitive |
| `password_hash` | text | argon2/bcrypt hash | never plaintext |
| `full_name` | text | display name | required |
| `phone` | text | contact, `+998XXXXXXXXX` | required |
| `status` | enum | `active` / `blocked` | default `active` |
| `force_password_change` | bool | must change password before using the app | default `true` on creation |
| `failed_login_count` | int | brute-force counter | reset on success |
| `locked_until` | timestamp? | brute-force lock expiry | null when not locked |
| `last_login_at` | timestamp? | | |
| `created_at` / `updated_at` | timestamp | | |

## States / lifecycle

`active` ↔ `blocked` (soft delete only — never `DELETE`). `force_password_change` clears on the
first successful password change.

## Invariants

- `login` unique across platform users (case-insensitive) — DB constraint.
- A blocked platform user cannot log in; blocking deletes its sessions (service rule, [`docs/spec/access.md`](../../../spec/access.md)).
- Password meets complexity (≥ 8, upper + lower + digit) — service rule.
- Created only by another platform user.

## Relationships

- has many → [`docs/ref/entities/identity/session.md`](session.md) (one per logged-in device)
- (acts on, no FK) → [`docs/ref/entities/workshop/workshop.md`](../workshop/workshop.md), [`docs/ref/entities/identity/workshop-user.md`](workshop-user.md) (provisioning)
- receives → [`docs/ref/entities/support/notification.md`](../support/notification.md)

## Owner

[`docs/ref/features/workshop-provisioning.md`](../../features/workshop-provisioning.md) and [`docs/ref/features/platform-ops.md`](../../features/platform-ops.md) own its rules; auth posture is [`docs/spec/access.md`](../../../spec/access.md).
