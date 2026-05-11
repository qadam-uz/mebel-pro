---
title: Workshop user management
status: stable
owner: shape
updated: 2026-05-11
order: 12
related:
  - docs/spec/access.md
  - docs/ref/entities/identity/workshop-user.md
  - docs/ref/entities/identity/permission-grant.md
  - docs/ref/entities/identity/session.md
---

# Workshop user management

## Problem

A workshop owner can't do everything alone — the order desk, the warehouse, the catalog all need
hands. But staff shouldn't see the whole workshop, only the branch(es) and tasks they're given. The
old role hierarchy couldn't express "this person handles orders for branch A only". The owner needs
to create staff, give each a precise set of branch-scoped capabilities, reset their passwords, and
cut their access off cleanly.

## User stories

- As a **workshop owner**, I want to create a staff user with a temporary password so they can log in.
- As a **workshop owner**, I want to grant a staff user specific permissions on specific branches so
  they see exactly what they need.
- As a **workshop owner**, I want to change a staff user's grants later without re-creating them.
- As a **workshop owner**, I want to reset a staff user's password (forcing a change) and block /
  unblock them.
- As a **workshop owner**, I want to revoke a staff user's sessions immediately when something's
  wrong.
- As a **workshop staff** member, I want to change my own password and see/end my own sessions.

## Requirements

1. `create-workshop-user` (owner only): creates a `workshop_user` in the owner's workshop —
   `is_owner = false`, `force_password_change = true`, a temp password (auto-generated, manual
   override). Input: full_name, login, phone, temp password, **and optionally an initial set of
   `(permission, branch)` grants** — created in the same atomic operation so the user isn't left
   with zero grants in a window. Returns the user + the temp password **once**.
2. `update-workshop-user` (owner): edit full_name, phone.
3. `set-user-grants` (owner): replace the user's `permission_grant` rows with a new set, atomically;
   each `(permission, branch)` validated — the permission is in the v1 branch-scoped catalog
   (`view_dashboard` / `manage_orders` / `manage_catalog` / `manage_inventory` / `manage_workers`)
   and the branch belongs to this workshop. Takes effect on the user's next request; no session
   revoke. (Workshop-wide capabilities are owner-only in v1 and aren't grantable — [`docs/spec/access.md`](../../spec/access.md), [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q1.)
4. `reset-workshop-user-password` (owner): generates a temp password, sets `force_password_change`,
   revokes the user's sessions.
5. `block-workshop-user` / `unblock-workshop-user` (owner): set `status`; blocking revokes sessions
   immediately; unblocking does not restore them; data and history are kept.
6. `change-my-password` (any workshop user): set a new password meeting complexity; revokes all
   *other* sessions; clears `force_password_change`.
7. `list-my-sessions` / `revoke-my-session` / `revoke-my-sessions` (any workshop user): see and end
   own sessions.
8. The owner cannot create another owner, demote themselves, or delete a user; exactly one owner per
   workshop holds; a brute-force lockout (5 fails → 15 min) applies to staff logins ([`docs/spec/access.md`](../../spec/access.md)).
9. Every action writes an audit-log row; block/unblock also write a status-change-log row.

## UX

In the **seh app**, under Settings → Users (owner-only nav item):

- **Users list** — table: name, login, phone, status, granted-branches count, last login, action
  menu. "+ User" action. Empty: "No staff yet — add one to delegate work."
- **Create-user dialog** — fields + temp password (auto/manual, copy) + an initial grants matrix
  (permission rows × branch columns, within the workshop). On success: read-only "share login + temp
  password — shown once" confirmation with copy.
- **User detail** — header (name, status badge, last login); tabs: Profile (edit), Permissions (the
  grants matrix — toggling saves atomically with an explicit Save + unsaved-changes guard), Sessions
  (list with current marker, revoke one / all), Audit (this user's actions, read-only).
- Row/detail actions: Edit, Reset password (→ same one-time-secret confirmation), Block / Unblock
  (confirm; block warns sessions are revoked), Revoke sessions.
- **Self** screen (every workshop user): Profile, Change password (strength meter — ≥ 8, upper +
  lower + digit), Sessions list with current marker + "log out everywhere".
- States: loading, empty (no staff), error (`trace_id`), the one-time-secret confirmation, a
  "you have no permissions — ask your workshop owner" empty screen for a staff user with zero grants.
- Accessibility: the grants matrix is keyboard-navigable with proper labels; destructive actions
  (block, revoke, reset) are danger-styled and name their effect; modal focus management.

Shared patterns (matrix editor, one-time-secret field, sessions list, confirm dialogs): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/identity/workshop-user.md`](../entities/identity/workshop-user.md) — created, edited, blocked, password reset.
- [`docs/ref/entities/identity/permission-grant.md`](../entities/identity/permission-grant.md) — created/removed in the grants matrix.
- [`docs/ref/entities/identity/session.md`](../entities/identity/session.md) — revoked on block / reset / password change / "log out everywhere".
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md).

## Edge cases

- **Staff user with zero grants** → can log in; every workshop screen is empty/hidden; the app shows
  the "ask your owner for access" message. Not an error.
- **Grant on a branch that later goes `inactive`** → inert; the branch disappears from the user's
  branch switcher; reactivating the branch makes the grant live again.
- **Owner blocks themselves** — disallowed (a workshop must have an active owner; ownership changes
  only via a platform operator).
- **Login collision within the workshop** → rejected (`login` unique per workshop).
- **Reset password while the user is mid-action** → their sessions are dropped; next request 401s.
- **Two owners editing the same staff user's grants** — last write wins; both audited.

## Out of scope

- Delegating workshop-wide capabilities (branches, pricing, settings, reports, user management) to
  staff — owner-only in v1 ([`docs/spec/open-questions.md`](../../spec/open-questions.md) Q1).
- Named permission presets / role templates — future (could layer on the same grant rows).
- Self-service password reset for staff — not in v1 (owner-driven only).
- SSO / federation for workshop users — out.

## Open questions

- Delegable workshop-wide permissions and named presets — owner: shape — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q1.
