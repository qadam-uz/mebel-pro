---
title: Catalog & inventory
status: draft
owner: shape
updated: 2026-05-22
order: 50
---

# Catalog & inventory

Platform material catalog, har bir branch nima saqlaydi va qanday narxlaydi, warehouse, va
stock qaysi supplier'lardan keladi. **Materials** — bu ikki kind'dagi platform-wide master
record'lar: **sheets** va **edges**; workshop faqat qaysisini saqlashini *select* qiladi.
**Stock** warehouseman tomonidan kiritiladi va production yakunlanishi bilan **order state
machine tomonidan auto-decrement** qilinadi — reservation yo'q. Order ↔ stock contract
[`orders.md`](orders.md) → *The stock seam* tomonidan owned; bu doc uning ortidagi warehouse
mexanikasi.

## Materials (platform master catalog)

Materials platform level'da yashaydi. Workshop'lar materials'ni define qilmaydi; ular bu
catalog'dan tanlaydi. v1'da ikki **kind**:

| Kind | What it is | Measured in | Has |
|---|---|---|---|
| `sheet` | a cuttable board (DSP / MDF / plywood / …) | sheets | type, thickness, colour / decor, sheet length × width (`length ≥ width` = grain direction), grain yes/no, image |
| `edge` | edge-banding tape applied to a panel's sides | metres | thickness, colour / decor, image |

**Operations (platform operator):**

- **Create / edit a material** — `kind` + o'sha kind uchun field'lar. (spec, sheet size)'ga
  bitta master record — bir xil spec ikki sheet size'da ikkita material, har biri o'z size'ini
  nomida ko'rsatadi. Bu level'da narx yo'q — narx per-branch.
- **Activate / deactivate** platform level'da. `inactive` yangi branch selection'lar va
  client'lar uchun ko'rinmaydi; mavjud branch selection'lar master'ga reference qilishni
  davom ettiradi (history saqlanadi). Delete yo'q.
- **List / get** — operator'lar hammasini ko'radi; workshop user'lar "add to branch
  selection" picker orqali active subset'ni ko'radi; client'lar faqat o'z branch'i nima
  saqlaganini ko'radi.

