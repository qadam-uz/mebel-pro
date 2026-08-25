---
title: Identity & access
status: draft
owner: shape
updated: 2026-08-22
order: 20
---

# Identity & access

The mechanics of [`access-patterns.md`](../../access-patterns.md) — how each principal signs
in, how sessions work, how workshops are provisioned, how staff and their grants are managed,
and how the surfaces look in the three apps.

## Workshop & platform user sign-in

Platform users sign in with login + password. Workshop users also sign in with login +
password. Workshop-user login is case-insensitive and **unique across the whole platform**, so
the login alone names exactly one account and the workshop follows from it — sign-in is a single
lookup plus one password verification, never a scan across same-login candidates. The error on a
bad pair is a **generic** "login or password is incorrect" — no account-existence oracle. **Five consecutive bad attempts → a 15-minute
lockout** (`locked_until`); a correct password resets the counter. Passwords are argon2 /
bcrypt-hashed at rest; complexity ≥ 8 chars with at least one upper, one lower, one digit.

`account_locked` and `account_blocked` are returned only after the submitted credential pair is
otherwise valid. Unknown login, wrong password, wrong password for a locked account, and wrong
password for a blocked account all return the same generic credential error.

Failed password attempts are also **throttled per client IP**: too many credential misses inside
a sliding window (default 20 per 15 min) → `login_rate_limited` (429) with a
`retry_after_seconds`, and while an IP is tripped even valid credentials from it are refused.
Only credential misses count, a success never resets the budget (one valid login can't launder
brute-force budget for its IP), and both password sign-in surfaces share one bucket. This
covers what the per-account lockout can't: guessing rotated across many accounts stays under
each account's lockout threshold. The
counter is in-memory and process-local (the app runs as a single instance; the account lockout
remains the durable backstop across restarts) and is env-tunable via `LOGIN_IP_THROTTLE_*`
settings. Like the OTP per-IP budgets, it needs the deploy's trusted-proxy config
(`TRUSTED_PROXY_CIDRS`) — without it all traffic shares one bucket.

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
  the account is locked. A tripped IP throttle shows a generic "too many attempts, try again
  later" line — no per-IP detail is surfaced.
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
   (there is **no SMS fallback** in v1 — the client must have Telegram on that number).
   Exceeding any send budget is `code_send_rate_limited` with a `retry_after_seconds`. Every
   Gateway message costs money, so sends are budgeted at three scopes — per phone, per client
   IP, and platform-wide — each with an hourly and a daily cap (defaults: 60 s resend cooldown;
   phone 5 / hour, 10 / day; IP 30 / hour, 50 / day; global 150 / hour, 1000 / day — the global
   daily cap is the hard ceiling on the worst-case Telegram bill). The caps are env-tunable
   (`OTP_*` settings) so an abuse incident can be throttled without a deploy. **Failed
   deliveries count toward every budget and start the cooldown** — an unreachable number can't
   be probed for free. Per-IP budgets require the deploy's trusted-proxy config
   (`TRUSTED_PROXY_CIDRS` matching the edge network) — without it all traffic shares one bucket.
2. **Verify the code.** Client submits the phone + code. A wrong code is `invalid_code` (the
   challenge survives, attempt counter bumped); the 5th wrong attempt burns the challenge
   (`too_many_attempts`, must request a new code); a code past its 5-minute TTL is `code_expired`.
   The attempt counter and burns are committed even though the request itself fails — a rejected
   guess must consume an attempt (CB-133) — and concurrent guesses serialize on the challenge
   row, so a brute-forcer gets at most 5 guesses per challenge.
3. **Log in or register.** On a correct code:
   - **Phone found, `active`** → log in.
   - **Phone found, `blocked`** → `account_blocked`.
   - **Phone not found** → the response carries `is_new = true`; the client supplies a `name`
     (1–80 chars; `name_required` if blank) and the system creates the client
     (`status = active`) and logs them in.

