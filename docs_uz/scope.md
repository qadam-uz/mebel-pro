---
title: Scope
status: stable
owner: shape
updated: 2026-06-03
order: 20
---

# Scope

v1 nimani qamrab oladi va nimani ataylab qamramaydi. v1 — haqiqiy workshop va haqiqiy mijoz
boshidan oxirigacha foydalana oladigan eng kichik system — furniture-cutting biznesi uchun
minimal ERP: mijoz koʻradigan storefront, staff yurituvchi workshop floor, inventory oʻtadigan
warehouse va accountant yopadigan books. Quyidagi "out" roʻyxati "in" roʻyxati qadar ogʻirlikka
ega: v1 integration oʻrniga manual path yetkazgan joyda (payments, refunds) — bu oʻylab qilingan
substitution.

## In scope

- **Identity & access** — platform operator'lar workshop'larni provision qiladi; owner'lar
  staff'ni per-branch permission'lar bilan boshqaradi; client'lar phone + Telegram OTP bilan
  self-register qiladi. Tenant-isolated, revocable, brute-force'dan himoyalangan.
- **Workshops & branches** — multi-branch workshop'lar; har bir branch platform-curated material
  catalog'dan nimani olib yurishini tanlaydi va oʻz price'lari, worker'lari va settings'ini
  belgilaydi.
- **Warehouse & inventory** (ERP core) — arrivals va adjustments bilan per-branch stock,
  stock-in uchun lightweight supplier label'lar, order'lar tomonidan boshqariladigan automatic
  consumption va low-stock surfacing. v1 da reservation balance yoʻq.
- **Optimized cutting** — bir nechta cutting-optimization algoritmlari parallel run boʻladi;
  platforma eng yaxshi result'ni qaytaradi va **gʻolib algoritmni nomlaydi**. Output har bir panel
  boʻyicha layout, panel count, waste, cut va edge-banding length va print-ready cutting map'ni
  oʻz ichiga oladi.
- **Orders** — finalized cutting result'dan client tomonidan joylashtirilgan order'lar, **frozen
  pricing** va kichik production workflow (verify → cut → band → ready → collected, pickup-only),
  bir qadamli operator revert va asoslangan cancellation bilan. Order faqat production'ni
  kuzatadi — u money harakatlantirmaydi va stock saqlamaydi.
- **Finance & accounting** — workshop money ledger: income (jumladan order payment'lari) va
  expense'lar (jumladan staff salary) qoʻlda yozib boriladi, accountant pay'ni hisoblashda
  foydalanadigan worker-production report'lar va branch va period boʻyicha revenue / expense / net
  reporting — system ichida bir oyni yopish uchun yetarli.
- **Cross-cutting** — file storage, toʻliq audit log, in-app notifications inbox va
  platform-ops console (scheduled jobs, error monitor, manual triggers).

## Out of scope (v1) — explicit

- **Online payment gateway'lar** va **BNPL** — v1 income va refund'larni qoʻlda yozadi; order
  money harakatlantirmaydi.
- **Automatic payroll / compensation engine** — v1 hech qanday pay rate saqlamaydi va salary
  hisoblamaydi; u har bir worker boʻyicha xom production'ni report qiladi va accountant salary'ni
  expense sifatida qoʻlda yozadi.
- **Post-placement order modification** — notoʻgʻri order (sabab bilan) cancel qilinadi va
  re-order qilinadi; edit / re-price path yoʻq.
- **SMS, email va bot notification'lar** — v1 faqat in-app.
- **Delivery fulfilment** — v1 **pickup-only**. Delivery model'i (address capture,
  fixed-fee zone'lar, driver flow, distance-based pricing, `process_delivery` grant)
  loyihalangan, ammo v1 dan tashqariga gate qilingan.
- **Workshop-wide control'larni non-owner staff'ga delegatsiya qilish** — v1 da owner-only.
- **Operator-created order'lar** — order'lar har doim client tomonidan joylashtiriladi.
- **Inter-branch stock transfer'lar** — v1 da har bir branch'ning stock'i mustaqil (faqat
  arrivals va adjustments); branch-to-branch transfer yoʻq. Agar material koʻchirish kerak boʻlsa,
  u har bir branch'da adjustment sifatida qoʻlda yoziladi.
- **Workshop-side audit viewer** — audit log hamma joyda yoziladi, ammo v1 viewer'ni faqat
  superadmin app'da koʻrsatadi; workshop owner'lar hali in-app audit screen olmaydi.
- **Operator browsing of workshop orders** — platform operator provision qiladi, block qiladi va
  monitor qiladi; v1 da cross-workshop order view yoʻq va operator'lar order kontentini oʻqimaydi.
- **Advanced cutting** — alternative result'lar, juda katta job'lar uchun async mode, manual layout
  edit'lar, bir nechta panel size, 3D nesting, CNC path'lar.
- **Advanced orders** — batching, reorder, template'lar, partial fulfilment, post-completion
  complaint'lar, client rating'lari.
- **Multi-currency** — faqat local currency.
- **Automatic purchase order'lar, supplier payable'lar / procurement management, remnant tracking,
  barcode scanning** — kelajak.

## Next

[`domain-model.md`](domain-model.md) — rol'lar boʻlishadigan ubiquitous language va entity map.
