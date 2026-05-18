---
title: Workshop
status: draft
owner: shape
updated: 2026-05-17
order: 20
---

# Workshop

Tenant — va har bir tenant per branch nima publish qilishi: branch'lar. Catalog
(material'lar, branch'ning ulardan tanlovi va branch pricing) [`catalog.md`](catalog.md)'da
yotadi; workshop user'lar [`identity.md`](identity.md)'da yotadi; income va expense'lar
[`finance.md`](finance.md)'da yotadi. Rule'lar:
[`access-patterns.md`](../../access-patterns.md) (tenancy + branch status),
[`orders.md`](../features/orders.md) (order state machine + production stamp'lar).

## Workshop

Tenant — bitta furniture-cutting biznesi. Aniq bitta owner, koʻp branch, koʻp workshop user
va settings bundle'ga ega. Platform operator tomonidan provision qilinadi.

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

**Settings (embedded — har bir workshop uchun bitta bundle):**

| Field | Type | Notes |
|---|---|---|
| `settings.currency` | enum | `UZS` (only value in v1) |

Delivery zone'lar, default advance % va payment channel'lar **v1'da yoʻq** — v1
pickup-only va order hech qanday money harakatlantirmaydi ([`scope.md`](../../scope.md));
ular delivery va gateway bilan qaytadi.

Block cascade'lari: owner'ning + staff'ning session'lari darhol revoke qilinadi; ochiq
order'lar muzlaydi (automatic transition yoʻq); client'larga taʼsir qilmaydi. Unblock
session'larni restore qilmaydi. Invariant'lar: har bir workshop uchun aniq bitta
`is_owner = true` workshop user (DB/service); `owner_user_id` shu user'ga reference qiladi;
hech qachon oʻchirilmaydi.

## Branch

Workshop'ning physical location'i. O'zining warehouse stock'ini, pricing'ini va
platform'ning material catalog'idan tanlovini egallaydi (see [`catalog.md`](catalog.md)).
Bu yerda ishlaydigan workshop user'lar buni oʻzining `home_branch_id`'si sifatida ushlaydi
([`identity.md`](identity.md)). Status client'lar uni koʻrishi va undan order qilishini
boshqaradi.

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

Lifecycle: `active` — client'larga koʻrinadi, yangi order & cutting qabul qiladi;
`temporarily_closed` — koʻrinadi (closed sifatida, `closed_reason` bilan), yangi order
yoʻq; `inactive` — client'larga koʻrinmaydi, yangi order yoʻq, mavjud order'lar
complete boʻladi. Transition'lar owner-only. Hech qachon oʻchirilmaydi. Status'ni
oʻzgartirish staff session'lar yoki grant'larni **revoke qilmaydi**.

Invariant'lar: branch ostidagi hamma narsa (branch material selection'lar, stock, pricing)
bir xil workshop'ga tegishli; active order'li branch `inactive` qilib qoʻyilishi mumkin
(order'lar tugaydi; UI ogohlantiradi).

Material, Branch material (per-branch selection) va Branch pricing
[`catalog.md`](catalog.md)'da yotadi. Cutter'lar, edger'lar va office staff hammasi
[`identity.md`](identity.md)'dagi workshop user'lar — alohida `worker` entity yoʻq va fixed
role yoʻq.
