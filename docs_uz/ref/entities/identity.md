---
title: Identity
status: draft
owner: shape
updated: 2026-06-02
order: 10
---

# Identity

Auth subjects va session record. Rules [`access-patterns.md`](../../access-patterns.md)
ichida; bu page data shapeni egallaydi.

## Platform user

Platform-operating teamdagi person ("superadmin"). Workshopga bound emas; permission model
yo'q — full platform scope. Superadmin app ishlatadi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `login` | text | unique, case-insensitive |
| `password_hash` | text | argon2/bcrypt; never plaintext |
| `full_name` / `phone` | text | required; phone `+998XXXXXXXXX` |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `password_reset_required` | bool | default `true` on creation; cleared by changing password |
| `failed_login_count` / `locked_until` | int / timestamp? | brute-force counter; resets on success |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

Invariants: `login` unique (DB); blocking deletes its sessions; complexity ≥ 8 chars (upper +
lower + digit); created only by another platform user.

## Workshop user

Workshop personi — **including its owner**, plus office staff, cutters, edge banders,
accountants. Login + password bilan log in qiladi. Exactly one workshopga belongs.
**Separate "worker" entity va fixed role yo'q** — capability owner flag (everything) yoki
branch-scoped [permission grants](#permission-grant) setidir, va bir person every grant
ushlashi mumkin. Workshop app ishlatadi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_id` | UUID | required; the tenant |
| `login` | text | unique per workshop, case-insensitive |
| `password_hash` / `full_name` / `phone` | text | as above |
| `is_owner` | bool | **exactly one `true` per workshop** |
| `home_branch_id` | UUID | user ishlaydigan branch; cutter / edger assignment uchun load-bearing (a **non-owner** order's `cutter_user_id` / `edger_user_id` must have `home_branch_id = order.branch_id`; the **owner is exempt** — `is_owner` holds `process_production` on every branch and may be assigned regardless of `home_branch_id`); owner / office staff branches bo'ylab ishlasa, o'tirgan branchni set qiling |
| `status` | enum | `active` / `blocked` |
| `password_reset_required` | bool | default `true` on creation; cleared by changing password |
| `failed_login_count` / `locked_until` | int / timestamp? | |
| `last_login_at` | timestamp? | |
| `created_at` / `updated_at` | timestamp | |

v1da **compensation policy yo'q**: system pay rates saqlamaydi va salary compute qilmaydi.
Worker pay accountantning worker-production reportsdan qiladigan manual calculationi,
`salary` expense sifatida booked ([`finance.md`](../features/finance.md)).

Invariants: exactly one owner per workshop (DB / service); `login` unique per workshop;
`home_branch_id` same workshopga belongs; user blocking yoki workshop blocking sessionsni
delete qiladi; zero grantsli staff log in qila oladi, lekin actionable screens yo'q; only
platform operator ownershipni boshqa userga move qila oladi.

## Permission grant

One row that grants a (non-owner) workshop user one coarse permission, scoped to one branch.
v1 catalog: `view_dashboard`, `manage_orders`, `process_production`, `manage_catalog`,
`manage_inventory`, `manage_finance`, `view_finance_reports` (`process_delivery` delivery
bilan v1dan gated out). Har bir grant nimani beradi va qaysilari owner-only ekanini
[`../features/access-management.md`](../features/access-management.md) ko'rsatadi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `workshop_user_id` | UUID | required; must not be an owner |
| `permission` | enum | one of the v1 catalog above |
| `branch_id` | UUID | required; branch in the user's workshop |
| `granted_by_user_id` | UUID | the owner who created it |
| `granted_at` | timestamp | |

Invariants: `(workshop_user_id, permission, branch_id)` unique (DB); `branch_id` same
workshop as the userga belongs (service); only workshop owner creates/removes grants; grant
on an `inactive` branch is inert.

## Client

Customer. Workshop/platform usersdan **separate entity**. **Telegram orqali yuborilgan
one-time code bilan verified phone number** orqali identified; yangi number birinchi marta
verified bo'lganda self-register (name only); platform-wide global (workshop/branch binding
yo'q); per order branch tanlaydi. Client app ishlatadi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `phone` | text | `+998XXXXXXXXX`; **unique, required** — the verified identity and natural key |
| `name` | text | required; client typed registrationdagi display name (1-80 chars); workshop uni shu nom bilan chaqiradi |
| `preferred_branch_id` | UUID? | optional default branch — bu client ochadigan har new cutting draftdagi `preferred_branch_id`ni seed qiladi; draftda clear/change qilish bu defaultga tegmaydi. Client profiledan set va clear qiladi. |
| `status` | enum | `active` / `blocked` (soft delete only) |
| `created_at` / `updated_at` / `last_login_at` | timestamp / timestamp / timestamp? | |

Phone only verified fact; `name` client-entered va editable (external source of truth yo'q —
Telegramdan hech narsa sync qilinmaydi, u faqat login code delivery channel). No password, no
password-reset warning / lockout (auth integrity is the OTP check). Client
[code challenge](#phone-verification-challenge) orqali verified phone bo'lmasdan mavjud
bo'la olmaydi; row faqat new numberning first successful verificationidan keyin created
(operator yoki boshqa principal orqali never).

Invariants: `phone` unique (DB) va `+998XXXXXXXXX` shaped; blocking deletes its sessions;
created only by a successful first verification (never by an operator or another principal);
`preferred_branch_id`, set bo'lsa, client ko'ra oladigan branchga references (any workshop's
`active` yoki `temporarily_closed` branch); field **scope-enforced emas** (branch keyin
`inactive` bo'lsa clear qilinmaydi — cutting wizard buni no-longer-carried material bilan bir
xil recovery affordances sifatida ko'rsatadi; see [`cutting.md`](../features/cutting.md)).

## Phone verification challenge

In-flight client sign-in uchun transient state: phonega Telegram orqali yuborilgan one code,
entryni kutmoqda. `Client` rowga tied emas — u login/registrationdan oldin keladi va returning
hamda brand-new numbers uchun mavjud bo'ladi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `phone` | text | `+998XXXXXXXXX`; code yuborilgan number |
| `code_hash` | text | SHA-256 of the 6-digit code; plaintext never stored |
| `expires_at` | timestamp | now + 5 min at issue |
| `attempt_count` | int | wrong-code counter; burned at 5 |
| `consumed_at` | timestamp? | correct code accepted bo'lganda set; single-use |
| `created_at` | timestamp | |

Invariants: code 6 digits, hashed at rest, single-use, 5-minute TTL; challenge burn bo'lishidan
oldin ≤ 5 verify attempts; per-phone resend cooldown (60 s) va per-phone / per-IP send rate
limit; row short-lived va periodic session/expiry job prune qiladi. Delivery **Telegram-only**
— Telegramda reachable bo'lmagan number sign in qila olmaydi (v1da SMS fallback yo'q).

## Session

Principal uchun logged-in device. Opaque access token + opaque refresh token saqlaydi, ikkalasi
ham **hashed** (SHA-256) — JWT emas. Session row source of truth: uni delete qilish device ni
instant log out qiladi. Bitta `sessions` table uch principal typening hammasini qoplaydi.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `principal_type` | enum | `platform_user` / `workshop_user` / `client` |
| `principal_id` | UUID | the user/client |
| `access_token_hash` / `refresh_token_hash` | text | SHA-256; unique each |
| `access_token_expires_at` / `refresh_token_expires_at` | timestamp | now + 24 h / now + 7 d at issue |
| `device_info` | json | UA, IP ("where am I logged in" view + audit uchun) |
| `created_at` / `last_used_at` | timestamp / timestamp | `last_used_at` har authenticated requestda bumped |

Plaintext tokens never stored. Created on login; access token refresh token orqali refresh
qilinadi until refresh expiry; logout, "log out everywhere", password change (all *other*
sessionsni removes), principal blocking, principal's workshop blocking, yoki 5-session capda
oldest sifatida evicted bo'lish orqali removed. Expired sessions periodic job bilan pruned.

Invariants: principal boshiga ≤ 5 active sessions; token hashes unique (DB); expired yoki
unknown access token `unauthorized`; refresh principal (va workshop users uchun workshop)
still active ekanini re-check qiladi; tokens random 32-byte strings.
