---
title: Identity, access & tenancy
status: stable
owner: shape
updated: 2026-05-11
order: 70
related:
  - docs/spec/architecture.md
  - docs/spec/personas.md
  - docs/spec/scope-v1.md
  - docs/ref/entities/identity/workshop-user.md
  - docs/ref/entities/identity/permission-grant.md
  - docs/ref/entities/identity/client.md
  - docs/ref/entities/identity/session.md
---

# Identity, access & tenancy

The single home for **who proves who they are**, **what a workshop user may do**, and **what a
principal may see** — authentication, authorization, and multi-tenant isolation, with the design
decisions that shape them. The roles themselves are in [`docs/spec/personas.md`](personas.md); the
front-end split is in [`docs/ref/ux/information-architecture.md`](../ref/ux/information-architecture.md); the `identity` module owns all of this in code ([`docs/spec/architecture.md`](architecture.md)).

## Principals

Three principal types — three auth surfaces, one per front-end app. They don't overlap.

| Principal | Auth | Bound to | Capability | App |
|---|---|---|---|---|
| **Platform user** ("superadmin") | login + password; no permission model | no workshop | full platform scope | superadmin app |
| **Workshop user — owner** (`is_owner`) | login + password | one workshop | everything in the workshop on every branch, **plus owner-only powers** (see below) | seh app |
| **Workshop user — staff** | login + password | one workshop | exactly the `(permission, branch)` grants the owner gave them; zero grants ⇒ nothing actionable | seh app |
| **Client** | Telegram OAuth only; no password | no workshop (global) | own orders & cutting drafts; browse active branches of any workshop | client app |

Entity detail: [`docs/ref/entities/identity/platform-user.md`](../ref/entities/identity/platform-user.md), [`docs/ref/entities/identity/workshop-user.md`](../ref/entities/identity/workshop-user.md), [`docs/ref/entities/identity/client.md`](../ref/entities/identity/client.md).

## Authentication

### How each principal authenticates

- **Platform & workshop users** — login + password. Login is case-insensitive, unique per scope
  (platform-wide for platform users; per-workshop for workshop users). The owner is created by a
  platform operator during workshop provisioning; staff are created by the workshop owner; both with
  a temporary password and `force_password_change`. New users cannot use the app until they change
  it (every endpoint except change-password / logout / get-me returns `password_change_required`).
- **Clients** — **Telegram OAuth only**. No login, no password. A client self-registers on the first
  OAuth handshake; the stored profile (telegram id, username, phone, photo, name) is refreshed from
  Telegram on every login.

### Sessions — opaque, DB-backed

**Decision:** a session is an **opaque random token** (32 bytes, base64url), stored **hashed**
(SHA-256) in a `sessions` table — *not* a JWT. Each session has an access token (TTL **24 h**) and a
refresh token (TTL **7 d**); transport `Authorization: Bearer <access_token>`. Every request looks
the session up, loads the principal + its current scope/grants from the DB, and authorizes from
that. Max **5** concurrent sessions per principal (a 6th login evicts the oldest). Refresh re-issues
the access token only — **no refresh-token rotation in v1** — and re-checks the principal (and, for
workshop users, the workshop) is still active.

