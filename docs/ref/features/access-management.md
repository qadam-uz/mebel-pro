---
title: Identity & access
status: draft
owner: shape
updated: 2026-05-14
order: 20
---

# Identity & access

The implementation of [`access-patterns.md`](../../access-patterns.md) — how each principal signs in, how
sessions work, how workshops are provisioned, how staff and their grants are managed, and how
the surfaces look in the three apps. Data shape (fields, states, invariants) is in
[`../entities/identity.md`](../entities/identity.md).

## Workshop & platform user sign-in

### Mechanics

Login + password. Login is case-insensitive; unique per workshop (workshop users) or
platform-wide (platform users). The error on a bad pair is a generic "login or password is
incorrect" — no account-existence oracle. **5 consecutive bad attempts → 15-minute lockout**
(`locked_until`); a correct password resets the counter. Passwords are argon2/bcrypt-hashed at
rest; complexity ≥ 8 chars with at least one upper, one lower, one digit.

`force_password_change` (set on creation or after a reset) gates the user — every endpoint
except change-password / logout / get-me returns `password_change_required` until the user
changes it.

**Platform users are seeded by a backend CLI command** — there is no in-app creation flow
(they're the top of the hierarchy, with no higher principal to create them).

### Sessions

Opaque DB-backed tokens, hashed (SHA-256) — not JWTs. Access TTL **24 h**, refresh TTL **7 d**;
≤ **5** concurrent sessions per principal (a 6th login evicts the oldest). Revocation = delete
the row.

| Trigger                            | Effect                                                          |
| ---------------------------------- | --------------------------------------------------------------- |
| logout (this session)              | delete this session                                             |
| "log out everywhere"               | delete all the user's sessions                                  |
| change own password                | delete all *other* sessions; keep the current                   |
| reset password (higher principal)  | delete all the user's sessions                                  |
| block user                         | delete all the user's sessions                                  |
| block workshop                     | delete sessions for the workshop's owner + staff (clients unaffected) |
| 5-session cap exceeded             | evict the oldest                                                |
| token expiry                       | inert; a periodic job prunes the row                            |

### Endpoints

| Endpoint                                                            | Caller                  | What                                                                                                              |
| ------------------------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `workshop-login` / `platform-login`                                 | unauth                  | login + password → `access` + `refresh` token                                                                     |
| `workshop-logout` / `platform-logout`                               | self                    | end the current session                                                                                           |
| `workshop-refresh` / `platform-refresh`                             | unauth (refresh token)  | new access token; re-checks the user (and, for workshop users, the workshop) is still active                      |
| `change-my-password`                                                | self                    | new password meeting complexity; revokes all *other* sessions; clears `force_password_change`                     |
| `list-my-sessions` / `revoke-my-session` / `revoke-my-sessions`     | self                    | self-service session management                                                                                   |
| `get-me`                                                            | self                    | current principal context (type, ids, `is_owner`, grant set, `force_password_change`)                             |

### UX

- **Sign-in screen** (workshop app `/auth/login`; superadmin app `/auth/login`): login + password
  fields; generic error on failure; a lockout banner ("try again at HH:MM") when `locked_until`
  came back.
- **Force-password-change screen**: shown on first login (or after reset); strength meter
  (≥ 8 chars, upper + lower + digit); blocks the rest of the app until set.
- **Self profile** (`/workshop/profile`, `/admin/profile`): Profile (read-only fields), Change
  password (strength meter), Sessions list (current marker, "revoke" per row, "log out
  everywhere").

## Client sign-in (Telegram OAuth)

### Mechanics

`telegram-login` accepts the Telegram Login Widget payload (`telegram_id`, `first_name`,
`last_name`, `username`, `photo_url`, `phone_number`, `auth_date`, `hash`) and
**HMAC-verifies** it against the bot token; a bad signature or a stale `auth_date` is rejected
(`invalid_oauth_signature` / `oauth_expired`).

The **phone number is required** — if Telegram didn't share it the client is asked to allow
phone-sharing and retry (`missing_phone_number`). The phone is the client's primary human
identifier; the profile (telegram id, username, phone, photo, name) is refreshed from the
payload on every login.

Not found → create the client (`status = active`, `is_new = true`); found → use it. Blocked →
`account_blocked`. Either way, on success a session is created.

### Endpoints

| Endpoint                                                            | Caller                  | What                            |
| ------------------------------------------------------------------- | ----------------------- | ------------------------------- |
| `telegram-login`                                                    | unauth                  | Telegram payload → session      |
| `client-logout`                                                     | self                    | end the current session         |
| `client-refresh`                                                    | unauth (refresh token)  | new access token                |
| `list-my-sessions` / `revoke-my-session` / `revoke-my-sessions`     | self                    | self-service session management |
| `get-me`                                                            | self                    | current client context          |

### UX

- **Sign-in card** (client app `/auth/telegram`): Telegram Login Widget mounted with the bot
  username; the only error states are `missing_phone_number` ("share your phone with the bot
  and try again"), `account_blocked`, `invalid_oauth_signature` / `oauth_expired`.
- **Client profile** (`/c/profile`): Telegram-synced fields read-only; sessions list with
  current marker; "log out" / "log out everywhere".

## Workshop provisioning (superadmin app)

### Endpoints

| Endpoint                              | Caller            | What                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `create-workshop`                     | platform operator | creates a `workshop` **and** its first `workshop_user` (`is_owner = true`, `force_password_change = true`, temp password) **atomically** — never one without the other. Input: workshop fields + the owner's `full_name`, `login`, `phone`, temp password (auto, with manual override). Returns the summary + the temp password **once**. |
| `block-workshop` / `unblock-workshop` | platform operator | set workshop `status`; blocking revokes the owner's + staff's sessions immediately; unblocking does **not** restore them; clients are unaffected; open orders freeze.                                                                                                                                                                       |

The created owner cannot be created, demoted, or deleted by anyone except a platform operator;
exactly one owner per workshop. Workshop *editing* (settings, profile, lookups) lives in
[`workshop.md`](workshop.md).

### UX

- **Create-workshop dialog**: workshop fields + owner fields, temp password (auto-generated,
  copy button, manual toggle). On success: read-only confirmation showing the owner login + temp
  password with "share this with the owner — shown once" + copy button.
- **Block** (in the workshop detail): mandatory reason; warning that staff sessions are revoked
  and open orders freeze; destructive-styled.

## Workshop user management (workshop app)

### Permission catalog

A staff user holds a set of `(permission, branch)` grants. The v1 catalog:

| Permission         | Grants (on the granted branch)                                                                                                                                                                                              |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `view_dashboard`   | see the branch's dashboard / KPIs / order summary                                                                                                                                                                           |
| `manage_orders`    | the full order workflow — status transitions, discount, pay-later approval, driver assignment, recording cash/bank payments, refunds. *Except* force-cancelling `in_production`+ orders and reverting refunds (owner-only). |
| `manage_catalog`   | manage the branch's material selection — add from the platform catalog, set per-sheet price + min-stock, activate / deactivate. (Master materials are platform-side.)                                                       |
| `manage_inventory` | stock-in, adjust, view stock & transactions. Branch-to-branch transfers are owner-only.                                                                                                                                     |
| `manage_workers`   | create / edit / activate / deactivate workers                                                                                                                                                                               |

A staff user with zero grants can log in but sees nothing actionable. Grants live on the user,
not the branch: changing a branch's status doesn't touch grants; a grant on an `inactive` branch
is inert and becomes live again on reactivation.

### Owner-only powers

The owner (`is_owner`) holds every permission on every branch implicitly, plus these powers
that **cannot be delegated to staff in v1**:

- Create staff and grant/revoke their permissions.
- Create & edit branches; change branch status; set branch pricing.
- Edit workshop settings (delivery zones, payment-channel flags & credentials).
- View payment credentials.
- Branch-to-branch stock transfers.
- Force-cancel an order already `in_production` or later.
- Revert a completed refund.
- View workshop-wide reports / the audit log.

### Endpoints

| Endpoint                                                | Caller | What                                                                                                                                                                                                                                                            |
| ------------------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `create-workshop-user`                                  | owner  | creates a non-owner staff user in the owner's workshop, `force_password_change = true`, temp password (auto/manual), **and optionally an initial set of `(permission, branch)` grants** — created in the same atomic operation. Returns the user + temp password **once**. |
| `update-workshop-user`                                  | owner  | edit `full_name`, `phone`                                                                                                                                                                                                                                       |
| `set-user-grants`                                       | owner  | replaces the user's `permission_grant` rows atomically; each `(permission, branch)` validated against the catalog and the workshop's branches. Takes effect on the user's next request; no session revoke.                                                       |
| `reset-workshop-user-password`                          | owner  | temp password + `force_password_change`; revokes the user's sessions                                                                                                                                                                                            |
| `block-workshop-user` / `unblock-workshop-user`         | owner  | blocking revokes sessions immediately; unblocking does not restore them                                                                                                                                                                                         |
| `list-workshop-users` / `get-workshop-user`             | owner  | list / detail                                                                                                                                                                                                                                                   |

### UX

Under **Settings → Users** (owner-only nav item):

- **Users list** (`/workshop/settings/users`) — table: name, login, phone, status,
  granted-branches count, last login, action menu. "+ User". Empty: "No staff yet — add one to
  delegate work."
- **Create-user dialog** — fields + temp password (auto/manual, copy) + an initial grants matrix
  (permission rows × branch columns, within the workshop). On success: read-only "share login +
  temp password — shown once" confirmation with copy.
- **User detail** (`/workshop/settings/users/:id`) — header (name, status badge, last login);
  tabs: **Profile** (edit), **Permissions** (the grants matrix — toggling saves atomically with
  an explicit Save + unsaved-changes guard), **Sessions** (list with current marker, revoke
  one/all), **Audit** (this user's actions, read-only).
- Row/detail actions: Edit, Reset password (→ one-time-secret confirmation), Block / Unblock
  (block warns sessions are revoked), Revoke sessions.

## Branch context (workshop app)

A staff user may hold grants on multiple branches. The workshop app uses a **branch picker** — a
chip in the top bar ("Branch: Yunusobod ▼") that defines the current branch context. Every
branch-scoped screen (orders, inventory, dashboard, catalog selection, workers) reads from it.

Rules:

- The picker offers branches the user has any grant on (or **all branches**, if `is_owner`).
- On first login: auto-select if the user has exactly one accessible branch; otherwise prompt.
- The selection persists per session (local storage); a session revoke / re-login resets it.
- The picker UI never lets the user pick a branch they can't scope to. Server-side never trusts
  it anyway — every request still names the target's branch, checked against the grant set.
- For owner-only cross-branch tasks (e.g., stock transfer), the screen presents an explicit
  two-branch picker rather than using the current-branch state.

## How a request is authorized

1. Auth middleware turns the bearer token into a **principal context**: type, workshop id,
   `is_owner`, the user's grant set.
2. The endpoint determines the **target's branch** from stored data — never from a
   client-supplied branch id.
3. Allow if `is_owner`, or `(required_permission, target_branch)` is in the grant set; for
   owner-only endpoints, allow only if `is_owner`. Else `forbidden`.

## Edge cases

- **Create-workshop fails after the workshop row but before the owner row** → the whole
  operation rolls back (atomic).
- **Owner login collides** with an existing owner login in another workshop → fine (logins are
  unique per workshop, not globally).
- **Login collision within the same workshop** → rejected.
- **Block a workshop while staff are mid-action** → their next request 401s; the platform
  operator can still read the workshop's data for incident response.
- **A staff member's only granted branch goes `inactive`** → they effectively have no
  actionable screens until it's reactivated or they're granted another; the branch picker hides
  the inactive entry.
- **Staff user with zero grants** → can log in; every workshop screen is empty/hidden.
- **Grant on a branch that later goes `inactive`** → inert; the branch disappears from the
  picker; reactivating makes the grant live again.
- **Owner blocks themselves** — disallowed (a workshop must have an active owner).
- **Client without a shared phone** → `missing_phone_number`; the sign-in card shows the
  phone-share prompt.
- **Telegram payload signature/hash mismatch** → `invalid_oauth_signature`; `auth_date` older
  than the OAuth-expiry window → `oauth_expired`.

## Next

[`workshop.md`](workshop.md) — branches, workers, workshop settings, and audit (the
workshop-admin surfaces that *use* the staff & grants modelled here).
