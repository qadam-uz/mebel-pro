---
title: Workshop administration
status: draft
owner: shape
updated: 2026-06-02
order: 40
---

# Workshop administration

Workshop'ni ishlab turishi uchun owner-and-staff surface'lar — workshop settings va branch
CRUD. Workshop'ning action va status log'lari ustidagi **audit viewer** ham shu yerda spec
qilinadi, ammo v1'da u **faqat superadmin-app surface** — workshop owner'lar hali in-app audit
screen olmaydi (qarang [`scope.md`](../../scope.md)). Sign-in,
sessions, provisioning, va staff management [`access-management.md`](access-management.md)'da
yashaydi; income, expenses, va worker-production report'lar [`finance.md`](finance.md)'da
yashaydi.

## Workshop settings

Workshop'ning mutable profile'i:

- **Profile** — name, logo, phone, address. Workshop'ning owner'i tomonidan editable. Platform
  operator'lar incident response uchun profile'ni view qila oladi, lekin v1 ularga edit path
  bermaydi.
- **Currency** — UZS, v1'da fixed; future-proofing uchun shu yerda nomlangan.

Delivery zones, advance %, va payment channel'lar **v1'da emas** — v1 pickup-only va order
hech qanday money move qilmaydi ([`scope.md`](../../scope.md)); ular delivery va gateway
bilan qaytadi.

`is_owner` qoplaydigan owner-only kuch (access-management permission catalog'ga qarang):
settings'ni edit qilish.

### UX (superadmin app)

- **Workshops list** (`/admin/workshops`) — table: name, owner (name + phone), status badge,
  created, branches count, orders-30d count. Status filter; name search;
  **+ Workshop** (provisioning access-management'da). Empty: "No workshops yet."
- **Workshop detail** — header (name, status, owner, created); tabs: **Profile** (read-only),
  **Branches** (read-only list), **Block** (mandatory reason bilan block / unblock;
  destructive-styled; staff sessions revoke qilinishi va open order'lar freeze bo'lishi haqida
  ogohlantiradi).

### UX (workshop app)

- **Workshop settings** (`/workshop/settings`, owner-only): yagona **Profile** tab (name,
  logo, phone, address).

## Branches

Workshop bir yoki bir nechta branch'ga ega. Har bir branch'ning physical address'i, working
hours'i, qo'lda kiritilgan `(lat, lng)`'i, va `status`'i bor — semantika
[`access-patterns.md`](../../access-patterns.md#tenancy)'da.

Platform provisioning first branch'ni yaratgandan keyin branch operations **owner only**:

- **Create / edit a branch** — name, address, phone, lat / lng, per-weekday working hours.
  Branch yaratish bo'sh `branch_pricing` row ham yaratadi; stock item'lar branch'ning
  material selection'i qurilgani sari paydo bo'ladi.
- **Change status** — `active` ↔ `temporarily_closed` ↔ `inactive`. `temporarily_closed`
  optional reason olib yurishi mumkin. **Status change'lar staff session yoki grant'larni
  revoke qilmaydi** — `inactive` branch'dagi staff grant branch reactivate qilingunicha
  inert turadi xolos. Branch hech qachon delete qilinmaydi.

Branch'ni open order'lari bor paytida `inactive` qilish ruxsat etiladi (o'sha order'lar
normal tugaydi); UI ogohlantiradi va nechtaligini list qiladi.

Read operation'lar uchun visibility:
- Owner o'z workshop'ining har bir branch'ini ko'radi.
- Staff faqat grant ushlagan branch'larini ko'radi.
- Client har qanday workshop'ning `active` va `temporarily_closed` branch'larini ko'radi
  (picker bo'yicha).

### UX

- **Branches list** (`/workshop/branches`) — table: name, address, phone, status badge,
  materials count, workers count, low-stock count, active-orders count, action menu.
  **+ Branch** (owner). Empty: "No branches yet — add one to start taking orders."
- **Branch form dialog** — name, address, phone, lat / lng (numeric, range-validated),
  working-hours grid (per weekday open / close, "closed this day" toggle bilan), status.
- **Branch detail** (`/workshop/branches/:id`) — header (name, address, status, action set:
  change status · edit). Tabs: **Overview** (status, active-orders count, revenue 30d,
  low-stock count) · **Materials** · **Stock** · **Settings** · **Staff** (bu yerda read-only;
  bu branch'ni `home_branch` qilgan har kimni plus unda grant'i bor har kimni ko'rsatadi;
  [`access-management.md`](access-management.md)'da managed) · **Orders**. Materials,
  Stock, va Settings tab'lari [`catalog-inventory.md`](catalog-inventory.md) tomonidan owned;
  Orders [`orders.md`](orders.md) tomonidan.
- `temporarily_closed` branch reason bilan banner ko'rsatadi; `inactive` branch inactive
  banner ko'rsatadi.

## Audit viewer

Bu feature'ni ikkita append-only log qo'llaydi: **action log** (har bir mutating use case row
yozadi — actor, action, entity, branch, masked details) va **status change log** (har bir
order status transition). Ikkalasi ham source'da write-only; bu feature ularni faqat o'qiydi.

v1'da viewer **faqat superadmin app'da** yashaydi — platform operator'lar workshop'lar boʻylab
hammasini ko'radi, workshop filter bilan. Workshop owner'ning hali **in-app audit viewer'i
yo'q** (log'lar baribir ularning workshop'iga qarshi yoziladi).

### UX

- Superadmin app'da: ikkita tab'li **Audit** section — **Action log** (filters: action type /
  family, module, actor search, entity type + id, date range, branch, **workshop**;
  JSON-collapsible `details` preview'li row'lar) va **Status changes** (filters: entity type +
  id, from→to, actor, date range; transition'ni ko'rsatadigan row'lar). Har bir row mavjud
  bo'lsa ta'sirlangan entity'ga link qiladi. Read-only; workshop scoping yo'q.
- States: loading (skeleton row'lar), empty, error (`trace_id` bilan); `details` expander
  masked JSON'ni ochib beradi.

## Edge cases

- **Set a branch `inactive` with open orders** — ruxsat etiladi; warning nechtaligini list
  qiladi; o'sha order'lar normal tugaydi.
- **`temporarily_closed` branch in a client's branch picker** — reason bilan va disabled
  "start cutting" CTA bilan ko'rsatiladi.
- **Sensitive fields in audit `details`** — write time'da masked; hech qachon ko'rsatilmaydi.

## Next

[`catalog-inventory.md`](catalog-inventory.md) — branch platform catalog'dan nima saqlaydi,
uning narxlari, va uning stock'i.
