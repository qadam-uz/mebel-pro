---
title: Admin manual E2E
status: stable
owner: build
updated: 2026-06-21
order: 10
---

# Admin manual E2E

Manual QA protocol for the superadmin app. Use it when validating a release, doing a product
owner pass, or auditing visual and interaction quality beyond the automated E2E suite.

## Job

Primary user: platform operator.

Job to be done: when I operate the platform, I want to provision workshops, manage the platform
catalog, monitor jobs/errors/audit, and maintain operator access, so I can keep the service
healthy without entering workshop operations.

## Evidence

Each run produces local evidence under `.workflows/admin-manual-e2e/<run-id>/`:

| File | Purpose |
|---|---|
| `audit.md` | Human-readable findings, screenshot references, copy notes, and suggested fixes. |
| `manifest.json` | Machine-readable list of screenshots, routes, viewport sizes, and scenario ids. |
| `screenshots/` | PNG evidence. Name format: `<scenario-id>__<viewport>__<state>.png`. |

Do not commit screenshot evidence unless a reviewer explicitly asks for it. This runbook is the
source of truth; screenshots are evidence for one dated pass.

## Setup

Run against a local E2E database or a disposable staging tenant. Do not use real workshop data for
destructive scenarios.

Required data:

| Code | Data profile |
|---|---|
| `admin.ready` | Active platform operator with `password_reset_required = false`. |
| `admin.reset` | Active platform operator with `password_reset_required = true`. |
| `workshop.active` | Active workshop with first branch and owner. |
| `workshop.blocked` | Blocked workshop with block reason. |
| `catalog.full` | At least two manufacturers, one active and one inactive; at least one panel and one edge material; one material with an image; one carried by a branch. |
| `jobs.full` | `cleanup-expired-sessions` visible with at least one recent run. |
| `errors.full` | At least one open error and one resolved error, with context and stack on at least one occurrence. |
| `notifications.full` | At least one unread job/error notification and one read notification. |
| `audit.full` | Action logs and status-change logs from provisioning, block/unblock, material changes, user changes, job run, and error resolve/reopen. |

Before screenshots:

1. Open `http://localhost:5173/admin`.
2. Sign in as `admin.ready`.
3. Confirm the shell shows admin navigation, notification bell, and the **Yangi ustaxona**
   primary action.
4. Run the scenario set below in this order unless a specific defect requires isolation.

## Viewports

Capture each primary page and open component state at:

| Code | Size | Purpose |
|---|---:|---|
| `desktop` | `1440x900` | Dense operator workstation. |
| `tablet` | `768x1024` | Narrow layout with desktop/tablet density pressure. |
| `mobile` | `390x844` | Drawer navigation, stacked forms, and touch target pass. |

Also test at 200% browser zoom on at least `ADM-SHELL`, `ADM-WORKSHOP-FORM`,
`ADM-MATERIAL-FORM`, `ADM-ERROR-DETAIL`, and `ADM-AUDIT`.

## Pass rubric

A scenario passes only when:

- The stated user-visible outcome is correct.
- The page has no unexpected horizontal page scroll. Wide tables may scroll inside their own
  table container.
- All buttons, links, tabs, dropdowns, modals, and menus are reachable by keyboard.
- Focus is visible, enters dialogs, is trapped there, and returns to the trigger on close.
- Loading, empty, no-result, error, busy, success, and disabled states are understandable.
- Uzbek user messages are grammatical, concise, specific, and action-focused.
- Destructive actions name the consequence and require the intended confirmation path.

## Copy checklist

Use this for every screenshot and action result:

- Prefer short Uzbek labels that name the action: `Saqlash`, `Bloklash`, `Qayta urinish`,
  `Hammasini o'qilgan deb belgilash`.
- Avoid mixed English unless it is a product term already used in docs (`job`, `trace`, `API`).
- Error copy states what failed and how to recover. Avoid only `Amal bajarilmadi` when a clearer
  reason is available.
- Empty states distinguish first-run empty from filter no-results.
- Confirmation copy names the affected object and consequence.
- Password/secret copy states that the secret is shown once and must be shared outside the app.

## Route matrix

