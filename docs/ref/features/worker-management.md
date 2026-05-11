---
title: Worker management
status: stable
owner: shape
updated: 2026-05-11
order: 20
related:
  - docs/ref/entities/workshop/worker.md
  - docs/ref/entities/sales/order.md
  - docs/ref/features/order-fulfillment.md
---

# Worker management

## Problem

A branch has physical employees — saw operators, drivers, assemblers — who aren't system users but
who need to be on file so an order can be assigned to one when it goes into production (a cutter) or
out for delivery (a driver). Without a worker list, "who cut this / who's delivering it" isn't
recorded and can't be put on the order.

## User stories

- As a **workshop owner / staff with `manage_workers`**, I want to add a worker with their name,
  phone, and position so they can be assigned to orders.
- As the same, I want to edit a worker or deactivate one who's left, while keeping past assignments.
- As **staff handling orders**, I want to pick a worker (of this branch) when moving an order to
  production or to delivery.

## Requirements

1. `create-worker` (owner or `manage_workers` on the branch): branch_id (in scope), full_name, phone,
   position (`cutter` / `driver` / `assembler` / `other`), status (default `active`). Workers are
   **not system users** — no login, no auth.
2. `update-worker` (same): edit the above.
3. `toggle-worker-status` (same): `active ↔ inactive`. `inactive` workers can't be assigned to new
   orders; their in-progress orders should be reassigned. No delete.
4. `list-branch-workers` / `get-worker` (owner or `manage_workers` on the branch): list with filters
   (position, status).
5. Order assignment (in [`docs/ref/features/order-fulfillment.md`](order-fulfillment.md)): only a
   worker of the order's branch can be assigned as the order's cutter (on `→ in_production`) or
   driver (on `→ in_delivery`).
6. Every mutating action writes an audit-log row; status changes also write a status-change-log row
   and a notification to the branch's staff.

## UX

In the **seh app**, under a branch's **Workers** tab (and an owner-wide view with a branch filter):

- **Workers list** — table: full_name, phone, position, branch (in the workshop-wide view), status,
  action menu. "+ Worker". Empty: "No workers in this branch yet."
- **Worker form dialog** — branch (defaults to the current branch), full_name, phone (validated
  `+998…`), position select, status.
- Row actions: Edit, Activate/Deactivate (confirm; deactivate warns about in-progress assignments).
  No Delete.
- Worker picker (in the order workflow) — a select limited to the order's branch's `active` workers
  of the relevant position (cutters when starting production, drivers when starting delivery).
- States: loading, empty, error (`trace_id`).
- Accessibility: position is a labelled select; deactivate is danger-styled; the worker picker is a
  proper combobox/select with labels.

Shared patterns (data table, form dialog, select/combobox): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/workshop/worker.md`](../entities/workshop/worker.md) — created, edited, status-toggled.
- [`docs/ref/entities/workshop/branch.md`](../entities/workshop/branch.md) — the owning branch.
- [`docs/ref/entities/sales/order.md`](../entities/sales/order.md) — `cutter_worker_id` / `driver_worker_id` set from this list.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md), [`docs/ref/entities/support/notification.md`](../entities/support/notification.md).

## Edge cases

- **Deactivate a worker assigned to in-progress orders** — allowed, with a warning listing those
  orders; staff should reassign them.
- **Assign a worker from another branch** — rejected.
- **Worker referenced by old completed orders, then deactivated** — orders are unaffected.

## Out of scope

- Worker scheduling / capacity / shift management — out.
- Worker login / a worker-facing app — out (workers are not system users).
- Per-worker performance metrics — future.

## Open questions

- None specific to this feature; `manage_workers` is already in the v1 grant catalog.
