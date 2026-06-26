---
title: Platform operations
status: draft
owner: shape
updated: 2026-06-26
order: 70
---

# Platform operations

The superadmin app's ops corner: the platform material catalog (manufacturers + materials),
scheduled background jobs, the application-error monitor, and the platform-user registry.
Workshop provisioning and block / unblock live in
[`access-management.md`](access-management.md); the catalog mechanics workshops consume
sit in [`catalog-inventory.md`](catalog-inventory.md) — this doc owns the **platform-side
admin surfaces** for them.

## Platform catalog admin

The platform-curated catalog every workshop picks from. Two registries operators manage
end-to-end here: **Manufacturers** and **Materials**. The full operation rules (create,
activate / deactivate, the snapshot guarantee that a master edit never reaches existing
orders) live in [`catalog-inventory.md`](catalog-inventory.md); this section owns the
**superadmin app's** surfaces for them.

- **Manufacturers** — Kronospan, Egger, Rehau, and so on. A material's identity includes
  its manufacturer, so adding a new brand here precedes adding the materials it supplies.
- **Materials** — `panel` and `edge` master records, each carrying its manufacturer.

Operators do not edit per-branch prices or stock — that's workshop territory.

### UX (under a **Catalog** section in the superadmin app)

- **Manufacturers** (`/admin/catalog/manufacturers`) — table: name, country, materials
  count, status, action menu. **+ Yangi ishlab chiqaruvchi** -> dialog (name, optional country,
  optional note). Row actions: Edit · Activate / Deactivate. No Delete. Filters:
  status dropdown, country dropdown. Empty: "No manufacturers yet — add one before
  adding materials."
- **Materials** (`/admin/catalog/materials`) — table: image, kind, manufacturer chip,
  type/thickness, colour/decor, panel size (for panels), status, **branch-usage count**
  (how many distinct branches carry the material), action menu. Filters:
  kind dropdown (`panel` / `edge`), manufacturer multi-select, panel-type multi-select,
  thickness multi-select, status dropdown. A per-material "which branches carry this?"
  drill-down is a planned follow-up — it needs a cross-module branch lookup, so v1 ships
  only the count.
  **+ Yangi material** -> kind-specific form (manufacturer picker with inline-add -> opens the
  Manufacturers dialog without leaving this page; spec fields per the kind). The image field
  previews the selected or existing material image inside the form, keeps upload errors local to
  the field, and supports remove / replace before save. Row actions: Edit · Activate /
  Deactivate. No Delete. Empty: "No materials yet — add manufacturers, then materials."

States: loading skeletons, empty, error with `trace_id`; the inline-add for
manufacturers preserves the in-progress material form. Accessibility: status chip pairs
colour + text; table thumbnails use a fixed framed image with a swatch fallback instead of an
empty cell; destructive activation toggles confirm and name the consequence ("Existing branch
selections of this material will be hidden from clients.").

## Background jobs

The backend runs an **in-process scheduler** — no external queue, no Celery, no cron. The v1
jobs:

| Job                        | When   | What                       |
| -------------------------- | ------ | -------------------------- |
| `cleanup-expired-sessions` | hourly | prune expired session rows |

Cutting drafts have **no expiry job** — they persist until the client deletes them or hits
the 50-draft cap ([`cutting.md`](cutting.md)). There is no auto-cleanup of drafts anywhere.
Low-stock is surfaced by the inventory module when stock changes; v1 has **no scheduled
daily low-stock digest job**.

A job doesn't run twice concurrently (a guard). A failed job records its result and notifies
platform operators; the operator can re-trigger it manually.

Operators can list jobs (schedule, last run, last result, brief log) and trigger a run on
demand.

## Error monitor

The backend records application errors. The monitor **groups them by code + module**, with
counts (24 h / 7 d), the last occurrence, and a preview message. Operators can drill into a
single grouped record to see the full message, stack trace, the request / context details
(sensitive fields masked at write time), trace ids, and affected workshops / users where known
— and mark a code resolved. A resolved code can be **reopened** if it recurs, flipping it back
to open for re-triage.

An error spike (a code's 24 h count crossing a threshold) notifies platform operators.

The health endpoints (`/api/v1/healthz` for liveness, `/api/v1/readyz` for a DB-touching
readiness check) are unauthenticated; the docs site (`/docs`) is HTTP-Basic-gated through the
edge.

## Platform user registry

Operators can list, create, reset the password of, block, and unblock platform users. The
shape mirrors workshop-user management but **without a permission model** — every platform
user holds the same platform-ops scope, not workshop order-content or profile-edit scope. Creation
hands back a temp password to share once (with
`password_reset_required` set, see [`access-management.md`](access-management.md)).

A platform operator cannot block themselves, and the last active platform operator cannot be
blocked — there must always be at least one.

Platform users are seeded initially by a backend CLI command (chicken-and-egg); afterwards
in-app creation is the path.

## UX (superadmin app)

- **Dashboard** (`/admin`) — platform health at a glance: workshop / branch / client
  counts, a recent-workshops list (name, **owner login**, **branch count**, status), and
  job + error status. It carries **no workshop
  financials** — operators monitor health and incidents, not workshop money
  ([`access-patterns.md`](../../access-patterns.md#platform-operator)); revenue rollups are out of operator scope, so no
  per-workshop or platform revenue figure appears here.
- **Docs & API reference** — a nav link out to `/docs`, `/api-docs`, `/api-redoc` (the
  live docs site and the OpenAPI references). These remain HTTP-Basic-gated at the edge,
  but the superadmin UI keeps the navigation terse and does not explain that separate
  prompt inline.

Admin pages do not carry standalone refresh controls; operators use the browser reload action
when they need a full manual refresh. Object-creation buttons use a visible `+` prefix in the
Uzbek label, while non-action headings keep natural Uzbek copy.

Under a **Catalog** section, the Manufacturers and Materials surfaces above.

Under a **Platform** section:

- **Jobs** (`/admin/platform/jobs`) — table: job name, schedule, last run (relative), last
  result (badge: ok / failed), action menu ("Run now" → confirm; "View log" → drawer). Failed
  rows highlighted.
- **Errors** (`/admin/platform/errors`) — table: code, module, count (24 h / 7 d), last
  occurrence, preview message, action menu. Detail modal: full message, stack, masked context,
  affected workshops / users, trace ids; "Resolve" → confirm, and "Reopen" for an
  already-resolved code. Filters: module, code, time range, count threshold. Empty: "No errors
  recorded — nice."
- **Admins** (`/admin/platform/users`) — table: name, login, phone, status, last login,
  action menu (Edit · Reset password → one-time-secret confirmation · Block / Unblock).
  **+ Yangi admin** -> dialog (fields + auto / manual temp password).

The **Audit** viewer lives in [`workshop.md`](workshop.md) — in v1 it is a **superadmin-only**
surface, rendered cross-workshop in this app. There is **no cross-workshop orders view** in
v1: the operator provisions, blocks, and monitors, but does not browse workshops' orders (see
[`scope.md`](../../scope.md)).

States: loading / empty / error on every page; confirmation on every state-changing action;
the one-time-secret confirmation after creating a user or resetting a password. Admin pages keep
page headers terse, mark required fields with `*`, and validate required form fields before the
server fallback. Action menus are keyboard-operable; destructive actions confirm and name their
effect; result badges pair colour with text.

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