| Route | Scenario ids |
|---|---|
| `/admin/auth/login` | `ADM-AUTH-01` to `ADM-AUTH-06` |
| `/admin` | `ADM-DASH-01` to `ADM-DASH-08` |
| `/admin/profile` | `ADM-PROFILE-01` to `ADM-PROFILE-09` |
| `/admin/workshops` | `ADM-WORKSHOPS-01` to `ADM-WORKSHOPS-12` |
| `/admin/workshops/:workshop_id` | `ADM-WORKSHOP-DETAIL-01` to `ADM-WORKSHOP-09` |
| `/admin/catalog/manufacturers` | `ADM-MFR-01` to `ADM-MFR-09` |
| `/admin/catalog/materials` | `ADM-MATERIAL-01` to `ADM-MATERIAL-14` |
| `/admin/notifications` | `ADM-NOTIF-01` to `ADM-NOTIF-08` |
| `/admin/platform/jobs` | `ADM-JOBS-01` to `ADM-JOBS-09` |
| `/admin/platform/errors` | `ADM-ERRORS-01` to `ADM-ERRORS-12` |
| `/admin/platform/users` | `ADM-USERS-01` to `ADM-USERS-13` |
| `/admin/audit` | `ADM-AUDIT-01` to `ADM-AUDIT-10` |
| Unknown route | `ADM-404-01` |
| `/docs`, `/api-docs`, `/api-redoc` | `ADM-DOCS-01` |

## Component matrix

| Component/state | Scenario ids |
|---|---|
| Admin shell, sidebar, topbar, primary action | `ADM-SHELL-01` to `ADM-SHELL-08` |
| Mobile drawer | `ADM-SHELL-05` |
| Docs/API menu | `ADM-DOCS-01` |
| Notification bell/dropdown | `ADM-NOTIF-01`, `ADM-NOTIF-02` |
| Full notifications page | `ADM-NOTIF-03` to `ADM-NOTIF-08` |
| Tabs | `ADM-PROFILE-02`, `ADM-WORKSHOP-DETAIL-03`, `ADM-AUDIT-03` |
| Project dropdown | `ADM-WORKSHOPS-04`, `ADM-MFR-04`, `ADM-ERRORS-03`, `ADM-AUDIT-04` |
| Multi-select filter | `ADM-MATERIAL-04` |
| Form select | `ADM-MATERIAL-07`, `ADM-MATERIAL-08` |
| Data table and wide-table containment | `ADM-MATERIAL-02`, `ADM-USERS-02`, `ADM-AUDIT-02` |
| Create/edit modal | `ADM-WORKSHOPS-06`, `ADM-MFR-05`, `ADM-MATERIAL-07`, `ADM-USERS-05` |
| Nested modal | `ADM-MATERIAL-09` |
| Confirm dialog | `ADM-WORKSHOPS-10`, `ADM-MFR-08`, `ADM-JOBS-05`, `ADM-ERRORS-07`, `ADM-USERS-10` |
| One-time secret modal | `ADM-WORKSHOPS-08`, `ADM-USERS-06`, `ADM-USERS-09` |
| Loading skeleton | `ADM-DASH-02`, `ADM-WORKSHOPS-02`, `ADM-MATERIAL-02`, `ADM-AUDIT-02` |
| Empty first-run | `ADM-DASH-04`, `ADM-MFR-03`, `ADM-MATERIAL-03`, `ADM-NOTIF-04`, `ADM-JOBS-03` |
| Empty no-results | `ADM-WORKSHOPS-05`, `ADM-MATERIAL-05`, `ADM-ERRORS-04`, `ADM-AUDIT-05` |
| Error state | `ADM-DASH-03`, `ADM-WORKSHOPS-03`, `ADM-ERRORS-05`, `ADM-NOTIF-05` |
| Toast host | `ADM-WORKSHOPS-08`, `ADM-MATERIAL-11`, `ADM-JOBS-05`, `ADM-USERS-10` |

## Scenarios

