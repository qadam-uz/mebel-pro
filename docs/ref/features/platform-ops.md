---
title: Platform operations
status: stable
owner: shape
updated: 2026-05-11
order: 46
related:
  - docs/spec/architecture.md
  - docs/spec/nfr.md
  - docs/ref/features/workshop-provisioning.md
  - docs/ref/features/notifications-inbox.md
---

# Platform operations

## Problem

The team running the platform needs a small set of operational surfaces: see and act on the
in-process scheduled jobs (the ones that clean up stale draft cuttings, nudge overdue pay-later
orders, flag stale refunds, prune expired sessions), browse application errors when something's gone
wrong, and manage the platform users. None of this is a workshop-facing feature — it's the
superadmin app's ops corner. (Workshop provisioning and block/unblock are the other superadmin
surface — [`docs/ref/features/workshop-provisioning.md`](workshop-provisioning.md).)

## User stories

- As a **platform operator**, I want to see the scheduled jobs, when each last ran, and whether it
  succeeded — and to trigger one manually if I need to.
- As a **platform operator**, I want to browse recent application errors with their code, count, last
  occurrence, and a detail view (stack, context) — and to mark stale ones resolved.
- As a **platform operator**, I want to manage platform users (create, reset password, block/unblock).
- As a **platform operator**, I want alerts when errors spike or a scheduled job fails.

## Requirements

1. **Scheduled jobs console** (platform operator): `list-jobs` — each job with its schedule, last
   run time, last result (ok / failed), and a brief log; `trigger-job` — run a job now (confirmed).
   The v1 jobs (run on the in-process scheduler — [`docs/spec/nfr.md`](../../spec/nfr.md), [`docs/spec/architecture.md`](../../spec/architecture.md)): `expire-stale-draft-cuttings` (delete `draft` cutting results > 7 days old, with their sheets/placements), `notify-pay-later-overdue` (notify staff/owner about pay-later orders past their deadline), `notify-stale-refunds` (notify the owner about `pending` refunds > 7 days), `cleanup-expired-sessions` (prune session rows past their refresh expiry), and the daily low-stock summary. A failed job produces a notification to platform operators.
2. **Error monitor** (platform operator): `list-errors` — application errors grouped by code, with
   count (24h / 7d), last occurrence, a preview message; filters: module, code, time range, count
   threshold. `get-error` — detail: full message, stack trace, request/context details (sensitive
   fields masked), trace ids, affected workshops/users where known. `resolve-error` — mark a code
   resolved (per the spec's housekeeping). An error spike produces a notification to platform
   operators.
3. **Platform users** (platform operator): `list-platform-users` / `create-platform-user` (login,
   full_name, phone, temp password + `force_password_change`) / `reset-platform-user-password` /
   `block-platform-user` / `unblock-platform-user` — same shape as workshop-user management but
   without a permission model (full platform scope). See [`docs/ref/entities/identity/platform-user.md`](../entities/identity/platform-user.md).
4. Health endpoints (`GET /api/v1/healthz`, `GET /api/v1/readyz`) exist for liveness/readiness probes
   — not a UI feature, but part of the operational picture.
5. Every mutating action (trigger job, resolve error, manage platform users) is audited.

## UX

In the **superadmin app**, under a **Platform** section:

- **Jobs** (`/admin/platform/jobs`) — table: job name, schedule, last run (relative), last result
  (badge: ok / failed), action menu ("Run now" → confirm; "View log" → drawer). A failed-result row
  is highlighted. Empty: only if no jobs are registered (shouldn't happen).
- **Errors** (`/admin/platform/errors`) — table: code, module, count (24h / 7d), last occurrence,
  preview message, action menu ("Detail" → modal with the full message, stack, masked context,
  affected workshops/users, trace ids; "Resolve" → confirm). Filters: module, code, time range, count
  threshold. Empty: "No errors recorded — nice."
- **Platform users** (`/admin/platform/users`) — table: name, login, phone, status, last login,
  action menu (Edit, Reset password → one-time-secret confirmation, Block/Unblock). "+ Platform user"
  → dialog (fields + auto/manual temp password). Same one-time-secret pattern as workshop provisioning.
- States: loading/empty/error throughout; confirmation dialogs on every action that changes state
  (trigger, resolve, block, reset); a one-time-secret confirmation after creating a user / resetting
  a password.
- Accessibility: action menus are keyboard-operable; destructive/risky actions (trigger a job, block
  a user) confirm and name the effect; the error-detail modal manages focus; result badges pair color
  with text.

Shared components (data table, filter bar, drawer, confirm dialog, one-time-secret field): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/identity/platform-user.md`](../entities/identity/platform-user.md) — created, edited, blocked, password reset.
- [`docs/ref/entities/identity/session.md`](../entities/identity/session.md) — revoked on block / reset.
- (operates on infrastructure-level state — scheduled jobs, recorded errors — that has no business
  entity of its own, per the `platform` module's scope in [`docs/spec/architecture.md`](../../spec/architecture.md).)
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/notification.md`](../entities/support/notification.md).
- (the jobs themselves touch) [`docs/ref/entities/cutting/cutting-result.md`](../entities/cutting/cutting-result.md) (draft cleanup), [`docs/ref/entities/sales/order-refund.md`](../entities/sales/order-refund.md) (stale-refund notify), [`docs/ref/entities/sales/order.md`](../entities/sales/order.md) (pay-later overdue notify), [`docs/ref/entities/inventory/stock-item.md`](../entities/inventory/stock-item.md) (low-stock summary).

## Edge cases

- **A job fails** — the result is recorded and shown; a notification fires to platform operators; the
  operator can re-trigger it.
- **Triggering a job that's already running** — guarded (a job doesn't run twice concurrently); the
  UI says so.
- **A flood of errors of one code** — grouped; the count climbs; an error spike notifies operators.
- **Blocking a platform user mid-action** — their sessions are dropped; next request 401s.
- **A platform operator blocks themselves / the last operator** — disallowed (there must be at least
  one active platform operator).

## Out of scope

- A full job queue / DLQ console with retries (the old codebase's "taskmill") — v1's jobs are simple
  in-process scheduled tasks, not a queue ([`docs/spec/architecture.md`](../../spec/architecture.md)).
- Distributed tracing UI, metrics dashboards, log search — out (structured logs + the error monitor
  cover v1).
- An error catalog (all registered codes per module) — planned, not v1.
- Tenant impersonation by a platform operator — out (incident response is read-only).

## Open questions

- Whether the error-producer model should change (events vs. direct) — owner: build — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q11.
