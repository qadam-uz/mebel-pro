---
title: Session
status: stable
owner: shape
updated: 2026-05-11
related:
  - docs/spec/access.md
  - docs/ref/entities/identity/platform-user.md
  - docs/ref/entities/identity/workshop-user.md
  - docs/ref/entities/identity/client.md
---

# Session

## What it is

A logged-in device for a principal. Holds an opaque access token and an opaque refresh token, both
stored **hashed** — not a JWT ([`docs/spec/access.md`](../../../spec/access.md)). The session row is the source of truth: deleting it logs the device out instantly. One `sessions` table covers all three principal types (platform user / workshop user / client). Mechanics: [`docs/spec/access.md`](../../../spec/access.md).

## Fields

| Field | Type | Meaning | Constraints |
|---|---|---|---|
| `id` | UUID | PK | |
| `principal_type` | enum | `platform_user` / `workshop_user` / `client` | required |
| `principal_id` | UUID | the user/client this session belongs to | required; → the matching entity (logical) |
| `access_token_hash` | text | SHA-256 of the access token | unique |
| `refresh_token_hash` | text | SHA-256 of the refresh token | unique |
| `access_token_expires_at` | timestamp | now + 24 h at issue | |
| `refresh_token_expires_at` | timestamp | now + 7 d at issue | |
| `device_info` | json | user agent, IP (for the "where am I logged in" view + audit) | |
| `created_at` | timestamp | | |
| `last_used_at` | timestamp | bumped on each authenticated request | |

Plaintext tokens are never stored — only the SHA-256 hashes.

## States / lifecycle

A session is created on login; the access token is refreshed (re-issued, expiry bumped) via the
refresh token until the refresh token expires; the session is removed by logout, "log out
everywhere", a password change (removes all *other* sessions), blocking the principal, blocking the
principal's workshop, or being evicted as the oldest when the principal exceeds 5 concurrent
sessions; expired sessions are also pruned by a periodic cleanup job.

## Invariants

- ≤ 5 active sessions per principal — service rule (6th login evicts the oldest).
- Token hashes unique — DB constraint.
- A request with an expired or unknown access token is `unauthorized`; refresh checks the principal
  (and the workshop, for workshop users) is still active — service rules.
- Tokens are random 32-byte strings; stored hashed; transported as `Authorization: Bearer` — invariant.

## Relationships

- belongs to → one of [`docs/ref/entities/identity/platform-user.md`](platform-user.md), [`docs/ref/entities/identity/workshop-user.md`](workshop-user.md), [`docs/ref/entities/identity/client.md`](client.md) (via `principal_type` + `principal_id`)

## Owner

[`docs/spec/access.md`](../../../spec/access.md) and [`docs/spec/access.md`](../../../spec/access.md).