### Shell and navigation

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-SHELL-01` | `admin.ready` | Sign in and land on `/admin`. | Sidebar groups are **Platforma**, **Katalog**, **Operatorlik**, **Tizim**, **Ma'lumotnoma**. Active route is visually current. Counts show without layout jump. | desktop/tablet |
| `ADM-SHELL-02` | `admin.ready` | Tab from the browser chrome into the page. Activate **Kontentga o'tish**. | Skip link is visible on focus and moves focus to `#admin-content`. | desktop |
| `ADM-SHELL-03` | `admin.ready` | Click **Yangi ustaxona** in the top bar. | Navigates to `/admin/workshops`; primary action remains one clear action. | desktop/mobile |
| `ADM-SHELL-04` | `admin.ready` | Open **Hujjatlar & API**. | Menu opens below the nav item with Docs and API docs links; outside click closes it; Tab order is logical. | desktop |
| `ADM-SHELL-05` | `admin.ready`, mobile viewport | Tap **Menu**, navigate to **Materiallar**, then close with Escape and close button. | Drawer traps focus, closes on Escape/button/scrim, returns focus to Menu. No background scroll. | mobile |
| `ADM-SHELL-06` | `admin.reset` | Sign in. Try sidebar link, top primary action, notification bell, and direct `/admin/catalog/materials`. | User is pinned to `/admin/profile`; gate alert explains password change. Locked nav has `aria-disabled`; top action and mobile menu are disabled. | desktop/mobile |
| `ADM-SHELL-07` | `admin.ready` | Use browser back/forward between admin pages. | Document title changes, focus moves to main content, and shell state remains consistent. | desktop |
| `ADM-SHELL-08` | `admin.ready` | Simulate expired session or remove token, then navigate. | User is routed to login with no broken shell; returning sign-in respects redirect. | desktop |

### Authentication

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-AUTH-01` | none | Open `/admin/auth/login`. | Login card is centered, branded, and explains docs/API are separately protected. Inputs have visible labels. | desktop/mobile |
| `ADM-AUTH-02` | `admin.ready` | Sign in with valid credentials. | Button shows `Tekshirilmoqda`, then user lands on `/admin`. | desktop |
| `ADM-AUTH-03` | `admin.ready` | Submit bad password. | Generic error: `Login yoki parol noto'g'ri.` Form values are preserved. | desktop |
| `ADM-AUTH-04` | locked operator | Submit valid locked credentials. | Lockout message is concise and does not reveal account existence for wrong credentials. | desktop |
| `ADM-AUTH-05` | blocked operator | Submit valid blocked credentials. | `Hisob bloklangan.` appears only after otherwise valid credentials. | desktop |
| `ADM-AUTH-06` | API offline | Submit credentials. | Network error says server cannot be reached and lets the operator retry. | desktop |

### Dashboard

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-DASH-01` | full data | Open `/admin`. | KPI cards show active/blocked workshops, branches/clients, open errors, failed jobs. Recent tables and resource links align. | desktop/tablet/mobile |
| `ADM-DASH-02` | throttle initial requests | Open `/admin`. | Skeletons reserve space; no content jump. | desktop |
| `ADM-DASH-03` | fail overview request | Open `/admin`. | Admin error state has retry, trace id if present, and no dead end. | desktop |
| `ADM-DASH-04` | empty platform | Open `/admin`. | Empty states for workshops/jobs/errors explain what will appear. | desktop |
| `ADM-DASH-05` | one subload fails | Open `/admin`. | Warning says some sections could not refresh; existing data remains visible. | desktop |
| `ADM-DASH-06` | failed job | Click **Qayta**, confirm run. | Confirmation names the job; busy state prevents double-run; toast reports result. | desktop |
| `ADM-DASH-07` | open errors | Click errors KPI. | Navigates to error monitor and keeps context readable. | desktop |
| `ADM-DASH-08` | keyboard only | Navigate all dashboard links and buttons. | Visible focus, no traps, Enter/Space activate controls. | desktop |

### Profile and sessions

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-PROFILE-01` | `admin.ready` | Open `/admin/profile`. | Profile tab shows read-only identity, status, and session id without overflow. | desktop/mobile |
| `ADM-PROFILE-02` | `admin.ready` | Use mouse and arrow keys on tabs. | `AppTabs` exposes tablist semantics and switches panels without focus loss. | desktop |
| `ADM-PROFILE-03` | `admin.reset` | Sign in and open profile. | Password tab is selected by default. Reset gate remains visible. | desktop/mobile |
| `ADM-PROFILE-04` | `admin.ready` | Enter weak new password. | Strength text appears and remains concise. | desktop |
| `ADM-PROFILE-05` | `admin.ready` | Enter mismatched confirmation. | Inline error `Parollar mos kelmadi.` appears; submit disabled; fields preserved. | desktop |
| `ADM-PROFILE-06` | `admin.reset` | Change temporary password successfully. | Success `Parol o'zgartirildi.` appears; reset gate disappears; nav unlocks. | desktop |
| `ADM-PROFILE-07` | `admin.ready`, extra session | Open Sessions tab, revoke a non-current session. | Row busy/disabled state is visible; session disappears; toast confirms. | desktop |
| `ADM-PROFILE-08` | `admin.ready` | Click **Hammasi yopilsin**. | User is logged out and routed to login; no stale shell remains. | desktop |
| `ADM-PROFILE-09` | fail sessions request | Open Sessions tab. | Inline error has **Qayta urinish** and stays inside the sessions panel. | desktop |

