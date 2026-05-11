---
title: Workshop provisioning
status: stable
owner: shape
updated: 2026-05-11
order: 10
related:
  - docs/spec/scope-v1.md
  - docs/spec/access.md
  - docs/spec/journeys.md
  - docs/ref/entities/workshop/workshop.md
  - docs/ref/entities/identity/workshop-user.md
  - docs/ref/features/platform-ops.md
---

# Workshop provisioning

## Problem

A new furniture workshop wants on the platform. Someone trusted must create the tenant, hand it to a
real person to run, and be able to take it offline if things go wrong — without that person being
able to create themselves. Today there's no such trusted layer; a workshop can't "join" without a
human gatekeeper, and there's no clean separation between "the team that runs the platform" and "the
people who run a workshop".

## User stories

- As a **platform operator**, I want to create a workshop and its first owner in one step so the
  owner can log in and start setting up immediately.
- As a **platform operator**, I want to block a workshop (and unblock it later) so I can stop a
  misbehaving or non-paying tenant without deleting its data.
- As a **platform operator**, I want to set and edit a workshop's settings (delivery on/off, default
  advance %, payment-channel flags) — or let the owner do it — so the workshop is configured.
- As a **workshop owner**, I want a temporary password and a forced change on first login so my
  account is mine from the start.
- As a **platform operator**, I want to look across all workshops (read-only) for incident response.

## Requirements

1. `create-workshop` (platform operator): creates a `workshop` **and** its first `workshop_user`
   (`is_owner = true`, `force_password_change = true`, a temp password) **atomically** — never one
   without the other. Input: workshop name, phone, address?, and the owner's full_name, login,
   phone, temp password (auto-generated, with manual override). Returns the workshop summary + the
   temp password **once**.
2. `update-workshop` (platform operator; or the owner for their own workshop): edit name, logo,
   phone, address.
3. `update-workshop-settings` (platform operator or owner): delivery_enabled, delivery_zones (list
   of name + label/polygon + fee in tiyin), default_advance_percent (0–100), currency (UZS, fixed),
   payment_channels (per-channel enabled flag + merchant credentials — **stored, inert in v1**;
   credentials owner-visible only — [`docs/spec/scope-v1.md`](../../spec/scope-v1.md)).
4. `block-workshop` / `unblock-workshop` (platform operator only): set `status`; blocking revokes the
   owner's + staff's sessions immediately ([`docs/spec/access.md`](../../spec/access.md), [`docs/spec/access.md`](../../spec/access.md)); unblocking does not restore sessions; clients are unaffected; open orders freeze.
5. `list-workshops` / `get-workshop` (platform operator): cross-workshop list with status + a few
   denormalized counts (branches, orders last 30d), and per-workshop detail.
6. The created owner cannot be created, demoted, or deleted by anyone except a platform operator;
   exactly one owner per workshop is enforced.
7. Every action writes an audit-log row; `block-workshop` also writes a status-change-log row.

## UX

In the **superadmin app** (see [`docs/ref/ux/information-architecture.md`](../ux/information-architecture.md)):

- **Workshops list** — table: name, owner (name + phone), status badge (`active` / `blocked`),
  created, branches count, orders-30d count, search by name, status filter, "+ Workshop" action.
  Empty: "No workshops yet."
- **Create-workshop dialog** — workshop fields + owner fields, temp password (auto-generated, copy
  button, manual toggle). On success: a read-only confirmation showing the owner login + temp
  password with "share this with the owner — shown once" and a copy button.
- **Workshop detail** — header (name, status badge, owner, created); tabs: Profile (edit), Settings
  (delivery + advance % + payment channels grid — credentials masked, reveal on click), Branches
  (read-only list), Block (block/unblock with a mandatory reason; warning that staff sessions are
  revoked and open orders freeze). Block is destructive-styled.
- States: loading, empty, error (with `trace_id`), the success-with-secret confirmation, blocked-banner
  on a blocked workshop's detail.
- Accessibility: the temp-password reveal is keyboard-operable; the Block action is danger-colored
  and names the consequence; focus moves into the create dialog and returns to the trigger on close.

Cross-cutting patterns (tables, filter bar, confirm-with-reason dialog, masked-secret field) are in
[`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/workshop/workshop.md`](../entities/workshop/workshop.md) — created; settings edited; blocked/unblocked.
- [`docs/ref/entities/identity/workshop-user.md`](../entities/identity/workshop-user.md) — the first (owner) user created here.
- [`docs/ref/entities/identity/platform-user.md`](../entities/identity/platform-user.md) — the actor.
- [`docs/ref/entities/support/file.md`](../entities/support/file.md) — workshop logo.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md).

## Edge cases

- **Owner login collides** with an existing owner login in another workshop → fine (logins are
  unique per workshop, not globally); within the workshop being created there's only one user, so no
  collision possible at creation.
- **Create fails after the workshop row but before the owner row** → the whole operation rolls back;
  no orphan workshop, no orphan owner (atomic).
- **Block while staff are mid-action** → their next request 401s; the platform operator can still
  read the workshop's data for incident response.
- **Unblock** → owner/staff must log in again; the workshop's open orders resume normal handling.
- **Edit settings concurrently** (owner + platform operator) → last write wins; both are audited.

## Out of scope

- Self-service workshop signup (no human gatekeeper) — not in v1.
- Multiple owners / co-owners per workshop — not in v1.
- Billing the workshop (SaaS/transaction fees) — not modelled.
- Branch-level overrides of workshop settings — future ([`docs/spec/open-questions.md`](../../spec/open-questions.md)).

## Open questions

- Should the owner be able to delegate `manage_settings` to a staff user? — owner: shape — see [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q1.
