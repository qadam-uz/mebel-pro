---
title: Orders
status: draft
owner: shape
updated: 2026-06-03
order: 30
---

# Orders

Order lifecycle: client tugatilgan cutting'dan order joylashtiradi, workshop uni verify
qiladi, ikkita production phase ishlaydi va client uni olib ketadi. v1 **pickup-only**,
order **hech qachon pul harakatlantirmaydi** (finance module client nima toʻlaganini
yozadi — [`finance.md`](finance.md)) va **hech qachon stock balance ushlab turmaydi**
(inventory module production tugashi bilan avto-decrement qiladi —
[`catalog-inventory.md`](catalog-inventory.md)). Order — production spine; money va
material — u trigger qiladigan alohida module'lar.

## Problem

Bugun order — telefon qoʻngʻirogʻi, ogʻzaki price va doska. Client price'ni yoki cutting
plan'ni koʻrmaydi, va workshop kim nimani kesganini kuzatib bormaydi. v1 ordering'ni
self-serve, pricing'ni avtomatik, workflow'ni kichik state machine'ga cheklangan va har
bir transition'ni yozilgan row qiladi.

## What an order is

**Bir branch'da oʻlchamga kesilgan panel'ga client'ning soʻrovi** — item'larni, status
history'ni, production stamp'larni va frozen price snapshot'ni ushlab turadigan header.
**Faqat client tomonidan**, **chosen algorithm result**'iga ega cutting **draft**'dan
yaratiladi (result'siz order yoʻq — draft yaratishda `confirmed` boʻladi va bind
qilinadi; [`cutting.md`](cutting.md)'ga qarang).

Creation'da set qilinadi:

- **Branch** — client cutting'ning material set'ini fulfil qila oladigan bitta active
  branch'ni tanlaydi; cutting'dagi har bir `shop`-source panel **va har bir `shop`-source
  edge material**'ni olib yurmaydigan branch'lar koʻrsatilmaydi. Tanlov pricing'ni shu
  branch'ning rate'lariga qarshi **muzlatadi**.
- **Material source — panel uchun per-item, edge uchun per-side.** Har bir part `shop`
  (workshop panel'ni yetkazib beradi; inventory uning uchun avto-decrement qiladi) yoki
  `own` (client panel'ni olib keladi; faqat cutting service, oʻsha panel uchun stock
  harakati yoʻq). Har bir banded edge side mustaqil ravishda `shop` (workshop oʻsha
  tape'ni yetkazib beradi; inventory consumed length'ni ichkarida integer millimetres
  sifatida decrement qiladi, display va pricing'da metres sifatida koʻrsatiladi) yoki
  `own` (client tape'ni olib keladi; oʻsha side uchun stock harakati yoʻq). Order har bir
  level'da source'larni aralashtirishi mumkin; toʻliq `own` order stock'ga tegmaydi va
  saw'li har qanday active branch'da joylashtirilishi mumkin.
- **Handover — faqat pickup.** Client branch'da olib ketadi. Delivery v1'dan tashqarida
  ([`scope.md`](../../scope.md)).

**Post-placement modification yoʻq.** Agar biror narsa notoʻgʻri boʻlsa, order cancel
qilinadi (reason bilan) va client qayta cut qiladi va qayta order qiladi — bitta qoida,
re-pricing mexanikasi yoʻq.

## The state machine

Bitta toʻgʻri spine bitta gateway bilan — *biror part edge banding kerakmi?* Tepadan
pastga oʻqing: yaxlit yoʻl happy flow va punktir strelkalar operator **revert** (bir
step orqaga, xato tuzatish). **Cancellation chizilmagan** — u har bir quti orqali
oʻtgan boʻlardi: har qanday non-terminal status `cancelled`'ga oʻtishi mumkin (pastdagi
jadvalga qarang).

```mermaid
flowchart TD
    start([▶ client places order]) --> new[new<br/>placed · awaiting review]
    new -->|operator approves| confirmed[confirmed<br/>verified · awaiting cutter]
    confirmed -->|operator assigns a cutter| cutting[cutting<br/>cutter at the saw]
    cutting -->|Cutting done| gate{any part<br/>edge-banded?}
    gate -->|yes| edge_banding[edge_banding<br/>edger working]
    gate -->|no| ready[ready<br/>awaiting collection]
    edge_banding -->|Banding done| ready
    ready -->|operator marks collected| done([● completed])

    cutting -. "revert" .-> confirmed
    edge_banding -. "revert" .-> cutting
    ready -. "revert" .-> edge_banding
```

`completed` va `cancelled` **terminal**. Post-collection muammo (return, complaint) v1'dan
tashqarida ([`scope.md`](../../scope.md)) — dizayn boʻyicha `completed` final.
`edge_banding` hech bir part banded boʻlmaganda oʻtkazib yuboriladi (gateway'ning *no*
filiali).

### Transitions

Kim har bir step'ni trigger qiladi (per-branch grant orqali — fixed role yoʻq) va uning
effect'i:

| From → To | Trigger · who | Effect |
|---|---|---|
| — → `new` | client places the order from a chosen cutting result | price snapshot frozen |
| `new → confirmed` | **Approve** · `manage_orders` (reviewed, client called) | — |
| `new → cancelled` | **Cancel** · client (only while `new`) or `manage_orders` + reason | — |
| `confirmed → cutting` | **Assign a cutter** · `manage_orders` — the assignment *is* the trigger; the edger is assigned now too if any part is banded | — |
| `cutting → edge_banding` | **Cutting done** · `process_production`, or `manage_orders` on-behalf — *gateway: a part is banded* | stamp the cutter + snapshot; **decrement panel stock** (`shop` panels) |
| `cutting → ready` | **Cutting done** · same — *gateway: no part is banded* | stamp the cutter + snapshot; **decrement panel stock** (`shop` panels) |
| `edge_banding → ready` | **Banding done** · `process_production`, or `manage_orders` on-behalf | stamp the edger + snapshot; **decrement edge stock per edge material** (`shop` sides only) |
| `ready → completed` | **Mark collected** · `manage_orders` | stamp `picked_up_at` |
| `* → cancelled` | **Cancel** · `manage_orders` + reason (any pre-`completed` status) | already-decremented material stays consumed |
| revert: `cutting→confirmed`, `edge_banding→cutting`, `ready→edge_banding\|cutting` | **Revert** one step · `manage_orders` + reason | clears that step's stamps; **re-increments** the stock it decremented |

### Rules

- **Har bir job uchun bitta tugma; per-item ish yoʻq.** Worker'lar line item'larni
  boshqarmaydi. Cutter cutting plan'ni read-only koʻradi va **Cutting done**'ni bir marta
  belgilaydi; edger **Banding done**'ni bir marta belgilaydi. `manage_orders` user job'ni
  **on behalf** tugatishi mumkin (worker yoʻq / system issue) — dialog **"Kim bu ishni
  qildi?"**'ni soʻraydi, default assignee'ga; tanlangan user production report'lar uchun
  **credit oladi** ([`finance.md`](finance.md)).
- **Re-assignment** — oʻsha job done deb belgilanmaguncha cutter yoki edger qayta
  tayinlanishi mumkin.
- **Revert faqat xato tuzatish** — bir step, hech qachon `completed` yoki `cancelled`'dan
  tashqari.
- **Har bir transition `order_status_event`** (actor, from → to, reason, metadata),
  append-only, audit log'ga mirror qilinadi.
- **Optimistic locking** transition'larda (`version` column): concurrent staff
  action'lar serialize boʻladi; mag'lub yangilash va qayta urinishni xabar qilinadi.

### Production stamps

Cutter va edger — order'ning branch'ida `process_production` ushlab turgan workshop
user'lar, `home_branch_id = order.branch_id` bilan — **owner istisno**, u har bir
branch'da implicit ravishda `process_production` ushlab turadi va `home_branch_id`'idan
qatʼi nazar har qanday branch'da cutter yoki edger sifatida tayinlanishi mumkin (bir
odam shop'ining owner'i branch'lar oʻrtasida suzadi; constraint non-owner staff'ni ular
jismonan ishlaydigan branch'da ushlab turish uchun mavjud va owner'da bunday home
yoʻq). Alohida worker entity yoʻq —
[`access-patterns.md`](../../access-patterns.md)'ga qarang. System har bir job'ning
tugashida order'ni stamp qiladi; bu stamp'lar accountant ishlatadigan worker-production
report'larining **yagona** input'i ([`finance.md`](finance.md)).

| Stamp | Set at | Read by |
|---|---|---|
| `cutter_user_id`, `cut_completed_at`, `panels_used_snapshot`, `cut_count_snapshot` | `cutting → next` | production report (panels / cuts) |
| `edger_user_id`, `edge_completed_at`, `edge_length_snapshot` (by edge material) | `edge_banding → ready` | production report (metres of banding) |
| `picked_up_at` | `ready → completed` | client notify · audit |

v1'da order uchun bitta cutter, bitta edger. Stamp'lar bir marta set qilingandan keyin
immutable, transition bilan bir xil atomic transaction'da yoziladi va ularni qoʻygan
step'ning **revert'i tomonidan tozalanadi**.

## The stock seam

Toʻliq shu state machine tomonidan boshqariladi; mexanika
[`catalog-inventory.md`](catalog-inventory.md)'da yashaydi. Kontrakt:

- **Reservation yoʻq.** Verification past stock tomonidan **hech qachon
  bloklanmaydi** — baʼzi workshop'lar per order xarid qiladi. Approval'da agar `shop`
  material'ning projected balance bu order'ni qoplay olmasa, operator **warning**
  koʻradi (projected = on-hand minus oldidagi hali decrement qilmagan active
  order'larning demand'i), shunda u warehouseman'ga ogohlantirishi mumkin. Bu warning,
  gate emas.
- **Job tugashida avto-decrement.** `shop` panel'lar **Cutting done** belgilanganda
  decrement qilinadi; har bir `shop` edge material'ning consumed length'i **Banding done**
  belgilanganda decrement qilinadi (order'ning `edge_length_snapshot`'i shop millimetres
  bilan olib yurgan har bir edge material uchun bittadan inventory transaction — bular
  display/pricing'da **consumed** metres, *Pricing*'ga qarang).
  Revert oʻzining step'i decrement qilganini aniq qayta increment qiladi.
- **`own` part'lar va `own` edge side'lar stock'ga hech qachon tegmaydi.** `shop` panel
  va `shop` edge side yoʻq order bu seam'ni butunlay oʻtkazib yuboradi.
- **Decrement'dan keyin material sarflangan.** Panel'lar/edge'lar allaqachon decrement
  qilingan order'ni cancel qilish ularni **qayta tiklamaydi** (ular fizik ravishda
  kesilgan); yoʻqotish workshop'ga tegishli, offline yoziladi.

## The money seam

Order **hech qachon payment yoki refund ushlab turmaydi**. Barcha pul finance module'da
yashaydi ([`finance.md`](finance.md)): accountant (`manage_finance`) order'ga qarshi
*income* yozadi — client haqiqatda qancha toʻlagani (toʻliq yoki qisman) va sana —
counter'da. In-system payment yoʻq, gateway yoʻq, payment-driven status yoʻq.

- **Bitta disclosure rule.** Order'ning pul'ini ikkita qismga ajrating va ularni
  boshqacha gate qiling:
  - **Frozen total + price breakdown** client'ga **placement'dan boshlab** koʻrinadi
    (Overview tab). Client bu raqamlarni order wizard'da koʻrgan; pricing creation'da
    muzlatiladi va hech qachon qayta price qilinmaydi, shuning uchun yashiradigan
    narsa yoʻq va yashirish faqat chalkashtiradi ("bu qancha turadi?").
  - **Settlement figures** — hozirgacha yozilgan va balance — client'ga **faqat
    `ready` va `completed`'da** koʻrinadi (Finance tab), olib ketishda toʻlash kerak
    boʻlgan paytda va keyin receipt uchun. In-app payment action yoʻq; discrepancy
    ("Men toʻladim, belgilanmagan") workshop'ga qoʻngʻiroq qilib out-of-system hal
    qilinadi.
  - **Workshop side.** `view_finance_reports` yoki `manage_finance` bilan staff order
    detail'ida **har qanday** status'da read-only settlement summary (total /
    recorded / balance) koʻradi, finance module'dan manba olingan — client'ning
    ready/completed gate'idan farqli. Bu payments tab emas; pul yozish va tuzatish
    finance module'da qoladi ([`finance.md`](finance.md)).
- **Cancellation hech qachon refund record yaratmaydi.** Agar pul qaytishi kerak boʻlsa,
  accountant finance module'da *expense* book qiladi. Cancel qilingan order faqat
  oʻzining reason'ini olib yuradi.

## Pricing

System hammasini hisoblaydi; **discount yagona inson input'i** va reason talab qiladi.
Creation'da order'ga tanlangan branch'ning rate'lariga qarshi muzlatiladi; keyingi
catalog yoki pricing oʻzgarishlari mavjud order'ga hech qachon yetib bormaydi (qayta
price qilish yoʻq — modification yoʻq).