### Workshops

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-WORKSHOPS-01` | `workshop.active`, `workshop.blocked` | Open `/admin/workshops`. | Table lists name, owner login, branch count, phone, created date, status, and actions. | desktop/tablet/mobile |
| `ADM-WORKSHOPS-02` | throttle list request | Open page. | Skeleton appears in table region and reserves space. | desktop |
| `ADM-WORKSHOPS-03` | fail list request | Open page. | Error state has specific title, retry, trace id if present. | desktop |
| `ADM-WORKSHOPS-04` | full data | Search by name/code; filter **Faol**, **Bloklangan**, reset filter. | Dropdown labels are clear; filtered results match; no-results differs from first-run empty. | desktop |
| `ADM-WORKSHOPS-05` | full data | Search impossible value. | Empty state says no workshop matched and gives a way forward. | desktop |
| `ADM-WORKSHOPS-06` | `admin.ready` | Open **Yangi ustaxona**. | Wide modal opens, focus enters, labels persist, working-hours grid fits all viewports. | desktop/mobile |
| `ADM-WORKSHOPS-07` | create modal | Type workshop name, then edit code manually, clear branch name. | Code auto-generates until manually edited; branch name defaults to `Asosiy filial` only when empty. | desktop |
| `ADM-WORKSHOPS-08` | create modal | Fill valid data, submit. | Busy label `Yaratilmoqda`, success toast, one-time secret modal with code/login/password and copy buttons. | desktop/mobile |
| `ADM-WORKSHOPS-09` | create modal | Submit missing/invalid fields and duplicate code. | Form remains open, values preserved, error copy is concise and field problems are findable. | desktop |
| `ADM-WORKSHOPS-10` | active row | Click **Bloklash**, try confirm without reason, then add reason and confirm. | Confirm disabled until reason; copy names session revocation and frozen orders; row becomes blocked. | desktop |
| `ADM-WORKSHOPS-11` | blocked row | Click **Blokdan chiqarish**, confirm. | Copy states sessions are not restored; row becomes active; toast confirms. | desktop |
| `ADM-WORKSHOPS-12` | keyboard only | Operate search, status dropdown, row detail, block/unblock, create modal. | No hover-only actions; focus order follows visual order. | desktop |

### Workshop detail

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-WORKSHOP-DETAIL-01` | active workshop | Open detail from list. | Back link, heading, status, profile read-only card, block action are visible. | desktop/mobile |
| `ADM-WORKSHOP-DETAIL-02` | blocked workshop | Open detail. | Block banner states orders freeze and sessions are not restored; block reason visible. | desktop |
| `ADM-WORKSHOP-DETAIL-03` | active workshop | Switch **Profil**, **Filiallar**, **Xodimlar** tabs. | Tabs are keyboard-operable; no data overflows; users tab clearly says staff list is not shown in v1. | desktop/tablet |
| `ADM-WORKSHOP-DETAIL-04` | active workshop | Open block modal, close with Escape, reopen, close with X and scrim. | Focus traps and returns; modal copy names consequences. | desktop |
| `ADM-WORKSHOP-DETAIL-05` | active workshop | Block with reason. | Button busy state appears; status changes; toast confirms. | desktop |
| `ADM-WORKSHOP-DETAIL-06` | blocked workshop | Unblock. | Button disabled while acting; status changes; toast confirms. | desktop |
| `ADM-WORKSHOP-DETAIL-07` | invalid id | Open detail with unknown id. | Error state offers back to workshops and retry. | desktop |
| `ADM-WORKSHOP-DETAIL-08` | mobile viewport | Open every tab and block modal. | No horizontal page scroll except table container; modal content is reachable. | mobile |
| `ADM-WORKSHOP-DETAIL-09` | keyboard only | Navigate all controls. | Focus visible and tab order is consistent. | desktop |

