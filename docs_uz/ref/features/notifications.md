---
title: Notifications inbox
status: draft
owner: shape
updated: 2026-06-07
order: 60
---

# Notifications inbox

v1'ning yagona notification channel'i — **per principal in-app inbox**. Producing module'lar
(`orders`, `inventory`, `identity`, `workshop`, `platform`) notifiable event'da
`notifications` module'ni call qiladi va producer'ning scope rule'larini qo'llab, har bir
recipient uchun bitta row fan out qilishni so'raydi. Notifications module broadcast qilmaydi
va recipient'larni decide qilmaydi.

## How it works

- **Each principal has their own inbox.** Workshop-wide event (workshop blocked, low-stock
  condition) har bir ta'sirlangan staff member uchun bitta row fan out qiladi; har birining
  o'z unread count'i bor.
- **Pull delivery.** App'lar har ~30–60 s'da unread count'ni poll qiladi va list'ni on
  demand pull qiladi. v1'da WebSocket / SSE yo'q — bu scale'da overkill.
- **Each row carries a denormalized payload** (order number, branch name, amount, …) shunda
  dropdown follow-up fetch'siz render qila oladi; linked entity source of truth.
- **Coalescing.** Bitta material uchun low-stock event'lar toshqini daily summary job
  tomonidan kuniga material'ga bitta row'ga kamaytiriladi; live change'lar hali ham har
  biriga bittadan row ishlab chiqaradi.
- **Rows persist on block.** Blocked principal'ning row'lari qoladi (history); ular unblock'da
  qayta paydo bo'ladi.

Principal'ning o'z inbox'i quyidagilarni support qiladi: list'ni pull qilish (paginated,
newest first, optional unread filter va "since timestamp"), bell badge uchun unread count'ni
pull qilish, bittasini read marked qilish, hammasini read marked qilish.

## UX

Uchala app'da ham (client / workshop / superadmin), top bar'da:

- **Bell** — unread count'ni badge sifatida olib yuradigan labelled button (capped display:
  "9+"). Oxirgi ~10 notification'ni list qiladigan dropdown ochadi: event family'ga icon,
  payload'dan qurilgan bir qatorli summary, relative timestamp. Row'ni click qilish linked
  entity'ga navigate qiladi va uni read marked qiladi. Dropdown'da "mark all as read" va to'liq
  notifications page'ga "see all" link bor (paginated, read/unread filter bilan).
- **Toasts** critical event'lar uchun, badge'ga qo'shimcha — client uchun order status
  change; workshop staff uchun new order; owner uchun low stock; platform operator uchun
  error spike yoki failed job.
- **States** — zero unread'li bell (badge yo'q); dropdown loading; dropdown empty ("Nothing
  new"); notifications page'da loading / empty / error. Agar notifications endpoint down
  bo'lsa bell badge ko'rsatmaydi lekin underlying data hali ham tegishli page'larda
  reachable.
- **Accessibility** — bell unread count'ni announce qiladi; dropdown keyboard navigation'li
  proper menu / listbox; toast'lar announced, dismissible, va focus'ni trap qilmaydi;
  row'larning descriptive accessible name'lari bor (faqat icon emas).

## Edge cases

- **Notifications endpoint down** — bell badge ko'rsatmaydi; hech narsa buzilmaydi; data
  tegishli page'larda reachable.
- **A workshop-wide event** — har bir staff member uchun bitta row fan out qiladi; har
  birining o'z unread count'i bor.
- **Low-stock flood** — coalesced (daily job tomonidan kuniga material'ga bittadan); live
  change'lar hali ham har biriga bittadan ishlab chiqaradi.
- **A notification linking to an entity the principal can no longer see** (event'dan beri
  scope o'zgargan) — link leak qilish o'rniga "not available" state'ga resolve qiladi. Rare.

## Next

[`platform.md`](platform.md) — bularning ba'zilarini ishlab chiqaradigan job'lar (low-stock
summary, job failure) va error spike'da operator'larni notify qiladigan error monitor.
