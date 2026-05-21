---
title: Identity
status: draft
owner: shape
updated: 2026-05-22
order: 10
---

# Identity

The auth subjects and the session record. Rules are in
[`access-patterns.md`](../../access-patterns.md); this page is the data shape.

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

A workshop's person — **including its owner**, plus office staff, cutters, edge banders,
accountants. Logs in with login + password. Belongs to exactly one workshop. **There is no
separate "worker" entity and no fixed role** — capability is the owner flag (everything) or
a set of branch-scoped [permission grants](#permission-grant), and one person may hold every
grant. Uses the workshop app.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required; the tenant |
| `login` | text | unique per workshop, case-insensitive |
| `password_hash` / `full_name` / `phone` | text | as above |
| `is_owner` | bool | **exactly one `true` per workshop** |
| `home_branch_id` | UUID | the branch the user works at; load-bearing for cutter / edger assignment (a **non-owner** order's `cutter_user_id` / `edger_user_id` must have `home_branch_id = order.branch_id`; the **owner is exempt** — `is_owner` holds `process_production` on every branch and may be assigned regardless of `home_branch_id`); for owner / office staff who span branches, set the branch they sit at |
| `status` | enum | `active` / `blocked` |
| `force_password_change` | bool | default `true` on creation |
| `failed_login_count` / `locked_until` | int / timestamp? | |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

There is **no compensation policy** in v1: the system stores no pay rates and computes no
salary. A worker's pay is the accountant's manual calculation from the worker-production
reports, booked as a `salary` expense ([`finance.md`](../features/finance.md)).

Invariants: exactly one owner per workshop (DB / service); `login` unique per workshop;
`home_branch_id` belongs to the same workshop; blocking the user, or blocking its workshop,
deletes its sessions; staff with zero grants can log in but has no actionable screens; only a
platform operator may move ownership to another user.

## Permission grant

One row that grants a (non-owner) workshop user one coarse permission, scoped to one branch.
The v1 catalog: `view_dashboard`, `manage_orders`, `process_production`, `manage_catalog`,
`manage_inventory`, `manage_finance`, `view_finance_reports` (`process_delivery` is gated
out of v1 with delivery). See
[`../features/access-management.md`](../features/access-management.md) for what each one
grants and which are owner-only.

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

The customer. A **separate entity** from workshop/platform users. Identified by a **phone
number verified by a one-time code sent over Telegram**; self-registers (name only) the first
time a new number is verified; global to the platform (no workshop/branch binding); picks a
branch per order. Uses the client app.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `phone` | text | `+998XXXXXXXXX`; **unique, required** — the verified identity and natural key |
| `name` | text | required; the client's own display name, typed at registration (1–80 chars); how the workshop addresses them |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `created_at` / `updated_at` / `last_login_at` | timestamp / timestamp / timestamp? | |

The phone is the only verified fact; `name` is self-entered and editable by the client (no
external source of truth — nothing is synced from Telegram, which is only the delivery channel
for the login code). No password, no forced-change / lockout (auth integrity is the OTP check).
A client cannot exist without a phone that has been verified via the
[code challenge](#phone-verification-challenge); the row is created only on the first
successful verification of a new number.

Invariants: `phone` unique (DB) and `+998XXXXXXXXX`-shaped; blocking deletes its sessions;
created only by a successful first verification (never by an operator or another principal).

## Phone verification challenge

Transient state for an in-flight client sign-in: one code sent to a phone over Telegram,
awaiting entry. Not tied to a `Client` row — it precedes login/registration and exists for both
returning and brand-new numbers.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `phone` | text | `+998XXXXXXXXX`; the number the code was sent to |
| `code_hash` | text | SHA-256 of the 6-digit code; plaintext never stored |
| `expires_at` | timestamp | now + 5 min at issue |
| `attempt_count` | int | wrong-code counter; burned at 5 |
| `consumed_at` | timestamp? | set when a correct code is accepted; single-use |
| `created_at` | timestamp | |

Invariants: code is 6 digits, hashed at rest, single-use, 5-minute TTL; ≤ 5 verify attempts
before the challenge is burned; per-phone resend cooldown (60 s) and a per-phone / per-IP send
rate limit; the row is short-lived and pruned by the periodic session/expiry job. Delivery is
**Telegram-only** — a number not reachable on Telegram cannot sign in (no SMS fallback in v1).

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
