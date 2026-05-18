---
title: Finance
status: draft
owner: shape
updated: 2026-05-17
order: 55
---

# Finance

Workshop'ning money ledger'i: olingan **income** va qilingan **expense**. Rule'lar —
income type'lari, order link'i, client nima koʻrishi, accountant qoʻlda salary hisoblash
uchun ishlatadigan worker-production report'lari — [`finance.md`](../features/finance.md)'da
yotadi. v1'da payroll engine ham, compensation policy ham yoʻq; salary shunchaki accountant
record qiladigan expense.

## Income

Workshop olgan money, `manage_finance`'ga ega user tomonidan record qilinadi. Typed;
`order_payment` type u settle qiladigan order'ni olib yuradi, qolganlari hech narsa olib
yurmaydi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `branch_id` | UUID? | the branch the money is attributed to; for `order_payment` it is the order's branch |
| `type` | enum | `order_payment` / `other` |
| `order_id` | UUID? | **required iff `type = order_payment`**; null otherwise; an order in the workshop |
| `amount_tiyin` | bigint | > 0 (full order amount or a partial payment) |
| `method` | enum | `cash` / `bank_transfer` / `other` |
| `received_on` | date | when the money changed hands |
| `note` | text? | bank reference / receipt id |
| `receipt_file_id` | UUID? | → [file](support.md#file) — optional scan |
| `status` | enum | `recorded` / `voided` |
| `voided_reason` | text? | required when `status = voided` |
| `recorded_by_user_id` | UUID | the `manage_finance` user who recorded it |
| `voided_by_user_id` / `voided_at` | UUID? / timestamp? | required when voided |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `recorded` → `voided` (majburiy reason). Voided income report'lardan va order'ning
paid total'idan chiqarib tashlanadi. Delete yoʻq; row audit uchun saqlanadi.

Invariant'lar: `amount_tiyin > 0`; `order_id` **iff** `type = order_payment` mavjud;
`branch_id` (set qilinganda) bir xil workshop'ga tegishli; bitta order uchun uning
`recorded` `order_payment` income'lari yigʻindisi **≤ order'ning `total_tiyin`'i** deb
validate qilinadi; `received_on` future'da emas; faqat tegishli branch'da (yoki
workshop-wide) `manage_finance`'ga ega user'lar tomonidan record / void qilinadi; hech
qachon oʻchirilmaydi.

## Expense

Workshop sarflagan money — overhead'lar, sotib oladigan consumable'lar va **staff salary**
(accountant uni worker-production report'laridan hisoblaydi va shu yerda book qiladi;
system hech qanday salary calculation bajarmaydi).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required |
| `branch_id` | UUID? | nullable — workshop-level costs (e.g. HQ rent) have no branch |
| `category` | enum | `rent` / `utilities` / `raw_materials` / `supplies` / `transport` / `equipment` / `marketing` / `taxes_and_fees` / `salary` / `other` |
| `amount_tiyin` | bigint | > 0 |
| `incurred_on` | date | required; not in the future |
| `description` | text | required; short human description |
| `vendor` | text? | who was paid (optional free text) |
| `receipt_file_id` | UUID? | → [file](support.md#file) — optional scan |
| `status` | enum | `recorded` / `voided` |
| `voided_reason` | text? | required when `status = voided` |
| `recorded_by_user_id` | UUID | the `manage_finance` user who recorded it |
| `voided_by_user_id` / `voided_at` | UUID? / timestamp? | required when voided |
| `created_at` / `updated_at` | timestamp | |

Lifecycle: `recorded` → `voided` (majburiy reason); voided expense report'lardan chiqarib
tashlanadi. Delete yoʻq; row audit uchun saqlanadi.

Invariant'lar: `amount_tiyin > 0`; `branch_id` set qilinganda bir xil workshop'ga tegishli;
`incurred_on` future'da emas; faqat tegishli branch'da (yoki workshop-wide)
`manage_finance`'ga ega user'lar tomonidan record / void qilinadi; void qilish reason va
user talab qiladi; hech qachon oʻchirilmaydi.

## Next

- [`finance.md`](../features/finance.md) — income type'lari, order link'i,
  worker-production report'lari va shu row'lar feed qiladigan finance report'lar.
- [`sales.md`](sales.md) — `order_payment` settle qiladigan order va report'lar oʻqiydigan
  production stamp'lar.
