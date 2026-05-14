---
title: Workshop
status: draft
owner: shape
updated: 2026-05-14
order: 20
---

# Workshop

The tenant — and what each tenant publishes per branch: branches. The catalog (materials,
the branch's selection from them, and branch pricing) lives in [`catalog.md`](catalog.md);
workshop users (cutters, edgers, drivers, office staff) live in
[`identity.md`](identity.md); compensation, expenses, and payroll live in
[`finance.md`](finance.md). Rules: [`access-patterns.md`](../../access-patterns.md) (tenancy
+ branch status), [`orders.md`](../features/orders.md) (the order state machine + production
stamps).

## Workshop

The tenant — one furniture-cutting business. Has exactly one owner, many branches, many workshop
users, and a settings bundle. Provisioned by a platform operator.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `name` | text | required |
| `logo_file_id` | UUID? | → [file](support.md#file) |
| `phone` | text | `+998XXXXXXXXX` |
| `address` | text? | legal/postal |
| `owner_user_id` | UUID | → workshop user with `is_owner`; 1:1 |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

**Settings (embedded — one bundle per workshop):**

| Field | Type | Notes |
|---|---|---|
| `settings.delivery_enabled` | bool | default `false` |
| `settings.delivery_zones` | json | list of `{ id, name, polygon_or_label, fee_tiyin }` — static, admin-entered |
| `settings.default_advance_percent` | int | 0–100 |
| `settings.currency` | enum | `UZS` (only value in v1) |
| `settings.payment_channels` | json | per-channel `{ enabled: bool, credentials: {...} }` for Payme/Click/Uzum/BNPL — **stored, inert in v1**; credentials owner-visible only |

Blocking cascades: the owner's + staff's sessions are revoked immediately; open orders freeze
(no automatic transitions); clients are unaffected. Unblocking does not restore sessions.
Invariants: exactly one `is_owner = true` workshop user per workshop (DB/service);
`owner_user_id` references that user; `settings.payment_channels` credentials visible only to
the owner; `default_advance_percent ∈ [0, 100]`; never deleted.

## Branch

A physical location of a workshop. Owns its warehouse stock, its pricing, and its selection
from the platform's material catalog (see [`catalog.md`](catalog.md)). Workshop users who
work here have it as their `home_branch_id` ([`identity.md`](identity.md)). Status governs
whether clients see it and order from it.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `name` / `address` / `phone` | text | required; phone `+998XXXXXXXXX` |
| `latitude` / `longitude` | numeric | manual numeric (no geocoder in v1) |
| `working_hours` | json | per weekday `{ open, close }` |
| `status` | enum | `active` / `temporarily_closed` / `inactive` (default `active`) |
| `closed_reason` | text? | shown when `temporarily_closed` |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `active` — visible to clients, accepts new orders & cutting; `temporarily_closed` —
visible (shown as closed, with `closed_reason`), no new orders; `inactive` — invisible to
clients, no new orders, existing orders complete. Transitions owner-only. Never deleted.
Changing status does **not** revoke staff sessions or grants.

Invariants: everything under the branch (branch material selections, stock, pricing) belongs
to the same workshop; a branch with active orders can be set `inactive` (orders finish; UI
warns).

Material, Branch material (the per-branch selection), and Branch pricing live in
[`catalog.md`](catalog.md). Cutters, edgers, drivers, and office staff are all workshop
users in [`identity.md`](identity.md) — there is no separate `worker` entity in v1.
