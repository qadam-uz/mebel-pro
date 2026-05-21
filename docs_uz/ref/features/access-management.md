---
title: Identity & access
status: draft
owner: shape
updated: 2026-05-22
order: 20
---

# Identity & access

[`access-patterns.md`](../../access-patterns.md)'ning mexanikasi — har bir principal qanday
sign in qiladi, session'lar qanday ishlaydi, workshop'lar qanday provision qilinadi, staff va
ularning grant'lari qanday boshqariladi va surface'lar uchta app'da qanday ko'rinadi.

## Workshop & platform user sign-in

Login + password. Login case-insensitive; per workshop (workshop user'lar) yoki
platform-wide (platform user'lar) unique. Bad pair'dagi error **generic** "login or password
is incorrect" — account-existence oracle yo'q. **Ketma-ket besh bad attempt → 15-minutlik
lockout** (`locked_until`); to'g'ri password counter'ni reset qiladi. Password'lar at rest argon2 /
bcrypt-hashed; complexity ≥ 8 char kamida bitta upper, bitta lower, bitta digit bilan.

`force_password_change` (creation'da, higher-principal password reset'da va forced rotation'dan
keyin set qilinadi) user'ni gate qiladi — change-password / logout / get-me'dan boshqa
har bir operation user uni o'zgartirgunga qadar `password_change_required` qaytaradi.

**Platform user'lar backend CLI command bilan seed qilinadi.** Ular hierarchy'ning eng
tepasida, ularni yaratadigan higher principal yo'q; in-app creation kamida bitta platform
user mavjud bo'lganda ruxsat etiladi ([`platform.md`](platform.md)).

### Sessions

DB'da saqlangan opaque token'lar, hashed (SHA-256) — JWT emas. Access TTL **24 h**; refresh TTL
**7 d**; **per principal ko'pi bilan 5 concurrent session** (6-chi login eng eskisini evict
qiladi). Revoking = row'ni o'chirish.

| Trigger | Effect |
|---|---|
| logout (this session) | delete this session |
| "log out everywhere" | delete all the user's sessions |
| change own password | delete all *other* sessions; keep the current |
| reset password (higher principal) | delete all the user's sessions |
| block user | delete all the user's sessions |
| block workshop | delete the workshop's owner + staff sessions (clients unaffected) |
| 5-session cap exceeded | evict the oldest |
| token expiry | inert; a periodic job prunes the row |

### Operations

User sign in, sign out, o'z access token'ini refresh qila oladi (refresh path user'ni, va
workshop user'lar uchun workshop'ni, hali active ekanini re-check qiladi), o'z password'ini
o'zgartira oladi (barcha *boshqa* session'larni revoke qiladi; `force_password_change`'ni
clear qiladi), o'z session'larini list qilib bittasini yoki hammasini revoke qila oladi va
o'z `me`'sini fetch qila oladi (principal type, id'lar, `is_owner`, grant set,
`force_password_change`).

### UX

- **Sign-in screen** (workshop app `/auth/login`; superadmin app `/auth/login`) — login +
  password field'lar; failure'da generic error; `locked_until` qaytganda lockout banner
  ("try again at HH:MM").
- **Force-password-change screen** — birinchi login'da (yoki reset'dan keyin) ko'rsatiladi; strength meter
  (≥ 8 char, upper + lower + digit); set qilingunga qadar app'ning qolganini block qiladi.
