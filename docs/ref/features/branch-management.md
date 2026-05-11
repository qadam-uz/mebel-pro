---
title: Branch management
status: stable
owner: shape
updated: 2026-05-11
order: 14
related:
  - docs/spec/access.md
  - docs/ref/entities/workshop/branch.md
  - docs/ref/features/material-catalog.md
  - docs/ref/features/inventory-management.md
  - docs/ref/features/worker-management.md
  - docs/ref/features/branch-pricing.md
---

# Branch management

## Problem

A workshop has one or more physical locations, each with its own catalog, stock, workers, and
pricing. The owner needs to create and edit branches and control whether a branch is open to
customers — fully open, temporarily closed (holiday, repairs), or retired — without ever destroying
the branch and its order history.

## User stories

- As a **workshop owner**, I want to create a branch with its address, location, phone, and working
  hours so customers can find and order from it.
- As a **workshop owner**, I want to mark a branch temporarily closed (with a reason) so customers
  see it's not taking orders right now.
- As a **workshop owner**, I want to retire a branch (`inactive`) when it shuts down, while keeping
  its order history.
- As a **workshop owner**, I want one place per branch to reach its catalog, stock, workers, pricing,
  assigned staff, and orders.

## Requirements

1. `create-branch` (owner only): name, address (text), phone, latitude, longitude (manual numeric —
   no geocoder in v1), working_hours (per-weekday open/close), status (default `active`). The branch
   belongs to the owner's workshop. Creates the branch's one `branch_pricing` row (empty/unset, to
   be filled in [`docs/ref/features/branch-pricing.md`](branch-pricing.md)) and its (empty) stock as materials are added.
2. `update-branch` (owner): edit the above.
3. `change-branch-status` (owner): `active ↔ temporarily_closed ↔ inactive`; `temporarily_closed`
   takes an optional `closed_reason`; setting `inactive` while the branch has active orders is
   allowed (those finish) but the UI warns. A branch is never deleted. Changing status does **not**
   revoke staff sessions or grants ([`docs/spec/access.md`](../../spec/access.md)).
4. `list-branches` / `get-branch` (owner; staff see only branches they hold a grant on; clients see
   active + temporarily-closed branches of *any* workshop): list with status, a few counts
   (materials, workers, low-stock, active orders), search by name, status filter.
5. Branch status governs client visibility/ordering: `active` — visible, accepts orders;
   `temporarily_closed` — visible, no new orders; `inactive` — invisible, no new orders.
6. Every action writes an audit-log row; status changes also write a status-change-log row and a
   notification to the branch's staff.

## UX

In the **seh app** → Branches (owner-only for create/edit/status; staff with a grant see their
branch's detail tabs they can act on):

- **Branches list** — table: name, address, phone, status badge (`active` / `temporarily_closed` /
  `inactive`), materials count, workers count, low-stock count, active-orders count, action menu.
  "+ Branch" (owner). Empty: "No branches yet — add one to start taking orders."
- **Branch form dialog** — name, address, phone, lat/lng (numeric, range-validated), working-hours
  grid (per weekday open/close, with a "closed this day" toggle), status.
- **Branch detail** — header (name, address, status badge, action set: change status / edit /
  retire); tabs:
  - **Overview** — status, active-orders count, revenue (30d), low-stock count.
  - **Materials** — the per-branch catalog ([`docs/ref/features/material-catalog.md`](material-catalog.md)).
  - **Stock** — stock + transactions + transfer ([`docs/ref/features/inventory-management.md`](inventory-management.md)).
  - **Workers** — the per-branch worker list ([`docs/ref/features/worker-management.md`](worker-management.md)).
  - **Pricing** — cutting model + edge-banding rates ([`docs/ref/features/branch-pricing.md`](branch-pricing.md)).
  - **Staff** — workshop users with a grant on this branch (read-only here; managed in [`docs/ref/features/workshop-user-management.md`](workshop-user-management.md)).
  - **Orders** — orders for this branch ([`docs/ref/features/order-fulfillment.md`](order-fulfillment.md)).
- States: loading, empty (no branches), error (`trace_id`), a "this branch is temporarily closed"
  banner with the reason, an "inactive" banner.
- Accessibility: the working-hours grid is keyboard-operable with clear labels; retire/inactivate is
  danger-styled and warns about active orders; tab strip is ARIA-tabs.

Shared patterns (tables, tab strip, working-hours grid, status badges, confirm-with-warning):
[`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/workshop/branch.md`](../entities/workshop/branch.md) — created, edited, status-changed.
- [`docs/ref/entities/workshop/workshop.md`](../entities/workshop/workshop.md) — the owning tenant.
- [`docs/ref/entities/catalog/branch-pricing.md`](../entities/catalog/branch-pricing.md) — its (empty) row is created with the branch.
- [`docs/ref/entities/identity/permission-grant.md`](../entities/identity/permission-grant.md) — the Staff tab reads these.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md), [`docs/ref/entities/support/notification.md`](../entities/support/notification.md).

## Edge cases

- **Set `inactive` with open orders** — allowed; the warning lists how many; those orders complete
  normally; no new orders accepted.
- **A staff member's only granted branch goes `inactive`** — they effectively have no actionable
  screens until it's reactivated or they're granted another branch.
- **`temporarily_closed` branch in a client's branch picker** — shown with the reason and a disabled
  "start cutting" CTA.
- **Lat/lng outside Uzbekistan ranges** — flagged in the form (it's manual entry; no map check).
- **Two owners editing the same branch** — last write wins; both audited.

## Out of scope

- Geocoding / a map widget for the address — v1 is manual lat/lng ([`docs/spec/open-questions.md`](../../spec/open-questions.md) Q6).
- Auto open/close by working hours — future.
- Moving an order between branches — future.
- Branch-level overrides of workshop settings — future.

## Open questions

- Delegating `manage_branches` to staff — owner: shape — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q1.
