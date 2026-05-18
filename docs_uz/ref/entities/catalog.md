---
title: Catalog
status: draft
owner: shape
updated: 2026-05-17
order: 25
---

# Catalog

Platform'ning material catalog'i, har bir branch'ning undan tanlovi va har bir branch'ning
pricing'i. Material'lar **platform-wide master record'lar** — platform operator'lar
tomonidan bir marta belgilanadi; har bir branch qaysi birini olib yurishini tanlaydi va
oʻzining price'ini belgilaydi. Branch pricing (cutting model + edge-banding rate'lari) har
bir order'ning price'ini boshqaradi. Snapshot semantics (price oʻzgarishi mavjud order'ga
hech qachon yetib bormaydi) [`architecture.md`](../../architecture.md) → *Data model
invariants*'da yotadi.

## Material

Platform master record (har bir spec uchun bittadan), v1'da ikki **kind**'da: `sheet`
(kesiladigan board, sheet boʻyicha stock qilinadi va price beriladi) yoki `edge`
(edge-banding tape, metr boʻyicha stock qilinadi va oʻlchanadi). Client cutting boshlaganda
sheet'ni va har bir side uchun edge thickness'ni tanlaydi; optimizer sheet'ning size va
grain'ini oʻqiydi; order material'ning detail'larini va branch'ning price'ini snapshot
qiladi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `kind` | enum | `sheet` / `edge` |
| `type` | enum? | `sheet` only: `dsp` / `mdf` / `plywood` / `natural_wood` / `other` |
| `name` | text | required, e.g. "Kronospan DSP White 18mm" |
| `thickness_mm` | numeric | required (sheets e.g. 8/16/18; edges e.g. 0.4/2.0) |
| `color` / `decor_code` | text / text? | required / optional |
| `sheet_length_mm` / `sheet_width_mm` | int? | **`sheet` only**, required there; `length ≥ width` (long side = grain direction); null for `edge` |
| `grain_direction` | bool? | **`sheet` only**; `true` if the board has a grain; null for `edge` |
| `image_file_id` | UUID? | → [file](support.md#file) — sample image |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Invariant'lar: `sheet` material'larda `type`, sheet size (`length ≥ width`) va grain bor;
`edge` material'larda bularning hech biri yoʻq va metrda oʻlchanadi; har bir `sheet`
material uchun bitta standart sheet size (v1); faqat platform operator yaratadi va
tahrirlaydi (platform user'lar toʻliq platform scope'ga ega; workshop tomonidagi hech bir
permission grant buni bermaydi); `inactive` yangi branch tanlovlariga va client'larga
koʻrinmaydi; `inactive` master'ning mavjud branch tanlovlari unga reference qilishda davom
etadi (history saqlanadi); hech qachon oʻchirilmaydi; master'ni tahrirlash mavjud
order'larga hech qachon taʼsir qilmaydi (snapshot'lar).

## Branch material

Branch'ning platform material'idan tanlovi — "bu branch bu material'ni shu price'da olib
yuradi" deydigan (branch, material) link'i. Branch oʻz catalog'iga material qoʻshganda
yaratiladi; per-branch price'ni va branch-level visibility flag'ini ushlab turadi.
Material uchun branch'ning [`stock_item`](inventory.md#stock-item)'i shu record bilan birga
yaratiladi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `branch_id` | UUID | required |
| `material_id` | UUID | required; references a platform [Material](#material) |
| `price_tiyin` | bigint | per stock unit (per **sheet** for a `sheet`, per **metre** for an `edge`), integer tiyin, ≥ 0 |
| `min_stock` | int | low-stock threshold for the branch's stock item; ≥ 0 |
| `status` | enum | `active` / `inactive` at the branch level (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Order pricing `sheet`'ning `price_tiyin`'idan (`shop` part'lar uchun) va cutting hamda edge
banding uchun branch'ning [Branch pricing](#branch-pricing)'idan foydalanadi. `edge`
material'ning `price_tiyin`'i **faqat cost reference** — banding `edge_banding_rates`'dan
price qilinadi, per-metre material price'idan emas (v1).

Invariant'lar: `(branch_id, material_id)` unique; price integer tiyin (hech qachon float
emas); price'ni tahrirlash mavjud order'larga hech qachon taʼsir qilmaydi (snapshot'lar);
branch'da workshop owner yoki `manage_catalog` grantee tomonidan yaratiladi va
tahrirlanadi; tanlov yaratilganda reference qilingan Material platform level'da `active`
boʻlishi kerak (mavjud tanlovlar keyingi platform deactivation'idan keyin ham omon
qoladi); `inactive` shu branch'da xarid qilayotgan client'larga koʻrinmaydi va yangi
cutting'da tanlab boʻlmaydi; client branch'da material'ni faqat master Material **ham**
Branch material **ham** `active` boʻlganda koʻradi; hech qachon oʻchirilmaydi.

## Branch pricing

Branch'ning cutting service va edge banding uchun pricing configuration'i. Har bir branch
uchun bittadan. Order pricing uni order creation / re-pricing vaqtida oʻqiydi va
qiymatlarni order'ga snapshot qiladi; keyingi oʻzgarishlar mavjud order'larga yetib
bormaydi.

| Field | Type | Notes |
|---|---|---|
| `branch_id` | UUID | PK; 1:1 with branch |
| `cutting_model` | enum | `per_sheet` or `per_cut` |
| `cutting_rate_tiyin` | bigint | the rate per the chosen model, ≥ 0 |
| `edge_banding_rates` | json | map `thickness_mm → rate_tiyin per metre`, e.g. `{ "0.4": 300000, "2.0": 500000 }` |
| `updated_at` | timestamp | |
| `updated_by_user_id` | UUID | → workshop user with `is_owner` |

Invariant'lar: har bir branch uchun aniq bitta row (DB PK); rate'lar integer tiyin; rate'i
yoʻq banding thickness'ni ishlatadigan part order pricing'ni fail qiladi (operational gap;
owner uni qoʻshadi); faqat workshop owner tahrirlaydi (v1'da delegate qilib boʻlmaydi).
