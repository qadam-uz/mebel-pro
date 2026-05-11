---
title: Audit log
status: stable
owner: shape
updated: 2026-05-11
order: 44
related:
  - docs/spec/nfr.md
  - docs/ref/entities/support/action-log.md
  - docs/ref/entities/support/status-change-log.md
  - docs/ref/features/platform-ops.md
---

# Audit log

## Problem

When something looks wrong — a price discount no one remembers, an order force-cancelled, a worker
deactivated, a user's password reset — someone has to be able to ask "who did that, and when?". Every
mutating action and every status transition is recorded; the workshop owner needs a viewer scoped to
their workshop, and the platform operator needs one across all of them. This is a read-only,
look-it-up surface over an append-only log.

## User stories

- As a **workshop owner** (and staff with `view_reports` — owner-only in v1), I want to browse my
  workshop's action log and status changes, filtered by who, what, which entity, and when.
- As a **platform operator**, I want the same across all workshops, for incident response.
- As either, I want to drill from an audit entry to the entity it touched.

## Requirements

1. `list-action-log` (workshop owner — scoped to their workshop & granted branches; platform operator
   — all): paginated, newest first; filters: action code (or family), actor (user search), entity
   (type + id), date range, branch, workshop (platform operator only). Each row from
   [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md): actor, action, entity, summary, a collapsible `details` (sensitive fields masked), trace id, timestamp.
2. `list-status-change-log` (same scoping): paginated; filters: entity type + id, from/to status,
   actor, date range, branch, workshop. Rows from [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md). For orders this mirrors the order's own timeline; this view is the cross-entity one.
3. The log is **append-only** — never edited or deleted ([`docs/spec/architecture.md`](../../spec/architecture.md)); this feature only reads it. (Writing audit rows is a cross-cutting concern of every mutating use case — [`docs/spec/nfr.md`](../../spec/nfr.md), [`docs/spec/architecture.md`](../../spec/architecture.md).)
4. Pagination is cursor-friendly for a growing log; CSV export is a placeholder (disabled) unless the
   backend supports it.

## UX

- In the **seh app** (owner / `view_reports`): an **Audit** section with two tabs — **Action log**
  (filters: action type/family, module, actor search, entity type+id, date range, branch; rows with a
  JSON-collapsible `details` preview) and **Status changes** (filters: entity type+id, from→to, actor,
  date range; rows showing the transition). Each row links to the affected entity where one exists.
  Read-only.
- In the **superadmin app**: the same, plus a workshop filter and no workshop scoping (sees all).
- States: loading (skeleton rows), empty (no matching entries), error (`trace_id`); the `details`
  expander.
- Accessibility: the filter bar controls are labelled; the `details` collapsibles are keyboard-operable
  with proper expanded/collapsed semantics; the table has sortable, labelled columns; deep links have
  descriptive names.

Shared components (data table, filter bar, JSON-collapsible cell): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md) — read.
- [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md) — read.
- (deep-links to) any entity referenced by an entry — orders, branches, materials, workers, users, refunds, …

## Edge cases

- **A huge log** — pagination is cursor-based; the default view is a recent window; filters narrow it.
- **An entry referencing a soft-deleted entity** — the link still resolves (soft delete keeps the
  row); the entity shows as inactive.
- **Sensitive fields in `details`** (passwords, full payment credentials) — masked at write time;
  never shown.
- **A staff member without `view_reports`** trying to reach the Audit section — `forbidden`; the nav
  item isn't shown (owner-only in v1).

## Out of scope

- Editing or deleting audit entries — never (append-only).
- Alerting/anomaly detection on the audit stream — future (the dashboard surfaces a few highlights;
  the error monitor handles application errors — [`docs/ref/features/platform-ops.md`](platform-ops.md)).
- A SIEM / external log shipper integration — out.
- CSV export — placeholder unless the backend adds it.

## Open questions

- Delegating `view_reports` to staff — owner: shape — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q1.
