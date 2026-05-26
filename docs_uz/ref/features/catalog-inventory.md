---
title: Catalog & inventory
status: draft
owner: shape
updated: 2026-05-25
order: 50
---

# Catalog & inventory

Platform material catalog'i, ortidagi manufacturer'lar, har bir branch nima olib yurishi va
pricing'i, ombor va stock keladigan supplier'lar. **Material'lar** platform-wide master
record'lar ikki kind'da — **panel'lar** va **edge'lar**; workshop faqat qaysi birini olib
yurishini *tanlaydi*. **Stock** warehouseman tomonidan kiritiladi va production tugashi
bilan **order state machine tomonidan avto-decrement qilinadi** — reservation yoʻq.
Order ↔ stock kontrakti [`orders.md`](orders.md) → *The stock seam*'ga tegishli; bu doc
uning ortidagi warehouse mexanikasi.

## Manufacturers (platform master list)

Material'ni kim ishlab chiqargani — Kronospan, Egger, Rehau va hokazo. Alohida
platform-scoped list: material'ning identity'si manufacturer'ni oʻz ichiga oladi
(Egger H1334 18 mm va Kronospan H1334 18 mm — ikkita catalog row, ikkita stock item,
ikkita price). Platform operator'lar tomonidan curate qilinadi.

**Operation'lar (platform operator):**

- **Create / edit a manufacturer** — `name` (unique, case-insensitive), ixtiyoriy
  `country` va `note`.
- **Activate / deactivate** platform level'da. `inactive` yangi material yaratishlarga va
  branch material-selection picker'lariga koʻrinmaydi; inactive manufacturer'ning mavjud
  material'lari unga reference qilishda davom etadi (history saqlanadi). Delete yoʻq.
- **List / get** — operator'lar barchasini koʻradi; workshop user'lar va client'lar faqat
  oʻzlari koʻra olayotgan material'larga biriktirilgan manufacturer'larni filter chip
  sifatida koʻradi.

Manufacturer yaratish material-create form'idan side-trip (inline-add), supplier'ning
stock-in'dan inline-add'i bilan bir xil shape'da.

## Materials (platform master catalog)

Material'lar platform level'da yashaydi. Workshop'lar material'larni belgilamaydi; ular
shu catalog'dan tanlaydi. v1'da ikki **kind**:

| Kind | What it is | Measured in | Has |
|---|---|---|---|
| `panel` | a cuttable board (DSP / MDF / plywood / …) | panels | manufacturer, type, thickness, colour / decor, panel length × width (`length ≥ width` = grain direction), grain yes/no, image |
| `edge` | edge-banding tape applied to a panel's sides | metres | manufacturer, thickness, colour / decor, image |

**Operation'lar (platform operator):**

- **Create / edit a material** — `kind` + `manufacturer_id` + oʻsha kind uchun
  field'lar. Har bir (spec, panel size, manufacturer) uchun bittadan master record —
  ikki panel size'dagi bir xil spec ikki material, ikki manufacturer'dan bir xil spec
  yana ikkitasi; har biri oʻz specific'larini nomida koʻrsatadi. Bu level'da price yoʻq
  — price per-branch.
- **Activate / deactivate** platform level'da. `inactive` yangi branch tanlovlariga va
  client'larga koʻrinmaydi; mavjud branch tanlovlari master'ga reference qilishda davom
  etadi (history saqlanadi). Delete yoʻq.
- **List / get** — operator'lar barchasini koʻradi; workshop user'lar "add to branch
  selection" picker orqali active subset'ni koʻradi; client'lar faqat oʻz branch'i
  olib yurganini koʻradi.

Platform level'idagi edit mavjud order'larga hech qachon tegmaydi (snapshot'lar —
[`architecture.md`](../../architecture.md#data-model-invariants)).

## Branch material selection

Branch catalog'ning subset'ini olib yuradi. `(branch, material)` selection branch'ning
price'ini (`panel` uchun per panel, `edge` uchun per metr), min-stock threshold'ini va
client-visibility flag'ini ushlab turadi. Material qoʻshish branch'ning shu material
uchun stock item'ini yaratadi (on-hand nol).

**Operation'lar (owner yoki branch'da `manage_catalog`):**

- **Add a material** — platform-`active` material'ni tanlash (manufacturer + kind
  filter + search); per-unit price va `min_stock` (≥ 0)'ni set qilish.
- **Edit price or min-stock** — mavjud order'larga hech qachon tegmaydi (snapshot'lar).
- **Activate / deactivate** branch level'da. `inactive` client'larga koʻrinmaydi va
  yangi cutting'da tanlab boʻlmaydi; stock va history qoladi. Delete yoʻq.

Client material'ni faqat platform level'da **ham** branch level'da **ham** `active`
boʻlganda koʻradi.

## Branch pricing

Branch uchun bitta pricing row, branch bilan birga yaratiladi. Order pricing creation'da
uni oʻqiydi va qiymatlarni order'ga snapshot qiladi; keyingi oʻzgarishlar mavjud
order'larga yetib bormaydi.

