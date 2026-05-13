---
title: Workshop administration
status: draft
owner: shape
updated: 2026-05-13
order: 40
---

# Workshop administration

The owner-and-staff surfaces for keeping a workshop running — provisioning by the platform team,
branch CRUD, worker registry, workshop-user management with the per-branch grants matrix, and the
audit viewer. Auth/authz rules are in [`access.md`](../../access.md).

## Workshop provisioning (superadmin app)

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `create-workshop` | platform operator | creates a `workshop` **and** its first `workshop_user` (`is_owner = true`, `force_password_change = true`, temp password) **atomically** — never one without the other. Input: workshop name, phone, address?, and the owner's full_name, login, phone, temp password (auto-generated, with manual override). Returns the summary + the temp password **once**. |
| `update-workshop` | platform operator; or the owner for their own workshop | edit name, logo, phone, address |
| `update-workshop-settings` | platform operator or owner | delivery_enabled, delivery_zones (list of name + label/polygon + fee in tiyin), default_advance_percent (0–100), currency (UZS, fixed), payment_channels (per-channel enabled flag + merchant credentials — **stored, inert in v1**; credentials owner-visible only) |
| `block-workshop` / `unblock-workshop` | platform operator only | set `status`; blocking revokes the owner's + staff's sessions immediately; unblocking does not restore sessions; clients are unaffected; open orders freeze |
| `list-workshops` / `get-workshop` | platform operator | cross-workshop list + per-workshop detail |

The created owner cannot be created, demoted, or deleted by anyone except a platform operator;
exactly one owner per workshop.

### UX (superadmin app)

- **Workshops list** (`/admin/workshops`) — table: name, owner (name + phone), status badge
  (`active` / `blocked`), created, branches count, orders-30d count; search by name; status
  filter; "+ Workshop". Empty: "No workshops yet."
- **Create-workshop dialog** — workshop fields + owner fields, temp password (auto-generated,
  copy button, manual toggle). On success: read-only confirmation showing the owner login + temp
  password with "share this with the owner — shown once" + copy button.
- **Workshop detail** — header (name, status badge, owner, created); tabs: **Profile** (edit),
  **Settings** (delivery + advance % + payment channels grid — credentials masked, reveal on
  click), **Branches** (read-only list), **Block** (block/unblock with a mandatory reason;
  warning that staff sessions are revoked and open orders freeze). Block is destructive-styled.

## Branches (workshop app)

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `create-branch` / `update-branch` | owner only | name, address (text), phone, latitude, longitude (manual numeric — no geocoder in v1), working_hours (per-weekday open/close), status (default `active`). Creates an empty `branch_pricing` row and the branch's stock as materials are added. |
| `change-branch-status` | owner | `active ↔ temporarily_closed ↔ inactive`; `temporarily_closed` takes an optional `closed_reason`; setting `inactive` while the branch has active orders is allowed (those finish) but the UI warns. Never deleted. Status changes do **not** revoke staff sessions or grants. |
| `list-branches` / `get-branch` | owner; staff see only granted branches; clients see active + temporarily-closed of any workshop | |

Branch status governs client visibility/ordering: `active` — visible, accepts orders;
`temporarily_closed` — visible, no new orders; `inactive` — invisible, no new orders.

### UX

- **Branches list** (`/workshop/branches`) — table: name, address, phone, status badge, materials
  count, workers count, low-stock count, active-orders count, action menu. "+ Branch" (owner).
  Empty: "No branches yet — add one to start taking orders."
- **Branch form dialog** — name, address, phone, lat/lng (numeric, range-validated),
  working-hours grid (per weekday open/close, with "closed this day"), status.
- **Branch detail** (`/workshop/branches/:id`) — header (name, address, status badge, action set:
  change status / edit / retire); tabs: Overview (status, active-orders count, revenue 30d,
  low-stock count), **Materials**, **Stock**, **Workers**, **Pricing**, **Staff** (read-only
  here; managed via Workshop Users), **Orders**. The first four tabs are
  [`catalog-inventory.md`](catalog-inventory.md) / Workers below / Pricing in
  catalog-inventory; the last is [`orders.md`](orders.md).
- States: a "this branch is temporarily closed" banner with the reason; an "inactive" banner.

## Workers (workshop app)

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `create-worker` / `update-worker` / `toggle-worker-status` | owner or `manage_workers` on the branch | branch_id (in scope), full_name, phone (`+998…`), position (`cutter` / `driver` / `assembler` / `other`), status. Workers are **not system users**. `inactive` workers can't be assigned to new orders. No delete. |
| `list-branch-workers` / `get-worker` | same | |

Only a worker of an order's branch can be assigned as the order's cutter (on `→ in_production`)
or driver (on `→ in_delivery`).

### UX

Under a branch's **Workers** tab (and an owner-wide view with a branch filter):

- **Workers list** — table: full_name, phone, position, branch (workshop-wide view), status,
  action menu. "+ Worker". Empty: "No workers in this branch yet."
