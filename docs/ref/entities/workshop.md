---
title: Workshop
status: draft
owner: shape
updated: 2026-09-06
order: 20
---

# Workshop

The tenant — and what each tenant publishes per branch: branches. The catalog (materials,
the branch's own materials, and branch pricing) lives in [`catalog.md`](catalog.md);
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
| `public_code` | text | required, **unique platform-wide**. 8 characters of Crockford base32 (no `I L O U`), generated at provisioning and backfilled for older workshops. The code in the workshop's client link and printed QR ([`client-entry.md`](../features/client-entry.md)): machine-generated only — no API sets, regenerates, or revokes it, because a printed QR must never rot. Lookups normalize lookalike characters before matching |
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
(no automatic transitions); client sessions and orders are untouched, though a client pinned
to the workshop falls back to un-pinned for as long as the block lasts and its client link
resolves to nothing ([`client-entry.md`](../features/client-entry.md)). Unblocking does not
restore sessions. Invariants: exactly one `is_owner = true` workshop user per workshop
(DB/service); `owner_user_id` references that user; `public_code` unique (DB); never deleted.

## Branch

A physical location of a workshop. Owns its warehouse stock, its pricing, and the formats it
carries of the platform's decors (see [`catalog.md`](catalog.md)). Workshop users who
work here have it as their `home_branch_id` ([`identity.md`](identity.md)). Status governs
whether clients see it and order from it.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `branch_no` | int | platform-wide unique, assigned at creation as `max + 1` under an advisory lock. **Immutable** — it addresses the branch in its own client link and printed QR (`/w/{code}/{branch_no}`, [`client-entry.md`](../features/client-entry.md)), and it is the middle segment of the **legacy** order numbers this branch printed before numbers went global ([`sales.md`](sales.md)); changing it would rot counter QRs and orphan printed cutting maps. Not settable or patchable through any API |
| `name` / `address` / `phone` | text | required; phone `+998XXXXXXXXX`. `phone` is the **primary** number — the one compact surfaces (order card, order detail, PDF) and every order record carry |
| `additional_phones` | json | ordered list of extra published numbers, 0–3; same `+998XXXXXXXXX` rule; no duplicates, including against `phone`. Array order is display order. Shown alongside the primary wherever a client sees the branch ([`client-entry.md`](../features/client-entry.md)) |
| `latitude` / `longitude` | numeric? | optional coordinate pair, both null when unknown. No geocoder: the owner places the pin on the branch form's map ([`workshop.md`](../features/workshop.md#branches)), and where a client is shown a branch the pair renders a **Xaritada ko'rish** link into Yandex Maps — absent when the pair is null |
| `status` | enum | `active` / `temporarily_closed` / `inactive` (default `active`) |
| `closed_reason` | text? | shown when `temporarily_closed` |
| `kerf_mm` | int | the branch saw's kerf width; 1–20 mm; default `4`. Resolved into every cutting optimisation run scoped to this branch ([`cutting.md`](../features/cutting.md)) |
| `edge_trim_mm` | int | edge trim per side (usable panel area = panel − 2× this); 0–50 mm; default `5` |
| `edge_overhang_mm` | int | the bander's glue-and-trim allowance per banded **side** — tape is glued long and cut flush by hand, so consumed length = geometric length + this, once per side; 0–100 mm; default `30`. Drives what the client is billed and what stock is decremented ([`orders.md`](../features/orders.md#pricing)) |
| `own_material_allowed` | bool | whether a **client** may claim their own sheets self-serve in the app; default `false`. Off until the owner turns it on — accepting client material changes what the shop stores and what has to arrive before the saw starts, so it is opted into, never inherited. Gates the client write path on the server; the client app itself shows no own-material control in the MVP whatever the flag says ([`cutting.md`](../features/cutting.md#parts-and-materials)). **Not** a shop-floor ban: staff always may arrange client material — in the staff editor and on a placed order ([`orders.md`](../features/orders.md#pricing)) |
| `production_mode` | enum | `simple` / `full`; **default `simple`**, for existing branches as well as new ones — owner opt-in either way, never inherited from a backfill. Decides whether production is one **Tayyor** tap or the per-stage choreography; read at the moment of each action and never stamped on an order, so switching migrates nothing ([`orders.md`](../features/orders.md#production-mode)) |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `active` — visible to clients, accepts new orders & cutting; `temporarily_closed` —
visible (shown as closed, with `closed_reason`), no new orders; `inactive` — invisible to
clients, no new orders, existing orders complete. Transitions owner-only. Never deleted.
Changing status does **not** revoke staff sessions or grants.

Invariants: everything under the branch (branch materials, stock, pricing) belongs
to the same workshop; a branch with active orders can be set `inactive` (orders finish; UI
warns).

Material, Branch material (the per-branch selection), and Branch pricing live in
[`catalog.md`](catalog.md). Cutters, edgers, and office staff are all workshop users in
[`identity.md`](identity.md) — there is no separate `worker` entity and no fixed role.