- `cutting_rate_tiyin` — har bir kesilgan panel uchun ish haqi (v1'da per-cut model yoʻq;
  yagona model per panel).
- `edge_banding_rate_tiyin` — har bir yopishtirilgan metr uchun ish haqi. v1'da bitta rate,
  thickness'ga bogʻliq emas.
- Edge **material** narxi alohida — har bir
  [Branch material](#branch-material-selection) `edge` selection'idagi per-metre `price_tiyin`
  (xom material narxi). Order total = material + ish haqi, har bir `shop` side metr boʻyicha.

**Faqat owner** (v1'da delegate qilib boʻlmaydi). Branch olib yurmaydigan edge
material'ni ishlatadigan part order pricing'ini fail qiladi
(`branch_does_not_carry_edge`) — owner edge'ni branch'ning selection'iga qoʻshadi.

## Suppliers

Workshop material'ni kimdan sotib oladi. Yengil va **kerak boʻlganda yaratiladi**:
stock-in yozayotganda warehouseman mavjud supplier'ni tanlaydi yoki inline qoʻshadi
(name, ixtiyoriy phone / note). Workshop-scoped, hech qachon oʻchirilmaydi
(ishlatilmasa deactivate qilinadi). Supplier ≠ manufacturer: supplier — workshop'ning
xarid kontragenti, manufacturer — material'ni kim ishlab chiqargani — bitta supplier
koʻp manufacturer'ning tape'ini olib yurishi mumkin va aksincha.

v1'da purchase-order yoki accounts-payable flow yoʻq — xarid uchun *pul* alohida
accountant yozadigan [`finance.md`](finance.md) expense; bu yerda supplier faqat
stock qaerdan kelganini belgilaydi.

## Inventory

Branch olib yurgan har bir material uchun bitta stock item ushlab turadi —
material'ning unit'idagi (panel'lar yoki metr'lar) bitta `on_hand` balance va bitta
`min_stock` threshold. **`reserved` yoʻq, `available` yoʻq, reservation yoʻq** —
order stock ushlab turmaydi; uni faqat decrement qiladi.

**Operation'lar:**

- **Stock-in** (owner yoki branch'da `manage_inventory`) — material (branch'ning
  selection'ida boʻlishi kerak), musbat quantity, supplier (mavjud yoki inline
  qoʻshilgan), ixtiyoriy receipt file. `on_hand += qty`.
- **Adjust** (xuddi shu caller) — **majburiy note** bilan signed delta; `on_hand` 0'dan
  past tushishi mumkin emas. Stock-take va write-off (jumladan, cancelled-mid-production
  order fizik ravishda consume qilgan material) uchun ishlatiladi.
- **Consume / restore** (system) — toʻliq order state machine tomonidan boshqariladi.

**Order seam.** [`orders.md`](orders.md) boʻyicha: `shop` panel item'lar order'ning
**Cutting done**'i belgilanganda **consume** qilinadi; `shop` edge metr'lar har bir
edge material uchun **Banding done** belgilanganda **consume** qilinadi. Revert
oʻzining step'i decrement qilganini aniq qayta increment qiladi. `own`-source panel'lar
va `own`-source edge side'lar stock'ga hech qachon tegmaydi.

**Projected balance & verify warning.** Reservation yoʻq, shuning uchun "bizda yetarli
boʻladimi?"ning haqiqiy maʼnosi allaqachon flight'dagi demand'ga muhtoj. Branch'da bir
material uchun:

> projected = `on_hand` − Σ (oldida hali decrement qilmagan active order'lardan
> oʻsha material'ning demand'i)

— panel'lar hali ham `confirmed`/`cutting`'dagi order'lar tomonidan qarzdor; edge
metr'lar (har bir edge material uchun) `confirmed`/`cutting`/`edge_banding`'dagi
order'lar tomonidan. Operator order'ni verify qilganda ([`orders.md`](orders.md)),
projected balance bu order'ni qoplay olmaydigan `shop` material warehouseman'ga
ogohlantirish berishi uchun **warning** koʻtaradi — approval'ni **hech qachon
bloklamaydi** (baʼzi workshop'lar per order xarid qiladi).

**Low-stock.** Har qanday oʻzgarishdan keyin `on_hand ≤ min_stock` boʻlsa,
branch'ning `manage_inventory` grantee'lariga va owner'ga notification ketadi;
kunlik summary buni takrorlaydi.

## UX (workshop app)

Branch tab'lari ostida (va branch filter bilan owner-wide view'lar):

- **Materials** (`manage_catalog`) — master'dan jadval (image, kind, manufacturer,
  type/thickness, colour/decor, `panel` uchun panel size, branch'ning unit price,
  status). Filter chip'lar: kind, manufacturer, type. **+ Material** → catalog picker
  (kind + manufacturer + search) → per-branch form (price, min-stock). Row:
  Edit · Activate / Deactivate. Delete yoʻq.
- **Pricing** (faqat owner) — ikkita field: cutting rate (`cutting_rate_tiyin`, per panel)
  va krom yopishtirish ish haqi (`edge_banding_rate_tiyin`, per metre, barcha thickness'lar
  uchun). Save + unsaved-changes guard; yangi branch'da "pricing not set yet" empty state.
  Edge'ning **xom material** narxi alohida — har bir Branch material `edge` selection'ida
  yashaydi, bu yerda emas.
- **Stock** (`manage_inventory`) — jadval: material (name + image + manufacturer
  chip), on-hand, min-stock, unit, last updated; low-stock row'lar highlighted
  (chip + colour). Per-row **Record stock-in** → modal (qty, inline add bilan
  supplier picker, receipt upload). Inline min-stock. **Adjust** → modal (signed
  delta + majburiy reason). **Transactions** — toʻliq log: type
  (`stock_in` / `consume` / `restore` / `adjust`), signed quantity, balance-after,
  order link (consume/restore uchun), supplier (stock_in uchun), actor, note, date;
  read-only.
- **Suppliers** (`manage_inventory`) — oddiy list (name, phone, note, active);
  add / edit / deactivate. Asosan stock-in'dan inline yetib kelinadi.

**Client app**'da cutting wizard'ning material step'larida: branch'ning active `panel`
selection'i manufacturer / type / thickness chip'lari bilan searchable grid sifatida
(name, manufacturer, type, thickness, colour, panel size, grain, image, **va**
**branch'ning per panel price'i** faqat tanlangan source `shop` boʻlganda);
single-select. Edge banding wizard'da per side catalog **edge** material sifatida
tanlanadi ([`cutting.md`](cutting.md)'ga qarang); side'ning source'i `shop` boʻlganda
order branch'ning oʻsha edge'dagi per-metre **material** narxini va branch'ning
per-metre **krom yopishtirish ish haqi** rate'ini snapshot qiladi.

State'lar: loading (skeleton'lar); empty (hali tanlov yoʻq → "add materials to this
branch"); error (`trace_id`). Accessibility: low-stock chip + colour, faqat colour
emas; modal'lar focus boshqaradi; owner-only kontrol'lar non-owner'lar uchun
koʻrinarli gate qilinadi.

## Edge cases

- **Platform manufacturer'ni deactivate qiladi** — mavjud material'lar unga reference
  qilishda davom etadi (history saqlanadi); manufacturer new-material picker'dan
  yoʻqoladi; hech bir branch oʻsha manufacturer ostida yangi material qoʻsha olmaydi;
  stock tegilmaydi.
- **Platform branch'lar olib yurgan material'ni deactivate qiladi** — mavjud tanlovlar
  unga reference qilishda davom etadi (history saqlanadi); client'lardan
  yashiriladi; hech bir yangi branch uni qoʻsha olmaydi; stock tegilmaydi.
- **Branch hali ham platform-active material'ni deactivate qiladi** — oʻsha branch'da
  client'lardan yashiriladi; stock/history qoladi; boshqa branch'lar taʼsirlanmaydi.
- **Eski order'lar tomonidan reference qilingan material keyin deactivate qilinadi**
  — order'lar taʼsirlanmaydi (snapshot'lar).
- **Panel width length'dan katta kiritildi** — platform creation'da rad etiladi
  (uzun tomon grain direction). `edge` material'larga tegishli emas.
- **Operator order'ni verify qilganda `shop` material kam** — **warning**, hech
  qachon block emas; operator warehouseman'ga ogohlantiradi
  ([`orders.md`](orders.md)).
- **Order material consume qilingandan keyin mid-production cancel qilindi** — stock
  **avto-restore qilinmaydi** (u fizik ravishda kesilgan); agar count'ni
  toʻgʻrilash kerak boʻlsa warehouseman `adjust` write-off yozadi.
- **Operator tugatilgan job'ni revert qiladi** — system shu step consume qilgan
  miqdorni aniq `restore` qiladi; edge'lar uchun, step consume qilgan har bir edge
  material uchun bittadan restore.
- **Adjust 0'dan past** — rad etiladi.
- **Branch-deactivated material uchun stock-in** — ruxsat etiladi (selection hali
  ham mavjud); shunchaki reaktivatsiyaga qadar client'larga taklif qilinmaydi.
- **`own`-source order** — umuman inventory interaction yoʻq; faqat `own` panel va
  `own` edge'larga ega order seam'ni butunlay oʻtkazib yuboradi.
- **Inline supplier qoʻshish, allaqachon nomi boʻyicha mavjud** — picker mavjudini
  afzal koʻradi; near-duplicate'lar qoʻlda tozalanadi, v1'da enforce qilinmaydi.

## Next

- [`orders.md`](orders.md) — the state machine that consumes / restores stock and
  the pricing snapshot rule.
- [`finance.md`](finance.md) — the expense side of buying material from a supplier.