- **Worker form dialog** — branch (defaults to current), full_name, phone, position select,
  status.
- Row actions: Edit, Activate/Deactivate (confirm; deactivate warns about in-progress
  assignments). No Delete.
- **Worker picker** (in the order workflow) — a select limited to the order's branch's `active`
  workers of the relevant position (cutters when starting production, drivers when starting
  delivery).

## Workshop users — staff management (workshop app)

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `create-workshop-user` | owner only | creates a non-owner `workshop_user` in the owner's workshop, `force_password_change = true`, temp password (auto/manual), **and optionally an initial set of `(permission, branch)` grants** — created in the same atomic operation. Returns the user + temp password **once**. |
| `update-workshop-user` | owner | edit full_name, phone |
| `set-user-grants` | owner | replaces the user's `permission_grant` rows atomically; each `(permission, branch)` validated against the v1 catalog and the workshop's branches. Takes effect on the user's next request; no session revoke. |
| `reset-workshop-user-password` | owner | temp password + `force_password_change`; revokes the user's sessions |
| `block-workshop-user` / `unblock-workshop-user` | owner | blocking revokes sessions immediately; unblocking does not restore them |
| `change-my-password` | any workshop user | new password meeting complexity; revokes all *other* sessions; clears `force_password_change` |
| `list-my-sessions` / `revoke-my-session` / `revoke-my-sessions` | any workshop user | see and end own sessions |

The owner cannot create another owner, demote themselves, or delete a user; exactly one owner
per workshop holds.

### UX

Under Settings → Users (owner-only nav item):

- **Users list** (`/workshop/settings/users`) — table: name, login, phone, status, granted-branches
  count, last login, action menu. "+ User". Empty: "No staff yet — add one to delegate work."
- **Create-user dialog** — fields + temp password (auto/manual, copy) + an initial grants matrix
  (permission rows × branch columns, within the workshop). On success: read-only "share login +
  temp password — shown once" confirmation with copy.
- **User detail** (`/workshop/settings/users/:id`) — header (name, status badge, last login); tabs:
  Profile (edit), Permissions (the grants matrix — toggling saves atomically with an explicit
  Save + unsaved-changes guard), Sessions (list with current marker, revoke one/all), Audit
  (this user's actions, read-only).
- Row/detail actions: Edit, Reset password (→ one-time-secret confirmation), Block / Unblock
  (block warns sessions are revoked), Revoke sessions.
- **Self** screen (every workshop user, `/workshop/profile`): Profile, Change password (strength
  meter — ≥ 8, upper + lower + digit), Sessions list with current marker + "log out
  everywhere".
- A staff user with zero grants sees "you have no permissions — ask your workshop owner."

## Audit (workshop + superadmin apps)

### Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `list-action-log` | workshop owner (scoped to their workshop & granted branches); platform operator (all) | paginated, newest first; filters: action code (or family), actor, entity (type + id), date range, branch, workshop (platform operator only) |
| `list-status-change-log` | same | filters: entity type + id, from/to status, actor, date range, branch, workshop |

The log is **append-only** — never edited or deleted; this feature only reads it. Pagination is
cursor-friendly for a growing log.

### UX

- In the **workshop app** (owner / `view_reports`): **Audit** section with two tabs — **Action log**
  (filters: action type/family, module, actor search, entity type+id, date range, branch; rows
  with a JSON-collapsible `details` preview) and **Status changes** (filters: entity type+id,
  from→to, actor, date range; rows showing the transition). Each row links to the affected
  entity where one exists. Read-only.
- In the **superadmin app**: the same, plus a workshop filter and no workshop scoping (sees
  all).
- States: loading (skeleton rows), empty (no matching entries), error (`trace_id`); the
  `details` expander.

## Edge cases (whole feature)

- **Create-workshop fails after the workshop row but before the owner row** → the whole
  operation rolls back (atomic).
- **Owner login collides** with an existing owner login in another workshop → fine (logins are
  unique per workshop, not globally).
- **Block a workshop while staff are mid-action** → their next request 401s; platform operator
  can still read the workshop's data for incident response.
- **Set a branch `inactive` with open orders** — allowed; the warning lists how many; those
  orders complete normally.
- **A staff member's only granted branch goes `inactive`** — they effectively have no
  actionable screens until it's reactivated or they're granted another branch.
- **`temporarily_closed` branch in a client's branch picker** — shown with the reason and a
  disabled "start cutting" CTA.
- **Deactivate a worker assigned to in-progress orders** — allowed, with a warning listing those
  orders; staff should reassign them.
- **Assign a worker from another branch** — rejected.
- **Staff user with zero grants** → can log in; every workshop screen is empty/hidden.
- **Grant on a branch that later goes `inactive`** → inert; the branch disappears from the
  user's branch switcher; reactivating makes the grant live again.
- **Owner blocks themselves** — disallowed (a workshop must have an active owner).
- **Login collision within the workshop** → rejected (`login` unique per workshop).
- **Sensitive fields in audit `details`** — masked at write time; never shown.
