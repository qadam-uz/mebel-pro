---
title: Identity
status: draft
owner: shape
updated: 2026-05-17
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
| `home_branch_id` | UUID | the branch the user works at; load-bearing for cutter / edger assignment (an order's `cutter_user_id` / `edger_user_id` must have `home_branch_id = order.branch_id`); for owner / office staff who span branches, set the branch they sit at |
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

Customer. Workshop/platform user'lardan **alohida entity**. Faqat Telegram-OAuth identity;
birinchi OAuth handshake'da oʻzini self-register qiladi; platform'ga global (workshop/branch
binding yoʻq); har bir order uchun branch tanlaydi. Client app'dan foydalanadi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `telegram_id` | bigint | unique; required |
| `phone` | text | `+998XXXXXXXXX`; required (Telegram must share it) |
| `first_name` / `last_name` / `photo_url` | text / text? / text? | from Telegram (last/photo optional) |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `created_at` / `updated_at` / `last_login_at` | timestamp / timestamp / timestamp? | |

Telegram profile field'lari (`first_name`, `last_name`, `photo_url`) **har bir login'da
OAuth payload'idan refresh qilinadi** — Telegram source of truth. Telegram **username
saqlanmaydi**: u user-mutable va biz uning oʻzgarishlarini track qilmaymiz; customer'ga
`first_name` bilan murojaat qiling. Password yoʻq, forced-change / lockout yoʻq (auth
integrity bu HMAC check). Client verified Telegram identity va shared phone number'siz
mavjud boʻla olmaydi (aks holda `missing_phone_number`).

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
