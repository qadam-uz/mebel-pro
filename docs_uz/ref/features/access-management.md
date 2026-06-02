---
title: Identity & access
status: draft
owner: shape
updated: 2026-06-02
order: 20
---

# Identity & access

[`access-patterns.md`](../../access-patterns.md) mexanikasi — har bir principal qanday sign
in qiladi, sessions qanday ishlaydi, workshops qanday provision qilinadi, staff va ularning
grants qanday boshqariladi, va uch appdagi surfaces qanday ko'rinadi.

## Workshop & platform user sign-in

Login + password. Login case-insensitive; workshop users uchun bir workshop ichida unique,
platform users uchun platform-wide unique. Yomon pairdagi error **generic**: "login or
password is incorrect" — account-existence oracle yo'q. **Ketma-ket besh noto'g'ri urinish
→ 15-minute lockout** (`locked_until`); to'g'ri password counter ni reset qiladi. Passwords
argon2 / bcrypt bilan hash qilinadi; complexity ≥ 8 chars, kamida one upper, one lower, one
digit.

`password_reset_required` (creation, higher-principal password reset, yoki security
rotationdan keyin set qilinadi) advisory flag. U `get-me`dan qaytadi va workshop /
superadmin app shell password o'zgartirilguncha persistent warning ko'rsatadi. Bu flag
appning qolgan qismini gate qilmaydi; access faqat user yoki workshop block qilinganda
rad etiladi.

**Platform users are seeded by a backend CLI command.** Ular hierarchy tepasida, shuning
uchun ularni yaratadigan higher principal yo'q; kamida bitta platform user paydo bo'lgach
in-app creation ruxsat etiladi ([`platform.md`](platform.md)).

### Sessions

Opaque tokens DBda hash qilingan (SHA-256) holda saqlanadi — JWT emas. Access TTL **24 h**;
refresh TTL **7 d**; har principal uchun **ko'pi bilan 5 concurrent sessions** (6-login
eng eskisini evict qiladi). Revoking = row delete.

| Trigger | Effect |
|---|---|
| logout (this session) | this session delete qilinadi |
| "log out everywhere" | userning barcha sessions delete qilinadi |
| change own password | barcha *other* sessions delete qilinadi; current session qoladi |
| reset password (higher principal) | userning barcha sessions delete qilinadi |
| block user | userning barcha sessions delete qilinadi |
| block workshop | workshopning owner + staff sessions delete qilinadi (clients unaffected) |
| 5-session cap exceeded | oldest evict qilinadi |
| token expiry | inert; periodic job rowni prune qiladi |

### Operations

User sign in, sign out, access token refresh (refresh path user, va workshop users uchun
workshop hali active ekanini qayta tekshiradi), own password change (barcha *other*
sessions revoke qiladi; `password_reset_required`ni clear qiladi), sessions list, bir yoki
barchasini revoke qilish, va `me` fetch qilish (principal type, ids, `is_owner`, grant set,
`password_reset_required`) imkoniyatiga ega.

### UX

