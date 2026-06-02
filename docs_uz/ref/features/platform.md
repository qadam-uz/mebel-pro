---
title: Platform operations
status: draft
owner: shape
updated: 2026-06-02
order: 70
---

# Platform operations

Superadmin appning ops corneri: platform material catalog (manufacturers + materials),
scheduled background jobs, application-error monitor, va platform-user registry. Workshop
provisioning va block / unblock [`access-management.md`](access-management.md) ichida
yashaydi; workshops consume qiladigan catalog mechanics
[`catalog-inventory.md`](catalog-inventory.md) ichida — bu doc ular uchun
**platform-side admin surfaces**ni egallaydi.

## Platform catalog admin

Har workshop tanlaydigan platform-curated catalog. Operators end-to-end manage qiladigan
ikki registry: **Manufacturers** va **Materials**. Full operation rules (create, activate /
deactivate, master edit existing ordersga yetib bormasligi haqidagi snapshot guarantee)
[`catalog-inventory.md`](catalog-inventory.md) ichida; bu section **superadmin app's**
surfacesni egallaydi.

- **Manufacturers** — Kronospan, Egger, Rehau, va hokazo. Material identity manufacturer
  ichiga oladi, shuning uchun yangi brandni bu yerga qo'shish u supplied materialsni
  qo'shishdan oldin keladi.
- **Materials** — `panel` va `edge` master records, har biri manufacturerini olib yuradi.

Operators per-branch prices yoki stock edit qilmaydi — bu workshop territory.

### UX (under a **Catalog** section in the superadmin app)

- **Manufacturers** (`/admin/catalog/manufacturers`) — table: name, country, materials
  count, status, action menu. **+ Manufacturer** → dialog (name, optional country,
  optional note). Row actions: Edit · Activate / Deactivate. No Delete. Filters:
  status dropdown, country dropdown. Empty: "No manufacturers yet — add one before
  adding materials."
- **Materials** (`/admin/catalog/materials`) — table: image, kind, manufacturer chip,
  type/thickness, colour/decor, panel size (for panels), status, action menu. Filters:
  kind dropdown (`panel` / `edge`), manufacturer dropdown (multi-select), type dropdown,
  thickness dropdown, status dropdown.
  **+ Material** → kind-specific form (manufacturer picker with inline-add → opens the
  Manufacturers dialog without leaving this page; spec fields per the kind). Row
  actions: Edit · Activate / Deactivate · Image upload. No Delete. Empty: "No materials
  yet — add manufacturers, then materials."

States: loading skeletons, empty, error with `trace_id`; manufacturers inline-add
in-progress material formni preserve qiladi. Accessibility: status chip colour + textni pair
qiladi; destructive activation toggles confirm qiladi va consequence nomini aytadi
("Existing branch selections of this material will be hidden from clients.").

## Background jobs

Backend **in-process scheduler** ishlatadi — external queue yo'q, Celery yo'q, cron yo'q. v1
jobs:

| Job | When | What |
|---|---|---|
| `cleanup-expired-sessions` | hourly | expired session rows prune |
| `daily-low-stock-summary` | daily | per branch, daydagi low-stock conditionsni bitta notificationga roll up |

Cutting drafts uchun **expiry job yo'q** — client ularni delete qilmaguncha yoki 50-draft cap
ga yetmaguncha persist qiladi ([`cutting.md`](cutting.md)). Drafts uchun hech qayerda
auto-cleanup yo'q.

Job concurrent ikki marta run qilmaydi (guard). Failed job result yozadi va platform
operatorsga notify qiladi; operator uni manually re-trigger qila oladi.

Operators jobs list qila oladi (schedule, last run, last result, brief log) va on demand run
trigger qila oladi.

## Error monitor

Backend application errors record qiladi. Monitor ularni **code bo'yicha group** qiladi:
counts (24 h / 7 d), last occurrence, preview message. Operators single code ichiga drill
qilib full message, stack trace, request / context details (sensitive fields write timeda
masked), trace ids, va known bo'lsa affected workshops / usersni ko'radi — va codeni
resolved deb mark qiladi.

