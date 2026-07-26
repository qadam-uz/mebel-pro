---
title: Workshop
status: draft
owner: shape
updated: 2026-07-26
order: 20
---

# Workshop

The tenant — and what each tenant publishes per branch: branches. The catalog (materials,
the branch's selection from them, and branch pricing) lives in [`catalog.md`](catalog.md);
workshop users live in [`identity.md`](identity.md); income and expenses live in
[`finance.md`](finance.md). Rules: [`access-patterns.md`](../../access-patterns.md) (tenancy
+ branch status), [`orders.md`](../features/orders.md) (the order state machine + production
stamps).

## Workshop

The tenant — one furniture-cutting business. Has exactly one owner, many branches, many workshop
users, and a settings bundle. Provisioned by a platform operator. Public contact data belongs to
branches, not the workshop.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `name` | text | required |
| `logo_file_id` | UUID? | → [file](support.md#file) |
| `owner_user_id` | UUID | → workshop user with `is_owner`; 1:1 |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

**Settings (embedded — one bundle per workshop):**

| Field | Type | Notes |
|---|---|---|
| `settings.currency` | enum | `UZS` (only value in v1) |

Delivery zones, default advance %, and payment channels are **not in v1** — v1 is
pickup-only and an order moves no money ([`scope.md`](../../scope.md)); they return with
delivery and a gateway.

Blocking cascades: the owner's + staff's sessions are revoked immediately; open orders freeze
(no automatic transitions); clients are unaffected. Unblocking does not restore sessions.
Invariants: exactly one `is_owner = true` workshop user per workshop (DB/service);
`owner_user_id` references that user; never deleted.

## Branch

A physical location of a workshop. Owns its warehouse stock, its pricing, and its selection
from the platform's material catalog (see [`catalog.md`](catalog.md)). Workshop users who
work here have it as their `home_branch_id` ([`identity.md`](identity.md)). Status governs
whether clients see it and order from it.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `branch_no` | int | platform-wide unique, assigned at creation as `max + 1` under an advisory lock. **Immutable** — it is the middle segment of every order number the branch prints ([`sales.md`](sales.md)), so changing it would orphan printed cutting maps. Not settable or patchable through any API |
| `name` / `address` / `phone` | text | required; phone `+998XXXXXXXXX` |
| `latitude` / `longitude` | numeric? | optional coordinate pair (no geocoder in v1; **not collected via the UI** in v1, but the columns/API fields remain); both are null when unknown |
| `working_hours` | json | seven weekday keys, each `{ open, close }`; closed day is `{ open: null, close: null }` |
| `status` | enum | `active` / `temporarily_closed` / `inactive` (default `active`) |
| `closed_reason` | text? | shown when `temporarily_closed` |
| `kerf_mm` | int | the branch saw's kerf width; 1–20 mm; default `4`. Resolved into every cutting optimisation run scoped to this branch ([`cutting.md`](../features/cutting.md)) |
| `edge_trim_mm` | int | edge trim per side (usable panel area = panel − 2× this); 0–50 mm; default `5` |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `active` — visible to clients, accepts new orders & cutting; `temporarily_closed` —
visible (shown as closed, with `closed_reason`), no new orders; `inactive` — invisible to
clients, no new orders, existing orders complete. Transitions owner-only. Never deleted.
Changing status does **not** revoke staff sessions or grants.

Invariants: everything under the branch (branch material selections, stock, pricing) belongs
to the same workshop; a branch with active orders can be set `inactive` (orders finish; UI
warns).

Material, Branch material (the per-branch selection), and Branch pricing live in
[`catalog.md`](catalog.md). Cutters, edgers, and office staff are all workshop users in
[`identity.md`](identity.md) — there is no separate `worker` entity and no fixed role.