### Manufacturers

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-MFR-01` | `catalog.full` | Open manufacturers. | Table shows manufacturer, country, material count, status, note, actions. | desktop/mobile |
| `ADM-MFR-02` | throttle request | Open page. | Loading skeleton in data region. | desktop |
| `ADM-MFR-03` | empty catalog | Open page. | Empty state says manufacturer is needed before materials. | desktop |
| `ADM-MFR-04` | full data | Search and filter by status/country. | Dropdowns operate by mouse and keyboard; no-results state is clear. | desktop |
| `ADM-MFR-05` | full data | Open create modal. | Labels persist; optional fields are understandable; focus trap works. | desktop/mobile |
| `ADM-MFR-06` | create modal | Create valid manufacturer. | Success toast; row appears; modal closes. | desktop |
| `ADM-MFR-07` | existing row | Edit name/country/note. | Login-like stale values do not remain; row updates. | desktop |
| `ADM-MFR-08` | active row | Deactivate, then activate. | Confirm copy states effect on new selections and no effect on existing orders; status toggles. | desktop |
| `ADM-MFR-09` | API error | Save or status toggle fails. | Error/toast is visible; modal or row state remains recoverable. | desktop |

### Materials

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-MATERIAL-01` | `catalog.full` | Open materials. | Wide table shows image, material, manufacturer, kind, type/size, thickness, panel size, grain, status, usage count, actions. | desktop/tablet/mobile |
| `ADM-MATERIAL-02` | throttle request | Open page. | Loading skeleton; wide table never drags the page horizontally. | desktop |
| `ADM-MATERIAL-03` | no materials | Open page. | First-run empty explains adding manufacturer first and offers both actions. | desktop |
| `ADM-MATERIAL-04` | full data | Use kind dropdown and manufacturer/type/thickness multi-select filters. | Multi-select selected count is readable; keyboard toggles choices; clear path exists. | desktop/mobile |
| `ADM-MATERIAL-05` | full data | Search impossible value. | No-results empty offers **Filtrlarni tozalash**. | desktop |
| `ADM-MATERIAL-06` | material with image | Inspect table image and image fallback. | Images reserve space, have meaningful alt, and fallback does not shift the row. | desktop |
| `ADM-MATERIAL-07` | active manufacturer | Open **Yangi material** for panel. | FormSelect controls render instead of native selects; all labels visible; panel-only fields visible. | desktop/mobile |
| `ADM-MATERIAL-08` | create modal | Switch kind to **Krom**. | Edge explanation appears; panel dimensions/grain hide; save payload remains clear. | desktop |
| `ADM-MATERIAL-09` | material modal | Open inline **Yangi ishlab chiqaruvchi** modal. | Nested modal appears above parent, traps focus, saves, selects new manufacturer, and returns to material form. | desktop |
| `ADM-MATERIAL-10` | panel form | Enter length smaller than width. | Inline error appears; submit disabled; fields preserved. | desktop |
| `ADM-MATERIAL-11` | form with image | Upload image, remove image, upload invalid/failed image. | Upload state and failure copy are visible; image removal is obvious. | desktop |
| `ADM-MATERIAL-12` | existing material | Edit material. | Kind selector is disabled with explanation; save updates row. | desktop |
| `ADM-MATERIAL-13` | active row | Deactivate and reactivate. | Confirm copy names effect on new branch selections; status changes; toast confirms. | desktop |
| `ADM-MATERIAL-14` | keyboard + mobile | Complete filter and create/edit paths without mouse. | Hit targets are at least 44px; no clipped modal footer; no page horizontal scroll. | mobile |

