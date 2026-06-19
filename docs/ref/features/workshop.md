---
title: Workshop administration
status: draft
owner: shape
updated: 2026-06-20
order: 40
---

# Workshop administration

The owner-and-staff surfaces for keeping a workshop running — workshop settings and branch
CRUD. The **audit viewer** over a workshop's action and status logs is specified here too,
but in v1 it is a **superadmin-app surface only** — workshop owners get no in-app audit screen
yet (see [`scope.md`](../../scope.md)). Sign-in, sessions,
provisioning, and staff management live in [`access-management.md`](access-management.md);
income, expenses, and the worker-production reports live in [`finance.md`](finance.md).

## Workshop settings

The workshop's mutable profile:

- **Profile** — name, logo, phone, address. Editable by the workshop's owner. Platform
  operators can view the profile for incident response, but v1 gives them no edit path.
- **Currency** — UZS, fixed in v1; named here for future-proofing.

Delivery zones, advance %, and payment channels are **not in v1** — v1 is pickup-only and an
order moves no money ([`scope.md`](../../scope.md)); they return with delivery and a gateway.

Owner-only power covered by `is_owner` (see the access-management permission catalog):
editing settings.

### UX (superadmin app)

- **Workshops list** (`/admin/workshops`) — table: name, owner login, branch count, phone,
  created, status badge. Status filter; name search;
  **+ Workshop** (provisioning is in access-management). Empty: "No workshops yet." (The
  owner is identified by login here — the stable operational handle; the detail view carries
  the full owner contact.)
- **Workshop detail** — header (name, status, owner, created); tabs: **Profile** (read-only),
  **Branches** (read-only list), **Block** (block / unblock with a mandatory reason;
  destructive-styled; warns that staff sessions are revoked and open orders freeze). When the
  workshop is blocked, the detail shows the **reason captured at block time** in the danger
  banner.

### UX (workshop app)

- **Workshop settings** (`/workshop/settings`, owner-only): a single **Profile** tab (name,
  logo, phone, address).

## Branches

A workshop owns one or more branches. Each branch has a physical address, working hours, a
manually-entered `(lat, lng)`, and a `status` — semantics in
[`access-patterns.md`](../../access-patterns.md#tenancy).

After platform provisioning creates the first branch, branch operations are **owner only**:

- **Create / edit a branch** — name, address, phone, lat / lng, per-weekday working hours.
  Creating a branch also creates an empty `branch_pricing` row; stock items appear as the
  branch's material selection is built up.
- **Change status** — `active` ↔ `temporarily_closed` ↔ `inactive`. `temporarily_closed` may
  carry an optional reason. **Status changes do not revoke staff sessions or grants** — a
  staff grant on an `inactive` branch just stays inert until the branch is reactivated. A
  branch is never deleted.

Setting a branch to `inactive` while it has open orders is allowed (those orders finish
normally); the UI warns and lists how many.

Visibility for read operations:
- Owner sees every branch of their workshop.
- Staff see only branches they hold a grant on.
- Clients see `active` and `temporarily_closed` branches of any workshop (per the picker).

### UX

- **Branches list** (`/workshop/branches`) — table: name, address, phone, status badge,
  materials count, workers count, low-stock count, active-orders count, action menu.
  **+ Branch** (owner). Empty: "No branches yet — add one to start taking orders."
- **Branch form dialog** — name, address, phone, lat / lng (numeric, range-validated),
  working-hours grid (per weekday open / close, with a "closed this day" toggle), status.
- **Branch detail** (`/workshop/branches/:id`) — header (name, address, status, action set:
  change status · edit). Tabs: **Overview** (status, active-orders count, revenue 30d,
  low-stock count) · **Materials** · **Stock** · **Settings** · **Staff** (read-only here;
  shows everyone with this branch as their `home_branch` plus everyone with a grant on it;
  managed in [`access-management.md`](access-management.md)) · **Orders**. The Materials,
  Stock, and Settings tabs are owned by [`catalog-inventory.md`](catalog-inventory.md);
  Orders by [`orders.md`](orders.md).
- A `temporarily_closed` branch shows a banner with the reason; an `inactive` branch shows an
  inactive banner.

## Audit viewer

Two append-only logs back this feature: the **action log** (every mutating use case writes a
row — actor, action, entity, branch, masked details) and the **status change log** (every
order status transition). Both are write-only at source; this feature only reads them.

In v1 the viewer lives **only in the superadmin app** — platform operators see everything
across workshops, with a workshop filter. The workshop owner has **no in-app audit viewer**
yet (the logs are still recorded against their workshop).

### UX

- In the superadmin app: an **Audit** section with two tabs — **Action log** (filters: action
  type / family, module, actor search, entity type + id, date range, branch, **workshop**;
  rows with a JSON-collapsible `details` preview) and **Status changes** (filters: entity type
  + id, from→to, actor, date range; rows showing the transition). Each row links to the
  affected entity where one exists. Read-only; no workshop scoping.
- States: loading (skeleton rows), empty, error (with `trace_id`); the `details` expander
  reveals masked JSON.
- Export & paging: the loaded page exports to CSV; the list loads the latest N rows with a
  "load more" control to page further back, since the append-only history is otherwise only
  reachable as its newest slice.

## Edge cases

- **Set a branch `inactive` with open orders** — allowed; the warning lists how many; those
  orders complete normally.
- **`temporarily_closed` branch in a client's branch picker** — shown with the reason and a
  disabled "start cutting" CTA.
- **Sensitive fields in audit `details`** — masked at write time; never shown.

## Next

[`catalog-inventory.md`](catalog-inventory.md) — what a branch carries from the platform
catalog, its prices, and its stock.