- **Self profile** (`/workshop/profile`, `/admin/profile`) — Profile (read-only field'lar),
  Change password (strength meter), Sessions list (current marker, row bo'yicha "revoke", "log out
  everywhere").

## Client sign-in (phone + Telegram OTP)

Client **Telegram orqali yuborilgan one-time code bilan tasdiqlangan phone number** orqali sign
in qiladi — password yoʻq, widget yoʻq, app-switch yoʻq. Phone — bu identity; flow bitta uzluksiz
path boʻlib, raqam yangi boʻlgandagina registration'ga branch qiladi. Uchta qadam:

1. **Code soʻrash.** Client `+998XXXXXXXXX` phone yuboradi. System
   [verification challenge](../entities/identity.md#phone-verification-challenge) issue qiladi va
   oʻsha raqamga **Telegram orqali** (Telegram Gateway orqali) 6 xonali code yuboradi. Malformed
   raqam `invalid_phone`; Telegram'da reachable boʻlmagan raqam `phone_unreachable_on_telegram`
   (v1'da **SMS fallback yoʻq** — client'da oʻsha raqamda Telegram boʻlishi shart); resend
   cooldown (60 s) yoki per-phone / per-IP send rate limit'dan oshish `code_send_rate_limited`.
2. **Code'ni verify qilish.** Client phone + code yuboradi. Notoʻgʻri code `invalid_code`
   (challenge omon qoladi, attempt counter oshadi); 5-chi notoʻgʻri attempt challenge'ni burn
   qiladi (`too_many_attempts`, yangi code soʻrash kerak); 5-minutlik TTL'dan oʻtgan code
   `code_expired`.
3. **Sign in yoki register.** Toʻgʻri code'da:
   - **Phone topildi, `active`** → sign in.
   - **Phone topildi, `blocked`** → `account_blocked`.
   - **Phone topilmadi** → response `is_new = true` olib keladi; client `name` beradi (1–80 belgi;
     boʻsh boʻlsa `name_required`) va system client'ni yaratadi (`status = active`) hamda sign in
     qiladi.

Verification'dan *oldin* account-existence oracle yoʻq — sign-in-vs-register branch faqat toʻgʻri
code'dan keyin oshkor boʻladi. Success'da session yaratiladi; self-service session management
workshop / platform user'lar bilan bir xil.

### Dev & local sign-in

Local, CI va E2E run'larda Telegram Gateway ham, real phone ham yoʻq, shuning uchun code aslida
yuborib boʻlmaydi. Buni bitta setting — **`otp_dev_codes`**, fixed code'lar ro'yxati — qoplaydi:
u **non-empty** boʻlganda send qadami no-op boʻladi (Gateway call yoʻq) va verification **har
qanday** phone uchun ro'yxatdagi **har qanday** code'ni qabul qiladi, shunda developer istalgan
raqam bilan, masalan `000000`, sign in qiladi. U **empty** boʻlganda — default, va **production'da
majburiy** — real flow ishlaydi: Telegram orqali yetkaziladigan bitta random per-challenge code.
Bitta field, ikkita emas: code'lar mavjudligining oʻzi *on-switch*, alohida enable flag yoʻq;
production'da non-empty `otp_dev_codes` — boot-time misconfiguration.

### UX

Bitta sign-in card (client app `/auth/login`) qadamlarni joyida almashtiradi — oldinga yoki
orqaga oʻtganda client allaqachon yozgan phone hech qachon yoʻqolmaydi:

- **Phone qadami** — `+998` bilan prefilled bitta phone field, primary **Send code**. Error'lar
  inline: `invalid_phone`, `phone_unreachable_on_telegram` ("Bu raqamni Telegram'da topa olmadik —
  sign-in uchun shu raqamda Telegram kerak"), `code_send_rate_limited` ("N s dan keyin urinib
  koʻring").
- **Code qadami** — 6 xonali code input, masked target phone, phone qadamiga qaytaruvchi **Edit**
  affordance, va cooldown oʻtguncha live countdown bilan disabled boʻlgan **Resend**. Error'lar:
  `invalid_code` (qolgan attempt'lar bilan), `code_expired` va `too_many_attempts` (ikkalasi ham
  client'ni resend / yangi code soʻrashga qaytaradi).
- **Name qadami** — faqat verification `is_new = true` qaytarganda koʻrsatiladi: bitta `name`
  field, primary **Continue**; qaytuvchi client'lar toʻgʻridan-toʻgʻri app'ga oʻtadi.
- **Client profile** (`/c/profile`) — `name` editable (u client tomonidan kiritiladi, sync emas);
  `phone` read-only (uni oʻzgartirish re-verification'ni anglatadi — v1'da out of scope); current
  marker bilan sessions list; "log out" / "log out everywhere".

## Workshop provisioning (superadmin app)

Platform operator workshop'ni uning first user'i bilan atomik provision qiladi:

- **Workshop va uning owner'ini yaratish — atomik.** Input: workshop field'lar + owner'ning
  `full_name`, `login`, `phone`, plus auto-generated temp password (manual override). Bir xil
  transaction `workshop` row va `is_owner = true` hamda `force_password_change = true` bo'lgan
  `workshop_user` row yaratadi — **hech qachon biri ikkinchisisiz**. Summary va temp password'ni
  **bir marta** qaytaradi. Owner'ni platform operator'dan boshqa hech kim yarata, demote yoki
  delete qila olmaydi; per workshop aniq bitta owner.
- **Workshop'ni block / unblock qilish.** Block qilish owner'ning + staff'ning session'larini
  darhol revoke qiladi; ularning keyingi login'i rejected. Client'lar ta'sirlanmaydi. Open
  order'lar **freeze** bo'ladi — staff act qila olmaydi, chunki ular log in qila olmaydi; avtomatik
  transition yo'q. Unblock qilish session'larni **tiklamaydi** — user'lar qayta log in qiladi.

Operator'ning **yagona** workshop write action'lari: provision (workshop + first owner,
atomik), block va unblock. Operator workshop profile'ni yoki owner'ning identity field'larini
(name / phone / login) **edit qilmaydi** — bu owner hududi va unga operator path yo'q.
Workshop *editing* (profile, settings, payment channels) [`workshop.md`](workshop.md)'da;
owner-identity edit'lar owner self-service / owner-managed, operator-managed emas. Agar
operator orqali owner'ning phone'ini tuzatish hech qachon real ehtiyojga aylansa, u avval
shu yerda specify qilinishi kerak — u v1'da ataylab yo'q.

### UX

- **Create-workshop dialog** — workshop field'lar + owner field'lar, temp password (auto-generated,
  copy button, manual toggle). Success'da: owner login + temp password'ni "share this with the
  owner — shown once" + copy button bilan ko'rsatuvchi read-only confirmation.
- **Block** (workshop detail'da) — mandatory reason; staff session'lar revoke qilinishi va
  open order'lar freeze bo'lishi haqida warning; destructive-styled.

## Workshop user management (workshop app)

Har bir staff user `(permission, branch)` grant'lar setiga ega. Owner har bir branch'da har
bir permission'ni implicitly ushlab turadi, plus owner-only carve-out'lar.

### Permission catalog

| Permission | Grants on the granted branch |
|---|---|
| `view_dashboard` | see the branch's dashboard / KPIs / order summary |
| `manage_orders` | the office side of the order workflow — verify / approve (`new → confirmed`), assign and re-assign the cutter / edger, apply discounts, complete a production job **on behalf** of an absent worker, **revert** one step on a mistake, and cancel any pre-`completed` order with a reason. Cannot do production work itself unless it also holds `process_production`. See [`orders.md`](orders.md). |
| `process_production` | the **cutter & edger workspaces** — see orders assigned to this user, view the cutting plan read-only, mark **Cutting done** (→ `edge_banding` or `ready`; stamps the cutter snapshot, decrements sheet stock) and **Banding done** (→ `ready`; stamps the edge snapshot, decrements edge stock). Cannot edit, verify, cancel, or revert an order. |
| `manage_catalog` | the branch's material selection — add from the platform catalog, set the per-unit price and min-stock, activate / deactivate. (Master materials are platform-side.) |
| `manage_inventory` | stock-in (from a supplier; suppliers added on demand), adjust, view stock and transactions. |
| `manage_finance` | the money ledger — record / edit / void income (including order payments) and expenses (including `salary`). See [`finance.md`](finance.md). |
| `view_finance_reports` | read-only access to the finance dashboards, the finance reports, and the worker-production reports. |

`process_delivery` v1'dan **gated out** — v1 pickup-only
([`scope.md`](../../scope.md)), shuning uchun driver workspace yo'q va grant catalog'da
emas; u delivery qaytganda qaytadi.

Zero grant'li staff user log in qila oladi, lekin actionable hech narsa ko'rmaydi. Grant'lar
user'da yashaydi, branch'da emas: branch'ning status'ini o'zgartirish grant'larga tegmaydi;
`inactive` branch'dagi grant inert va reactivation'da yana live bo'ladi.

**Worker'lar — workshop user'lar.** "cutter" yoki "edge bander" — bu shunchaki order'ning
branch'ida `process_production` ushlab turgan workshop user — **alohida `worker` entity yo'q**
va **role yo'q**: capability — grant set, va bir kishi `manage_orders` *va*
`process_production` *va* `manage_finance` ushlab turib butun flow'ni yolg'iz boshqarishi
mumkin. System hech qanday pay rate saqlamaydi; worker'ga qancha to'lash — bu accountant'ning
user haqiqatda qilgan ishdan manual hisob-kitobi, order'ning production stamp'laridan o'qiladi
(qarang [`finance.md`](finance.md) va [`orders.md`](orders.md)).

### Owner-only powers

Owner (`is_owner`) har bir branch'da har bir permission'ni implicitly ushlab turadi, plus
v1'da **staff'ga delegate qilib bo'lmaydigan** quyidagi power'lar:

- Staff yaratish va ularning permission'larini grant / revoke qilish.
- Branch yaratish va edit qilish; branch status'ini o'zgartirish; branch pricing set qilish.
- Workshop settings'ni edit qilish (profile).
- Workshop-wide report'larni ko'rish.

### Operations (owner)

- **Workshop user yaratish** — `full_name`, `phone`, `login`, `force_password_change = true`,
  temp password (auto / manual), `home_branch_id` (user ishlaydigan branch — o'sha branch'da
  order'ga cutter / edger assignment'ni gate qiladi; branch'lar bo'ylab span qiladigan office
  staff uchun ular o'tiradigan branch'ni set qiling) va **optional initial `(permission, branch)`
  grant'lar seti**. Bitta atomic operation'da yaratiladi; user'ni va temp password'ni
  **bir marta** qaytaradi.
- **Profile field'larni edit qilish** — `full_name`, `phone`, `home_branch_id`.
- **Grant'larni set qilish** — user'ning `permission_grant` row'larini atomik almashtiradi;
  har bir `(permission, branch)` catalog'ga va workshop'ning branch'lariga qarshi validate
  qilinadi. **Yangi grant'lar user'ning keyingi request'ida effect oladi** — session revoke yo'q.
- **Password reset** — temp password + `force_password_change`; user'ning session'larini revoke qiladi.
- **Block / unblock** — block qilish session'larni darhol revoke qiladi; unblock qilish ularni tiklamaydi.
- **List / get** — owner uchun workshop'ning user'lari.

### UX

**Settings → Users** ostida (owner-only nav item):

- **Users list** (`/workshop/settings/users`) — table: name, login, phone, home branch,
  granted-branches count, status, last login, action menu. Filter'lar: home branch, status.
  **+ User**. Empty: "No staff yet — add one to delegate work."
- **Create-user dialog** — profile field'lar (incl. home branch) + temp password (auto / manual,
  copy) + initial grants matrix (permission row × branch column, workshop ichida).
  Success'da: read-only "share login + temp password — shown once" confirmation copy bilan.
- **User detail** (`/workshop/settings/users/:id`) — header (name, status badge, home branch,
  last login); tab'lar:
  - **Profile** (edit) — profile field'lar incl. home branch.
  - **Permissions** — grants matrix; toggling explicit Save va unsaved-changes guard bilan
    atomik saqlaydi.
  - **Sessions** — current marker bilan list; bittasini / hammasini revoke.
- Row / detail action'lar: Edit · Reset password (→ one-time-secret confirmation) · Block /
  Unblock (block session'lar revoke qilinishini ogohlantiradi) · Revoke sessions.

## Branch context (workshop app)

Staff user bir nechta branch'da grant ushlab turishi mumkin. Workshop app **branch picker**
ishlatadi — top bar'dagi current branch context'ni belgilovchi chip ("Branch: Yunusobod ▼").
Har bir branch-scoped screen (orders, inventory, dashboard, catalog selection, workers)
undan o'qiydi.

Rules:

- Picker user'ning biror grant'i bor branch'larni taklif qiladi — yoki **barcha branch'larni**, agar `is_owner`.
- Birinchi login'da: agar user'ning aniq bitta accessible branch'i bo'lsa auto-select;
  aks holda prompt.
- Selection per session persist qiladi (local storage); session revoke yoki re-login uni reset qiladi.
- Picker UI hech qachon user'ga scope qila olmaydigan branch tanlashga ruxsat bermaydi.
  Server baribir unga ishonmaydi — har bir request hali ham target'ning branch'ini nomlaydi,
  grant set'ga qarshi tekshiriladi.

## How a request is authorized

1. Auth middleware bearer token'ni **principal context**'ga aylantiradi: type, workshop
   id, `is_owner`, grant set.
2. Operation **target'ning branch'ini stored data'dan** aniqlaydi — hech qachon
   client-supplied branch id'dan emas.
3. Agar `is_owner` bo'lsa, yoki `(required_permission, target_branch)` grant set'da bo'lsa
   allow; owner-only operation'lar uchun, faqat `is_owner` bo'lsa allow. Aks holda → `forbidden`.

## Edge cases

- **Create-workshop workshop row'dan keyin lekin owner row'dan oldin fail bo'ladi** — butun
  operation roll back bo'ladi (atomik).
- **Owner login boshqa workshop'dagi mavjud owner login bilan to'qnashadi** — fine (login'lar
  per workshop unique, globally emas).
- **Bir xil workshop ichida login collision** — rejected.
- **Staff mid-action paytida workshop'ni block qilish** — ularning keyingi request'i 401;
  platform operator incident response uchun workshop'ning data'sini hali ham o'qiy oladi.
- **Staff member'ning yagona granted branch'i `inactive` bo'ladi** — u reactivate qilinmaguncha
  yoki ularga boshqasi grant qilinmaguncha ular amalda actionable screen'larsiz qoladi; branch
  picker inactive entry'ni yashiradi.
- **Zero grant'li staff user** — log in qila oladi; har bir workshop screen empty / hidden.
- **Owner non-home branch'da cutter / edger** — allowed: `is_owner` har bir branch'da
  `process_production` ushlab turadi va non-owner staff'ni bog'laydigan
  `home_branch_id = order.branch_id` assignment check'dan **exempt** (qarang
  [`orders.md`](orders.md)).
- **Keyinroq `inactive` bo'ladigan branch'dagi grant** — inert; branch picker'dan
  yo'qoladi; reactivate qilish grant'ni yana live qiladi.
- **Owner o'zini block qiladi** — disallowed (workshop'da active owner bo'lishi kerak).
- **Client'ning raqami Telegram'da yoʻq** — `phone_unreachable_on_telegram`; sign-in card sign-in
  uchun shu raqamda Telegram kerakligini tushuntiradi (v1'da SMS fallback yoʻq).
- **Client code'ni notoʻgʻri yozadi** — `invalid_code`, qolgan attempt'lar bilan; 5-chi notoʻgʻri
  attempt challenge'ni burn qiladi (`too_many_attempts`) va 5-minutlik TTL'dan oʻtgan code
  `code_expired` — ikkalasi ham client'ni yangi code soʻrashga qaytaradi.
- **Code juda tez-tez soʻraladi** — `code_send_rate_limited`; resend control 60 s cooldown
  oʻtguncha countdown bilan disabled qoladi.

## Next

- [`workshop.md`](workshop.md) — branch'lar, workshop settings va audit.
- [`finance.md`](finance.md) — income, expense'lar va accountant bu yerda access grant
  qilingan worker'larga to'lash uchun ishlatadigan worker-production report'lar.