### Notifications

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-NOTIF-01` | `notifications.full` | Open bell dropdown. | Bell announces unread count; badge caps cleanly; dropdown aligns and shows latest items. | desktop/mobile |
| `ADM-NOTIF-02` | unread item | Use dropdown keyboard navigation; click a notification. | Item marks read and routes to jobs/errors/detail destination. | desktop |
| `ADM-NOTIF-03` | full data | Open `/admin/notifications`. | Full page shows filter dropdown, unread/read styling, event-family tiles, dates, and row actions. | desktop/mobile |
| `ADM-NOTIF-04` | empty inbox | Open page and dropdown. | Empty copy is concise and not alarming. | desktop |
| `ADM-NOTIF-05` | fail notifications request | Open page/dropdown. | Error state does not break shell; retry exists on full page. | desktop |
| `ADM-NOTIF-06` | unread items | Click **O'qilgan** on one row. | Row changes to read state, unread count drops, action is disabled while marking. | desktop |
| `ADM-NOTIF-07` | unread items | Click **Hammasini o'qilgan**. | Disabled when unread is zero; toast confirms success. | desktop |
| `ADM-NOTIF-08` | >50 items | Click **Yana yuklash**. | Busy state appears and appended rows do not duplicate. | desktop |

### Jobs

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-JOBS-01` | `jobs.full` | Open jobs. | `cleanup-expired-sessions` is visible; daily low-stock digest is absent. | desktop/mobile |
| `ADM-JOBS-02` | throttle request | Open page. | Skeleton visible. | desktop |
| `ADM-JOBS-03` | no registered jobs | Open page. | Empty state explains jobs appear after bootstrap. | desktop |
| `ADM-JOBS-04` | job with runs | Open **Jurnalni ko'rish**. | Modal shows recent runs, result badges, logs, trace ids; focus trap works. | desktop |
| `ADM-JOBS-05` | job | Click **Hozir ishga tushirish**, confirm. | Confirm copy names off-schedule run; busy/disabled state prevents repeat; toast reports ok/skipped/failed. | desktop |
| `ADM-JOBS-06` | failed job | Click **Qayta urinish**. | Retry label and confirm copy differ from normal run. | desktop |
| `ADM-JOBS-07` | route query | Open `/admin/platform/jobs?job=cleanup-expired-sessions`. | Log modal opens for the named job. | desktop |
| `ADM-JOBS-08` | job already running | Trigger run while running. | UI says skipped/already running; no duplicate run appears. | desktop |
| `ADM-JOBS-09` | API error | Run fails. | Inline error and toast appear; row remains usable. | desktop |

### Error monitor

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-ERRORS-01` | `errors.full` | Open errors. | Table groups by code/module and shows 24h/7d counts, last occurrence, preview, status. | desktop/mobile |
| `ADM-ERRORS-02` | throttle request | Open page. | Skeleton visible. | desktop |
| `ADM-ERRORS-03` | full data | Search, status/module/threshold/time filters. | Filter labels are clear; filtered rows match. | desktop |
| `ADM-ERRORS-04` | no matching filters | Apply impossible search. | Empty copy says no errors are recorded/matched and does not imply success if filters are active. | desktop |
| `ADM-ERRORS-05` | fail list request | Open page. | Error state has retry and trace id. | desktop |
| `ADM-ERRORS-06` | open record | Open detail modal. | Full message, occurrence, trace id, context, workshop/user ids, and raw toggle are visible. | desktop/mobile |
| `ADM-ERRORS-07` | open record detail | Resolve. | Confirmation appears; status becomes resolved; **Qayta ochish** replaces resolve. | desktop |
| `ADM-ERRORS-08` | resolved record detail | Reopen. | Record becomes open; resolve affordance returns; no confirmation needed. | desktop |
| `ADM-ERRORS-09` | route query | Open `/admin/platform/errors?code=<code>` and `?record=<id>`. | Search/detail state opens to the target without losing list. | desktop |
| `ADM-ERRORS-10` | fail detail request | Open detail. | Detail-level error has retry without closing modal. | desktop |
| `ADM-ERRORS-11` | raw stack/context | Toggle raw data. | Pre blocks scroll internally and do not widen the page. | desktop/mobile |
| `ADM-ERRORS-12` | keyboard only | Open/resolve/reopen/close detail with keyboard. | Focus remains inside modal and returns to trigger. | desktop |

### Platform users

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-USERS-01` | at least two operators | Open platform users. | Current operator marked `Joriy`; self-block and last-active constraints are visible. | desktop/mobile |
| `ADM-USERS-02` | throttle request | Open page. | Loading skeleton visible; wide table contained. | desktop |
| `ADM-USERS-03` | fail list request | Open page. | Error state has retry. | desktop |
| `ADM-USERS-04` | full data | Search by name/login/phone/status. | Results filter correctly; no-results copy is actionable. | desktop |
| `ADM-USERS-05` | full data | Open create modal. | Login enabled, temporary password field visible, focus trap works. | desktop/mobile |
| `ADM-USERS-06` | create modal | Create operator. | One-time secret modal shows login/password and copy actions; new row appears. | desktop |
| `ADM-USERS-07` | existing user | Edit operator. | Login disabled; temp password absent; save updates name/phone only. | desktop |
| `ADM-USERS-08` | current user | Check block button. | Button is disabled and labelled `O'zini bloklab bo'lmaydi`. | desktop |
| `ADM-USERS-09` | non-current user | Reset password. | Danger confirm names session revocation; one-time secret modal appears. | desktop |
| `ADM-USERS-10` | non-current active user | Block with reason. | Modal requires reason; sessions revocation copy is clear; toast confirms. | desktop |
| `ADM-USERS-11` | blocked user | Unblock. | User returns to active; sessions are not restored. | desktop |
| `ADM-USERS-12` | one active user only | Try to block last active operator. | Button disabled and labelled `Oxirgi faol operatorni bloklab bo'lmaydi`; server rejection copy is specific if forced. | desktop |
| `ADM-USERS-13` | API error | Save/reset/block/unblock fails. | Error/toast visible; form state recoverable. | desktop |

