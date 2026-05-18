---
title: Cutting
status: draft
owner: shape
updated: 2026-05-16
order: 40
---

# Cutting

Client'ning cutting workspace'i (draft) va optimisation run'lar natijasi (har bir algorithm
uchun bitta result). Client iteratsiya qilayotganda draft'lar mutable; result'lar
immutable. Rule'lar [`cutting.md`](../features/cutting.md)'da.

## Cutting draft

Client'ning bitta part'lar toʻplami uchun tahrirlanadigan workspace'i. Part'lar list'ini,
eng soʻnggi optimisation run'ining result'larini (har bir algorithm uchun bittadan —
quyiga qarang) va client tanlagan result'ni ushlab turadi. Client'ga private. Cheksiz
saqlanadi (expiry yoʻq); client bir vaqtning oʻzida koʻpi bilan 50 ta draft ochiq tutishi
mumkin.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `client_id` | UUID | the client who owns it |
| `parts_snapshot` | json | the parts list as the client has edited it — each part has `part_ref` (UUID), `material_id`, `material_source` (`shop` / `own`), `length_mm`, `width_mm`, `quantity`, and per-side `edge_*_mm` (top / bottom / left / right; each `0.4` / `2.0` / null). Grain is derived from the material (not stored on the part). |
| `chosen_result_id` | UUID? | the result the client picked from the latest run; null between edits and the next optimise |
| `created_at` / `updated_at` | timestamps | |

Invariant'lar: client tomonidan yaratiladi, unga tegishli, hech qachon share qilinmaydi;
`parts_snapshot`'da 1..100 part boʻladi; har optimise'da oldingi run'ning result'lari
almashtiriladi va `chosen_result_id` qayta yoʻnaltiriladi (default sifatida eng kam waste'li
algorithm'ga); draft'da bir vaqtning oʻzida koʻpi bilan bitta `chosen` boʻladi; order
placement'da chosen result `confirmed`'ga oʻtadi (order'ga bound boʻladi) va draft +
tanlanmagan result'lar oʻchiriladi; client tomonidan istalgan vaqtda deletable (result'lar,
sheet'lar, placement'larga cascade qiladi).

## Cutting result

Draft'ning part'lari ustida **bitta algorithm**'ning output'i. Bitta optimise call N ta
result chiqaradi (har bir mavjud algorithm uchun bittadan); keyingi optimise call ularni
almashtirgunicha hammasi saqlanadi va client bittasini `chosen` qilib oladi. Order
placement'da chosen result `confirmed` boʻladi va bound qilinadi; qolganlari tashlab
yuboriladi. Algorithm version stamp qilinadi — algorithm'ni keyin almashtirish oʻtgan
result'larga tegmaydi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `draft_id` | UUID? | the draft this result came from; null once `confirmed` (the draft is gone, the result outlives it via `order_id`) |
| `algorithm_name` / `algorithm_version` | text | e.g. `ffd-guillotine` / `1.0` — stamped at run time |
| `status` | enum | `candidate` (one of N from an optimise run) · `confirmed` (chosen and bound to an order) · `invalidated` (was confirmed; an order modify produced a fresher result) |
| `kerf_mm` / `edge_trim_mm` | int | snapshot of the global constants at run time |
| `sheets_used_by_material` | json | `{ "<material_id>": 3, "<material_id>": 1 }` — total sheets needed per material in this result (≤ 20 per material) |
| `waste_percentage` | numeric | 0.0–1.0; weighted across all materials in the result |
| `total_cut_length_mm` / `total_edge_length_mm` | int | feed pricing metrics |
| `edge_length_by_thickness` | json | `{ "0.4": 12500, "2.0": 4800 }` — per-thickness pricing input, summed across materials |
| `order_id` | UUID? | the order it's bound to, once `confirmed` |
| `created_at` / `confirmed_at` / `invalidated_at` | timestamps | as the lifecycle moves |

Lifecycle: optimise'da `candidate` → order placement'da `confirmed` (`order_id` set,
`confirmed_at`, `draft_id` cleared) → order fresh result kerak boʻladigan tarzda modify
qilinganda `invalidated` (yangi result bound qilinadi; bunisi saqlanadi). `confirmed` va
`invalidated` abadiy saqlanadi; `candidate` result'lar qisqa umrli (keyingi optimise
call'da, tanlanmagan order placement'da, yoki draft bilan birga oʻchiriladi).

Invariant'lar: yaratilgandan keyin **immutable** — faqat `status`, `order_id`,
`confirmed_at`, `invalidated_at` va `draft_id` (confirm'da cleared) oʻzgaradi; layout,
metric'lar va per-sheet row'lar hech qachon oʻzgarmaydi. `confirmed` / `invalidated`
result'da non-null `order_id` boʻladi; `candidate`'da non-null `draft_id` boʻladi.
`sheets_used_by_material`'dagi har bir material uchun count ≤ 20; result'da source
parts list'idan har bir part-instance'ni qoplaydigan placement'lar boʻladi. `candidate`
ekan faqat draft'ining creator'iga; `confirmed` / `invalidated` boʻlgach scope'dagi
workshop staff'ga va client'ga koʻrinadi.

## Cutting sheet

Result ichidagi bitta physical sheet — uning material'i, shu material ichidagi index'i va
qancha waste'i borligi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_result_id` | UUID | required |
| `material_id` | UUID | required — which material this sheet is, and which sheet-size + grain rules govern its placements |
| `sheet_index` | int | 1, 2, 3, … **within the result's sheets of this material**; unique per (result, material); 1..the material's count in `sheets_used_by_material` |
| `waste_area_mm2` | bigint | ≥ 0 |

Invariant'lar: `sheet_index` shu result uchun shu material'ning count'igacha 1'dan
contiguous; immutable; oʻzining parent result'i bilan oʻchiriladi.

## Cutting placement

Bitta sheet ustidagi bitta placed part: u qaysi input part ekanligi, qayerda joylashgani
(origin bottom-left'dan), placed dimensions'lari (agar rotate qilingan boʻlsa part'ning
nominal dimensions'idan farq qiladi) va 90° rotate qilinganmi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_sheet_id` | UUID | required |
| `part_ref` | text | the part id from the draft's `parts_snapshot` |
| `part_quantity_index` | int | 1..quantity, when the part has quantity > 1; ≥ 1 |
| `x_mm` / `y_mm` | int | origin (bottom-left corner) on the sheet; within the usable area |
| `length_mm` / `width_mm` | int | dimensions as placed |
| `rotated` | bool | `true` if rotated 90° from the part's nominal orientation |

Invariant'lar: source parts list'dagi har bir input part-instance (har bir `part_ref` × har
bir quantity index) result'ning placement'lari boʻylab aniq bir marta paydo boʻladi;
placement `material_id`'si part'ning material'iga mos keladigan sheet ustida oʻtiradi;
grained material'dagi part hech qachon `rotated` emas; placement'lar overlap qilmaydi va
`sheet − 2× edge_trim` ichida qoladi; immutable.
