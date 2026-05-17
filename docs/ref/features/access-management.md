---
title: Identity & access
status: draft
owner: shape
updated: 2026-05-17
order: 20
---

# Identity & access

The mechanics of [`access-patterns.md`](../../access-patterns.md) — how each principal signs
in, how sessions work, how workshops are provisioned, how staff and their grants are managed,
and how the surfaces look in the three apps.

## Workshop & platform user sign-in

Login + password. Login is case-insensitive; unique per workshop (workshop users) or
platform-wide (platform users). The error on a bad pair is a **generic** "login or password
is incorrect" — no account-existence oracle. **Five consecutive bad attempts → a 15-minute
lockout** (`locked_until`); a correct password resets the counter. Passwords are argon2 /
bcrypt-hashed at rest; complexity ≥ 8 chars with at least one upper, one lower, one digit.

`force_password_change` (set on creation, on a higher-principal password reset, and after a
forced rotation) gates the user — every operation except change-password / logout / get-me
returns `password_change_required` until the user changes it.

**Platform users are seeded by a backend CLI command.** They're the top of the hierarchy, with
no higher principal to create them; in-app creation is allowed once at least one platform
user exists ([`platform.md`](platform.md)).

### Sessions

Opaque tokens stored in the DB, hashed (SHA-256) — not JWTs. Access TTL **24 h**; refresh TTL
**7 d**; **at most 5 concurrent sessions per principal** (a 6th login evicts the oldest).
Revoking = deleting the row.

| Trigger | Effect |
|---|---|
| logout (this session) | delete this session |
| "log out everywhere" | delete all the user's sessions |
| change own password | delete all *other* sessions; keep the current |
| reset password (higher principal) | delete all the user's sessions |
| block user | delete all the user's sessions |
| block workshop | delete the workshop's owner + staff sessions (clients unaffected) |
| 5-session cap exceeded | evict the oldest |
| token expiry | inert; a periodic job prunes the row |

### Operations

A user can sign in, sign out, refresh their access token (the refresh path re-checks the
user, and for workshop users the workshop, is still active), change their own password
(revokes all *other* sessions; clears `force_password_change`), list their sessions and
revoke one or all, and fetch their `me` (principal type, ids, `is_owner`, grant set,
`force_password_change`).

### UX

- **Sign-in screen** (workshop app `/auth/login`; superadmin app `/auth/login`) — login +
  password fields; generic error on failure; a lockout banner ("try again at HH:MM") when
  `locked_until` came back.
- **Force-password-change screen** — shown on first login (or after a reset); strength meter
  (≥ 8 chars, upper + lower + digit); blocks the rest of the app until set.
- **Self profile** (`/workshop/profile`, `/admin/profile`) — Profile (read-only fields),
  Change password (strength meter), Sessions list (current marker, "revoke" per row, "log out
  everywhere").

## Client sign-in (Telegram OAuth)

The client signs in by passing the Telegram Login Widget's payload (`telegram_id`,
`first_name`, `last_name`, `username`, `photo_url`, `phone_number`, `auth_date`, `hash`). The
system **HMAC-verifies** it against the bot token; a bad signature or a stale `auth_date` is
rejected (`invalid_oauth_signature` / `oauth_expired`).

**The phone number is required.** If Telegram didn't share one, the client is asked to allow
phone-sharing and retry (`missing_phone_number`). The phone is the client's primary human
identifier; the profile (telegram id, username, phone, photo, name) is refreshed from the
payload on every login.

Not found → create the client (`status = active`, `is_new = true`); found → use it. Blocked →
`account_blocked`. Either way, on success a session is created. Self-service session
management is the same as workshop / platform users.

### UX

