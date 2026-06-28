---
title: Identity & access
status: draft
owner: shape
updated: 2026-06-28
order: 20
---

# Identity & access

The mechanics of [`access-patterns.md`](../../access-patterns.md) — how each principal signs
in, how sessions work, how workshops are provisioned, how staff and their grants are managed,
and how the surfaces look in the three apps.

## Workshop & platform user sign-in

Platform users sign in with login + password. Workshop users also sign in with login +
password. Workshop-user login is case-insensitive and unique only inside one workshop, so the
backend resolves the submitted login by checking the password across same-login accounts:
exactly one password match authenticates, no match fails, and more than one match fails as
ambiguous. The error on a bad pair is a **generic** "login or password is
incorrect" — no account-existence oracle. **Five consecutive bad attempts → a 15-minute
lockout** (`locked_until`); a correct password resets the counter. Passwords are argon2 /
bcrypt-hashed at rest; complexity ≥ 8 chars with at least one upper, one lower, one digit.

`account_locked` and `account_blocked` are returned only after the submitted credential pair is
otherwise valid. Unknown login, wrong password, wrong password for a locked account, wrong
password for a blocked account, and ambiguous same-login / same-password matches all return the
same generic credential error.

`password_reset_required` (set on creation, on a higher-principal password reset, and after
a security rotation) is an account gate. It is returned from `get-me` and the workshop /
superadmin app shell shows a blocking account banner until the user changes their password.
While the flag is true, the user may use only `me`, profile/password, sessions, logout, and
logout-everywhere surfaces; branch-scoped, platform-ops, and workshop-management routes are
forbidden until password change clears the flag.

**Platform users are seeded by a backend CLI command for bootstrap.** The in-app platform-user
registry is owned by [`platform.md`](platform.md) and is outside this identity slice.

### Sessions

Opaque tokens stored in the DB, hashed (SHA-256) — not JWTs. Access TTL **24 h**; refresh TTL
**7 d**; **at most 5 concurrent sessions per principal** (a 6th login evicts the oldest).
Revoking = deleting the row.

Browser clients keep the access token in memory only. The refresh token is issued as an
httpOnly, Secure, SameSite cookie scoped to the relevant app/API surface; it is never exposed to
frontend JavaScript. A page reload restores auth by calling refresh through that cookie.

| Trigger                           | Effect                                                            |
| --------------------------------- | ----------------------------------------------------------------- |
| logout (this session)             | delete this session                                               |
| "log out everywhere"              | delete all the user's sessions                                    |
| change own password               | delete all _other_ sessions; keep the current                     |
| reset password (higher principal) | delete all the user's sessions                                    |
| block user                        | delete all the user's sessions                                    |
| block workshop                    | delete the workshop's owner + staff sessions (clients unaffected) |
| 5-session cap exceeded            | evict the oldest                                                  |
| token expiry                      | inert; a periodic job prunes the row                              |

### Operations

A user can sign in, sign out, refresh their access token (the refresh path re-checks the
user, and for workshop users the workshop, is still active), change their own password
(revokes all _other_ sessions; clears `password_reset_required`), list their sessions and
revoke one or all, and fetch their `me` (principal type, ids, `is_owner`, grant set,
`password_reset_required`).

### UX

- **Sign-in screen** (workshop app `/auth/login`; superadmin app `/auth/login`) — both
  password-auth surfaces show login + password only. Failure uses the same generic error; a
  lockout banner ("try again at HH:MM") appears only after credentials are otherwise valid and
  the account is locked.
- **Password-reset gate** — shown in the workshop / superadmin app shell when
  `password_reset_required = true`; it is persistent, blocking for non-account routes, and links
  to the profile password tab. The gate disappears only after a successful password change.