Error spike (codening 24 h counti threshold crossing qilsa) platform operatorsni notify
qiladi.

Health endpoints (`/api/v1/healthz` liveness uchun, `/api/v1/readyz` DB-touching readiness
check uchun) unauthenticated; docs site (`/docs`) edge orqali HTTP-Basic-gated.

## Platform user registry

Operators platform usersni list, create, password reset, block, unblock qila oladi. Shape
workshop-user managementni mirror qiladi, lekin **permission model yo'q** — har platform
user full platform scope ushlaydi. Creation share once uchun temp password qaytaradi
(`password_reset_required` set qilingan holda, see
[`access-management.md`](access-management.md)).

Platform operator o'zini block qila olmaydi, va last active platform operator block
qilinmaydi — har doim kamida bitta active bo'lishi shart.

Platform users initially backend CLI command bilan seeded (chicken-and-egg); keyin in-app
creation path.

## UX (superadmin app)

- **Dashboard** (`/admin`) — platform health at a glance: workshop / branch / client counts,
  recent provisioning, job + error status. U **workshop financials** olib yurmaydi —
  operators health va incidentsni monitor qiladi, workshop money emas
  ([`access-patterns.md`](../../access-patterns.md#platform-operator)); revenue rollups
  operator scope out, shuning uchun per-workshop yoki platform revenue figure bu yerda yo'q.
- **Docs & API reference** — `/docs`, `/api-docs`, `/api-redoc`ga nav link (live docs site va
  OpenAPI references). Bular edge orqali HTTP-Basic-gated, **app sessiondan separate
  sign-in** — link new tabda ochiladi va second prompt surprise bo'lmasligi uchun labelled.

**Catalog** section ostida yuqoridagi Manufacturers va Materials surfaces.

**Platform** section ostida:

- **Jobs** (`/admin/platform/jobs`) — table: job name, schedule, last run (relative), last
  result (badge: ok / failed), action menu ("Run now" → confirm; "View log" → drawer). Failed
  rows highlighted.
- **Errors** (`/admin/platform/errors`) — table: code, module, count (24 h / 7 d), last
  occurrence, preview message, action menu. Detail modal: full message, stack, masked context,
  affected workshops / users, trace ids; "Resolve" → confirm. Filters: module, code, time
  range, count threshold. Empty: "No errors recorded — nice."
- **Platform users** (`/admin/platform/users`) — table: name, login, phone, status, last
  login, action menu (Edit · Reset password → one-time-secret confirmation · Block /
  Unblock). "+ Platform user" → dialog (fields + auto / manual temp password).

**Audit** viewer [`workshop.md`](workshop.md) ichida yashaydi — v1da u **superadmin-only**
surface, bu appda cross-workshop rendered. v1da **cross-workshop orders view yo'q**:
operator provisions, blocks, va monitors qiladi, lekin workshops' orders browse qilmaydi
(see [`scope.md`](../../scope.md)).

States: har pageda loading / empty / error; har state-changing actionda confirmation; user
create qilish yoki password resetdan keyin one-time-secret confirmation. Action menus
keyboard-operable; destructive actions confirm qiladi va effect nomini aytadi; result badges
colour bilan textni pair qiladi.

## Edge cases

- **A job fails** — result recorded va shown; notification operatorsga fire; operator
  re-trigger qila oladi.
- **Triggering a job already running** — guarded; UI shuni aytadi.
- **An error code spikes** — count climbs; error-spike notification threshold crossing
  boshiga once fire qiladi.
- **Blocking a platform user mid-action** — sessions dropped; next request 401.
- **Block self or the last operator** — disallowed; UI prevent qiladi; server defensively
  rejects.

## Next

[`notifications.md`](notifications.md) — the inbox that surfaces job-failure and error-spike
alerts to operators.
