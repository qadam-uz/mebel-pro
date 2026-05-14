---
title: Identity
status: draft
owner: shape
updated: 2026-05-13
order: 10
---

# Identity

The auth subjects and the session record. Rules are in [`access-patterns.md`](../../access-patterns.md);
this page is the data shape.

## Platform user

A person on the platform-operating team ("superadmin"). Not bound to any workshop; no permission
model — full platform scope. Uses the superadmin app.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `login` | text | unique, case-insensitive |
| `password_hash` | text | argon2/bcrypt; never plaintext |
| `full_name` / `phone` | text | required; phone `+998XXXXXXXXX` |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `force_password_change` | bool | default `true` on creation |
| `failed_login_count` / `locked_until` | int / timestamp? | brute-force counter; resets on success |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

Invariants: `login` unique (DB); blocking deletes its sessions; complexity ≥ 8 chars (upper +
lower + digit); created only by another platform user.

## Workshop user

A staff member of a workshop — **including its owner**. Logs in with login + password. Belongs to
exactly one workshop. Capability is the owner flag (everything) or a set of branch-scoped
[permission grants](#permission-grant). Uses the workshop app.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required; the tenant |
| `login` | text | unique per workshop, case-insensitive |
| `password_hash` / `full_name` / `phone` | text | as above |
| `is_owner` | bool | **exactly one `true` per workshop** |
| `status` | enum | `active` / `blocked` |
| `force_password_change` | bool | default `true` on creation |
| `failed_login_count` / `locked_until` | int / timestamp? | |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

Invariants: exactly one owner per workshop (DB/service); `login` unique per workshop; blocking
the user, or blocking its workshop, deletes its sessions; staff with zero grants can log in but
has no actionable screens; only a platform operator may move ownership to another user.

## Permission grant

One row that grants a (non-owner) workshop user one coarse permission, scoped to one branch. The
grantable catalog is the v1 set: `view_dashboard`, `manage_orders`, `manage_catalog`,
`manage_inventory`, `manage_workers`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_user_id` | UUID | required; must not be an owner |
| `permission` | enum | one of the v1 catalog above |
| `branch_id` | UUID | required; branch in the user's workshop |
| `granted_by_user_id` | UUID | the owner who created it |
| `granted_at` | timestamp | |

Invariants: `(workshop_user_id, permission, branch_id)` unique (DB); `branch_id` belongs to the
same workshop as the user (service); only the workshop owner creates/removes grants; a grant on
an `inactive` branch is inert.

## Client

The customer. A **separate entity** from workshop/platform users. Telegram-OAuth identity only;
self-registers on first OAuth handshake; global to the platform (no workshop/branch binding);
picks a branch per order. Uses the client app.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `telegram_id` | bigint | unique; required |
| `telegram_username` | text? | may be null |
| `phone` | text | `+998XXXXXXXXX`; required (Telegram must share it) |
| `first_name` / `last_name` / `photo_url` | text / text? / text? | from Telegram (last/photo optional) |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `created_at` / `updated_at` / `last_login_at` | timestamp / timestamp / timestamp? | |

Telegram profile fields are **refreshed from the OAuth payload on every login** — Telegram is
the source of truth. No password, no forced-change / lockout (auth integrity is the HMAC check).
A client cannot exist without a verified Telegram identity and a shared phone number
(`missing_phone_number` otherwise).

## Session

A logged-in device for a principal. Holds an opaque access token + opaque refresh token, both
stored **hashed** (SHA-256) — not a JWT. The session row is the source of truth: deleting it
logs the device out instantly. One `sessions` table covers all three principal types.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `principal_type` | enum | `platform_user` / `workshop_user` / `client` |
| `principal_id` | UUID | the user/client |
| `access_token_hash` / `refresh_token_hash` | text | SHA-256; unique each |
| `access_token_expires_at` / `refresh_token_expires_at` | timestamp | now + 24 h / now + 7 d at issue |
| `device_info` | json | UA, IP (for the "where am I logged in" view + audit) |
| `created_at` / `last_used_at` | timestamp / timestamp | `last_used_at` bumped on each authenticated request |

Plaintext tokens are never stored. Created on login; access token refreshed via the refresh
token until refresh expiry; removed by logout, "log out everywhere", a password change (removes
all *other* sessions), blocking the principal, blocking the principal's workshop, or being
evicted as the oldest at the 5-session cap. Expired sessions are pruned by a periodic job.

Invariants: ≤ 5 active sessions per principal; token hashes unique (DB); an expired or unknown
access token is `unauthorized`; refresh re-checks the principal (and the workshop, for workshop
users) is still active; tokens are random 32-byte strings.