Platform-level edit hech qachon mavjud order'larga tegmaydi (snapshots —
[`architecture.md`](../../architecture.md#data-model-invariants)).

## Branch material selection

Branch catalog'ning bir subset'ini saqlaydi. `(branch, material)` selection branch'ning
stock unit price'ini, uning min-stock threshold'ini va client-visibility flag'ini ushlab
turadi. Material qo'shish o'sha branch uchun stock item yaratadi (zero on hand).

**Operations (owner, yoki branch'da `manage_catalog`):**

- **Add a material** — platform-`active` material'ni tanlang; per-unit price'ni (`sheet`
  uchun per sheet, `edge` uchun per metre) va `min_stock`'ni (≥ 0) belgilang.
- **Edit price or min-stock** — hech qachon mavjud order'larga tegmaydi (snapshots).
- **Activate / deactivate** branch level'da. `inactive` client'larga ko'rinmaydi va yangi
  cutting'da selectable emas; stock va history qoladi. Delete yo'q.

Client material'ni faqat u platform va branch level'da **ikkalasida** ham `active` bo'lganda
ko'radi.

## Branch pricing

Branch'ga bitta pricing row, branch bilan birga yaratiladi. Order aynan shundan narxlanadi —
per-metre edge material price'idan **emas**; order uni creation'da snapshot qiladi
([`orders.md`](orders.md) → *Pricing*).

- `cutting_model` (`per_sheet` / `per_cut`) + `cutting_rate_tiyin`.
- `edge_banding_rates` — har bir banding thickness uchun all-in rate (masalan, `0.4`, `2.0`).
  Bu banding'ning **price**'i; u consume qiladigan `edge` material alohida stock sifatida
  track qilinadi (uning per-metre selection price'i cost reference, v1 order pricing'da
  ishlatilmaydi).

**Owner only** (v1'da delegable emas). Rate'i yo'q banding thickness'ni ishlatuvchi part
order pricing'ni fail qiladi (`missing_edge_rate`) — owner rate'ni qo'shadi.

## Suppliers

Workshop material'ni kimdan sotib oladi. Yengil va **on demand yaratiladi**: stock-in'ni
record qilayotganda warehouseman mavjud supplier'ni tanlaydi yoki inline bittasini qo'shadi
(name, optional phone / note). Workshop-scoped, hech qachon delete qilinmaydi (ishlatilmasa
deactivate qilinadi). v1'da purchase-order yoki accounts-payable flow yo'q — purchase uchun
*money* alohida [`finance.md`](finance.md) expense bo'lib, uni accountant record qiladi; bu
yerdagi supplier faqat stock qayerdan kelganini label qiladi.

## Inventory

Branch o'zi saqlaydigan har bir material uchun bitta stock item ushlab turadi — material'ning
unit'idagi (sheets yoki metres) yagona `on_hand` balans va `min_stock` threshold. **`reserved`
yo'q, `available` yo'q, reservation yo'q** — order hech qachon stock ushlamaydi; u faqat uni
decrement qiladi.

**Operations:**

- **Stock-in** (owner, yoki branch'da `manage_inventory`) — material (branch'ning
  selection'ida bo'lishi shart), positive quantity, supplier (mavjud yoki inline qo'shilgan),
  optional receipt file. `on_hand += qty`.
- **Adjust** (xuddi shu caller) — **mandatory note** bilan signed delta; `on_hand` 0'dan
  pasaymasligi mumkin emas. Stock-take va write-off uchun ishlatiladi (jumladan
  cancelled-mid-production order fizik consume qilgan material).
- **Consume / restore** (system) — to'liq order state machine tomonidan haydaladi.

**The order seam.** [`orders.md`](orders.md) bo'yicha: `shop` sheet item'lar order'ning
**Cutting done** marked bo'lganda **consume** qilinadi; `shop` edge material **Banding done**
marked bo'lganda **consume** qilinadi; operator'ning har ikkala step'dan birini **revert**
qilishi aynan u consume qilgan narsani **restore** qiladi. `own`-source item'lar hech qachon
stock'ga tegmaydi.

**Projected balance & the verify warning.** Reservation yo'q, shuning uchun ma'noli "yetarli
bo'ladimi?" allaqachon in flight'dagi demand'ni talab qiladi. Branch'dagi material uchun:

> projected = `on_hand` − Σ (oldindagi active order'lardan o'sha material'ning hali uni
> decrement qilmagan demand'i)

— sheets'lar hali `confirmed`/`cutting`'dagi order'lar tomonidan qarzdor; edge metres'lar
`confirmed`/`cutting`/`edge_banding`'dagi order'lar tomonidan. Operator order'ni verify
qilganda ([`orders.md`](orders.md)), projected balance'i bu order'ni qoplamaydigan `shop`
material **warning** ko'taradi, shunda ular warehouseman'ni prompt qila olishadi — bu hech
qachon approval'ni **block qilmaydi** (ba'zi workshop'lar per order sotib oladi).

**Low-stock.** Har qanday o'zgarishdan keyin `on_hand ≤ min_stock` bo'lsa, branch'ning
`manage_inventory` grantee'lariga va owner'ga notification fire qiladi; daily summary uni
takrorlaydi.

## UX (workshop app)

Branch tab'lari ostida (va branch filter'li owner-wide view'larda):

- **Materials** (`manage_catalog`) — master'dan table (image, kind, type/thickness,
  colour/decor, sheets uchun sheet size, branch'ning unit price'i, status). **+ Material** →
  catalog picker (kind + search) → per-branch form (price, min-stock). Row: Edit ·
  Activate / Deactivate. Delete yo'q.
- **Pricing** (owner only) — cutting model + rate; edge-banding-rate grid (thickness |
  rate per metre, add/remove). Save + unsaved-changes guard; yangi branch'da "pricing not set
  yet" empty state.
- **Stock** (`manage_inventory`) — table: material (name + image), on-hand, min-stock,
  unit, last updated; low-stock row'lar highlight qilingan (chip + colour). Per-row **Record
  stock-in** → modal (qty, inline add'li supplier picker, receipt upload). Inline
  min-stock. **Adjust** → modal (signed delta + mandatory reason). **Transactions** — to'liq
  log: type (`stock_in` / `consume` / `restore` / `adjust`), signed quantity, balance-after,
  order link (consume/restore uchun), supplier (stock_in uchun), actor, note, date; read-only.
- **Suppliers** (`manage_inventory`) — oddiy list (name, phone, note, active); add / edit /
  deactivate. Asosan stock-in'dan inline yetib boriladi.

**Client app** cutting wizard'ning material step'ida: branch'ning active `sheet` selection'i
searchable grid sifatida (name, type, thickness, colour, sheet size, grain, image, **va
branch'ning per sheet price'i** faqat item'ning source'i `shop` bo'lganda); single-select.
Edge banding wizard'da har bir side uchun thickness sifatida tanlanadi
([`cutting.md`](cutting.md)); mos `edge` material va uning stock'i server-side resolve
qilinadi.

States: loading (skeletons); empty (hali selection yo'q → "add materials to this branch");
error (`trace_id`). Accessibility: low-stock chip + colour, faqat colour emas; modal'lar
focus'ni manage qiladi; owner-only control'lar non-owner'lar uchun ko'rinarli gate qilingan.

## Edge cases

- **Platform deactivates a material branches carry** — mavjud selection'lar unga reference
  qilishni davom ettiradi (history saqlanadi); client'lardan yashirilgan; yangi branch uni
  qo'sha olmaydi; stock tegilmagan.
- **Branch deactivates a material still platform-active** — o'sha branch'da client'lardan
  yashirilgan; stock/history qoladi; boshqa branch'lar ta'sirlanmagan.
- **Material referenced by old orders, then deactivated** — order'lar ta'sirlanmagan
  (snapshots).
- **Sheet width entered larger than length** — platform creation'da reject qilinadi (uzun
  tomon grain direction). `edge` material'larga taalluqli emas.
- **`shop` material short when an operator verifies an order** — **warning**, hech qachon
  block emas; operator warehouseman'ni prompt qiladi ([`orders.md`](orders.md)).
- **Order cancelled mid-production after material was consumed** — stock **auto-restore
  qilinmaydi** (u fizik kesilgan edi); count tuzatilishi kerak bo'lsa warehouseman `adjust`
  write-off'ni record qiladi.
- **Operator reverts a completed job** — system o'sha step consume qilgan quantity'ni aynan
  `restore` qiladi.
- **Adjust below 0** — reject qilinadi.
- **Stock-in for a branch-deactivated material** — ruxsat etiladi (selection hali mavjud);
  u reactivate qilingunicha client'larga taklif qilinmaydi xolos.
- **`own`-source order** — umuman inventory interaction yo'q.
- **Add a supplier inline that already exists by name** — picker mavjudini afzal ko'radi;
  near-duplicate'lar manual cleanup, v1'da enforce qilinmagan.

## Next

- [`orders.md`](orders.md) — stock'ni consume / restore qiluvchi state machine va pricing
  snapshot rule.
- [`finance.md`](finance.md) — supplier'dan material sotib olishning expense tomoni.