- **Self profile** (`/workshop/profile`, `/admin/profile`) — Profile (read-only fields),
  Change password (strength meter), Sessions list (current marker, "revoke" per row, "log out
  everywhere").

## Client sign-in (phone + Telegram OTP)

The client signs in with a **phone number verified by a one-time code sent over Telegram** — no
password, no widget, no app-switch. The phone is the identity; the flow is one continuous path
that branches to registration only when the number is new. Three steps:

1. **Request a code.** Client submits a `+998XXXXXXXXX` phone. The system issues a
   [verification challenge](../entities/identity.md#phone-verification-challenge) and sends a
   6-digit code to that number **over Telegram** (via the Telegram Gateway). A malformed number
   is `invalid_phone`; a number not reachable on Telegram is `phone_unreachable_on_telegram`
   (there is **no SMS fallback** in v1 — the client must have Telegram on that number); exceeding
   the resend cooldown (60 s), per-phone rate limit (5 sends / hour), or per-IP rate limit
   (30 sends / hour) is `code_send_rate_limited`.
2. **Verify the code.** Client submits the phone + code. A wrong code is `invalid_code` (the
   challenge survives, attempt counter bumped); the 5th wrong attempt burns the challenge
   (`too_many_attempts`, must request a new code); a code past its 5-minute TTL is `code_expired`.
3. **Log in or register.** On a correct code:
   - **Phone found, `active`** → log in.
   - **Phone found, `blocked`** → `account_blocked`.
   - **Phone not found** → the response carries `is_new = true`; the client supplies a `name`
     (1–80 chars; `name_required` if blank) and the system creates the client
     (`status = active`) and logs them in.

There is no account-existence oracle _before_ verification — the login-vs-register branch is
only revealed after a correct code. On success a session is created; self-service session
management is the same as workshop / platform users.

### Dev & local sign-in

Local, CI, and E2E runs have no Telegram Gateway and no real phone, so a code can't actually be
sent. A single setting — **`otp_dev_codes`**, a list of fixed codes — covers this: when it is
**non-empty**, the send step is a no-op (no Gateway call) and verification accepts **any** code
in the list for **any** phone, so a developer signs in as any number with, say, `000000`. When
it is **empty** — the default, and **mandatory in production** — the real flow runs: one random
per-challenge code delivered over Telegram.

Production rejects non-empty `otp_dev_codes` unless
**`ALLOW_PROD_OTP_DEV_CODES=true`** is also set. That flag exists only for pre-production public
testing before the Telegram Gateway account is funded and configured; remove it, set
`OTP_DEV_CODES=[]`, and configure `TELEGRAM_GATEWAY_ACCESS_TOKEN` before onboarding real users or
real workshop data.

Send-rate enforcement is controlled separately by **`OTP_RATE_LIMITS_ENABLED`**. It defaults
to `true` and must stay enabled outside automated test runs; local E2E sets it to `false` so
repeated parallel browser tests from one localhost IP do not exhaust the per-IP OTP bucket.

### UX

One sign-in card (client app `/auth/login`) that advances through steps in place — never lose
the phone the client already typed when stepping forward or back:

- **Phone step** — a single phone field prefilled with `+998`, primary **Send code**. Errors
  inline: `invalid_phone`, `phone_unreachable_on_telegram` ("We couldn't reach this number on
  Telegram — sign-in needs Telegram on this number"), `code_send_rate_limited` ("Try again in
  N s").
- **Code step** — a 6-digit code input, the masked target phone, an **Edit** affordance back to
  the phone step, and a **Resend** that's disabled with a live countdown until the cooldown
  elapses. Errors: `invalid_code` (with attempts remaining), `code_expired` and
  `too_many_attempts` (both route the client back to resend / request a new code).
- **Name step** — shown **only** when verification returned `is_new = true`: one `name` field,
  primary **Continue**; returning clients skip straight into the app.
- **Client profile** (`/c/profile`) — `name` editable (it's client-entered, not synced); `phone`
  read-only (changing it would mean re-verification — out of scope in v1); order count; sessions
  list with a current marker; "log out" / "log out everywhere". The model still has
  `preferred_branch_id`, but the profile UI to set it is not currently surfaced.

## Workshop provisioning (superadmin app)

A platform operator provisions a workshop atomically with its first user and first branch:

- **Create a workshop, first branch, and owner — atomically.** Input: workshop `name`
  (`currency` defaults to `UZS`) + first branch fields (`name`, `address`, `phone`,
  `working_hours`) + the owner's `login`, plus an auto-generated temp password (manual
  override).
  The same transaction creates the `workshop` row, an `active` first `branch` row with empty
  `branch_pricing`, and a `workshop_user` row with `is_owner = true`,
  `home_branch_id = first_branch.id`, and `password_reset_required = true`. Returns the summary
  and the temp password **once**. The returned confirmation shows the owner login and temp
  password; only the temp password is secret and shown once. Provisioning creates exactly one
  owner; after that, v1 has no owner create / demote / delete / transfer path. Platform
  provisioning does not collect workshop-level contact data, branch coordinates, or owner
  name/phone; branch contact and precise branch location are owner-managed after first sign-in.
- **Block / unblock the workshop.** Blocking revokes the owner's + staff's sessions
  immediately; their next login is rejected. Clients are unaffected. Open orders **freeze** —
  staff can't act because they can't log in; no automatic transitions. Unblocking does **not**
  restore sessions — users log in again.

The operator's **only** workshop write actions are: provision (workshop + first branch + first
owner, atomic), block, and unblock. The operator does **not** edit the workshop profile or the
owner's profile/contact fields (name / phone) — that is owner territory and there is no
operator path to it. Workshop _editing_ (profile, settings) lives in
[`workshop.md`](workshop.md); owner-identity edits are owner self-service / owner-managed,
not operator-managed. If correcting an owner's phone via the operator ever becomes a real
need, it must be specified here first — it is deliberately absent in v1.

### UX

- **Create-workshop dialog** — workshop name + first branch name/address/phone/working-hours,
  owner login, temp password (auto-generated, copy button, manual toggle). On success:
  read-only confirmation showing the owner login + temp password with "share this with the
  owner — temp password shown once" + copy button; the owner sees the password-reset gate after
  sign-in and lands with the first branch available in branch context.
- **Block** (in the workshop detail) — mandatory reason; warning that staff sessions are
  revoked and open orders freeze; destructive-styled.

All provisioning, create-user, reset-password, and block dialogs move focus into the dialog, trap
focus while open, and return focus to the trigger on close. One-time-secret confirmations expose a
copy button and keep the secret visible until the operator/owner closes the confirmation. Action
menus are keyboard-operable, and destructive actions move focus to the confirmation's primary
decision. The grants matrix is keyboard-operable by row/column, has an explicit Save, and preserves
unsaved changes until save, cancel, or confirmed navigation.

## Workshop user management (workshop app)

Each staff user holds a set of `(permission, branch)` grants. The owner holds every
permission on every branch implicitly, plus owner-only carve-outs.

### Permission catalog

| Permission             | Grants on the granted branch                                                                                                                                                                                                                                                                                                                                                                            |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `view_dashboard`       | see the branch's dashboard / KPIs / order summary                                                                                                                                                                                                                                                                                                                                                       |
| `manage_orders`        | the office side of the order workflow — verify / approve (`new → confirmed`), assign and re-assign the cutter / edger, apply discounts, complete a production job **on behalf** of an absent worker, **revert** one step on a mistake, and cancel any pre-`completed` order with a reason. Cannot do production work itself unless it also holds `process_production`. See [`orders.md`](orders.md).    |
| `process_production`   | the **cutter & edger workspaces** — see orders assigned to this user, view the cutting plan read-only, mark **Cutting done** (→ `edge_banding` or `ready`; stamps the cutter snapshot, decrements panel stock for `shop` panels) and **Banding done** (→ `ready`; stamps the edge snapshot, decrements edge stock per edge material for `shop` sides). Cannot edit, verify, cancel, or revert an order. |
| `manage_catalog`       | the branch's material selection — add from the platform catalog, set the per-unit price and min-stock, activate / deactivate. (Master materials are platform-side.)                                                                                                                                                                                                                                     |
| `manage_inventory`     | stock-in (from a supplier; suppliers added on demand), adjust, view stock and transactions.                                                                                                                                                                                                                                                                                                             |
| `manage_finance`       | the money ledger — record / edit / void income (including order payments) and expenses (including `salary`). See [`finance.md`](finance.md).                                                                                                                                                                                                                                                            |
| `view_finance_reports` | read-only access to the finance dashboards, the finance reports, and the worker-production reports.                                                                                                                                                                                                                                                                                                     |

`process_delivery` is **gated out of v1** — v1 is pickup-only
([`scope.md`](../../scope.md)), so there is no driver workspace and the grant is not in the
catalog; it returns when delivery does.

A staff user with zero grants can log in but sees nothing actionable. Grants live on the
user, not the branch: changing a branch's status doesn't touch grants; a grant on an
`inactive` branch is inert and becomes live again on reactivation.

**Workers are workshop users.** A "cutter" or "edge bander" is just a workshop user holding
`process_production` on the order's branch — there is **no separate `worker` entity** and
**no role**: capability is the grant set, and one person may hold `manage_orders` _and_
`process_production` _and_ `manage_finance` and run the whole flow alone. The system stores
no pay rates; how much a worker is paid is the accountant's manual calculation from the
work the user actually did, read from the order's production stamps (see
[`finance.md`](finance.md) and [`orders.md`](orders.md)).

### Owner-only powers

The owner (`is_owner`) holds every permission on every branch implicitly, plus these powers
that **cannot be delegated to staff in v1**:

- Create staff and grant / revoke their permissions.
- Create and edit branches; change branch status; set branch pricing.
- Edit workshop settings (profile).
- View workshop-wide reports.

### Operations (owner)

- **Create a workshop user** — `full_name`, `phone`, `login`, `password_reset_required = true`,
  temp password (auto / manual), a multi-branch picker that scopes the initial grants matrix,
  a derived `home_branch_id` (the first selected branch; it remains the assignment home for
  cutter / edger work), and **an optional initial set of `(permission, branch)` grants**.
  Created in one atomic operation; returns the user and the temp password
  **once**.
- **Edit profile fields** — `full_name`, `phone`, `home_branch_id`.
- **Set grants** — replaces the user's `permission_grant` rows atomically; each
  `(permission, branch)` is validated against the catalog and the workshop's branches. **The
  new grants take effect on the user's next request** — no session revoke.
- **Reset password** — a temp password + `password_reset_required = true`; revokes the user's
  sessions.
- **Block / unblock** — blocking revokes sessions immediately; unblocking does not restore
  them.
- **List / get** — the workshop's users for the owner.

### UX

Under **Settings → Users** (owner-only nav item):

- **Users list** (`/workshop/settings/users`) — table: name, login, phone, home branch,
  granted-branches count, status, last login, action menu. Filters: home branch, status.
  **+ User**. Empty: "No staff yet — add one to delegate work."
- **Create-user dialog** — profile fields + multi-branch picker + temp password (auto / manual,
  copy) + an initial grants matrix (permission rows × selected branch columns, within the workshop).
  On success: read-only "share login + temp password — shown once" confirmation with copy.
- **User detail** (`/workshop/settings/users/:id`) — header (name, status badge, home branch,
  last login); tabs:
  - **Profile** (edit) — profile fields incl. home branch.
  - **Permissions** — the grants matrix; toggling saves atomically with an explicit Save and
    an unsaved-changes guard.
  - **Sessions** — list with current marker; revoke one / all.
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
  trusts it anyway: create/list operations may submit a branch id, which the service validates
  against the grant set; operations on existing records derive the target branch from stored data.

Zero-grant staff keep access to account controls: profile, password-reset gate, sessions, logout,
and logout-everywhere. Branch-scoped navigation and work screens stay hidden / empty until the owner
grants at least one active branch permission.

## How a request is authorized

1. The auth middleware turns the bearer token into a **principal context**: type, workshop
   id, `is_owner`, the grant set.
2. The operation determines the **target branch**. Create/list operations may use a submitted
   branch id after validating it against stored branch/workshop data; operations on existing
   records derive the branch from the stored record, never from a client-supplied replacement.
3. Allow if `is_owner`, or if `(required_permission, target_branch)` is in the grant set; for
   owner-only operations, allow only if `is_owner`. Otherwise → `forbidden`.

## Edge cases

- **Create-workshop fails after the workshop row but before the owner row** — the whole
  operation rolls back (atomic).
- **Owner login collides** with an existing owner login in another workshop — allowed because
  logins are unique per workshop, not globally. If the same login also has the same password in
  more than one workshop, sign-in rejects it as ambiguous until one password differs.
- **Login collision within the same workshop** — rejected.
- **Block a workshop while staff are mid-action** — their next request 401s; the platform
  operator can still read the workshop's data for incident response.
- **A staff member's only granted branch goes `inactive`** — they effectively have no
  actionable screens until it's reactivated or they're granted another; the branch picker
  hides the inactive entry.
- **Staff user with zero grants** — can log in; account controls remain available, while
  branch-scoped screens are empty / hidden.
- **Owner as cutter / edger on a non-home branch** — allowed: `is_owner` holds
  `process_production` on every branch and is **exempt** from the
  `home_branch_id = order.branch_id` assignment check that binds non-owner staff (see
  [`orders.md`](orders.md)).
- **Grant on a branch that later goes `inactive`** — inert; the branch disappears from the
  picker; reactivating makes the grant live again.
- **Owner blocks themselves** — disallowed (a workshop must have an active owner).
- **Client's number isn't on Telegram** — `phone_unreachable_on_telegram`; the sign-in card
  explains sign-in needs Telegram on that number (no SMS fallback in v1).
- **Client mistypes the code** — `invalid_code` with attempts remaining; the 5th wrong attempt
  burns the challenge (`too_many_attempts`) and a code past its 5-minute TTL is `code_expired` —
  both send the client back to request a fresh code.
- **Code requested too often** — `code_send_rate_limited`; the resend control stays disabled
  with a countdown until the 60 s cooldown elapses.

## Next

- [`workshop.md`](workshop.md) — branches, workshop settings, and audit.
- [`finance.md`](finance.md) — income, expenses, and the worker-production reports the
  accountant uses to pay the workers granted access here.