- **Sign-in card** (client app `/auth/telegram`) — the Telegram Login Widget mounted with the
  bot username; the only error states are `missing_phone_number` ("share your phone with the
  bot and try again"), `account_blocked`, `invalid_oauth_signature` / `oauth_expired`.
- **Client profile** (`/c/profile`) — Telegram-synced fields read-only; sessions list with
  current marker; "log out" / "log out everywhere".

## Workshop provisioning (superadmin app)

A platform operator provisions a workshop atomically with its first user:

- **Create a workshop and its owner — atomically.** Input: workshop fields + the owner's
  `full_name`, `login`, `phone`, plus an auto-generated temp password (manual override). The
  same transaction creates the `workshop` row and a `workshop_user` row with `is_owner = true`
  and `force_password_change = true` — **never one without the other**. Returns the summary
  and the temp password **once**. The owner cannot be created, demoted, or deleted by anyone
  except a platform operator; exactly one owner per workshop.
- **Block / unblock the workshop.** Blocking revokes the owner's + staff's sessions
  immediately; their next login is rejected. Clients are unaffected. Open orders **freeze** —
  staff can't act because they can't log in; no automatic transitions. Unblocking does **not**
  restore sessions — users log in again.

Workshop *editing* (profile, settings, payment channels) lives in
[`workshop.md`](workshop.md).

### UX

- **Create-workshop dialog** — workshop fields + owner fields, temp password (auto-generated,
  copy button, manual toggle). On success: read-only confirmation showing the owner login +
  temp password with "share this with the owner — shown once" + copy button.
- **Block** (in the workshop detail) — mandatory reason; warning that staff sessions are
  revoked and open orders freeze; destructive-styled.

## Workshop user management (workshop app)

Each staff user holds a set of `(permission, branch)` grants. The owner holds every
permission on every branch implicitly, plus owner-only carve-outs.

### Permission catalog

| Permission | Grants on the granted branch |
|---|---|
| `view_dashboard` | see the branch's dashboard / KPIs / order summary |
| `manage_orders` | the office side of the order workflow — verify / approve (`new → confirmed`), assign and re-assign the cutter / edger, apply discounts, complete a production job **on behalf** of an absent worker, **revert** one step on a mistake, and cancel any pre-`completed` order with a reason. Cannot do production work itself unless it also holds `process_production`. See [`orders.md`](orders.md). |
| `process_production` | the **cutter & edger workspaces** — see orders assigned to this user, view the cutting plan read-only, mark **Cutting done** (→ `edge_banding` or `ready`; stamps the cutter snapshot, decrements sheet stock) and **Banding done** (→ `ready`; stamps the edge snapshot, decrements edge stock). Cannot edit, verify, cancel, or revert an order. |
| `manage_catalog` | the branch's material selection — add from the platform catalog, set the per-unit price and min-stock, activate / deactivate. (Master materials are platform-side.) |
| `manage_inventory` | stock-in (from a supplier; suppliers added on demand), adjust, view stock and transactions. Branch-to-branch transfers are owner-only. |
| `manage_finance` | the money ledger — record / edit / void income (including order payments) and expenses (including `salary`). See [`finance.md`](finance.md). |
| `view_finance_reports` | read-only access to the finance dashboards, the finance reports, and the worker-production reports. |

`process_delivery` is **gated out of v1** — v1 is pickup-only
([`scope.md`](../../scope.md)), so there is no driver workspace and the grant is not in the
catalog; it returns when delivery does.

A staff user with zero grants can log in but sees nothing actionable. Grants live on the
user, not the branch: changing a branch's status doesn't touch grants; a grant on an
`inactive` branch is inert and becomes live again on reactivation.

**Workers are workshop users.** A "cutter" or "edge bander" is just a workshop user holding
`process_production` on the order's branch — there is **no separate `worker` entity** and
**no role**: capability is the grant set, and one person may hold `manage_orders` *and*
`process_production` *and* `manage_finance` and run the whole flow alone. The system stores
no pay rates; how much a worker is paid is the accountant's manual calculation from the
work the user actually did, read from the order's production stamps (see
[`finance.md`](finance.md) and [`orders.md`](orders.md)).

### Owner-only powers

The owner (`is_owner`) holds every permission on every branch implicitly, plus these powers
that **cannot be delegated to staff in v1**:

- Create staff and grant / revoke their permissions.
- Create and edit branches; change branch status; set branch pricing.
- Edit workshop settings (profile).
- Branch-to-branch stock transfers.
- View workshop-wide reports / the audit log.

### Operations (owner)

- **Create a workshop user** — `full_name`, `phone`, `login`, `force_password_change = true`,
  temp password (auto / manual), a `home_branch_id` (the branch the user works at — gates
  cutter / edger assignment to an order at that branch; for office staff who span branches,
  set the branch they sit at), and **an optional initial set of `(permission, branch)`
  grants**. Created in one atomic operation; returns the user and the temp password
  **once**.