**Why opaque, not JWT:** the system needs **instant revocation** (blocking a principal or a workshop
must log them out *now*; "log out everywhere" and "log out others on password change" must take
effect now) and **fresh authorization** (a new permission grant, a reactivated branch must apply on
the *next* request, not after a token expires). JWT would need a denylist anyway (which is a DB
lookup per request — so you've paid the cost and kept the complexity), short TTLs (re-login churn),
and the temptation to encode role/scope in the token (then stale on a grant change); the "stateless"
win doesn't apply because we *want* the DB as source of truth and the request volume doesn't make
the lookup hurt. **Consequences:** instant revocation; grant changes apply next request; no
signing-key management; the `sessions` table doubles as a "where am I logged in" view. Costs: a DB
read per authenticated request (fine at this scale; cache it later if measured slow). **Revisit
when** authenticated request volume makes the per-request session lookup a measured bottleneck
(then: cache the lookup with a short TTL + an invalidation hook on revoke — not "switch to JWT").

**Revocation = `DELETE` the row(s):** on block (a principal, or a workshop → its owner's + staff's
sessions, cascade), on "log out everywhere", and on a password change (all *other* sessions; the
current one stays). A reset password (owner resets staff; platform operator resets owners) generates
a temp password + `force_password_change` and revokes the user's sessions. Expired session rows are
also pruned by a periodic job.

### Password hygiene & brute-force

- Passwords are hashed at rest with argon2 or bcrypt — never plaintext. Complexity: ≥ 8 chars with
  at least one upper, one lower, one digit.
- 5 consecutive wrong passwords for a login → a 15-minute lock (`locked_until`); a correct password
  resets the counter. The error is a generic "login or password is incorrect" — no account-existence
  oracle.
- A user cannot reset their own password — only a higher principal does (owner → staff; platform
  operator → owners).

### Telegram OAuth integrity

The widget payload (`telegram_id`, `first_name`, `last_name`, `username`, `photo_url`,
`phone_number`, `auth_date`, `hash`) is **HMAC-verified** against the bot token; a bad signature or
a stale `auth_date` → rejected. The **phone number is required** — if Telegram didn't share it the
client is asked to allow phone-sharing and retry (`missing_phone_number`). The phone is the client's
primary human identifier; the profile is refreshed from the payload on every login.

### Why the client is a separate entity

**Decision:** the client is its own entity (a `clients` table), **not** a "user with `role=client`".
Authentication is Telegram-OAuth-only; clients self-register; they are global to the platform — bound
to no workshop or branch, no permission model, picking a branch per order.

**Why:** workshop staff (internal, login-auth, tenant-bound, permission-governed) and customers
(external, self-registering, no tenant, no permissions) are genuinely different things; conflating
them into one `users` table forces a `role` check at every "staff or customer?" branch and pollutes
the staff identity model with Telegram-anchored fields and "no organization" special cases.
Alternatives rejected: *clients as `users` with `role=client`* (the old shape) — conflation, as
above; *a separate table but with an optional client password fallback* — adds a second auth path
(reset, brute-force, …) to maintain for a benefit (Telegram-down fallback) that doesn't justify it
yet. **Consequences:** the staff identity model stays clean; client-specific rules live in one
place; the client app talks to a clean client-auth surface. Cost: no fallback if Telegram OAuth is
unavailable. **Revisit when** Telegram OAuth availability proves unreliable enough that customers
can't log in, or a non-Telegram client signup is needed — then layer a second method on the same
`clients` entity. Entity: [`docs/ref/entities/identity/client.md`](../ref/entities/identity/client.md).

## Authorization — workshop permissions

### The model

Workshop staff capability is governed by **coarse-grained permissions, each grant scoped to a
branch** — `(workshop user, permission, branch)` rows. There is **no role taxonomy** for workshop
users; the only "roles" are the `is_owner` flag and the grant set.

- **Owner** (`is_owner`): holds **every permission on every branch** of the workshop implicitly,
  **plus the owner-only powers** — create workshop staff and grant/revoke their permissions; create
  & edit branches and change their status; set branch pricing; edit workshop settings (delivery
  zones, payment-channel flags & credentials); view payment credentials; branch-to-branch stock
  transfers; force-cancel an order already `in_production` or later; revert a completed refund; view
  workshop-wide reports / the audit log. Created/demoted only by a platform operator; exactly one
  owner per workshop. *None of the owner-only powers are delegable to staff in v1* —
  [`docs/spec/open-questions.md`](open-questions.md) Q1, Q12.
- **Staff**: the grants the owner gave them, drawn from the **branch-scoped permission catalog**:

  | Permission | Grants (on the granted branch) |
  |---|---|
  | `view_dashboard` | see the branch's dashboard / KPIs / order summary |
  | `manage_orders` | the full order workflow — status transitions, apply discount, approve pay-later, assign driver, record cash/bank payments, process refunds. *Except* force-cancelling an `in_production`+ order and reverting a completed refund — those are owner-only. |
  | `manage_catalog` | create / edit / activate / deactivate materials |
  | `manage_inventory` | stock-in, adjust, view stock & transactions. *Branch-to-branch transfers are owner-only.* |
  | `manage_workers` | create / edit / activate / deactivate workers |

  A staff user with zero grants can log in but sees nothing actionable (the seh app shows an "ask
  your workshop owner for access" message). Grants live on the user, not the branch: changing a
  branch's status doesn't touch grants or sessions; a grant on an `inactive` branch is inert and
  becomes live again on reactivation. Entity: [`docs/ref/entities/identity/permission-grant.md`](../ref/entities/identity/permission-grant.md).

### Why coarse-grained & per-branch

**Decision rationale:** workshops divide labour by branch and task ("this person handles orders for
branch A; that person also keeps branch A's catalog current; the owner does everything"). The old
fixed hierarchy (`super_admin ⊇ admin ⊇ operator`) couldn't express "order desk for branch A only"
and added per-role scope rules on top. Alternatives rejected: *keep the hierarchy* — doesn't fit how
workshops actually staff; *fine-grained permissions* (~50, one per use case) — over-engineered for
the envelope; a small business doesn't want a 50-checkbox editor, and a coarse bundle's blast radius
is acceptable here (it's not a bank); *named presets / role templates* (Owner / Branch Manager /
Operator / Viewer) — deferred; presets can layer on the same grant rows later as a UI convenience.
**Consequences:** real staffing is expressible; the seh app's nav & actions are a simple function of
`is_owner` + the grant set; no "X+" hierarchy semantics to reason about. Costs: `manage_orders` is a
lot of power in one grant; the carve-outs (force-cancel, refund-revert, transfers → owner-only) are
exceptions to remember; "give a staff member just one workshop-wide capability" isn't possible in
v1. **Revisit when** a workshop with many staff per branch reports the coarseness is a problem, or
owners report being a bottleneck for the owner-only actions, or fine-grained audit forces splitting
power inside `manage_orders`.

### How a request is authorized

1. The auth middleware turns the bearer token into a **principal context**: type, workshop id (for
   workshop users), `is_owner`, the user's grant set.
2. The endpoint determines the **target's branch** from stored data (the order / material / stock
   row / branch id) — never from a client-supplied branch id.
3. Allow if `is_owner`, or the grant set contains `(required_permission, target_branch)`; for
   owner-only endpoints, allow only if `is_owner`; else `forbidden`.

Use-case specs name the required permission(s) directly ("requires `manage_orders` on the order's
branch, or owner"); the seh app hides screens & actions the current user can't perform.

## Multi-tenancy & data isolation

The tenant is the **workshop**. One database, one app, many workshops — isolation is enforced in
software, on every read and every write.

- **Tenant hierarchy:** `workshop` (1) ─owns─▶ `branch` (N) ─owns─▶ `material` / `stock item` /
  `worker` / `branch pricing` (N). Exactly one owner per workshop; a workshop user belongs to one
  workshop. **Clients are global** — bound to no workshop or branch; an order, once placed,
  references a workshop + branch (snapshotted) and is owned by the client who placed it. Entities:
  [`docs/ref/entities/workshop/workshop.md`](../ref/entities/workshop/workshop.md), [`docs/ref/entities/workshop/branch.md`](../ref/entities/workshop/branch.md).
- **Scope by principal** (derived from the authenticated principal, never from client input):

  | Principal | Read/write scope |
  |---|---|
  | Platform operator | all workshops, all branches |
  | Workshop owner | own workshop; all its branches |
  | Workshop staff | own workshop; only branches they hold a relevant grant on |
  | Client | own orders / cutting drafts; browse active (+ temporarily-closed) branches of any workshop |

  A query that would cross these lines returns `forbidden` (or simply excludes the rows, for list
  endpoints). Cross-module references stay within a tenant — an `assign-driver` rejects a worker
  from another branch; a grant rejects a branch from another workshop.
- **Workshop blocking is a cascade.** A platform operator blocks a workshop (`status = blocked`):
  the owner's + staff's sessions are revoked immediately; their next login is rejected
  (`workshop_blocked`); **clients are unaffected**; open orders **freeze** — the system performs no
  automatic transitions, and staff can't act because they can't log in. Unblocking restores
  `status = active` but **not** sessions — users log in again. (Payment webhooks would still be
  accepted in v1.1; in v1 there are none.)
- **Branch status governs visibility, not access destruction.** `active` — visible to clients,
  accepts new orders & cutting; `temporarily_closed` — visible (shown as closed, optional reason),
  no new orders; `inactive` — invisible to clients, no new orders, existing orders complete. A
  branch is never deleted; changing its status doesn't touch staff sessions or grants.
- **Soft delete keeps history.** Workshops, branches, materials, workers, workshop/platform users go
  to an `inactive`/`blocked` status, never `DELETE`; orders, audit, status events are kept forever.
  (The why for soft delete, snapshots, append-only, etc. is in [`docs/spec/architecture.md`](architecture.md) → *Data model invariants*.)

## See also

- [`docs/spec/architecture.md`](architecture.md) — the modular-monolith / single-DB shape this lives in; the data-model invariants.
- [`docs/spec/personas.md`](personas.md) — the four roles in prose.
- [`docs/spec/scope-v1.md`](scope-v1.md) — what's in/out of v1 for identity & access.
- [`docs/ref/features/workshop-provisioning.md`](../ref/features/workshop-provisioning.md), [`docs/ref/features/workshop-user-management.md`](../ref/features/workshop-user-management.md), [`docs/ref/features/client-onboarding.md`](../ref/features/client-onboarding.md), [`docs/ref/features/branch-management.md`](../ref/features/branch-management.md).
- [`docs/ref/entities/identity/`](../ref/entities/identity/), [`docs/ref/entities/workshop/`](../ref/entities/workshop/).
