---
title: Platform operations
status: draft
owner: shape
updated: 2026-05-17
order: 70
---

# Platform operations

Superadmin app'ning ops burchagi: scheduled background job'lar, application-error monitor, va
platform-user registry. Workshop provisioning va block / unblock
[`access-management.md`](access-management.md)'da yashaydi.

## Background jobs

Backend **in-process scheduler** ishlatadi — external queue yo'q, Celery yo'q, cron yo'q. v1
job'lari:

| Job | When | What |
|---|---|---|
| `expire-draft-cuttings` | daily | expire cutting drafts past their TTL (see [`cutting.md`](cutting.md)) |
| `cleanup-expired-sessions` | hourly | prune expired session rows |
| `daily-low-stock-summary` | daily | per branch, one notification rolling up the day's low-stock conditions |

Job ikki marta concurrent ishlamaydi (guard). Failed job o'z result'ini record qiladi va
platform operator'larni notify qiladi; operator uni qo'lda re-trigger qila oladi.

Operator'lar job'larni list qila oladi (schedule, last run, last result, brief log) va on
demand run trigger qila oladi.

## Error monitor

Backend application error'larni record qiladi. Monitor **ularni code bo'yicha group qiladi**,
count'lar bilan (24 h / 7 d), last occurrence, va preview message. Operator'lar bitta code'ga
drill in qilib full message, stack trace, request / context details (sensitive field'lar write
time'da masked), trace id'lar, va ma'lum bo'lsa ta'sirlangan workshop / user'larni ko'ra
oladi — va code'ni resolved marked qila oladi.

Error spike (code'ning 24 h count'i threshold'dan oshib ketishi) platform operator'larni
notify qiladi.

Health endpoint'lar (liveness uchun `/api/v1/healthz`, DB-touching readiness check uchun
`/api/v1/readyz`) unauthenticated; docs site (`/docs`) edge orqali HTTP-Basic-gated.

## Platform user registry

Operator'lar platform user'larni list, create, password'ini reset, block, va unblock qila
oladi. Shape workshop-user management'ni mirror qiladi lekin **permission model'siz** — har
bir platform user full platform scope ushlaydi. Creation bir marta share qilish uchun temp
password qaytaradi (`force_password_change` set bilan,
[`access-management.md`](access-management.md)'ga qarang).

Platform operator o'zini block qila olmaydi, va oxirgi active platform operator block
qilinishi mumkin emas — har doim kamida bittasi bo'lishi shart.

Platform user'lar dastlab backend CLI command bilan seed qilinadi (chicken-and-egg);
keyinchalik in-app creation yo'l bo'ladi.

## UX (superadmin app)

**Platform** section ostida:

- **Jobs** (`/admin/platform/jobs`) — table: job name, schedule, last run (relative), last
  result (badge: ok / failed), action menu ("Run now" → confirm; "View log" → drawer). Failed
  row'lar highlight qilingan.
- **Errors** (`/admin/platform/errors`) — table: code, module, count (24 h / 7 d), last
  occurrence, preview message, action menu. Detail modal: full message, stack, masked context,
  affected workshops / users, trace id'lar; "Resolve" → confirm. Filters: module, code, time
  range, count threshold. Empty: "No errors recorded — nice."
- **Platform users** (`/admin/platform/users`) — table: name, login, phone, status, last login,
  action menu (Edit · Reset password → one-time-secret confirmation · Block / Unblock).
  "+ Platform user" → dialog (field'lar + auto / manual temp password).

Cross-workshop **Orders** (`/admin/orders`, read-only) [`orders.md`](orders.md)'da yashaydi;
**Audit** viewer [`workshop.md`](workshop.md)'da yashaydi (bu app'da cross-workshop render
qilinadi).

States: har bir page'da loading / empty / error; har bir state-changing action'da
confirmation; user yaratgandan yoki password reset qilgandan keyin one-time-secret
confirmation. Action menu'lar keyboard-operable; destructive action'lar confirm qiladi va o'z
effektini nomlaydi; result badge'lar colour'ni text bilan juftlaydi.

## Edge cases

- **A job fails** — uning result'i record qilinadi va ko'rsatiladi; operator'larga
  notification fire qiladi; operator re-trigger qila oladi.
- **Triggering a job already running** — guarded; UI shunday deydi.
- **An error code spikes** — count ko'tariladi; error-spike notification har threshold
  crossing'da bir marta fire qiladi.
- **Blocking a platform user mid-action** — ularning session'lari drop qilinadi; keyingi
  request 401 qaytaradi.
- **Block self or the last operator** — disallowed; UI uni prevent qiladi; server defensively
  reject qiladi.

## Next

[`notifications.md`](notifications.md) — operator'larga job-failure va error-spike alert'larni
surface qiladigan inbox.
