---
title: Identity
status: draft
owner: shape
updated: 2026-05-22
order: 10
---

# Identity

Auth subject'lar va session record. Rule'lar
[`access-patterns.md`](../../access-patterns.md)'da; bu sahifa data shape.

## Platform user

Platform-operating jamoasidagi odam ("superadmin"). Hech bir workshop'ga bogʻlanmagan;
permission model yoʻq — toʻliq platform scope. Superadmin app'dan foydalanadi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `login` | text | unique, case-insensitive |
| `password_hash` | text | argon2/bcrypt; never plaintext |
| `full_name` / `phone` | text | required; phone `+998XXXXXXXXX` |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `force_password_change` | bool | default `true` on creation |
| `failed_login_count` / `locked_until` | int / timestamp? | brute-force counter; resets on success |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

Invariant'lar: `login` unique (DB); block qilish uning session'larini oʻchiradi;
complexity ≥ 8 char (upper + lower + digit); faqat boshqa platform user tomonidan
yaratiladi.

## Workshop user

Workshop'ning odami — **uning owner'i ham**, plus office staff, cutter'lar, edge
bander'lar, accountant'lar. Login + password bilan login qiladi. Aniq bitta workshop'ga
tegishli. **Alohida "worker" entity yoʻq va fixed role yoʻq** — capability bu owner flag
(hammasi) yoki branch-scoped [permission grant](#permission-grant)'lar toʻplami, va bir
odam har bir grant'ni ushlab turishi mumkin. Workshop app'dan foydalanadi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required; the tenant |
| `login` | text | unique per workshop, case-insensitive |
| `password_hash` / `full_name` / `phone` | text | as above |
| `is_owner` | bool | **exactly one `true` per workshop** |
| `home_branch_id` | UUID | the branch the user works at; load-bearing for cutter / edger assignment (a **non-owner** order's `cutter_user_id` / `edger_user_id` must have `home_branch_id = order.branch_id`; the **owner is exempt** — `is_owner` holds `process_production` on every branch and may be assigned regardless of `home_branch_id`); for owner / office staff who span branches, set the branch they sit at |
| `status` | enum | `active` / `blocked` |
| `force_password_change` | bool | default `true` on creation |
| `failed_login_count` / `locked_until` | int / timestamp? | |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

v1'da **compensation policy yoʻq**: system pay rate'larni saqlamaydi va salary
hisoblamaydi. Worker'ning pay'i accountant'ning worker-production report'laridan qoʻlda
hisoblashi, `salary` expense sifatida book qilinadi
([`finance.md`](../features/finance.md)).

Invariant'lar: har bir workshop uchun aniq bitta owner (DB / service); `login` har bir
workshop uchun unique; `home_branch_id` bir xil workshop'ga tegishli; user'ni block
qilish, yoki uning workshop'ini block qilish, uning session'larini oʻchiradi; zero grant'li
staff login qila oladi lekin actionable screen'lari yoʻq; faqat platform operator
ownership'ni boshqa user'ga koʻchira oladi.

## Permission grant

Bitta (non-owner) workshop user'ga bitta coarse permission beradigan, bitta branch'ga
scoped boʻlgan bitta row. v1 catalog: `view_dashboard`, `manage_orders`,
`process_production`, `manage_catalog`, `manage_inventory`, `manage_finance`,
`view_finance_reports` (`process_delivery` delivery bilan birga v1'dan chiqarib
tashlangan). Har biri nima berishini va qaysilari owner-only ekanligini bilish uchun
[`../features/access-management.md`](../features/access-management.md)'ga qarang.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_user_id` | UUID | required; must not be an owner |
| `permission` | enum | one of the v1 catalog above |
| `branch_id` | UUID | required; branch in the user's workshop |
| `granted_by_user_id` | UUID | the owner who created it |
| `granted_at` | timestamp | |

Invariant'lar: `(workshop_user_id, permission, branch_id)` unique (DB); `branch_id` user
bilan bir xil workshop'ga tegishli (service); faqat workshop owner grant'larni
yaratadi/olib tashlaydi; `inactive` branch'dagi grant inert.

## Client

Customer. Workshop/platform user'lardan **alohida entity**. **Telegram orqali yuborilgan
one-time code bilan tasdiqlangan phone number** orqali identify qilinadi; yangi raqam birinchi
marta verify qilinganda oʻzini self-register qiladi (faqat name); platform'ga global
(workshop/branch binding yoʻq); har bir order uchun branch tanlaydi. Client app'dan foydalanadi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `phone` | text | `+998XXXXXXXXX`; **unique, required** — verified identity va natural key |
| `name` | text | required; client'ning oʻz display name'i, registration'da yoziladi (1–80 belgi); workshop unga shunday murojaat qiladi |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `created_at` / `updated_at` / `last_login_at` | timestamp / timestamp / timestamp? | |

Phone — yagona verified fakt; `name` esa client tomonidan kiritiladi va oʻzgartirilishi mumkin
(external source of truth yoʻq — Telegram'dan hech narsa sync qilinmaydi, u faqat login code'ning
delivery channel'i). Password yoʻq, forced-change / lockout yoʻq (auth integrity bu OTP check).
Client [code challenge](#phone-verification-challenge) orqali verify qilingan phone'siz mavjud
boʻla olmaydi; row faqat yangi raqamning birinchi muvaffaqiyatli verification'ida yaratiladi.

Invariant'lar: `phone` unique (DB) va `+998XXXXXXXXX` shaklida; block qilish uning session'larini
oʻchiradi; faqat muvaffaqiyatli birinchi verification orqali yaratiladi (hech qachon operator yoki
boshqa principal tomonidan emas).

## Phone verification challenge

In-flight client sign-in uchun transient state: Telegram orqali phone'ga yuborilgan bitta code,
kiritilishini kutmoqda. `Client` row'iga bogʻliq emas — u login/registration'dan oldin keladi va
ham qaytuvchi, ham butunlay yangi raqamlar uchun mavjud.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `phone` | text | `+998XXXXXXXXX`; code yuborilgan raqam |
| `code_hash` | text | 6 xonali code'ning SHA-256'i; plaintext hech qachon saqlanmaydi |
| `expires_at` | timestamp | issue'da now + 5 min |
| `attempt_count` | int | notoʻgʻri-code counter; 5 da burn qilinadi |
| `consumed_at` | timestamp? | toʻgʻri code qabul qilinganda set qilinadi; single-use |
| `created_at` | timestamp | |

Invariant'lar: code 6 xonali, at rest hash qilinadi, single-use, 5-minutlik TTL; challenge
burn qilinishidan oldin ≤ 5 verify attempt; per-phone resend cooldown (60 s) va per-phone /
per-IP send rate limit; row qisqa umrli va periodic session/expiry job tomonidan prune qilinadi.
Delivery **Telegram-only** — Telegram'da reachable boʻlmagan raqam kira olmaydi (v1'da SMS
fallback yoʻq).

## Session

Principal uchun login qilingan device. Opaque access token + opaque refresh token'ni
ushlab turadi, ikkalasi ham **hashed** (SHA-256) saqlanadi — JWT emas. Session row source
of truth: uni oʻchirish device'ni darhol log out qiladi. Bitta `sessions` table uchala
principal type'ni qoplaydi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `principal_type` | enum | `platform_user` / `workshop_user` / `client` |
| `principal_id` | UUID | the user/client |
| `access_token_hash` / `refresh_token_hash` | text | SHA-256; unique each |
| `access_token_expires_at` / `refresh_token_expires_at` | timestamp | now + 24 h / now + 7 d at issue |
| `device_info` | json | UA, IP (for the "where am I logged in" view + audit) |
| `created_at` / `last_used_at` | timestamp / timestamp | `last_used_at` bumped on each authenticated request |

Plaintext token'lar hech qachon saqlanmaydi. Login'da yaratiladi; access token refresh
expiry'gacha refresh token orqali refresh qilinadi; logout, "log out everywhere",
password oʻzgarishi (barcha *boshqa* session'larni olib tashlaydi), principal'ni block
qilish, principal'ning workshop'ini block qilish, yoki 5-session cap'da eng eski sifatida
evict qilinish orqali olib tashlanadi. Expired session'lar periodic job tomonidan prune
qilinadi.

Invariant'lar: har bir principal uchun ≤ 5 active session; token hash'lar unique (DB);
expired yoki unknown access token `unauthorized`; refresh principal'ni (va workshop user'lar
uchun workshop'ni) hali ham active ekanligini qayta tekshiradi; token'lar random 32-byte
string'lar.