There is no account-existence oracle _before_ verification — the login-vs-register branch is
only revealed after a correct code. On success a session is created; self-service session
management is the same as workshop / platform users.

### Staff-resolved walk-ins (find-or-create)

A walk-in customer at the counter has no app session, but their order still belongs to a
real client row. Workshop staff holding `manage_orders` resolve the walk-in **by phone**
from the workshop app's order-creation flow
([`orders.md`](orders.md#staff-created-orders-walk-in-clients)):

- **Phone-first, answered as it is typed.** The moment the phone is complete
  (`+998XXXXXXXXX`) the base is asked who owns it. A match fills the client's registered
  name into a read-only field with a "found in the base — check the number if this is
  someone else" caption, and the staffer reads that name before pressing continue; a miss
  leaves the field empty and required. **The disclosure still happens before the commit** —
  that is what stops a phone typo attaching an order to a stranger — but on one screen
  rather than behind a second confirm card.
- **Asking does not write.** The read is its own endpoint, separate from find-or-create:
  resolving on every typed phone would mint a client per typo. The write happens once, on
  continue, and creates the row (`status = active`) exactly as OTP registration would.
- **A blocked client is rejected** (`account_blocked`) on the write path — mirrors OTP
  verification. On the read path a blocked account reads as a **miss**: the answer to "may
  I write an order for this number" is no either way, and raising there would make the
  lookup an oracle for account status.
- **Never a login.** The staff path finds or creates the row; it creates **no client
  session**. OTP remains the only way a client signs in — the first time the walk-in
  verifies that number they claim the row and see their order history.
- **Guardrails.** Both paths deliberately disclose an existing client's stored name to
  `manage_orders` staff — the trade for the anti-typo confirmation, and the name is already
  what the counter conversation runs on. In exchange each is **rate-limited per staff user**
  (the same convention as the OTP send limits) and **every call writes an audit row** (the
  phone, the outcome, the acting staffer) — a staffer scanning phone numbers is throttled
  and visible. The read carries the larger hourly budget of the two: looking a number up
  and not writing an order is the normal case at a counter, not a suspicious one. Revisit
  if name disclosure draws a real privacy complaint — then mask the returned name, at the
  cost of a weaker confirmation.

**Why find-or-create, not a guest entity.** `phone` is unique on the client and the account
is passwordless — OTP verification is itself already a find-or-create on the phone. Reusing
that identity makes a staff-created client automatically claimable (no merge tooling, no
orphaned guest rows, order history intact) and needs no order schema change. A separate
guest/walk-in entity, or staff-typed contact fields with no client link, were rejected:
both split the customer's history and require a claim/merge path v1 doesn't have.

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

Send-rate enforcement is controlled separately by **`OTP_RATE_LIMITS_ENABLED`** — the master
switch for the cooldown and all six send budgets (per-phone, per-IP, and global; hourly and
daily). It defaults to `true` and must stay enabled outside automated test runs; local E2E sets
it to `false` so repeated parallel browser tests from one localhost IP do not exhaust the
per-IP OTP bucket.

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
  (`currency` defaults to `UZS`) + first branch fields (`name`, `address`, `phone`) + the
  owner's `login`, plus an auto-generated temp password (manual override).
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
- **Reset the owner's password.** The operator is the owner's only recovery path: the
  owner-side staff reset refuses the owner as a target, so a locked-out owner has nowhere
  else to go. The reset issues a new auto-generated temp password (shown **once**), sets
  `password_reset_required`, revokes all the owner's sessions, and is audited. It works on a
  blocked workshop too — unblock and reset are often the same support call, and login stays
  gated by the block either way.

The operator's **only** workshop write actions are: provision (workshop + first branch + first
owner, atomic), block, unblock, and owner password reset. The operator does **not** edit the workshop profile or the
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
- **Reset owner password** (in the workshop detail, next to the owner login) —
  destructive-styled confirmation naming the owner login and that all their sessions are
  revoked; on success, the standard one-time-secret confirmation with the login + temp
  password.

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
| `view_orders`          | **read-only** access to the branch's orders — list, search, and open any order in the branch, including the client's name and phone, line prices, materials and production stamps. No action on them, and no dashboard section of its own. It was called `view_dashboard` until 2026-07; the name promised a KPI page while the grant handed over every order in the branch, so it was renamed to what it does. |
| `manage_orders`        | the office side of the order workflow — verify / approve (`new → confirmed`), assign and re-assign the cutter / edger, apply discounts, complete a production job **on behalf** of an absent worker, **revert** one step on a mistake, cancel any pre-`completed` order with a reason, and **create a cutting draft + place an order on behalf of a walk-in client**, resolving them by phone ([Staff-resolved walk-ins](#staff-resolved-walk-ins-find-or-create)). Cannot do production work itself unless it also holds `process_production`. See [`orders.md`](orders.md).    |
| `process_production`   | the **cutter & edger workspaces** — see orders assigned to this user, view the cutting plan read-only, mark **Cutting done** (→ `edge_banding` or `ready`; stamps the cutter snapshot, decrements panel stock for `shop` panels) and **Banding done** (→ `ready`; stamps the edge snapshot, decrements edge stock per edge material for `shop` sides). Cannot edit, verify, cancel, or revert an order. |
| `manage_catalog`       | the branch's own materials — attach the platform formats the branch carries, set each one's price and min-stock, activate / deactivate. (Decors and their formats are platform-side.)                                                                                                                                                                                                                                     |
| `manage_inventory`     | stock-in (from a supplier; suppliers added on demand), adjust, view stock and transactions.                                                                                                                                                                                                                                                                                                             |
| `manage_finance`       | the money ledger — record / edit / void income (including order payments) and expenses (including `salary`), and **read** the supplier list an expense is attributed to. It also carries the **To'lov qabul qilish** action on an order page the holder can already open (i.e. alongside `view_orders` or `manage_orders`), so the counter takes money where the order is. See [`finance.md`](finance.md). |
| `view_finance_reports` | read-only access to the home finance summary tiles (income · expenses · net) and the worker-production report. The income / expense ledgers themselves require `manage_finance`. See [`finance.md`](finance.md).                                                                                                                                                                                          |

`process_delivery` is **gated out of v1** — v1 is pickup-only
([`scope.md`](../../scope.md)), so there is no driver workspace and the grant is not in the
catalog; it returns when delivery does.

**A shared lookup is readable by every permission that legitimately needs it.** The supplier
list is the one case in v1: the warehouseman picks a supplier for an arrival and the accountant
attributes an expense to one, so both `manage_inventory` and `manage_finance` read it while
creating and editing a supplier stays with `manage_inventory`. Gating a lookup behind a single
grant is what leaves the second reader with a field that is offered and cannot work.

The converse holds too: **a screen must not fetch a lookup its viewer cannot read.** The
assignable-worker list is `manage_orders` only, and the order screen also admits `view_orders`
and `process_production` — so it asks for that list only when the viewer could act on it.
Fetching it regardless buys those readers nothing but a refusal on a page they are entitled to.

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
- Read and edit workshop settings (profile).
- View workshop-wide reports.

Reading the settings row is owner-only, but the workshop's **name** is not a secret — every
workshop surface shows it as the tenant label. It therefore travels on the signed-in principal
itself, alongside the workshop id, so staff render the real name without asking for a row they
may not read.

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
  new grants take effect on the user's next request** — no session revoke. An open tab holding
  the old set corrects itself the first time the server refuses it: the refused read drops the
  rows it was refreshing, the app re-reads the principal and the branch context, and a page that
  is no longer allowed redirects home.
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

## Workshop app access matrix

The workshop SPA gates in two independent places; the server is the backstop behind both.

- **The sidebar** (`web/src/shared/app/workshopNav.ts`) is built from the grants the user holds
  **on the branch currently selected** in the branch picker.
- **The router guard** (route `meta.workshopAccess` in `web/src/apps/workshop/routes.ts`,
  evaluated by `canAccessWorkshopRoute`) tests the **whole grant set, branch-blind** — no
  workshop route declares `branchParam` today. A refused route redirects to `/workshop`, and the
  guard resolves before the target view mounts, so none of the refused page paints first.

The two predicates are deliberately different: a nav entry is an invitation, a route requirement
is a floor. Every place they diverge is listed below.

### What each permission unlocks in the sidebar

| Permission             | Sidebar entries (group)                                                   |
| ---------------------- | ------------------------------------------------------------------------- |
| `view_orders`          | none — it is an order-read grant, and the board it reads needs `manage_orders` |
| `manage_orders`        | Buyurtmalar (Boshqaruv)                                                   |
| `process_production`   | Kesish · Krom (Ishlab chiqarish)                                          |
| `manage_inventory`     | Ombor (Resurslar)                                                         |
| `manage_catalog`       | Material katalogi (Resurslar)                                             |
| `manage_finance`       | Tushum va xarajat · Qarzdorlik · Xodimlar mehnati (Moliya)                |
| `view_finance_reports` | Xodimlar mehnati (Moliya)                                                 |
| `is_owner`             | all of the above, plus Filiallar · Xodimlar · Sozlamalar (Tizim)          |

**Asosiy** (Boshqaruv) is shown to every signed-in workshop user, zero-grant staff included. It
is the app's home path and the redirect target for every refused route, so it cannot be gated
without first giving each principal its own landing page. Because it is ungated, the dashboard
carries the honest empty state instead: it names what the reader is missing whenever **no
section of the page renders** — not only when the grant set is empty. A holder of
`manage_catalog` alone has grants and still no dashboard card, and gets "nothing to show here,
your work is elsewhere" plus a link to the catalog, rather than a bare heading and a refresh
button.

Below 921px the sidebar becomes a **drawer** carrying the same item list — together with the
branch picker, the create action and the account button, which exist nowhere else on a phone — so
a permission-hidden entry stays hidden there too. There is no collapsed icon-rail state on the
desktop — the 264px column *is* the layout — so no tooltip can name a page the user cannot open.

### Links obey the target's requirement, not the card's

A card, panel row or back link is gated on the permission that **renders** it; the page it points
at has its own, usually stricter, requirement. The two must be checked separately or the link
bounces off the router guard straight back to `/workshop`. A KPI card whose target is out of reach
therefore renders as a plain card — no anchor, no hover lift, no pointer cursor — and a panel's
"more" link disappears rather than dangling. The rule lives in one place,
`web/src/shared/app/workshopDashboard.ts`, which answers both questions side by side:
`view_orders` renders the order KPI but cannot open `/workshop/orders`; `view_finance_reports`
renders the money figures but cannot open the ledgers.

A **Sizdan kutilmoqda** row splits the same rule across the row and its button. The **row**
appears whenever its condition holds and the reader can see the data behind it; the panel as a
whole is off only for a viewer holding neither an order grant nor `manage_inventory`, because
none of its rows would then have a source. The **button** is what follows the acting grant:
`manage_orders` gets the board or the order that carries the assign controls, a `view_orders`
reader gets the single order it can actually open, and where nothing is reachable the row states
the stall with no button at all — an instruction the reader cannot carry out is worse than a row
that only reports. On an order screen the back link points at the orders board for `manage_orders`
holders and at **Asosiy** for everyone else the page admits.

### What each route requires

| Route                                                                                                                                                        | Requirement                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `/workshop`                                                                                                                                                  | none                                                   |
| `/workshop/profile` · `/workshop/notifications`                                                                                                              | none — account surfaces stay open to zero-grant staff  |
| `/workshop/orders` · `/orders/new` · `/orders/new/cutting` · `/orders/cutting/:id` · `/orders/cutting/:id/result` · `/orders/new/:draft_id/checkout` · `/orders/drafts` · `/orders/edit/:draft_id/review` | `manage_orders`                                        |
| `/workshop/orders/:order_id`                                                                                                                                 | `view_orders` · `manage_orders` · `process_production` |
| `/workshop/cutting` · `/workshop/banding` · `/workshop/production/:order_id` (`/workshop/production` redirects into them)                                     | `process_production` · `manage_orders`                 |
| `/workshop/inventory`                                                                                                                                        | `manage_inventory`                                     |
| `/workshop/catalog`                                                                                                                                          | `manage_catalog`                                       |
| `/workshop/finance/income` · `/finance/expenses` · `/finance/debts`                                                                                          | `manage_finance`                                       |
| `/workshop/finance/production`                                                                                                                               | `manage_finance` · `view_finance_reports`              |
| `/workshop/settings` · `/settings/users` · `/settings/users/:user_id` · `/branches` · `/branches/:branch_id`                                                  | owner only                                             |

The station pages accept `manage_orders` as well as `process_production`, but the sidebar offers
them only on `process_production` — an order manager reaches Kesish / Krom by URL and finds the
"no work assigned to you" state, which is the intended read.

### What the global search returns

| Grant on the **selected** branch          | Search section    |
| ----------------------------------------- | ----------------- |
| `view_orders` or `manage_orders`          | Buyurtmalar       |
| `manage_catalog`                          | Material katalogi |
| `manage_inventory`                        | Ombor             |
| owner only                                | Xodimlar          |

Search reads the selected branch's grants, so it is branch-scoped where the router guard is not.
With none of them the panel says "Bu filial bo'yicha qidiruv uchun ruxsat yo'q" rather than
returning an empty result set.

### Verified — 2026-07-26

One probe user per permission, each holding exactly that grant on one branch, driven through
every workshop route in a browser against the seeded demo world. `pass` means the cell matched
the tables above; a `D` reference points at a known deviation below. The table carries the
state after **every** deviation D1–D7 was fixed on 2026-07-26, across two changes: the
permission rename plus the dashboard/link/staleness fixes, and the profile, supplier-lookup
and order-refusal fixes. Rows were re-driven in the browser on each change, and the combined
state was re-driven again after the two were integrated.

| Principal                                | Sidebar | Forbidden URL refused | Allowed pages clean | Global search | Empty / partial states |
| ---------------------------------------- | ------- | --------------------- | ------------------- | ------------- | ---------------------- |
| owner                                    | pass    | pass (nothing refused) | pass               | pass          | pass                   |
| `view_orders`                            | pass    | pass                  | pass                  | pass          | pass                     |
| `manage_orders`                          | pass    | pass                  | pass                  | pass          | pass                     |
| `process_production`                     | pass    | pass                  | pass                  | pass          | pass                     |
| `manage_catalog`                         | pass    | pass                  | pass                  | pass          | pass                   |
| `manage_inventory`                       | pass    | pass                  | pass                  | pass          | pass                   |
| `manage_finance`                         | pass    | pass                  | pass                 | pass          | pass                   |
| `view_finance_reports`                   | pass    | pass                  | pass                  | pass          | pass                   |
| no grants                                | pass    | pass                  | pass                  | pass          | pass                   |
| `manage_orders` + `manage_inventory`     | pass    | pass                  | pass                  | pass          | pass                     |
| `manage_inventory` on the second branch  | pass    | pass                  | pass                  | pass          | pass                   |

Every refused route landed on `/workshop` with no frame of the refused view rendered, and no
principal saw a nav entry, search section, or owner-only route it was not entitled to. Grants on
one branch unlocked nothing on the other: the branch picker offers only granted branches, and an
order in a branch the reader has no grant on answers 404. No screen offered a link to a page its
viewer could not open.

Revoking a grant while the holder is signed in fails closed on the server, and the open tab now
follows within one round-trip: the refused request clears the rows it was meant to refresh, the
app re-reads `me` and the branch context, the sidebar drops the entries the user no longer holds,
and a page that is no longer allowed redirects to `/workshop`. No reload needed.

### Known deviations

Each is a defect against the tables above, not a rule. Identifiers are stable, so a fixed one
leaves a gap rather than renumbering the rest.

**All seven deviations found by the 2026-07-26 permission walk were fixed the same day**, in two
changes that landed together:

| | Was | Closed by |
|---|---|---|
| **D1** | `/workshop` rendered blank for staff whose grants light up no dashboard section | the empty state now fires on "no visible section", not "no grants" |
| **D2** | `view_dashboard` was an order-read grant labelled "Asosiy panel" | renamed to `view_orders`, labelled `Buyurtmalarni ko'rish (faqat o'qish)` |
| **D3** | the finance ledger fetched a supplier list gated on `manage_inventory` | `manage_finance` admitted to the supplier read; writes stay `manage_inventory` |
| **D4** | every non-owner took a 403 on their own profile, and the workshop name fell back to the generic tenant label | the name rides on the `me` principal; the profile no longer reads owner-only settings |
| **D5** | screens linked to routes the viewer could not open | each link is gated on the **target route's** requirement, not the card's |
| **D6** | an order the reader is not entitled to reported a network failure | 404/403 is distinguished from transport failure, with copy naming the real outcome |
| **D7** | a revoked grant left a stale shell until reload | a 403 triggers a deduped `me` + branch-context re-read, and stores drop rows on refusal |

One defect was created by the *combination* of D2 and D4 and fixed at integration:
`WorkshopProfileView.vue` kept a **private copy** of the permission-label map, so the rename in D2
left its Ruxsatlar panel printing the raw `view_orders` code. The private copy is gone; the view
now reads `permissionLabels` from `workshopUi`. A duplicate that only breaks on rename is worse
than no duplicate — if another one appears, delete it rather than syncing it.

## Branch context (workshop app)

A staff user may hold grants on multiple branches. The workshop app uses a **branch picker** — a
two-line card at the top of the sidebar, under the wordmark: the workshop's name on the dominant
line, the selected branch beneath it, opening the list of branches. It defines the current branch
context, and every branch-scoped screen (orders, inventory, the Asosiy dashboard, material
catalog, workers) reads from it. Below 921px it travels into the drawer with the rest of the sidebar,
because a phone has nowhere else to put it.

Rules:

- The picker offers branches the user has any grant on — or **all branches**, if `is_owner`.
- On first login: auto-select if the user has exactly one accessible branch; otherwise
  prompt.
- The selection persists per session (local storage); a session revoke or re-login resets it.
- The picker UI never lets the user pick a branch they can't scope to. The server never
  trusts it anyway: create/list operations may submit a branch id, which the service validates
  against the grant set; operations on existing records derive the target branch from stored data.

### Which pages the context reaches

Not every screen is branch-scoped, and a picker that looks live while doing nothing is worse
than no picker. Every workshop route **declares** its scope; the shell renders the picker from
that declaration, so a new route has to state where it stands.

| Scope | What it means | Picker | Pages |
| --- | --- | --- | --- |
| `branch` | Reads the context and reloads when it changes | live | Asosiy · Buyurtmalar · Saqlangan chizmalar · Kesish · Krom · Ombor · Material katalogi · Tushum va xarajat · Qarzdorlik · Xodimlar mehnati · Yangi buyurtma |
| `workshop` | Workshop-wide by design | disabled, the reason stacked beneath the card | Filiallar · Xodimlar ro'yxati · Sozlamalar · Bildirishnomalar · Profil |
| `entity` | Takes its branch from the record on screen | disabled, the reason stacked beneath the card | Buyurtma tafsilotlari · Chizma (ish) · Kesim chizmasi + natija + rasmiylashtirish · Filial tafsilotlari · Xodim tafsilotlari |

**The whole finance module is `branch`.** `Qarzdorlik` included: every term in the debt fold —
invoice, supplier payment, order, adjustment — names a branch, so a branch's balance is a real
number and the branches sum to the workshop. Only the three **Tizim** pages are workshop-wide,
because a branch list, a staff list and the workshop's own settings have no branch to be scoped
to; `Bildirishnomalar` and `Profil` join them as personal surfaces reached from the chrome rather
than the nav — the bell in the header, the profile from the sidebar's account button. An `entity`
page must never let the picker override the branch stored on the record — a cutting draft in
particular is frozen to the branch it was started on, and the editor keeps its own in-page branch
control for that reason. It seeds that control from the current context when the draft has no
branch bound yet, so the user isn't asked twice for a choice they already made in the picker.

**Below two branches the card stays and stops being a control.** A workshop with one branch — or
none, before the first is created — renders the same two-line block as an inert outlined card:
same shape and position, no chevron, no listbox, nothing to open. Hiding it would change the
shape of the sidebar from one workshop to the next, and the outline is the signal the `workshop`
and `entity` scopes above already carry (minus their stacked reason) — the card is stating that
there is no choice to make here. The context auto-pins to the one branch and every page behaves
as if it is selected; with no branches at all the second line reads `Filial yo'q` rather than
going blank.

### The route guard is branch-blind, deliberately

Route requirements name permissions, never a branch: a grant on *any* branch satisfies a
workshop route. **The frontend route layer is not part of branch isolation, and shouldn't
be.** Every request re-derives the target branch server-side from the grant set and the stored
record, so a route guard that also checked branches would be a second, weaker copy of a rule
the server already enforces — and one that drifts. The guard's job is narrower: don't route a
user to a screen they can hold no permission for. Branch scope is the server's.

This leaves one asymmetry worth naming: global search *is* branch-scoped in the client — it
reads the selected branch's permission list to decide which result sections to request. That's
result shaping, not enforcement; the search endpoints re-derive scope like everything else.

Revisit if a branch-scoped route ever needs to render before its first API call resolves — a
guard would then be the only thing standing between the user and a flash of another branch's
shell. Nothing does today.

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
- **Login collides with any existing workshop login** — rejected with `login_exists` (409),
  whether the holder is in this workshop or another one. The create-user form surfaces it inline
  on the login field ("Bu login band. Boshqa login tanlang.") and prefills a workshop-derived
  prefix (a slug of the workshop name + `_`) to steer owners away from the obvious collisions.
  The prefix is a suggestion only — fully editable and clearable, with no enforced format.
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
  explains sign-in needs Telegram on that number (no SMS fallback in v1). The failed delivery
  still consumes a challenge: it counts toward every send budget and starts the 60 s cooldown,
  so reachability can't be probed for free.
- **Client mistypes the code** — `invalid_code` with attempts remaining; the 5th wrong attempt
  burns the challenge (`too_many_attempts`) and a code past its 5-minute TTL is `code_expired` —
  both send the client back to request a fresh code.
- **Code requested too often** — `code_send_rate_limited`; the resend control stays disabled
  with a countdown until the 60 s cooldown elapses.
- **Platform-wide send budget exhausted** — the same `code_send_rate_limited`, with a longer
  `retry_after_seconds`; sign-in is unavailable until the window rolls over. Deliberate
  trade-off: the global cap is the ceiling on the worst-case Telegram bill, so a distributed
  attack can exhaust it and deny OTP sign-in platform-wide — the caps are generous (~10×
  expected legit traffic), the trip is logged loudly, and raising a cap is an env edit away.

## Next

- [`workshop.md`](workshop.md) — branches, workshop settings, and audit.
- [`finance.md`](finance.md) — income, expenses, and the worker-production reports the
  accountant uses to pay the workers granted access here.
