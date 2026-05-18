---
title: Sales
status: draft
owner: shape
updated: 2026-05-17
order: 50
---

# Sales

Order header, uning item'lari, status event'lari va bitta cancel event. Lifecycle rule'lar,
pricing, state machine va stock / money seam'lar [`orders.md`](../features/orders.md)'da.
Money (client nima toʻlagani, refund'lar) finance context'ida yotadi
([`finance.md`](finance.md)); order **hech qanday payment row**'ni ushlab turmaydi.

## Order

Client'ning branch'da size'ga kesilgan panel'lar uchun soʻrovi — item'larni, status
history'ni, production stamp'larni va frozen price snapshot'ni egallaydigan header. Faqat
client tomonidan, chosen algorithm result'li cutting draft'dan yaratiladi. v1 pickup-only;
order oʻzining confirmed cutting result'iga reference qiladi. Material source **per item** —
[Order item](#order-item)'ga qarang.

**Identity & lifecycle**

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_number` | text | human-readable, `ORD-2026-000123` (per-year sequence); unique |
| `client_id` | UUID | the client who placed it |
| `workshop_id` / `branch_id` | UUID | required (branch in the workshop) |
| `cutting_result_id` | UUID | the confirmed (current) cutting result |
| `status` | enum | `new` / `confirmed` / `cutting` / `edge_banding` / `ready` / `completed` / `cancelled`; default `new` |
| `version` | int | optimistic-lock counter for status transitions |
| `note_client` / `note_workshop` | text? | client and staff notes |
| `created_at` / `updated_at` / `confirmed_at` / `completed_at` / `cancelled_at` | timestamps | as the lifecycle moves |

**Pricing snapshot** (creation'da chosen branch'ning rate'lariga qarshi frozen qilinadi;
post-placement modification yoʻq, shuning uchun hech qachon re-price qilinmaydi)

| Field | Type | Notes |
|---|---|---|
| `subtotal_cutting_tiyin` / `subtotal_materials_tiyin` / `subtotal_edge_banding_tiyin` | bigint | snapshot subtotals (materials = 0 unless `shop`); each ≥ 0 |
| `discount_tiyin` | bigint | applied by a `manage_orders` user; ≥ 0; ≤ pre-discount total |
| `discount_reason` / `discount_applied_by_user_id` | text? / UUID? | required if `discount_tiyin > 0` |
| `total_tiyin` | bigint | `cutting + materials + edge banding − discount`; ≥ 0 |
| `currency` | enum | `UZS` (only value in v1) |

**Worker assignment + production stamps** (job tugagunicha assignment mutable; stamp'lar
set qilingach immutable va ularni set qilgan step'ning revert'i bilan cleared boʻladi —
ular [`finance.md`](../features/finance.md)'dagi worker-production report'larining yagona
input'i)

| Field | Type | Set at | Notes |
|---|---|---|---|
| `assigned_cutter_user_id` | UUID? | operator assigns | setting it is the `confirmed → cutting` trigger; holds `process_production` on the branch |
| `assigned_edger_user_id` | UUID? | operator assigns | set when the order has banded parts; holds `process_production` on the branch |
| `cutter_user_id` | UUID? | `cutting → next` | the user credited (assignee, or the on-behalf "who did this work?" pick) |
| `cut_completed_at` | timestamp? | `cutting → next` | |
| `sheets_used_snapshot` / `cut_count_snapshot` | int? | `cutting → next` | from the cutting result; production-report inputs |
| `edger_user_id` | UUID? | `edge_banding → ready` | the user credited; null when the order had no banded parts |
| `edge_completed_at` | timestamp? | `edge_banding → ready` | |
| `edge_length_snapshot` | json? | `edge_banding → ready` | `{ "0.4": 12500, "2.0": 4800 }` metres of banding by thickness |
| `picked_up_at` | timestamp? | `ready → completed` | |

Invariant'lar: faqat client tomonidan, `chosen` result'li cutting draft'dan yaratiladi
(u `confirmed` boʻladi va bound qilinadi); barcha money field'lar integer tiyin;
`total_tiyin` formula'ga ergashadi va negative boʻla olmaydi; price snapshot creation'da
frozen qilinadi (re-pricing yoʻq — modification yoʻq); status transition'lar faqat state
machine'ga ergashadi; concurrent transition'lar `version` boʻyicha serialize boʻladi;
`cutter_user_id` / `edger_user_id` `branch_id`'da `process_production`'ni ushlab turadigan
workshop user'larga reference qiladi; production stamp'lar oʻz transition'i bilan bir xil
atomic transaction'da set qilinadi va shu step'ning **revert'i bilan cleared boʻladi**;
stock inventory module tomonidan har bir `shop` item boʻyicha auto-decrement qilinadi
(sheet'lar `cutting →` next'da, edge'lar `edge_banding → ready`'da) — order hech qanday
stock balance ushlamaydi; `completed` va `cancelled` terminal; order hech qachon
oʻchirilmaydi (`cancelled`'ga ketadi).

## Order item

Order'ning bitta part line'i — berilgan dimensions va quantity'dagi panel, optional edge
banding, plus u kesilgan material'ning va ishlatilgan price'larning frozen snapshot'i.
Item'lar client shu order uchun cutting wizard'iga kiritgan part'larni mirror qiladi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `material_id` | UUID | logical reference (the snapshot is authoritative for the order) |
| `material_source` | enum | `shop` / `own` — per-item; an order can mix sources |
| `material_snapshot` | json | `{ name, type, thickness_mm, color, decor_code, sheet_length_mm, sheet_width_mm, price_tiyin }` as of order creation |
| `part_ref` | text | the part's id (matches the cutting result's parts snapshot / placements) |
| `length_mm` / `width_mm` | int | within material / cutting bounds |
| `quantity` | int | ≥ 1 |
| `edge_top_mm` / `edge_bottom_mm` / `edge_left_mm` / `edge_right_mm` | numeric? | edge-banding thickness per side, or null |
| `unit_cutting_price_tiyin` | bigint | snapshot, ≥ 0 |
| `unit_material_price_tiyin` | bigint | snapshot; 0 when `material_source = own`; ≥ 0 |
| `edge_cost_tiyin` | bigint | snapshot for this line; ≥ 0 |
| `line_total_tiyin` | bigint | `(unit_cutting + unit_material) × quantity + edge_cost`; ≥ 0 |

Invariant'lar: snapshot field'lar keyingi catalog oʻzgarishlarini aks ettirish uchun hech
qachon update qilinmaydi; `part_ref` order'ning cutting result'idagi part'ga toʻgʻri
keladi; grain item'ning material'ining property'si (`material_snapshot`'dan oʻqiladi);
grained material'dagi part'lar cutting vaqtida rotate qilinmaydi. Modify path yoʻq —
item'lar order bilan yaratiladi va hech qachon almashtirilmaydi.

## Order status event

Har bir status transition uchun bitta row — kim qildi, qaysi state'dan qaysiga, nega
(reason talab qilinganda) va har qanday context. Order'ning audit trail'i; shuningdek
global [status change log](support.md#status-change-log)'ga mirror qilinadi. Append-only;
order timeline shundan quriladi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `from_status` | enum? | null for the creation event |
| `to_status` | enum | required; a valid transition target (including a revert step) |
| `actor_type` | enum | `client` / `workshop_user` / `system` |
| `actor_user_id` / `actor_client_id` | UUID? / UUID? | mutually exclusive (or both null if `system`) |
| `reason` | text? | required for cancellations and reverts |
| `metadata` | json? | optional context (e.g. the credited user on an on-behalf completion) |
| `changed_at` | timestamp | |

Invariant'lar: **har bir** transition uchun bir xil atomic operation'da yoziladi;
`to_status` state machine boʻyicha `from_status`'dan legal transition (yoki revert);
cancellation va revert `reason` olib yuradi; hech qachon update yoki delete qilinmaydi.

## Order cancellation

Bitta cancel event: kim cancel qildi, qaysi sifatda va nega. Order koʻpi bilan bir marta
cancel qilinadi (keyin terminal). Allaqachon toʻlangan money offline qaytariladi va
finance module'da expense sifatida record qilinadi — refund entity yoʻq.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required; **unique** (one cancellation per order) |
| `cancelled_by_type` | enum | `client` (only while `new`) / `workshop_user` |
| `cancelled_by_user_id` / `cancelled_by_client_id` | UUID? / UUID? | mutually exclusive |
| `reason` | text | mandatory; non-trivially short |
| `cancelled_at` | timestamp | |

Invariant'lar: har bir order uchun aniq bitta cancellation (DB unique); `reason`
mandatory; cancel qiluvchi tomon order'ning status'ida [`orders.md`](../features/orders.md)
boʻyicha ruxsat etilgan (`workshop_user` har qanday pre-`completed` state'da
`manage_orders` bilan; `client` faqat `new` ekan); allaqachon decrement qilingan material
restore qilinmaydi.

## Next

- [`orders.md`](../features/orders.md) — bu row'larni boshqaradigan state machine,
  pricing va stock / money seam'lar.
- [`finance.md`](../features/finance.md) — order income va stamp'lar feed qiladigan
  worker-production report'lar.
