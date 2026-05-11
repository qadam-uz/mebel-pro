---
title: Action log
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/nfr.md
  - docs/ref/entities/support/status-change-log.md
  - docs/ref/features/audit-log.md
---

# Action log

## What it is

One row per mutating action anyone took anywhere in the system — who did what, when, to which entity,
with the relevant context (and before/after values where they matter). The "who did what" half of
the audit log (the "what changed state" half is the [status change log](status-change-log.md)).
Append-only. Surfaced in the seh app's audit viewer and the superadmin app. See [`docs/spec/nfr.md`](../../../spec/nfr.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `actor_type` | enum | `platform_user` / `workshop_user` / `client` / `system` | required |
| `actor_user_id` | UUID? | the workshop/platform user (if applicable) | |
| `actor_client_id` | UUID? | the client (if applicable) | |
| `workshop_id` | UUID? | the workshop the action affected (for scoping the viewer); null for client-only / platform-only actions | |
| `branch_id` | UUID? | the branch, when relevant | |
| `action` | text | a stable action code, e.g. `material.created`, `order.discount_applied`, `workshop.blocked`, `user.password_reset` | required |
| `entity_type` | text? | the affected entity type | |
| `entity_id` | UUID? | the affected entity's id | |
| `summary` | text? | a short human description | |
| `details` | json? | context / before-after (sensitive fields masked) | |
| `trace_id` | text | the request trace id | |
| `created_at` | timestamp | | |

## States / lifecycle

No lifecycle — write once, never update or delete (append-only).

## Invariants

- Every mutating use case writes exactly one action-log row, in the same atomic operation as the
  change — invariant ([`docs/spec/nfr.md`](../../../spec/nfr.md)).
- Never updated or deleted — append-only ([`docs/spec/architecture.md`](../../../spec/architecture.md)).
- Sensitive values (passwords, full payment credentials) are masked in `details` — service rule.
- Scoping: a workshop owner/staff sees only rows for their workshop (and their granted branches); a
  platform operator sees all — service rule.

## Relationships

- actor → [`docs/ref/entities/identity/platform-user.md`](../identity/platform-user.md) / [`docs/ref/entities/identity/workshop-user.md`](../identity/workshop-user.md) / [`docs/ref/entities/identity/client.md`](../identity/client.md)
- subject (logical) → any entity in the system
- companion → [`docs/ref/entities/support/status-change-log.md`](status-change-log.md)

## Owner

The `audit` module; viewer in [`docs/ref/features/audit-log.md`](../../features/audit-log.md).