### Audit

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-AUDIT-01` | `audit.full` | Open audit. | Actions tab loads with action rows and server-filter count. | desktop/mobile |
| `ADM-AUDIT-02` | throttle request | Open page. | Skeleton visible. | desktop |
| `ADM-AUDIT-03` | full data | Switch between **Amallar** and **Holat o'zgarishlari**. | Tab semantics correct; each panel keeps its table shape. | desktop |
| `ADM-AUDIT-04` | full data | Filter by workshop, entity type, time; search action prefix, actor, UUID. | Server filters update results; Enter in search runs filter. | desktop |
| `ADM-AUDIT-05` | no matching filter | Apply impossible search/filter. | Empty state is clear and count reflects zero. | desktop |
| `ADM-AUDIT-06` | >50 rows | Click **Ko'proq yuklash**. | Rows append, button busy label appears, max 200 cap is understandable. | desktop |
| `ADM-AUDIT-07` | actions tab | Click **CSV**. | CSV downloads with BOM, current tab data only, no UI break. | desktop |
| `ADM-AUDIT-08` | status tab | Click **CSV**. | Status CSV includes transition and reason. | desktop |
| `ADM-AUDIT-09` | fail audit request | Open page or filter. | Error state has retry; filters remain. | desktop |
| `ADM-AUDIT-10` | mobile + 200% zoom | Open both tabs. | Wide table scrolls inside container; page itself does not scroll sideways. | mobile |

### Docs, API docs, and not-found

| ID | Setup | Steps | Expected | Screenshots |
|---|---|---|---|---|
| `ADM-DOCS-01` | `admin.ready` | Open docs menu and each Docs/API link. | Links open new tab; labels make separate HTTP-Basic prompt unsurprising; `/docs`, `/api-docs`, `/api-redoc` load behind docs auth. | desktop |
| `ADM-404-01` | `admin.ready` | Open `/admin/unknown-route`. | Not-found page is inside admin shell, offers **Asosiyga qaytish**, and copy is localized or intentionally accepted. | desktop/mobile |

## Visual audit checklist

For each screenshot, record pass/fail in `audit.md`:

- Layout: no clipped text, no overlapping controls, no unexpected page horizontal scroll, table
  scroll affordance visible where needed.
- Responsive: drawer, modal, table, and form footer remain usable on `390x844`; no target is
  smaller than 44px.
- Hierarchy: one clear primary action per page; secondary actions do not compete.
- Consistency: admin buttons, pills, tabs, dropdowns, empty/error states, and modal headers use
  the same visual language across pages.
- Accessibility: visible focus, reachable controls, labels, role/name/state, modal focus trap,
  Escape behavior, reduced-motion sanity.
- Feedback: busy state on async actions, disabled state explains why, toast/status appears after
  action.
- Copy: Uzbek is grammatical, concise, and specific; avoid vague `Amal bajarilmadi` where a
  specific fix is possible.

## Suggested audit format

Use this structure in `.workflows/admin-manual-e2e/<run-id>/audit.md`:

```markdown
# Admin manual E2E audit — <run-id>

## Summary

## Coverage

## Findings

1. **[High] <title>** — route/component: `<value>`. Screenshot: `<path>`. Impact: <impact>.
   Suggested fix: <fix>.

## Copy notes

## Screenshot manifest

## Residual risk
```

Next: [`docs/ref/features/platform.md`](../features/platform.md) for the platform-ops feature
spec, and [`docs/ref/features/access-management.md`](../features/access-management.md) for
operator auth/session rules.
