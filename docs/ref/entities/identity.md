---
title: Identity
status: draft
owner: shape
updated: 2026-09-06
order: 10
---

# Identity

The auth subjects and the session record. Rules are in
[`access-patterns.md`](../../access-patterns.md); this page is the data shape.

## Platform user

A person on the platform-operating team ("superadmin"). Not bound to any workshop; no permission
model — platform-ops scope. Uses the superadmin app.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `login` | text | unique, case-insensitive |
| `password_hash` | text | argon2/bcrypt; never plaintext |
| `full_name` / `phone` | text | required; phone `+998XXXXXXXXX` |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `password_reset_required` | bool | default `true` on creation; gates non-account routes until password change |
| `failed_login_count` / `locked_until` | int / timestamp? | brute-force counter; resets on success |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

Invariants: `login` unique (DB); blocking deletes its sessions; complexity ≥ 8 chars (upper +
lower + digit); bootstrap creation is CLI-only; in-app creation by another platform user is owned
by the platform-user registry.

## Workshop user

A workshop's person — **including its owner**, plus office staff, cutters, edge banders,
accountants. Logs in with login + password. Belongs to exactly one workshop.
**There is no separate "worker" entity and no fixed role** — capability is the owner flag
(everything) or a set of branch-scoped [permission grants](#permission-grant), and one person may
hold every grant. Uses the workshop app.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required; the tenant |
| `login` | text | **unique platform-wide**, case-insensitive — the login alone names the account, and the workshop follows from it |
| `password_hash` / `full_name` / `phone` | text | as above |
| `is_owner` | bool | **exactly one `true` per workshop** |
| `home_branch_id` | UUID | the branch the user works at; load-bearing for cutter / edger assignment (a **non-owner** order's `cutter_user_id` / `edger_user_id` must have `home_branch_id = order.branch_id`; the **owner is exempt** — `is_owner` holds `process_production` on every branch and may be assigned regardless of `home_branch_id`); for owner / office staff who span branches, set the branch they sit at |
| `status` | enum | `active` / `blocked` |
| `password_reset_required` | bool | default `true` on creation; gates non-account routes until password change |
| `failed_login_count` / `locked_until` | int / timestamp? | |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

There is **no compensation policy** in v1: the system stores no pay rates and computes no
salary. A worker's pay is the accountant's manual calculation from the worker-production
reports, booked as a `salary` expense ([`finance.md`](../features/finance.md)).

Invariants: exactly one owner per workshop (DB / service); `login` unique across every workshop
(`uq_workshop_users_login_ci` on `lower(login)`); sign-in is a single lookup by that login, so a
login already taken in another workshop is refused at creation rather than resolved by password;
`home_branch_id` belongs to the same workshop; blocking the user, or
blocking its workshop, deletes its sessions; staff with zero grants can log in but has no
actionable screens; v1 has no owner transfer path after provisioning.

## Permission grant

One row that grants a (non-owner) workshop user one coarse permission, scoped to one branch.
The permission catalog and owner-only carve-outs are owned by
[`../features/access-management.md`](../features/access-management.md).

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
number**, proven by sharing the Telegram-verified contact in the platform's bot; self-registers
the first time a new number is shared, or is registered at the counter by workshop staff
resolving a walk-in by phone; global to the platform (no workshop/branch binding); picks a
branch per order. Uses the client app.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `phone` | text | `+998XXXXXXXXX`; **unique, required** — the identity and natural key (Telegram-verified via the bot's contact share on the self-serve path; staff-entered for a walk-in until their first bot sign-in) |
| `telegram_user_id` | bigint? | **unique when set** — the Telegram account that signs in as this client; linked by the bot's contact step, relinked when a new account proves the same phone; `null` on a staff-created row until first bot sign-in. Private-chat id equals user id, so bot messages are sent to it directly |
| `telegram_unreachable_at` | timestamp? | set when a bot send bounces with 403 (client blocked the bot); cleared on the next `/start` or successful send; while set, Telegram delivery is skipped — the inbox is unaffected |
| `name` | text | required; the client's display name (1–80 chars) — prefilled from the Telegram profile at registration, client-editable, never re-synced; how the workshop addresses them |
| `preferred_branch_id` | UUID? | the **pin**: the branch, and through it the workshop, the client app is scoped to ([`client-entry.md`](../features/client-entry.md)). Seeds the `preferred_branch_id` of every new cutting draft this client opens unless the drawing was started at another branch; a draft's own branch never writes back here. Written by exactly two operations and by no profile form: applying a workshop-link entry, which cross-checks the branch against the link's code before it writes (the star's «Asosiy qilish» is that same operation), and placing a client order, which pins the order's branch. It is **left untouched** when a link does not settle a branch, and by a branch row's «Yangi chizma», which pins nothing. Surfaced as the **Asosiy** star on a branch row, never as a bare branch field |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `created_at` / `updated_at` / `last_login_at` | timestamp / timestamp / timestamp? | |

The phone is the identity; the Telegram account is the credential linked to it. No password,
no password-reset warning / lockout (auth integrity is the bot handshake).
A client row is created by the first confirmed contact share of a new number in the bot
([login token](#telegram-login-token)), **or by workshop staff resolving a walk-in
by phone** (find-or-create; semantics and rationale in
[`access-management.md`](../features/access-management.md#staff-resolved-walk-ins-find-or-create)).
On the self-serve path the phone is verified before the row exists; on the staff path it is
staff-entered and verified the first time the client signs in through the bot — which is also
when they claim the row and `telegram_user_id` is filled. The staff path never creates a
client session — the bot remains the only login.

Invariants: `phone` unique (DB) and `+998XXXXXXXXX`-shaped; `telegram_user_id` unique when set
(DB, partial); blocking deletes its sessions;
created only by a successful first bot registration or by workshop staff resolving a walk-in
(never by a platform operator); a `blocked` client can neither sign in nor be resolved by
staff (`account_blocked` on both paths);
`preferred_branch_id`, when set, references a branch that was visible (`active` or
`temporarily_closed`) at the moment it was pinned; the field is **not** scope-enforced (a
branch later going `inactive` doesn't clear it — the workshop's other branches stay listed and
startable; see [`client-entry.md`](../features/client-entry.md)). It is likewise never cleared
when its workshop is `blocked`: the session read reports the pinned workshop and branch
**names as null** instead, so the app stops scoping while the row survives to revive on unblock.

The session read (`/auth/me`) carries **`pinned_workshop_name`** and **`pinned_branch_name`**
resolved from this field, both null when un-pinned or when the workshop is `blocked`. That
pair is the client app's entire "is pinned" signal — one predicate, so home's card, the
new-drawing guard and the editor can never disagree about it.

## Client workshop entry

One workshop this client has walked into through a link, and when they last did. Written on
**every** entry, whether or not the link settled a branch to pin
([`client-entry.md`](../features/client-entry.md#what-entry-writes)); this is the stored half
of Ustaxonalarim.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `client_id` | UUID | required |
| `workshop_id` | UUID | required |
| `last_entered_at` | timestamp | the last time this client came through this workshop's door. Separate from `updated_at`, which a schema backfill would also move; this column means one thing, and Ustaxonalarim orders by it |
| `created_at` / `updated_at` | timestamp | |

Invariants: `(client_id, workshop_id)` unique (DB, `uq_client_workshop_entries_pair`) — **the
pair is the identity**, upserted, so the table stays the size of the relationships it records
rather than of the scans that made them; one index on `(client_id, last_entered_at)`, which is
the only way the table is ever read. A row is never deleted by entry: a workshop leaves the
client's list by being `blocked`, which is a read-time exclusion.

## Telegram login token

Transient state for one browser↔bot sign-in handshake: the browser mints it, the bot advances
it, the browser's poll redeems it. Not tied to a `Client` row at creation — it precedes
login/registration and exists for both returning and brand-new clients.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `token_hash` | text | SHA-256 of the deep-link token (random ≥ 32 bytes, URL-safe); unique; plaintext never stored |
| `poll_secret_hash` | text | SHA-256 of the browser-held poll secret; unique; the **only** credential a session is released against |
| `status` | enum | `pending` → `started` → (`awaiting_contact` →) `confirmed` → `used`; `declined` terminal (client cancelled, blocked account, expired mid-conversation) |
| `telegram_user_id` | bigint? | set at `/start` |
| `client_id` | UUID? | set at `confirmed` |
| `request_ip` / `device_info` | text / json | normalized creating IP (per-IP budget) + UA — rendered into the bot's confirm message |
| `expires_at` | timestamp | now + 5 min at issue |
| `created_at` / `confirmed_at` / `used_at` | timestamp / timestamp? / timestamp? | |

Invariants: both secrets random ≥ 32 bytes, hashed at rest, single-use; status only moves
forward; a session is issued exactly once, only against the poll secret, only from `confirmed`;
the deep-link token alone can never redeem a session. Creation counts toward the per-IP budget
(`TELEGRAM_LOGIN_*` settings; rules in
[`access-management.md`](../features/access-management.md#client-sign-in-telegram-bot)).
`request_ip` is the socket peer in direct/dev traffic; when the immediate peer is a trusted
proxy (`TRUSTED_PROXY_CIDRS`), it is the right-most `X-Forwarded-For` hop outside the trusted
CIDRs — the address a trusted proxy actually vouches for; untrusted or malformed headers are
ignored. Rows are pruned by the periodic session/expiry job after 7 days — retention must
exceed the longest (24 h) budget window.

## Telegram login code

Transient state for the fallback path: a short code the bot shows to an already-identified
client, typed into the login page. Issued only after the bot conversation has resolved the
client, so it always references a `Client` row.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `code_hash` | text | HMAC-SHA-256 of the 6-digit code using `TELEGRAM_LOGIN_CODE_PEPPER`; plaintext never stored |
| `client_id` | UUID | required — the identified client the code logs in |
| `expires_at` | timestamp | now + 5 min at issue |
| `consumed_at` | timestamp? | set on successful redeem; single-use |
| `created_at` | timestamp | |

Invariants: 6 digits, HMAC-hashed at rest with a server-side pepper, single-use, 5-minute TTL;
redeeming is throttled per client IP and answers one generic `invalid_code` for unknown,
expired, and used alike — the low-entropy code is protected by the throttle, the TTL, and
burn-on-redeem, not by per-row attempt counters (no row is addressable before a correct
guess). Pruned with login tokens after 7 days.

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
