---
title: Platform operations
status: draft
owner: shape
updated: 2026-05-13
order: 70
---

# Platform operations

The superadmin app's ops corner: the in-process scheduled jobs, the application-error monitor, and
the platform-user registry. Workshop provisioning + block/unblock are in
[`workshop.md`](workshop.md).

## Endpoints

| Endpoint | Caller | What |
|---|---|---|
| `list-jobs` | platform operator | each job with its schedule, last run time, last result (ok / failed), a brief log |
| `trigger-job` | platform operator | run a job now (confirmed); a job doesn't run twice concurrently |
| `list-errors` | platform operator | application errors grouped by code, with count (24h / 7d), last occurrence, preview message; filters: module, code, time range, count threshold |
| `get-error` | platform operator | full message, stack trace, request/context details (sensitive fields masked), trace ids, affected workshops/users where known |
| `resolve-error` | platform operator | mark a code resolved |
| `list-platform-users` / `create-platform-user` / `reset-platform-user-password` / `block-platform-user` / `unblock-platform-user` | platform operator | same shape as workshop-user management but without a permission model (full platform scope) |

The v1 jobs (on the in-process scheduler): `expire-stale-draft-cuttings` (delete `draft` cutting
results > 7 days old, with their sheets/placements), `notify-pay-later-overdue`,
`notify-stale-refunds` (`pending` refunds > 7 days), `cleanup-expired-sessions`, daily low-stock
summary. A failed job produces a notification to platform operators. Health endpoints
(`GET /api/v1/healthz`, `GET /api/v1/readyz`) exist for liveness/readiness probes.

Every mutating action (trigger job, resolve error, manage platform users) is audited.

## UX (superadmin app)

Under a **Platform** section:

- **Jobs** (`/admin/platform/jobs`) — table: job name, schedule, last run (relative), last
  result (badge: ok / failed), action menu ("Run now" → confirm; "View log" → drawer). A
  failed-result row is highlighted.
- **Errors** (`/admin/platform/errors`) — table: code, module, count (24h / 7d), last
  occurrence, preview message, action menu ("Detail" → modal with full message, stack, masked
  context, affected workshops/users, trace ids; "Resolve" → confirm). Filters: module, code,
  time range, count threshold. Empty: "No errors recorded — nice."
- **Platform users** (`/admin/platform/users`) — table: name, login, phone, status, last login,
  action menu (Edit, Reset password → one-time-secret confirmation, Block/Unblock). "+ Platform
  user" → dialog (fields + auto/manual temp password).

Cross-workshop **Orders** (`/admin/orders`, read-only) and **Audit** (`/admin/audit`) live in
[`orders.md`](orders.md) and [`workshop.md`](workshop.md) respectively.

States: loading / empty / error throughout; confirmation dialogs on every action that changes
state; a one-time-secret confirmation after creating a user / resetting a password.
Accessibility: action menus keyboard-operable; destructive/risky actions confirm and name the
effect; the error-detail modal manages focus; result badges pair color with text. Component specs
in [`web/DESIGN.md`](../../../web/DESIGN.md).

## Edge cases

- **A job fails** — the result is recorded and shown; a notification fires to platform
  operators; the operator can re-trigger it.
- **Triggering a job that's already running** — guarded; the UI says so.
- **A flood of errors of one code** — grouped; the count climbs; an error spike notifies
  operators.
- **Blocking a platform user mid-action** — their sessions are dropped; next request 401s.
- **A platform operator blocks themselves / the last operator** — disallowed (there must be at
  least one active platform operator).