- **Edit profile fields** — `full_name`, `phone`, `home_branch_id`.
- **Set grants** — replaces the user's `permission_grant` rows atomically; each
  `(permission, branch)` is validated against the catalog and the workshop's branches. **The
  new grants take effect on the user's next request** — no session revoke.
- **Reset password** — a temp password + `force_password_change`; revokes the user's
  sessions.
- **Block / unblock** — blocking revokes sessions immediately; unblocking does not restore
  them.
- **List / get** — the workshop's users for the owner.

### UX

Under **Settings → Users** (owner-only nav item):

- **Users list** (`/workshop/settings/users`) — table: name, login, phone, home branch,
  granted-branches count, status, last login, action menu. Filters: home branch, status.
  **+ User**. Empty: "No staff yet — add one to delegate work."
- **Create-user dialog** — profile fields (incl. home branch) + temp password (auto / manual,
  copy) + an initial grants matrix (permission rows × branch columns, within the workshop).
  On success: read-only "share login + temp password — shown once" confirmation with copy.
- **User detail** (`/workshop/settings/users/:id`) — header (name, status badge, home branch,
  last login); tabs:
  - **Profile** (edit) — profile fields incl. home branch.
  - **Permissions** — the grants matrix; toggling saves atomically with an explicit Save and
    an unsaved-changes guard.
  - **Sessions** — list with current marker; revoke one / all.
  - **Audit** — this user's actions, read-only.
- Row / detail actions: Edit · Reset password (→ one-time-secret confirmation) · Block /
  Unblock (block warns sessions are revoked) · Revoke sessions.

## Branch context (workshop app)

A staff user may hold grants on multiple branches. The workshop app uses a **branch picker** —
a chip in the top bar ("Branch: Yunusobod ▼") that defines the current branch context. Every
branch-scoped screen (orders, inventory, dashboard, catalog selection, workers) reads from
it.

Rules:

- The picker offers branches the user has any grant on — or **all branches**, if `is_owner`.
- On first login: auto-select if the user has exactly one accessible branch; otherwise
  prompt.
- The selection persists per session (local storage); a session revoke or re-login resets it.
- The picker UI never lets the user pick a branch they can't scope to. The server never
  trusts it anyway — every request still names the target's branch, checked against the
  grant set.
- For owner-only cross-branch tasks (e.g., stock transfer), the screen uses an explicit
  two-branch picker rather than the current-branch state.

## How a request is authorized

1. The auth middleware turns the bearer token into a **principal context**: type, workshop
   id, `is_owner`, the grant set.
2. The operation determines the **target's branch from stored data** — never from a
   client-supplied branch id.
3. Allow if `is_owner`, or if `(required_permission, target_branch)` is in the grant set; for
   owner-only operations, allow only if `is_owner`. Otherwise → `forbidden`.

## Edge cases

- **Create-workshop fails after the workshop row but before the owner row** — the whole
  operation rolls back (atomic).
- **Owner login collides** with an existing owner login in another workshop — fine (logins
  are unique per workshop, not globally).
- **Login collision within the same workshop** — rejected.
- **Block a workshop while staff are mid-action** — their next request 401s; the platform
  operator can still read the workshop's data for incident response.
- **A staff member's only granted branch goes `inactive`** — they effectively have no
  actionable screens until it's reactivated or they're granted another; the branch picker
  hides the inactive entry.
- **Staff user with zero grants** — can log in; every workshop screen is empty / hidden.
- **Grant on a branch that later goes `inactive`** — inert; the branch disappears from the
  picker; reactivating makes the grant live again.
- **Owner blocks themselves** — disallowed (a workshop must have an active owner).
- **Client without a shared phone** — `missing_phone_number`; the sign-in card shows the
  phone-share prompt.
- **Telegram payload signature mismatch** — `invalid_oauth_signature`; an `auth_date` older
  than the OAuth-expiry window → `oauth_expired`.

## Next

- [`workshop.md`](workshop.md) — branches, workshop settings, and audit.
- [`finance.md`](finance.md) — income, expenses, and the worker-production reports the
  accountant uses to pay the workers granted access here.