| Component | When | Source |
|---|---|---|
| Cutting service | always | the branch's `cutting_rate_tiyin` × the chosen result's total panels — one rate, applied per panel cut (v1's only model) |
| Panel materials | parts with `material_source = shop` | Σ (the branch's per-panel price × panels attributable to that material's `shop` parts) |
| Edge materials | per side, when the side has an edge material and `source = shop` | Σ (**consumed metres** of that edge material × the branch's per-metre **raw material** price on its Branch material `edge` selection) |
| Edge banding labour | when any `shop` side has banding | total `shop` **consumed metres** of banding × the branch's `edge_banding_rate_tiyin` (one labour rate, all thicknesses) |
| Discount | when a `manage_orders` user adds one | percent or fixed sum; subtracted; **reason + the user id recorded** (audited); no enforced cap in v1 — the reason + audit are the control |

**Total = cutting + panel materials + edge materials + edge banding labour − discount.**

**Consumed metres.** Banded side koʻrinadigan edge'idan koʻproq tape yeydi: master uni
uzunroq yopishtiradi va keyin tekis qirqadi — har bir side uchun ~3 sm (har bir uchida 15 mm).
Shuning uchun edge metr'lar — edge-material price, banding labour, client'ning tape total'i
**va** stock decrement ortidagi yagona figura — geometric emas, **consumed**:

> consumed metres (per edge material) = the cutting result's geometric `edge_length_by_material`
> + a fixed **30 mm trim overhang** × the order's banded `shop` sides for that material

30 mm overhang — **har bir branch'da bir xil system constant** (har bir banded side uchun
3 sm workshop standarti, shuning uchun branch'da sozlanmaydi). Banded-side count order'ning
oʻz per-side edge pick'laridan keladi; `own` side'lar na bill qilinadi na decrement qilinadi,
shuning uchun yigʻindiga kirmaydi. Overhang constant boʻlgani uchun consumed figura **cutting
result**'dan boshlab maʼlum — branch tanlangandan keyingina emas — shu sababli client wizard'da
([`cutting.md`](cutting.md)) haqiqiy metr'larni koʻradi; faqat *price* branch'ning rate'larini
kutadi. Bitta figura — downstream'da alohida geometric-vs-consumed column'lar yoʻq.

**Operational setup gap'lar baland tovushda fail boʻladi.** Agar branch'ning cutting
rate'i set qilinmagan boʻlsa, banded part'lar bor lekin edge-banding ish haqi rate'i
set qilinmagan boʻlsa, yoki part ishlatadigan edge material'ni branch olib yurmasa,
order creation aniq error bilan fail boʻladi va client boshqa branch tanlaydi —
owner branch'ning pricing'ini yoki selection'ini tuzatishi kerak
([`catalog-inventory.md`](catalog-inventory.md)). Tegishli error code'lar:
`missing_cutting_rate`, `missing_edge_banding_rate`, `branch_does_not_carry_panel`,
`branch_does_not_carry_edge`.

## UX — client app

Client app'ning home'i cutting wizard entry'si (**New cutting** + **My drafts** + **My
orders**). Branch placement'da, aniq cutting'ga qarshi tanlanadi — draft'ning
`preferred_branch_id`'i set boʻlsa shundan default boʻladi.

- **Cutting wizard** — [`cutting.md`](cutting.md)'ga qarang. Entry point va client
  oʻz vaqtining koʻp qismini sarflaydigan joy.
- **Order create wizard** (`/c/orders/new/:draftId`) — cutting result'ning **Place
  order with this cutting** tugmasidan ochiladi. Draft hali ham chosen result bilan
  `draft` ekanini pre-check qiladi (boʻlmasa toast bilan redirect). Ikki ekran, har
  birida sticky summary card (parts, har bir material uchun panel'lar, har bir
  material uchun edge metr — **consumed**, standart trim allaqachon qoʻshilgan — waste %, branch tanlangandan keyin total):

  1. **Branch pick.** Cutting'ning material set'ini fulfil qila oladigan active
     branch'lar (har bir `shop` panel va har bir `shop` edge side'ning material'i).
     Toʻliq-`own` cutting saw'li har qanday active branch'ni qabul qiladi. Draft'ning
     `preferred_branch_id`'i (agar u fulfil qila olsa) "Recommended — your preferred
     branch" chip bilan tepada **oldindan tanlangan** boʻladi; client xuddi shu
     step'da boshqa har qanday fulfilling branch'ga oʻtishi mumkin. Har bir card:
     name, address, today's hours va shu branch'ning rate'larida **price breakdown**
     (cutting, har bir material uchun panel material — faqat `shop` qismi, har bir
     edge material uchun edge banding — faqat `shop` qismi, **subtotal**). Card'ni
     tap qilish branch'ni commit qiladi va pricing'ni muzlatadi. Empty / error
     state'lari: hech bir branch set'ni olib yurmaydi (offending material'larni list
     qiladigan inline panel + "flip these to *I'll bring it*" link); branch
     `temporarily_closed` boʻldi (reason bilan greyed card); branch pricing
     toʻliq emas (greyed, "this branch can't take orders right now").
  2. **Checkout** — bitta scrollable sahifa, ikki section:
     - **Contact** — phone va name, client'ning profile'idan prefill qilingan,
       checkout dan keyin workshop-facing contact snapshot sifatida order ga frozen qilinadi.
       inline tahrirlanadigan, non-dismissible note bilan: *"This is shared with the
       workshop so they can call you about your order."* va har bir field uchun
       reset-to-profile link.
     - **Review** — final price breakdown + pickup branch (address + hours) +
       contact. Primary **Place order** tugma; Edit link tegishli field'ga qaytaradi.

  Client payment plan tanlamaydi va online hech narsa toʻlamaydi — payment workshop'ning
  accountant'i tomonidan counter'da yoziladi ([`finance.md`](finance.md)). Success'da
  → `/c/orders/:id` banner bilan: *"Order placed — the workshop will review and call
  you."*

- **My orders** (`/c/orders`) — status dropdown (All / Active / Completed / Cancelled),
  order number bo'yicha search, cards (order #, branch, date, status badge, **frozen
  total** — placement'dan ko'rsatiladi, hech qachon "price after confirm" emas, chunki pricing
  creation'da frozen — primary action "Track", order detail'ni ochadi). Empty: "No orders
  yet — start from a cutting."
