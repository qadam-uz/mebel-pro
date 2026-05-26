---
title: Inventory
status: draft
owner: shape
updated: 2026-05-25
order: 30
---

# Inventory

Branch'ning har bir material uchun ombor balance'i, append-only transaction log va stock
qaerdan kelishini koʻrsatuvchi supplier'lar. v1'da **reservation yoʻq**: order state
machine production tugashi bilan stock'ni **consume** qiladi va revert uni **restore**
qiladi — kontrakt [`orders.md`](../features/orders.md) → *The stock seam*'da.

## Stock item

Bir material uchun branch'ning balance'i — material'ning unit'idagi bitta on-hand qiymat
(`panel` material uchun panel'lar, `edge` uchun metr) va low-stock threshold. Branch boʻyicha
har bir material uchun bittadan.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `material_id` | UUID | required; `(branch_id, material_id)` unique |
| `on_hand` | int | quantity physically in the warehouse, in the material's unit; ≥ 0 |
| `min_stock` | int | low-stock alert threshold; ≥ 0 |
| `updated_at` | timestamp | |

Operation'lar (barchasi atomic; row davomi davomida `FOR UPDATE` orqali lock qilinadi):

- `stock_in(qty)`: `on_hand += qty` (warehouseman; supplier'dan).
- `adjust(delta)`: `on_hand += delta` (stock-take / write-off; ≥ 0 bilan chegaralangan;
  reason note majburiy).
- `consume(qty)`: `on_hand -= qty` — system, order state machine tomonidan boshqariladi.
- `restore(qty)`: `on_hand += qty` — system, consume qilingan step'ning operator revert'i.

Invariant'lar: doim `on_hand ≥ 0`; `(branch_id, material_id)` unique; stock faqat inventory
module'ning operation'lari orqali oʻzgaradi (hech qachon boshqa joydan raw SQL emas);
`consume` / `restore` `order_id` bilan keladi va actor'siz (system); `stock_in` / `adjust`
actor bilan keladi. Oʻzgarishdan keyin `on_hand ≤ min_stock` boʻlsa, branch'ning
`manage_inventory` grantee'lariga va owner'ga low-stock notification ketadi. Verify-time
"projected balance" warning'i ([`catalog-inventory.md`](../features/catalog-inventory.md))
read-time hisob, saqlanadigan field emas.

Edge `consume` / `restore` **edge material id** boʻyicha kalitlanadi (thickness boʻyicha
emas): `edge_banding → ready` transition order'ning `edge_length_snapshot`'i koʻtaradigan
har bir `shop` edge material uchun bittadan `consume` ishga tushiradi, har biri shu aynan
material'ning metr'lari uchun. Revert har bir material uchun bittadan `restore` ishga
tushiradi va consume'ni mirror qiladi.

## Stock transaction

Stock item'ga bir oʻzgarish uchun bitta audit row. Append-only.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `stock_item_id` | UUID | required |
| `type` | enum | `stock_in` / `consume` / `restore` / `adjust` |
| `quantity` | int | signed change, non-zero, in the material's unit |
| `balance_after` | int | `on_hand` after the change |
| `order_id` | UUID? | for `consume` / `restore`; null otherwise |
| `supplier_id` | UUID? | for `stock_in`; null otherwise |
| `actor_user_id` | UUID? | for `stock_in` / `adjust`; null when the system did it (`consume` / `restore`) |
| `note` | text? | supplier note, adjustment reason (required for `adjust`) |
| `created_at` | timestamp | |

Invariant'lar: oʻsha atomic operation'da qoʻllanilgan oʻzgarishga mos keladi;
`consume` / `restore` `order_id` bilan keladi va `actor_user_id`'siz; `stock_in`
`supplier_id` va `actor_user_id` bilan keladi; `adjust` `note` talab qiladi; hech qachon
yangilanmaydi yoki oʻchirilmaydi.

## Supplier

Branch'ning stock'i qaerdan kelganini bildiruvchi — workshop-scoped, yengil label,
stock-in form'idan kerak boʻlganda yaratiladi. v1'da purchase-order yoki payables flow
yoʻq; xarid pul'i alohida [`finance.md`](../features/finance.md) expense.
Supplier — workshop'ning xarid kontragenti; material'ning **manufacturer**'i
([`catalog.md`](catalog.md)) esa uni kim ishlab chiqargani — alohida tushunchalar (bitta
supplier bir nechta manufacturer'ning material'larini olib yurishi mumkin va aksincha).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `name` | text | required |
| `phone` | text? | optional |
| `note` | text? | optional |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_by_user_id` | UUID | the `manage_inventory` user who added it |
| `created_at` / `updated_at` | timestamp | |

Invariant'lar: `name` required; workshop-scoped (supplier bitta workshop'ga tegishli);
`manage_inventory` bilan user tomonidan yaratiladi; hech qachon oʻchirilmaydi (ishlatilmasa
deactivate qilinadi).

## Next

- [`catalog-inventory.md`](../features/catalog-inventory.md) — stock-in, adjust,
  the projected-balance warning, and the order seam mechanics.
- [`sales.md`](sales.md) — the order whose state machine consumes and restores stock.
