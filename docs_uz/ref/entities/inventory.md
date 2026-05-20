---
title: Inventory
status: draft
owner: shape
updated: 2026-05-20
order: 30
---

# Inventory

Branch'ning har bir material boʻyicha warehouse balance'i, append-only transaction log va
stock keladigan supplier'lar. v1'da **reservation yoʻq**: order state machine production
yakunlanganda stock'ni **consume** qiladi va revert uni **restore** qiladi — contract
[`orders.md`](../features/orders.md) → *The stock seam*'da.

## Stock item

Branch'ning bitta material boʻyicha balance'i — material'ning unit'ida bitta on-hand
quantity (`sheet` material uchun sheet'lar, `edge` uchun metrlar) va low-stock threshold.
Har bir branch'da har bir material uchun bittadan.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `material_id` | UUID | required; `(branch_id, material_id)` unique |
| `on_hand` | int | quantity physically in the warehouse, in the material's unit; ≥ 0 |
| `min_stock` | int | low-stock alert threshold; ≥ 0 |
| `updated_at` | timestamp | |

Operation'lar (hammasi atomic; row davomida `FOR UPDATE` lock qilinadi):

- `stock_in(qty)`: `on_hand += qty` (warehouseman; supplier'dan).
- `adjust(delta)`: `on_hand += delta` (stock-take / write-off; ≥ 0 bilan bounded; reason
  note required).
- `consume(qty)`: `on_hand -= qty` — system, order state machine tomonidan boshqariladi.
- `restore(qty)`: `on_hand += qty` — system, consumed step'ning operator revert'i.

Invariant'lar: doim `on_hand ≥ 0`; `(branch_id, material_id)` unique; stock faqat
inventory module'ning operation'lari orqali oʻzgaradi (boshqa joydan hech qachon raw SQL
emas); `consume` / `restore` `order_id`'ni olib yuradi va actor'siz (system); `stock_in` /
`adjust` actor olib yuradi. O'zgarishdan keyin `on_hand ≤ min_stock`
boʻlganda branch'ning `manage_inventory` grantee'lariga va owner'ga low-stock notification
fire qilinadi. Verify-time "projected balance" warning
([`catalog-inventory.md`](../features/catalog-inventory.md)) bu read-time computation,
stored field emas.

## Stock transaction

Stock item'ga bitta oʻzgarish uchun bitta audit row. Append-only.

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

Invariant'lar: bir xil atomic operation'da apply qilingan oʻzgarishga mos keladi;
`consume` / `restore` `order_id`'ni olib yuradi va `actor_user_id`'siz; `stock_in`
`supplier_id` va `actor_user_id`'ni olib yuradi; `adjust` `note` talab qiladi; hech
qachon update yoki delete qilinmaydi.

## Supplier

Branch'ning stock'i qayerdan kelgani — yengil, workshop-scoped label, stock-in form'dan
on-demand yaratiladi. v1'da purchase-order yoki payables flow yoʻq; purchase uchun money
bu alohida [`finance.md`](../features/finance.md) expense.

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
`manage_inventory`'ga ega user tomonidan yaratiladi; hech qachon oʻchirilmaydi
(ishlatilmasa deactivate qilinadi).

## Next

- [`catalog-inventory.md`](../features/catalog-inventory.md) — stock-in, adjust,
  projected-balance warning va order seam mexanikasi.
- [`sales.md`](sales.md) — state machine'i stock'ni consume va restore qiladigan order.