- **Sign-in screen** (workshop app `/auth/login`; superadmin app `/auth/login`) — login +
  password fields; failureda generic error; `locked_until` qaytganda lockout banner ("try
  again at HH:MM").
- **Password-reset warning** — workshop / superadmin app shell ichida
  `password_reset_required = true` bo'lsa ko'rsatiladi; persistent, non-blocking va profile
  password tabiga link qiladi. Warning faqat successful password changedan keyin yo'qoladi.
- **Self profile** (`/workshop/profile`, `/admin/profile`) — Profile (read-only fields),
  Change password (strength meter), Sessions list (current marker, "revoke" per row,
  "log out everywhere").

## Client sign-in (phone + Telegram OTP)

Client **Telegram orqali yuborilgan one-time code bilan verified phone number** orqali sign
in qiladi — password yo'q, widget yo'q, app-switch yo'q. Phone identity; flow bitta
continuous path bo'lib, faqat number new bo'lganda registrationga branch qiladi. Uch step:

1. **Request a code.** Client `+998XXXXXXXXX` phone submit qiladi. System
   [verification challenge](../entities/identity.md#phone-verification-challenge) chiqaradi
   va 6-digit codeni shu raqamga **Telegram** orqali yuboradi (Telegram Gateway). Malformed
   number `invalid_phone`; Telegramda reachable bo'lmagan number
   `phone_unreachable_on_telegram` (v1da **SMS fallback yo'q** — client shu raqamda
   Telegramga ega bo'lishi kerak); resend cooldown (60 s) yoki per-phone / per-IP send rate
   limit oshsa `code_send_rate_limited`.
2. **Verify the code.** Client phone + code submit qiladi. Wrong code `invalid_code`
   (challenge saqlanadi, attempt counter bump); 5-wrong attempt challenge ni burn qiladi
   (`too_many_attempts`, yangi code request kerak); 5-minute TTLdan o'tgan code
   `code_expired`.
3. **Log in or register.** Correct codeda:
   - **Phone found, `active`** → log in.
   - **Phone found, `blocked`** → `account_blocked`.
   - **Phone not found** → response `is_new = true` olib keladi; client `name` beradi
     (1-80 chars; blank bo'lsa `name_required`) va system clientni create qiladi
     (`status = active`) va log in qiladi.

Verificationdan oldin account-existence oracle yo'q — login-vs-register branch faqat
correct codedan keyin ochiladi. Successda session created; self-service session management
workshop / platform users bilan bir xil.

### Dev & local sign-in

Local, CI va E2E runsda Telegram Gateway va real phone yo'q, shuning uchun code real
yuborilmaydi. Bitta setting — **`otp_dev_codes`**, fixed codes list — buni qoplaydi: u
**non-empty** bo'lsa, send step no-op (Gateway call yo'q) va verification listdagi **any**
codeni **any** phone uchun qabul qiladi, shuning uchun developer istalgan numberga, masalan
`000000` bilan sign in qiladi. U **empty** bo'lsa — default va **productionda mandatory** —
real flow ishlaydi: per-challenge random code Telegram orqali delivered. Bitta field, ikkita
emas: codes mavjudligi on-switch, alohida enable flag yo'q; productionda non-empty
`otp_dev_codes` boot-time misconfiguration.

### UX

Bitta sign-in card (client app `/auth/login`) step by step joyida yuradi — oldinga yoki
orqaga yurganda client typed phone yo'qolmaydi:

- **Phone step** — `+998` prefilled bitta phone field, primary **Send code**. Inline errors:
  `invalid_phone`, `phone_unreachable_on_telegram` ("We couldn't reach this number on
  Telegram — sign-in needs Telegram on this number"), `code_send_rate_limited` ("Try again
  in N s").
- **Code step** — 6-digit code input, masked target phone, phone stepga qaytadigan **Edit**
  affordance, va cooldown tugaguncha disabled live countdownli **Resend**. Errors:
  `invalid_code` (attempts remaining bilan), `code_expired` va `too_many_attempts`
  (ikkalasi clientni resend / request a new codega qaytaradi).
- **Name step** — verification `is_new = true` qaytarganda **only** ko'rsatiladi: bitta
  `name` field, primary **Continue**; returning clients to'g'ri appga kiradi.
- **Client profile** (`/c/profile`) — `name` editable (client-entered, synced emas);
  `phone` read-only (change qilish re-verification degani — v1 out of scope); sessions list
  current marker bilan; "log out" / "log out everywhere".

## Workshop provisioning (superadmin app)

Platform operator workshopni first useri bilan atomically provision qiladi:

- **Create a workshop and its owner — atomically.** Input: workshop fields + owner
  `full_name`, `login`, `phone`, plus auto-generated temp password (manual override). Same
  transaction `workshop` row va `workshop_user` row yaratadi: `is_owner = true`,
  `password_reset_required = true`. Summary va temp password **once** qaytadi. Ownerni
  platform operatordan boshqa hech kim create, demote yoki delete qila olmaydi; har workshopda
  exactly one owner.
- **Block / unblock the workshop.** Blocking owner + staff sessions immediately revoke
  qiladi; next login rejected. Clients unaffected. Open orders **freeze** — staff login qila
  olmagani uchun act qila olmaydi; automatic transitions yo'q. Unblocking sessionsni restore
  qilmaydi — users qaytadan log in qiladi.

Operatorning **only** workshop write actions: provision (workshop + first owner, atomic),
block, unblock. Operator workshop profile yoki owner identity fields (name / phone / login)
edit qilmaydi — bu owner territory va operator path yo'q. Workshop *editing* (profile,
settings, payment channels) [`workshop.md`](workshop.md) ichida; owner-identity edits owner
self-service / owner-managed, operator-managed emas. Agar owner's phone ni operator orqali
correct qilish real need bo'lsa, avval shu yerda specified bo'lishi kerak — v1da deliberate
absent.

### UX

- **Create-workshop dialog** — workshop fields + owner fields, temp password
  (auto-generated, copy button, manual toggle). Successda read-only confirmation owner login
  + temp passwordni "share this with the owner — shown once" + copy button bilan ko'rsatadi;
  owner sign-indan keyin non-blocking password-reset warning ko'radi.
- **Block** (workshop detailda) — mandatory reason; staff sessions revoked va open orders
  freeze bo'lishi haqida warning; destructive-styled.

## Workshop user management (workshop app)

Har staff user `(permission, branch)` grants setiga ega. Owner har branchda har permissionga
implicitly ega, plus owner-only carve-outs.

### Permission catalog

| Permission | Grants on the granted branch |
|---|---|
| `view_dashboard` | branch dashboard / KPIs / order summary ko'rish |
| `manage_orders` | order workflow office side — verify / approve (`new -> confirmed`), cutter / edger assign va re-assign, discounts apply, absent worker nomidan production job complete qilish, mistake bo'lsa **revert** one step, va pre-`completed` orderni reason bilan cancel qilish. O'zi production work qila olmaydi, agar `process_production` ham bo'lmasa. [`orders.md`](orders.md)ga qarang. |
| `process_production` | **cutter & edger workspaces** — ushbu userga assigned orders ko'rish, cutting planni read-only ko'rish, **Cutting done** belgilash (→ `edge_banding` yoki `ready`; cutter snapshot stamp, `shop` panels stock decrement) va **Banding done** belgilash (→ `ready`; edge snapshot stamp, `shop` sides uchun edge material stock decrement). Edit, verify, cancel, yoki revert qila olmaydi. |
| `manage_catalog` | branch material selection — platform catalogdan add, per-unit price va min-stock set, activate / deactivate. (Master materials platform-side.) |
| `manage_inventory` | stock-in (supplierdan; suppliers on demand add qilinadi), adjust, stock va transactions view. |
| `manage_finance` | money ledger — income (including order payments) va expenses (including `salary`) record / edit / void. [`finance.md`](finance.md)ga qarang. |
| `view_finance_reports` | finance dashboards, finance reports, worker-production reports read-only access. |

`process_delivery` **v1dan gated out** — v1 pickup-only ([`scope.md`](../../scope.md)),
shuning uchun driver workspace yo'q va grant catalogda emas; delivery qaytsa u ham qaytadi.

Zero grantsli staff user log in qila oladi, lekin actionable hech narsa ko'rmaydi. Grants
userda yashaydi, branchda emas: branch status change grantsga tegmaydi; `inactive` branchdagi
grant inert bo'ladi va reactivationda yana live bo'ladi.

**Workers are workshop users.** "cutter" yoki "edge bander" bu order branchida
`process_production` ushlagan workshop user xolos — separate `worker` entity yo'q va
**role** yo'q: capability grant set, bir odam `manage_orders` *and* `process_production`
*and* `manage_finance` ushlab butun flow ni yolg'iz yurita oladi. System pay rates
saqlamaydi; worker qancha paid bo'lishi accountantning manual calculationi, order
production stampsdan o'qiladigan work asosida (see [`finance.md`](finance.md) and
[`orders.md`](orders.md)).

### Owner-only powers

Owner (`is_owner`) har branchda har permissionga implicitly ega, plus v1da staffga delegate
qilinmaydigan powers:

- Staff create qilish va permissions grant / revoke qilish.
- Branches create va edit qilish; branch status change; branch pricing set.
- Workshop settings (profile) edit.
- Workshop-wide reports view.

### Operations (owner)

- **Create a workshop user** — `full_name`, `phone`, `login`,
  `password_reset_required = true`, temp password (auto / manual), `home_branch_id`
  (user ishlaydigan branch — orderdagi cutter / edger assignmentni shu branchga gate qiladi;
  branches bo'ylab ishlaydigan office staff uchun o'tirgan branchni set qiling), va
  **optional initial `(permission, branch)` grants**. Bitta atomic operationda created;
  user va temp password **once** qaytadi.
- **Edit profile fields** — `full_name`, `phone`, `home_branch_id`.
- **Set grants** — user's `permission_grant` rows atomically replace qilinadi; har
  `(permission, branch)` catalog va workshop branchesga qarshi validate qilinadi. **New
  grants userning next requestida take effect qiladi** — session revoke yo'q.
- **Reset password** — temp password + `password_reset_required = true`; user's sessions
  revoke qilinadi.
- **Block / unblock** — blocking sessions immediately revoke qiladi; unblocking ularni
  restore qilmaydi.
- **List / get** — owner uchun workshop users.

### UX

**Settings → Users** ostida (owner-only nav item):

- **Users list** (`/workshop/settings/users`) — table: name, login, phone, home branch,
  granted-branches count, status, last login, action menu. Filters: home branch, status.
  **+ User**. Empty: "No staff yet — add one to delegate work."
- **Create-user dialog** — profile fields (incl. home branch) + temp password (auto /
  manual, copy) + initial grants matrix (permission rows × branch columns, workshop ichida).
  Successda read-only "share login + temp password — shown once" confirmation with copy.
- **User detail** (`/workshop/settings/users/:id`) — header (name, status badge, home
  branch, last login); tabs:
  - **Profile** (edit) — profile fields incl. home branch.
  - **Permissions** — grants matrix; toggling explicit Save bilan atomically saqlanadi va
    unsaved-changes guard bor.
  - **Sessions** — list with current marker; revoke one / all.
- Row / detail actions: Edit · Reset password (→ one-time-secret confirmation) · Block /
  Unblock (block warns sessions are revoked) · Revoke sessions.

## Branch context (workshop app)

Staff user multiple branchesda grants ushlashi mumkin. Workshop app **branch picker** ishlatadi
— top bardagi chip ("Branch: Yunusobod ▼") current branch contextni belgilaydi. Har
branch-scoped screen (orders, inventory, dashboard, catalog selection, workers) undan o'qiydi.

Rules:

- Picker user grant olgan branchesni taklif qiladi — yoki `is_owner` bo'lsa **all branches**.
- First login: user exactly one accessible branchga ega bo'lsa auto-select; aks holda prompt.
- Selection per session persisted (local storage); session revoke yoki re-login reset qiladi.
- Picker UI user scope qila olmaydigan branchni tanlatmaydi. Server baribir unga ishonmaydi
  — har request target branchni names qiladi, grant setga qarshi check qilinadi.

## How a request is authorized

1. Auth middleware bearer tokenni **principal context**ga aylantiradi: type, workshop id,
   `is_owner`, grant set.
2. Operation **target's branch from stored data** aniqlaydi — hech qachon client-supplied
   branch iddan emas.
3. `is_owner` bo'lsa, yoki `(required_permission, target_branch)` grant setda bo'lsa allow;
   owner-only operations uchun faqat `is_owner`. Aks holda → `forbidden`.

## Edge cases

- **Create-workshop fails after the workshop row but before the owner row** — whole operation
  roll back (atomic).
- **Owner login collides** with an existing owner login in another workshop — fine (logins
  per workshop unique, global emas).
- **Login collision within the same workshop** — rejected.
- **Block a workshop while staff are mid-action** — next request 401; platform operator
  incident response uchun workshop data read qila oladi.
- **A staff member's only granted branch goes `inactive`** — reactivated yoki boshqa branch
  grant qilinguncha actionable screens yo'q; branch picker inactive entryni hide qiladi.
- **Staff user with zero grants** — log in qila oladi; har workshop screen empty / hidden.
- **Owner as cutter / edger on a non-home branch** — allowed: `is_owner` har branchda
  `process_production` ushlaydi va non-owner staffni bog'laydigan
  `home_branch_id = order.branch_id` assignment checkdan **exempt** (see
  [`orders.md`](orders.md)).
- **Grant on a branch that later goes `inactive`** — inert; branch pickerdan yo'qoladi;
  reactivating grantni yana live qiladi.
- **Owner blocks themselves** — disallowed (workshop active ownerga ega bo'lishi shart).
- **Client's number isn't on Telegram** — `phone_unreachable_on_telegram`; sign-in card sign
  in shu numberdagi Telegramni talab qilishini tushuntiradi (v1da SMS fallback yo'q).
- **Client mistypes the code** — `invalid_code` attempts remaining bilan; 5th wrong attempt
  challenge burn qiladi (`too_many_attempts`) va 5-minute TTLdan o'tgan code
  `code_expired` — ikkalasi clientni fresh code request qilishga qaytaradi.
- **Code requested too often** — `code_send_rate_limited`; resend control 60 s cooldown
  tugaguncha countdown bilan disabled qoladi.

## Next

- [`workshop.md`](workshop.md) — branches, workshop settings, and audit.
- [`finance.md`](finance.md) — income, expenses, and the worker-production reports the
  accountant uses to pay the workers granted access here.
