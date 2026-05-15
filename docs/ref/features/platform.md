---
title: Platform operations
status: draft
owner: shape
updated: 2026-05-15
order: 70
---

# Platform operations

The superadmin app's ops corner: scheduled background jobs, the application-error monitor, and
the platform-user registry. Workshop provisioning and block / unblock live in
[`access-management.md`](access-management.md).

## Background jobs

The backend runs an **in-process scheduler** — no external queue, no Celery, no cron. The v1
jobs:

| Job | When | What |
|---|---|---|
| `notify-pay-later-overdue` | daily | for each pay-later order past its handover deadline, notify the order's branch and the owner |
| `notify-stale-refunds` | daily | for each `pending` refund > 7 days old, notify the owner; flag stale on the dashboard |
| `cleanup-expired-sessions` | hourly | prune expired session rows |
| `daily-low-stock-summary` | daily | per branch, one notification rolling up the day's low-stock conditions |

A job doesn't run twice concurrently (a guard). A failed job records its result and notifies
platform operators; the operator can re-trigger it manually.

Operators can list jobs (schedule, last run, last result, brief log) and trigger a run on
demand.

## Error monitor

The backend records application errors. The monitor **groups them by code**, with counts
(24 h / 7 d), the last occurrence, and a preview message. Operators can drill into a single
code to see the full message, stack trace, the request / context details (sensitive fields
masked at write time), trace ids, and affected workshops / users where known — and mark a
code resolved.

An error spike (a code's 24 h count crossing a threshold) notifies platform operators.

The health endpoints (`/api/v1/healthz` for liveness, `/api/v1/readyz` for a DB-touching
readiness check) are unauthenticated; the docs site (`/docs`) is HTTP-Basic-gated through the
edge.

## Platform user registry

Operators can list, create, reset the password of, block, and unblock platform users. The
shape mirrors workshop-user management but **without a permission model** — every platform
user holds full platform scope. Creation hands back a temp password to share once (with
`force_password_change` set, see [`access-management.md`](access-management.md)).

A platform operator cannot block themselves, and the last active platform operator cannot be
blocked — there must always be at least one.

Platform users are seeded initially by a backend CLI command (chicken-and-egg); afterwards
in-app creation is the path.

## UX (superadmin app)

Under a **Platform** section:

- **Jobs** (`/admin/platform/jobs`) — table: job name, schedule, last run (relative), last
  result (badge: ok / failed), action menu ("Run now" → confirm; "View log" → drawer). Failed
  rows highlighted.
- **Errors** (`/admin/platform/errors`) — table: code, module, count (24 h / 7 d), last
  occurrence, preview message, action menu. Detail modal: full message, stack, masked context,
  affected workshops / users, trace ids; "Resolve" → confirm. Filters: module, code, time
  range, count threshold. Empty: "No errors recorded — nice."
- **Platform users** (`/admin/platform/users`) — table: name, login, phone, status, last login,
  action menu (Edit · Reset password → one-time-secret confirmation · Block / Unblock).
  "+ Platform user" → dialog (fields + auto / manual temp password).

Cross-workshop **Orders** (`/admin/orders`, read-only) live in [`orders.md`](orders.md); the
**Audit** viewer lives in [`workshop.md`](workshop.md) (rendered cross-workshop in this app).

States: loading / empty / error on every page; confirmation on every state-changing action;
the one-time-secret confirmation after creating a user or resetting a password. Action menus
are keyboard-operable; destructive actions confirm and name their effect; result badges pair
colour with text.

## Edge cases

- **A job fails** — its result is recorded and shown; a notification fires to operators; the
  operator can re-trigger.
- **Triggering a job already running** — guarded; UI says so.
- **An error code spikes** — count climbs; an error-spike notification fires once per
  threshold crossing.
- **Blocking a platform user mid-action** — their sessions are dropped; next request 401s.
- **Block self or the last operator** — disallowed; UI prevents it; server rejects defensively.

## Next

[`notifications.md`](notifications.md) — the inbox that surfaces job-failure and error-spike
alerts to operators.