- **Order detail** (`/c/orders/:id`) — header (order #, branch, status badge,
  vaqtlar). Client-facing status **besh phase**: Placed → **Confirmed** → **In
  production** → **Ready** → Done — `cutting`/`edge_banding`'ni "In production"'ga
  qoʻshib, ixtiyoriy sub-text bilan. Tab'lar: Overview (item snapshot'lar, price
  breakdown, izohlar), Cutting (SVG + PDF link; agar bind qilingan result
  `invalidated` boʻlsa izoh), **Finance** (**faqat `ready` va `completed`'da**
  koʻrinadi — total, hozirgacha yozilgan, balance; read-only; "contact the workshop
  about a payment" hint), Timeline. "Cancel" faqat `new` paytida koʻrsatiladi.
- **Branches page** (`/c/branches`) — passive directory (name, address, hours,
  materials carried); flow'ning boshlanishi emas; per-branch CTA yoʻq.

## UX — workshop app

Quyidagi permission nomlari
[`access-management.md`](access-management.md)'dagi per-branch grant'lar; bitta user
hammasini ushlab turishi mumkin.

- **Orders** (`/workshop/orders`, koʻrish uchun `view_dashboard`; harakat uchun
  `manage_orders`) — branch-scoped, ikki rejim:
  - **Board** — ustunlar `new` / `confirmed` / `cutting` / `edge_banding` / `ready`;
    har bir header'da count; card'lar: order #, client name + phone, total, item
    count, age, set qilinganda tayinlangan cutter / edger chip. **Status ustunlari
    oʻrtasida drag yoʻq** — status oʻzgarishlari card'ning action menu orqali
    boradi.
  - **Table** — sortable; ustunlar: order #, branch (multi-branch boʻlsa), client,
    total, items, created, action menu. Filters: status dropdown, search, date range,
    date range, branch. Empty: "No orders in your branch(es)." Zero branches: "No
    branches assigned — ask your workshop owner."
- **Order detail** (`/workshop/orders/:id`) — header (order #, branch chip, client
  mini-card link, status badge, total) status'ga mos action'lar bilan:

  | Status | Actions | Permission |
  |---|---|---|
  | `new` | Approve (→ `confirmed`) · Cancel (reason) · Apply discount (reason) | `manage_orders` |
  | `confirmed` | Assign cutter (→ `cutting`) · Assign / change edger · Apply discount · Cancel (reason) | `manage_orders` |
  | `cutting` | Cutting done (→ `edge_banding`/`ready`; decrements panels) · Revert → `confirmed` (reason) · Cancel (reason) | done: `process_production` or `manage_orders` on-behalf · revert/cancel: `manage_orders` |
  | `edge_banding` | Banding done (→ `ready`; decrements edges per material) · Revert → `cutting` (reason) · Cancel (reason) | done: `process_production` or `manage_orders` on-behalf · revert/cancel: `manage_orders` |
  | `ready` | Mark collected (→ `completed`) · Revert → `edge_banding`/`cutting` (reason) · Cancel (reason) | `manage_orders` |
  | `completed` / `cancelled` | (read-only) | — |

  On-behalf job tugatish **"Kim bu ishni qildi?"**'ni soʻraydi (default assignee'ga;
  tanlangan user credit oladi). Destructive action'lar (cancel, revert) va "Mark
  collected" effect'ni nomlaydigan danger / confirm dialog ishlatadi ("client
  collected everything?").

  Tab'lar: Overview (per-side edge material'larni koʻrsatadigan item snapshot'lar,
  price breakdown, **read-only settlement summary** — total / recorded / balance,
  finance module'dan manba, `view_finance_reports`/`manage_finance` bilan staff'ga har
  qanday status'da koʻrsatiladi; boshqa hollarda yashiriladi — `shop` material kam
  boʻlsa warehouse warning, internal note — inline tahrirlanadigan), Cutting (SVG +
  PDF; agar mavjud boʻlsa invalidated izoh), Timeline (status event'lar + audit),
  Notes. Bu yerda **Payments yoki Refunds tab yoʻq** — pul yozish va tuzatish
  finance module; summary read-only mirror.

- **Cutter workspace** (`/workshop/cutting`, `process_production`) — tablet uchun
  optimallashtirilgan. Bu user'ga **tayinlangan** order'larni list qiladi: `confirmed`
  (tayinlangan, kesish kutilmoqda) va `cutting` (uniki, jarayonda). Card: order #,
  parts count, kerakli panel'lar, age, cutting plan link (saw uchun SVG / PDF).
  Bitta action: **Cutting done** (cutter'ni + snapshot'ni stamp qiladi, panel'larni
  decrement qiladi, agar biror banded part boʻlsa `edge_banding`'ga aks holda
  `ready`'ga route qiladi). Empty: "Nothing assigned — nice."
- **Edger workspace** (`/workshop/banding`, `process_production`) — shu user'ga
  tayinlangan `edge_banding` order'lar uchun bir xil shape. Card: order #, parts,
  edge material boʻyicha total metr (faqat `shop` side'lar hisoblanadi), age. Bitta
  action: **Banding done** (edger'ni + metres-by-material snapshot'ni stamp qiladi,
  har bir edge material uchun stock'ni decrement qiladi, → `ready`).

State'lar: list / detail har biri loading / empty / error'ga ega; action'lar busy
state koʻrsatadi va success yoki recoverable error'da tugaydi; optimistic-lock
conflict "this order changed — refresh and try again" sifatida paydo boʻladi;
infinite spinner yoʻq. Accessibility: board keyboard-navigable; status action'lar
labelled menu'da, drag target emas; destructive action'lar danger-styled va
effect'ini nomlaydi; modal focus boshqariladi.

## Edge cases

- **Cutting draft allaqachon ishlatilgan / client'niki emas / `draft` emas** →
  `cutting_result_not_usable`; uning detail'iga redirect.
- **Branch cutting va order oʻrtasida `inactive` / `temporarily_closed` boʻldi** →
  `branch_closed`; client boshqa branch tanlaydi.
- **Cutting va order oʻrtasida workshop block qilindi** → `workshop_blocked`.
- **Branch'ning `cutting_rate_tiyin`'i set qilinmagan** → `missing_cutting_rate`;
  client "this branch can't take orders right now" koʻradi; workshop app branch'ni
  flag qiladi.
- **Order'da banded part'lar bor lekin branch'ning `edge_banding_rate_tiyin`'i set
  qilinmagan** → `missing_edge_banding_rate`; xuddi shu gate va flag.
- **Branch cutting ishlatadigan `shop` panel'ni olib yurmaydi** →
  `branch_does_not_carry_panel`; cutting wizard'ning recovery affordance (bring own /
  swap) buni avvalroq qamrab oladi; order step final gate.
- **Branch side ishlatadigan `shop` edge material'ni olib yurmaydi** →
  `branch_does_not_carry_edge`; xuddi shu affordance path.
- **Verification'da `shop` material kam** → approval **bloklanmaydi**; operator
  warning koʻradi va warehouseman'ga ogohlantiradi
  ([`catalog-inventory.md`](catalog-inventory.md)).
- **Hech qanday decrement'dan oldin cancel** (`new` / `confirmed` / `cutting`) →
  stock oʻzgarishi yoʻq.
- **Decrement'dan keyin cancel** (`edge_banding` / `ready`) → kesilgan material
  sarflangan, qayta tiklanmaydi; agar pul qaytarilsa, u accountant expense
  ([`finance.md`](finance.md)).
- **Revert** → oldingi step'ning stamp'larini aniq teskari oʻgiradi va oʻsha step
  decrement qilgan stock'ni qayta increment qiladi (edge'lar uchun step consume
  qilgan har bir edge material uchun bittadan restore); hech qachon `completed`'dan
  tashqari.
- **Order'da banded side yoʻq** → `edge_banding` oʻtkazib yuboriladi; **Cutting
  done** toʻgʻridan-toʻgʻri `ready`'ga oʻtadi.
- **Order'da banded side bor lekin har bir side `own`** → `edge_banding` step hali
  ham ishlaydi (edger client olib kelgan tape'ni qoʻllaydi), lekin **Banding
  done**'da hech qanday inventory transaction ishga tushmaydi — `shop`
  metres-by-material boʻsh.
- **Bir odam `manage_orders` + `process_production` ushlab turadi** → toʻgʻri; u
  approve qiladi, oʻzini tayinlaydi va job'larni tugatadi (oʻziga credit oladi). v1
  **separation of duties yoʻq** deb hisoblaydi.
- **Concurrent staff transition'lar / cancel** → ikkinchisida optimistic-lock
  conflict; refresh va qayta urinish.
- **Boshqa branch'dan cutter / edger, block qilingan user yoki bu branch'da
  `process_production`'siz** — assignment'da rad etiladi. **Owner istisno**
  same-branch (`home_branch_id = order.branch_id`) check'idan — u har joyda
  `process_production` ushlab turadi va har qanday branch'da oʻzini tayinlashi
  mumkin.
- **Worker yoʻq** — order `confirmed` (yoki `edge_banding`)'da kutadi; board ustun
  count'ini flag qiladi; `manage_orders` user on-behalf tugatishi mumkin.
  Auto-timeout yoʻq.
- **Client yozilgan payment'ga eʼtiroz bildiradi** — out-of-system; client workshop'ga
  qoʻngʻiroq qiladi va accountant finance module'da income'ni tuzatadi.
- **Cutting result invalidated** (uning draft'i boshqa joyda qayta cut qilingan) →
  order'ning bind qilingan result'i oʻzgarmagan; detail izoh koʻrsatadi.

## Next

- [`cutting.md`](cutting.md) — the cutting-result lifecycle the order binds and
  depends on.
- [`catalog-inventory.md`](catalog-inventory.md) — materials, the warehouse, and the
  auto-decrement contract this state machine drives.
- [`finance.md`](finance.md) — order income, the worker-production reports, and
  expenses.
