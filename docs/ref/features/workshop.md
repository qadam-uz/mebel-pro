---
title: Workshop administration
status: draft
owner: shape
updated: 2026-05-14
order: 40
---

# Workshop administration

The owner-and-staff surfaces for keeping a workshop running — workshop settings, branch CRUD,
worker registry, and the audit viewer. Identity & access (sign-in, sessions, provisioning,
staff management with the permission grants matrix) is in [`access-management.md`](access-management.md).

## Workshop administration (superadmin + workshop apps)

### Endpoints

| Endpoint                                | Caller                                            | What                                                                                                                                                                                                                                                                                                                                |
| --------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `update-workshop`                       | platform operator; or the owner for their own | edit name, logo, phone, address                                                                                                                                                                                                                                                                                                     |
| `update-workshop-settings`              | platform operator or owner                        | `delivery_enabled`, `delivery_zones` (list of name + label/polygon + fee in tiyin), `default_advance_percent` (0–100), `currency` (UZS, fixed), `payment_channels` (per-channel enabled flag + merchant credentials — **stored, inert in v1**; credentials owner-visible only) |
| `list-workshops` / `get-workshop`       | platform operator (all); owner (own)              | cross-workshop list (superadmin) / per-workshop detail                                                                                                                                                                                                                                                                              |

Creation, blocking, and unblocking of a workshop live in [`access-management.md`](access-management.md) — they
cascade into the identity domain (owner creation, session revocation).

### UX (superadmin app)

- **Workshops list** (`/admin/workshops`) — table: name, owner (name + phone), status badge
  (`active` / `blocked`), created, branches count, orders-30d count; search by name; status
  filter; "+ Workshop" (creation flow in [`access-management.md`](access-management.md)). Empty: "No workshops
  yet."
- **Workshop detail** — header (name, status badge, owner, created); tabs: **Profile** (edit),
  **Settings** (delivery + advance % + payment channels grid — credentials masked, reveal on
  click), **Branches** (read-only list), **Block** (block/unblock with a mandatory reason;
  warning that staff sessions are revoked and open orders freeze — destructive-styled).

### UX (workshop app)

- **Workshop settings** (`/workshop/settings`, owner-only): tabs Profile, Delivery zones,
  Advance %, Payment channels (credentials owner-visible, masked by default).

## Branches (workshop app)

### Endpoints

| Endpoint                            | Caller                                                                                | What                                                                                                                                                                                                                                                                                                                                                       |
| ----------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `create-branch` / `update-branch`   | owner only                                                                            | name, address (text), phone, latitude, longitude (manual numeric — no geocoder in v1), `working_hours` (per-weekday open/close), `status` (default `active`). Creates an empty `branch_pricing` row and the branch's stock as materials are added.                                                                                                          |
| `change-branch-status`              | owner                                                                                 | `active ↔ temporarily_closed ↔ inactive`; `temporarily_closed` takes an optional `closed_reason`; setting `inactive` while the branch has active orders is allowed (those finish) but the UI warns. Never deleted. Status changes do **not** revoke staff sessions or grants.                                                                              |
| `list-branches` / `get-branch`      | owner; staff see only granted branches; clients see active + temporarily-closed of any workshop |                                                                                                                                                                                                                                                                                                                                                            |

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
  here; managed via Workshop Users in [`access-management.md`](access-management.md)), **Orders**. The first four
  tabs are [`catalog-inventory.md`](catalog-inventory.md) / Workers below / Pricing in
  catalog-inventory; the last is [`orders.md`](orders.md).
- States: a "this branch is temporarily closed" banner with the reason; an "inactive" banner.

## Workers (workshop app)

### Endpoints

| Endpoint                                                          | Caller                                  | What                                                                                                                                                                                                  |
| ----------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `create-worker` / `update-worker` / `toggle-worker-status`        | owner or `manage_workers` on the branch | `branch_id` (in scope), `full_name`, `phone` (`+998…`), `position` (`cutter` / `driver` / `assembler` / `other`), `status`. Workers are **not system users**. `inactive` workers can't be assigned to new orders. No delete. |
| `list-branch-workers` / `get-worker`                              | same                                    |                                                                                                                                                                                                       |

Only a worker of an order's branch can be assigned as the order's cutter (on `→ in_production`)
or driver (on `→ in_delivery`).

### UX

Under a branch's **Workers** tab (and an owner-wide view with a branch filter):

- **Workers list** — table: `full_name`, phone, position, branch (workshop-wide view), status,
  action menu. "+ Worker". Empty: "No workers in this branch yet."
- **Worker form dialog** — branch (defaults to current), full_name, phone, position select,
  status.
- Row actions: Edit, Activate/Deactivate (confirm; deactivate warns about in-progress
  assignments). No Delete.
- **Worker picker** (in the order workflow) — a select limited to the order's branch's `active`
  workers of the relevant position (cutters when starting production, drivers when starting
  delivery).

## Audit (workshop + superadmin apps)

### Endpoints

| Endpoint                  | Caller                                                                          | What                                                                                                                                                                                          |
| ------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `list-action-log`         | workshop owner (scoped to their workshop & granted branches); platform operator (all) | paginated, newest first; filters: action code (or family), actor, entity (type + id), date range, branch, workshop (platform operator only)                                                    |
| `list-status-change-log`  | same                                                                            | filters: entity type + id, from/to status, actor, date range, branch, workshop                                                                                                                |

The log is **append-only** — never edited or deleted; this feature only reads it. Pagination is
cursor-friendly for a growing log.

### UX

- In the **workshop app** (owner / `view_reports`): **Audit** section with two tabs — **Action
  log** (filters: action type/family, module, actor search, entity type+id, date range, branch;
  rows with a JSON-collapsible `details` preview) and **Status changes** (filters: entity
  type+id, from→to, actor, date range; rows showing the transition). Each row links to the
  affected entity where one exists. Read-only.
- In the **superadmin app**: the same, plus a workshop filter and no workshop scoping (sees
  all).
- States: loading (skeleton rows), empty (no matching entries), error (`trace_id`); the
  `details` expander.

## Edge cases

- **Set a branch `inactive` with open orders** — allowed; the warning lists how many; those
  orders complete normally.
- **`temporarily_closed` branch in a client's branch picker** — shown with the reason and a
  disabled "start cutting" CTA.
- **Deactivate a worker assigned to in-progress orders** — allowed, with a warning listing those
  orders; staff should reassign them.
- **Assign a worker from another branch** — rejected.
- **Sensitive fields in audit `details`** — masked at write time; never shown.

## Next

[`catalog-inventory.md`](catalog-inventory.md) — what a branch carries from the platform
catalog, its prices, and its stock.
