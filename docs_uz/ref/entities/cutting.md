---
title: Cutting
status: draft
owner: shape
updated: 2026-06-03
order: 40
---

# Cutting

Client'ning cutting workspace'i (draft) va optimisation run'larining output'i (har bir
algorithm uchun bittadan result). Client iterate qilayotganda draft'lar oʻzgaruvchan;
result'lar immutable. Rule'lar [`cutting.md`](../features/cutting.md)'da.

## Cutting draft

Client'ning bir set part uchun tahrirlanadigan workspace'i. Part'lar list'ini, eng oxirgi
optimisation run'ining result'larini (har bir algorithm uchun bittadan — pastga qarang),
client'ning tanlangan result'ini va ixtiyoriy intended-branch pre-filter'ni ushlab turadi.
Client'ga private. Cheksiz saqlanadi (expiry yoʻq); bir client bir vaqtning oʻzida 50 ta
draft'gacha ochiq tutishi mumkin.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `client_id` | UUID | the client who owns it |
| `preferred_branch_id` | UUID? | optional — when set, the material picker is pre-filtered to this branch's selection; the order step defaults to it. Seeded from the client's `preferred_branch_id` on draft create; the client can clear or change it on the draft without affecting the profile default. Never enforces destructively (rows referencing materials this branch doesn't carry stay editable with inline recovery affordances — see [`cutting.md`](../features/cutting.md)). |
| `parts_snapshot` | json | the parts list as the client has edited it — each part has `part_ref` (UUID), `material_id` (a `panel`), `material_source` (`shop` / `own`), `length_mm`, `width_mm`, `quantity`, and per-side `edge_<top\|bottom\|left\|right>` — each either `null` (no banding on that side) or `{ "material_id": <edge-material>, "source": "shop" \| "own" }`. Grain is derived from the panel material (not stored on the part); edge thickness/colour are derived from each side's edge material. |
| `chosen_result_id` | UUID? | the result the client picked from the latest run; null between edits and the next optimise |
| `created_at` / `updated_at` | timestamps | |

Invariant'lar: client tomonidan yaratiladi, unga tegishli, hech qachon ulashilmaydi;
`parts_snapshot`'da 1..100 part bor; har bir reference qilingan `material_id` `panel`-kind
material; har bir side'ning `edge_*`'i (null boʻlmaganda) `edge`-kind material'ga reference
qiladi; har optimise'da oldingi run'ning result'lari almashtiriladi va `chosen_result_id`
qayta yoʻnaltiriladi (default'da eng past waste'li algorithm'ga); draft'da bir vaqtning
oʻzida koʻpi bilan bitta `chosen` boʻladi; order placement'da tanlangan result `confirmed`'ga
oʻtadi (order'ga bind qilinadi) va draft + tanlanmagan result'lar oʻchiriladi; client uni
istalgan vaqtda oʻchirishi mumkin (result'lar, panel'lar, placement'lar cascade tarzida
oʻchadi).

## Cutting result

Draft'ning part'larida **bitta algorithm**'ning output'i. Bitta optimise call N ta result
ishlab chiqaradi (har bir mavjud algorithm uchun bittadan); barchasi keyingi optimise call
ularni almashtirgunicha saqlanadi va client bittasini `chosen` deb tanlaydi. Order
placement'da tanlangan result `confirmed` boʻladi va bind qilinadi; boshqalari oʻchiriladi.
Algorithm version stamp qilinadi — algorithm'ni keyinroq almashtirish oʻtgan result'larga
tegmaydi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `draft_id` | UUID? | the draft this result came from; null once `confirmed` (the draft is gone, the result outlives it via `order_id`) |
| `algorithm_name` / `algorithm_version` | text | e.g. `ffd-guillotine` / `1.0` — stamped at run time |
| `status` | enum | `candidate` (one of N from an optimise run) · `confirmed` (chosen and bound to an order) · `invalidated` (was confirmed; an order modify produced a fresher result) |
| `kerf_mm` / `edge_trim_mm` | int | snapshot of the global constants at run time |
| `panels_used_by_material` | json | `{ "<material_id>": 3, "<material_id>": 1 }` — total panels needed per `panel` material in this result (≤ 20 per material) |
| `waste_percentage` | numeric | 0.0–1.0; weighted across all panel materials in the result |
| `total_cut_length_mm` / `total_edge_length_mm` | int | feed pricing metrics |
| `edge_length_by_material` | json | `{ "<edge-material_id>": 12500, "<edge-material_id>": 4800 }` — per-edge-material geometric length integer millimetre'da; UI/pricing metre sifatida koʻrsatadi. |
| `parts_snapshot` | json | optimise vaqtida draft'dan copy qilingan source parts, shuning uchun result order placement'da draft oʻchirilgandan keyin ham render qilinadi |
| `material_snapshots` | json | result reference qiladigan har bir panel/edge material uchun optimise vaqtida copy qilingan material display/spec fact'lari; catalog edit'laridan keyin label va PDF uchun ishlatiladi |
| `edge_length_shop_by_material` / `edge_length_own_by_material` | json | source-split geometric edge length, edge material id boʻyicha keyed, integer millimetre'da |
| `edge_consumed_shop_by_material` / `edge_consumed_own_by_material` | json | source-split edge consumption, edge material id boʻyicha keyed, integer millimetre'da; har bir banded side uchun fixed 30 mm overhang'ni qoʻshadi |
| `edge_banded_sides_by_material` | json | `{ "<edge-material_id>": { "shop": 4, "own": 2 } }` — consumption va Phase 5 stock math'ni feed qiladigan source-split banded side count |
| `order_id` | UUID? | the order it's bound to, once `confirmed` |
| `created_at` / `confirmed_at` / `invalidated_at` | timestamps | as the lifecycle moves |

Lifecycle: optimise'da `candidate` → order placement'da `confirmed` (`order_id` set,
`confirmed_at`, `draft_id` clear) → order'ni modify qilish yangi result kerak qiladigan
holatda `invalidated` (yangi result bind qilinadi; bu esa saqlanadi). `confirmed` va
`invalidated` cheksiz saqlanadi; `candidate` result'lar qisqa muddatli (keyingi optimise
call'da, ular tanlanmagan order placement'da yoki draft bilan birga oʻchiriladi).

Invariant'lar: yaratilgandan keyin **immutable** — faqat `status`, `order_id`,
`confirmed_at`, `invalidated_at` va `draft_id` (confirm'da clear qilinadi) oʻzgaradi;
layout, metric, snapshot va per-panel row'lar hech qachon oʻzgarmaydi. Result draft
oʻchirilgandan yoki catalog display fact'lari oʻzgargandan keyin confirmed plan'ni render
qilish uchun yetarli source/material snapshot'larni olib yuradi. `confirmed` / `invalidated`
result'ning `order_id`'i null emas; `candidate`'ning `draft_id`'i null emas.
`panels_used_by_material`'dagi har bir material uchun count ≤ 20; result manba parts
list'idagi har bir part-instance'ni qoplaydigan placement'lar bilan keladi. `candidate`
holatida faqat draft yaratuvchisiga koʻrinadi; `confirmed` / `invalidated` boʻlganda
scope'idagi workshop staff'iga va client'ga koʻrinadi.

## Cutting panel

Result ichidagi bitta fizik panel — uning material'i, oʻsha material doirasidagi index'i va
qancha waste'ga ega ekanligi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_result_id` | UUID | required |
| `material_id` | UUID | required — which `panel` material this panel is, and which panel-size + grain rules govern its placements |
| `panel_index` | int | 1, 2, 3, … **within the result's panels of this material**; unique per (result, material); 1..the material's count in `panels_used_by_material` |
| `waste_area_mm2` | bigint | ≥ 0 |

Invariant'lar: `panel_index` shu result uchun shu material'ning count'igacha 1'dan boshlab
ketma-ket; immutable; parent result bilan birga oʻchiriladi.

## Cutting placement

Bir panel'dagi bir joylashtirilgan part: qaysi input part ekanligi, qayerda turishi (origin
pastki-chap burchakdan), joylashtirilgan oʻlchamlari (agar part 90° aylantirilgan boʻlsa,
ular part'ning nominal oʻlchamlaridan farq qiladi) va 90° aylantirilgan-aylantirilmaganligi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `cutting_panel_id` | UUID | required |
| `part_ref` | text | the part id from the draft's `parts_snapshot` |
| `part_quantity_index` | int | 1..quantity, when the part has quantity > 1; ≥ 1 |
| `x_mm` / `y_mm` | int | origin (bottom-left corner) on the panel; within the usable area |
| `length_mm` / `width_mm` | int | dimensions as placed |
| `rotated` | bool | `true` if rotated 90° from the part's nominal orientation |

Invariant'lar: manba parts list'idagi har bir part-instance (har bir `part_ref` × har bir
quantity index) result'ning placement'lari boʻyicha aniq bir marta uchraydi; placement
shunday panel'da turadi-ki uning `material_id`'i part'ning panel material'iga mos keladi;
grained material'dagi part hech qachon `rotated` emas; placement'lar bir-birini qoplamaydi
va `panel − 2× edge_trim` ichida qoladi; immutable.
