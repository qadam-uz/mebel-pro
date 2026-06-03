---
title: Sales
status: draft
owner: shape
updated: 2026-06-03
order: 50
---

# Sales

Order header, uning item'lari, status event'lar va bitta cancel event. Lifecycle rule'lari,
pricing, state machine va stock / money seam'lari [`orders.md`](../features/orders.md)'da.
Pul (client nima toʻladi, refund'lar) finance context'da yashaydi
([`finance.md`](finance.md)); order **hech qanday payment row'larini** ushlab turmaydi.

## Order

Client'ning branch'da oʻlchamga kesilgan panel'ga boʻlgan request'i — item'larni, status
history'ni, production stamp'larni va frozen price snapshot'ni ushlab turadigan header.
Faqat client tomonidan yaratiladi, chosen algorithm result'iga ega cutting draft'dan. v1
pickup-only; order oʻzining confirmed cutting result'iga reference qiladi. Material source
panel uchun **per item** va har bir edge uchun **per side** — [Order item](#order-item)'ga
qarang.

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

**Pricing snapshot** (creation paytida tanlangan branch'ning rate'lariga qarshi muzlatiladi;
post-placement modification yoʻq, shuning uchun hech qachon qayta price qilinmaydi)

| Field | Type | Notes |
|---|---|---|
| `subtotal_cutting_tiyin` | bigint | snapshot subtotal — `Σ panels × cutting_rate_tiyin` at this branch; ≥ 0 |
| `subtotal_materials_tiyin` | bigint | snapshot subtotal — `shop`-source panel cost; ≥ 0 |
| `subtotal_edge_banding_tiyin` | bigint | snapshot subtotal — `shop`-source edge cost; ≥ 0 |
| `discount_tiyin` | bigint | applied by a `manage_orders` user; ≥ 0; ≤ pre-discount total |
| `discount_reason` / `discount_applied_by_user_id` | text? / UUID? | required if `discount_tiyin > 0` |
| `total_tiyin` | bigint | `cutting + materials + edge banding − discount`; ≥ 0 |
| `currency` | enum | `UZS` (only value in v1) |

**Worker assignment + production stamps** (job done boʻlmagunicha assignment oʻzgaruvchan;
stamp'lar bir marta set qilinsa immutable va ularni qoʻygan step'ning revert'ida tozalanadi
— ular [`finance.md`](../features/finance.md)'dagi worker-production report'larining yagona
input'i)

| Field | Type | Set at | Notes |
|---|---|---|---|
| `assigned_cutter_user_id` | UUID? | operator assigns | setting it is the `confirmed → cutting` trigger; holds `process_production` on the branch |
| `assigned_edger_user_id` | UUID? | operator assigns | set when the order has banded parts; holds `process_production` on the branch |
| `cutter_user_id` | UUID? | `cutting → next` | the user credited (assignee, or the on-behalf "who did this work?" pick) |
| `cut_completed_at` | timestamp? | `cutting → next` | |
| `panels_used_snapshot` / `cut_count_snapshot` | int? | `cutting → next` | from the cutting result; production-report inputs |
| `edger_user_id` | UUID? | `edge_banding → ready` | the user credited; null when the order had no banded parts |
| `edge_completed_at` | timestamp? | `edge_banding → ready` | |
| `edge_length_snapshot` | json? | `edge_banding → ready` | `{ "<edge-material_id>": 12500, "<edge-material_id>": 4800 }` — consumed banding length in integer millimetres by edge material (only `shop` source). UI/reports metres sifatida koʻrsatadi. Thickness is derived from each material at report read time. |
| `picked_up_at` | timestamp? | `ready → completed` | |

Invariant'lar: faqat client tomonidan yaratiladi, `chosen` result'iga ega cutting draft'dan
(`confirmed` boʻladi va bind qilinadi); barcha money field integer tiyin; `total_tiyin`
formulaga rioya qiladi va manfiy boʻla olmaydi; price snapshot creation'da muzlatiladi
(qayta price qilish yoʻq — modification yoʻq); status transition'lar faqat state machine
boʻyicha; concurrent transition'lar `version` orqali serialize boʻladi; `cutter_user_id` /
`edger_user_id` `branch_id`'da `process_production` ushlab turgan workshop user'larga
reference qiladi; production stamp'lar oʻz transition'lari bilan bir xil atomic
transaction'da set qilinadi va oʻsha step'ning **revert'i tomonidan tozalanadi**; stock
inventory module tomonidan har bir `shop` source uchun avto-decrement qilinadi
(`cutting → next`'da panel'lar, `edge_banding → ready`'da edge'lar, per edge material) —
order stock balance ushlab turmaydi; `completed` va `cancelled` terminal; order hech qachon
oʻchirilmaydi (u `cancelled` boʻladi).

## Order item

Order'ning bir part line'i — berilgan oʻlcham va quantity'dagi panel, **har bir side uchun**
ixtiyoriy edge banding, plus panel va har bir side edge'ning frozen snapshot'lari (order
uchun snapshot'lar authoritative) va ishlatilgan price'lar. Item'lar client'ning shu order
uchun cutting wizard'ga kiritgan part'larini aks ettiradi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required |
| `material_id` | UUID | logical reference to the panel material (the snapshot is authoritative for the order) |
| `material_source` | enum | `shop` / `own` — for the panel; per-item; an order can mix |
| `material_snapshot` | json | `{ name, type, thickness_mm, color, decor_code, manufacturer_name, panel_length_mm, panel_width_mm, price_tiyin }` as of order creation |
| `part_ref` | text | the part's id (matches the cutting result's parts snapshot / placements) |
| `length_mm` / `width_mm` | int | within material / cutting bounds |
| `quantity` | int | ≥ 1 |
| `edge_top` / `edge_bottom` / `edge_left` / `edge_right` | json? | per side: either null (no banding) or `{ material_id, source, snapshot: { name, manufacturer_name, thickness_mm, color, decor_code, price_tiyin } }` |
| `unit_cutting_price_tiyin` | bigint | snapshot, ≥ 0 |
| `unit_material_price_tiyin` | bigint | snapshot; 0 when panel `material_source = own`; ≥ 0 |
| `edge_cost_tiyin` | bigint | snapshot for this line — sum across the four sides of `shop` edge cost; 0 when every banded side is `own`; ≥ 0 |
| `line_total_tiyin` | bigint | `(unit_cutting + unit_material) × quantity + edge_cost`; ≥ 0 |

Invariant'lar: snapshot field'lar keyingi catalog oʻzgarishlarini aks ettirish uchun hech
qachon yangilanmaydi; `part_ref` order'ning cutting result'idagi part'ga mos keladi; panel
`material_id` `panel`-kind material; har bir side'ning edge `material_id`'i (set boʻlganda)
`edge`-kind material; grain panel material'ning xususiyati (`material_snapshot`'dan
oʻqiladi); grained material'dagi part cutting vaqtida rotate qilinmaydi; per-side `source`
mustaqil va bir item'ning side'lari boʻyicha turlicha boʻlishi mumkin. Modify path yoʻq —
item'lar order bilan birga yaratiladi va hech qachon almashtirilmaydi.

## Order status event

Har bir status transition uchun bitta row — kim qildi, qaysi state'dan qaysi state'ga, nima
uchun (reason talab qilinganda) va har qanday context. Order'ning audit trail'i; shuningdek
global [status change log](support.md#status-change-log)'ga ham mirror qilinadi. Append-only;
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

Invariant'lar: bitta atomic operation'da **har bir** transition uchun yoziladi; `to_status`
state machine boʻyicha `from_status`'dan legal transition (yoki revert); cancellation va
revert `reason` bilan keladi; hech qachon yangilanmaydi yoki oʻchirilmaydi.

## Order cancellation

Bitta cancel event: kim cancel qildi, qanday sifatda va nima uchun. Order koʻpi bilan bir
marta cancel qilinadi (keyin terminal). Allaqachon toʻlangan pul offline qaytariladi va
finance module'da expense sifatida yoziladi — refund entity yoʻq.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `order_id` | UUID | required; **unique** (one cancellation per order) |
| `cancelled_by_type` | enum | `client` (only while `new`) / `workshop_user` |
| `cancelled_by_user_id` / `cancelled_by_client_id` | UUID? / UUID? | mutually exclusive |
| `reason` | text | mandatory; non-trivially short |
| `cancelled_at` | timestamp | |

Invariant'lar: har bir order uchun aniq bitta cancellation (DB unique); `reason` mandatory;
cancel qiluvchi tomon order'ning status'ida [`orders.md`](../features/orders.md) boʻyicha
ruxsat etilgan (har qanday pre-`completed` state'da `manage_orders` bilan `workshop_user`;
faqat `new` paytida `client`); allaqachon decrement qilingan material qayta tiklanmaydi.

## Next

- [`orders.md`](../features/orders.md) — the state machine, pricing, and the stock / money
  seams that govern these rows.
- [`finance.md`](../features/finance.md) — order income and the worker-production reports
  the stamps feed.
