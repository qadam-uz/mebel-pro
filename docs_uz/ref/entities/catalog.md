---
title: Catalog
status: draft
owner: shape
updated: 2026-06-03
order: 25
---

# Catalog

Platform'ning material catalog'i, catalog ortidagi manufacturer'lar, har bir branch'ning
undan tanlovi va har bir branch'ning pricing'i. Material'lar **platform-wide master
record'lar** — platform operator'lar tomonidan bir marta belgilanadi; har bir branch qaysi
birini olib yurishini tanlaydi va oʻzining price'ini belgilaydi. Branch pricing ikkita
xizmat rate'ini olib yuradi (panel kesish uchun + metr krom yopishtirish ish haqi); branch'ning
har bir edge selection'idagi per-metre price esa oʻsha tape uchun **xom material** narxi.
Order pricing buni birlashtiradi: krom narxi = material + ish haqi, har bir metr uchun.
Snapshot semantics (price oʻzgarishi mavjud order'ga hech qachon yetib bormaydi)
[`architecture.md`](../../architecture.md) → *Data model invariants*'da yotadi.

## Manufacturer

Material'ni kim ishlab chiqargani — Kronospan, Egger, Rehau va hokazo. Platform-scoped master
record: bir xil spec'dagi ikki material agar manufacturer'lari boshqacha boʻlsa, ikkita
alohida catalog row sanaladi (identity manufacturer'ni oʻz ichiga oladi). Material-create
form'idan platform operator'lar tomonidan kerak boʻlganda yaratiladi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `name` | text | required; unique (case-insensitive) |
| `country` | text? | optional — disambiguates similarly-named brands |
| `note` | text? | optional — short free-text |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Invariant'lar: `name` unique; faqat platform operator yaratadi va tahrirlaydi; `inactive`
yangi material yaratishlarga va branch material-selection picker'lariga koʻrinmaydi;
`inactive` manufacturer'ning mavjud material'lari unga reference qilishda davom etadi
(history saqlanadi); hech qachon oʻchirilmaydi.

## Material

Platform master record (har bir spec, panel size mavjud boʻlganda va **manufacturer** uchun
bittadan), v1'da ikki **kind**'da: `panel` (kesiladigan board, panel boʻyicha stock qilinadi
va price beriladi) yoki `edge` (edge-banding tape, integer millimetres'da stock qilinadi va
metre boʻyicha price/display qilinadi). Client cutting boshlaganda panel'ni va har bir side
uchun edge material'ni tanlaydi; optimizer panel'ning size va grain'ini oʻqiydi; order
material'ning detail'larini va branch'ning price'ini snapshot qiladi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `kind` | enum | `panel` / `edge` |
| `manufacturer_id` | UUID | required; references a platform [Manufacturer](#manufacturer) |
| `type` | enum? | `panel` only: `dsp` / `mdf` / `plywood` / `natural_wood` / `other` |
| `name` | text | required; spec + size, e.g. "DSP H1334 ST9 · Dub Sonoma · 18 mm · 2750×1830" — manufacturer rendered separately, not embedded in the name |
| `thickness_mm` | numeric | required (panels e.g. 8/16/18; edges e.g. 0.4/2.0) |
| `color` / `decor_code` | text / text? | required / optional |
| `panel_length_mm` / `panel_width_mm` | int? | **`panel` only**, required there; `length ≥ width` (long side = grain direction); null for `edge` |
| `grain_direction` | bool? | **`panel` only**; `true` if the board has a grain; null for `edge` |
| `image_file_id` | UUID? | → [file](support.md#file) — sample image |
| `status` | enum | `active` / `inactive` (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Invariant'lar: `panel` material'larda `type`, panel size (`length ≥ width`) va grain bor;
`edge` material'larda bularning hech biri yoʻq va integer millimetres'da stock qilinadi; har bir `panel`
material uchun bitta standart panel size (v1) — material'ning identity'si uning spec'i, oʻsha
size'i **va manufacturer'i**, shuning uchun bir xil spec ikki manufacturer'da saqlansa
ikkita catalog row boʻladi va bir xil spec ikki panel size'da saqlansa yana ikkita boʻladi,
har biri oʻz specific'larini nomida koʻrsatadi; faqat platform operator yaratadi va
tahrirlaydi (platform user'lar bu uchun platform-ops scope'ga ega; workshop tomonidagi hech bir
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
| `price_tiyin` | bigint | per sell unit (per **panel** for a `panel`, per **metre** for an `edge`), integer tiyin, ≥ 0 |
| `min_stock` | int | low-stock threshold for the branch's stock item, in the material's stock unit (panel count or edge millimetres); ≥ 0 |
| `status` | enum | `active` / `inactive` at the branch level (soft delete only) |
| `created_at` / `updated_at` | timestamp | |

Order pricing `price_tiyin`'ni **ikkala** kind uchun ham oʻqiydi: `shop` panel part'lar uchun
`panel`'ning per-panel price'i va har bir `shop` edge metr uchun `edge`'ning per-metre
price'i. Per-metre edge price oʻsha tape uchun **xom material narxi** — **krom
yopishtirish ish haqi** esa [Branch pricing](#branch-pricing)'dagi alohida per-metre rate,
materialga qoʻshilib hisoblanadi. Cutting service ham xuddi shu Branch pricing'dagi
per-panel rate.

Invariant'lar: `(branch_id, material_id)` unique; price integer tiyin (hech qachon float
emas); price'ni tahrirlash mavjud order'larga hech qachon taʼsir qilmaydi (snapshot'lar);
branch'da workshop owner yoki `manage_catalog` grantee tomonidan yaratiladi va tahrirlanadi;
tanlov yaratilganda reference qilingan Material platform level'da `active` boʻlishi kerak
(mavjud tanlovlar keyingi platform deactivation'idan keyin ham omon qoladi); `inactive` shu
branch'da xarid qilayotgan client'larga koʻrinmaydi va yangi cutting'da tanlab boʻlmaydi;
client branch'da material'ni faqat master Material **ham** Branch material **ham** `active`
boʻlganda koʻradi; hech qachon oʻchirilmaydi.

## Branch pricing

Branch'ning xizmat rate'lari: panel kesish uchun bitta rate va metr krom yopishtirish uchun
bitta rate (qalinlikdan qatʼi nazar). Har bir branch uchun bittadan row. Order pricing
uni order creation vaqtida oʻqiydi va qiymatlarni order'ga snapshot qiladi; keyingi
oʻzgarishlar mavjud order'larga yetib bormaydi. Edge **material** narxi alohida — har bir
[Branch material](#branch-material) `edge` selection'idagi per-metre `price_tiyin`'da
yashaydi.

| Field | Type | Notes |
|---|---|---|
| `branch_id` | UUID | PK; 1:1 with branch |
| `cutting_rate_tiyin` | bigint | the rate per panel cut, ≥ 0 |
| `edge_banding_rate_tiyin` | bigint | the labour rate per metre of tape applied, ≥ 0 (one rate; thickness is the material's property and doesn't change the rate in v1) |
| `updated_at` | timestamp | |
| `updated_by_user_id` | UUID | → workshop user with `is_owner` |

Invariant'lar: har bir branch uchun aniq bitta row (DB PK); rate'lar integer tiyin; faqat
workshop owner tahrirlaydi (v1'da delegate qilib boʻlmaydi). Branch olib yurmaydigan edge
material'ni ishlatadigan part order pricing'ni fail qiladi (operational gap; owner edge'ni
branch'ning selection'iga qoʻshadi).
