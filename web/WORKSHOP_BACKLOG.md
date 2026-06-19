# Workshop SPA — Improvement Backlog

A living, engineering-owned backlog for the **workshop SPA** (the owner + staff
app at `workshop.`). Separate from [`CLIENT_BACKLOG.md`](./CLIENT_BACKLOG.md) and
the (pending) admin backlog. Engineering/tracking artifact — **not** product canon,
so it lives under `web/` (no `docs_uz/` mirror). `docs/` stays the source of truth
for *what* the product is; this tracks *fixes/polish* against the current Vue impl.

> **Round 1** (2026-06-10): 10-lens audit (ux-flow, responsive, i18n, design-parity
> vs `web/prototypes/prototype-full/workshop`, a11y, correctness, performance,
> states/errors, completeness, **permission-gating**). 100 raw findings → 71 items
> (WS-01…WS-71). **Re-verify each against current code before implementing** — line
> numbers are point-in-time; ⚠ items are flagged as possibly-already-handled.
>
> **Round 2** (2026-06-10): the four pending lenses — spec-conformance
> (orders-production state machine + finance/inventory/catalog clause-by-clause),
> proto-screens (per-screen prototype diff of all 17 workshop screens), testing,
> security. 44 raw → **44 new items WS-72…WS-115** (zero duplicates — R2 audits
> ground R1 didn't reach). Standout: **WS-113 (security, P1)** — one-time temp
> passwords leak across users/logout on a shared device. 14 testing items, most
> regression tests pairing with a named R1 fix. All planned lenses now complete.
>
> **Round 3** (2026-06-19): one cross-project test-hygiene item — **WS-116** —
> added from local verification. Also normalized verified stale rows from code
> drift (WS-09, WS-42, WS-64, WS-102) so execution does not start from false
> premises.
>
> **Execution slice 1** (2026-06-19): completed the workshop permission foundation
> (WS-01, WS-03, WS-04, WS-05, WS-106, WS-107), partially closed WS-02, and made
> local E2E file-upload boot hermetic against developer `.env` drift (WS-116).
>
> **Execution slice 2** (2026-06-19): closed the first correctness/i18n batch:
> stock transaction display units, discount re-entry safety, order-conflict copy,
> localized workshop action errors, completion worker validation, and order-list cache
> isolation (WS-07/08/09/14/27/28 plus WS-101/104 tests).
>
> **Execution slice 3** (2026-06-19): closed the security/env batch:
> logout now resets session-bearing Pinia stores, temp-password residue is wiped
> across load/logout paths, and backend config/error tests ignore developer `.env`
> drift (WS-113/114/116).
>
> **Execution slice 4** (2026-06-19): closed the first spec-conformance batch:
> queue cards now use planned production metrics, order-detail worker assignment/revert
> controls match the status machine, finance ledger rows can be edited, production
> reports show labelled edge-material metres + thickness rollups, income order picking
> is branch-scoped, and ledger dates reject future values (WS-72/73/74/75/78/79/81/83).
>
> **Execution slice 5** (2026-06-19): closed the first finance/inventory batch:
> receipt scans upload/attach to finance rows with visible upload errors, production
> report rows link into salary-expense entry, and stock transaction logs show branch,
> supplier, actor names, order links, and notes in both inventory views. It also
> surfaced PDF download busy/error state, branch settings save feedback, and trace
> IDs for user/finance mutation failures (WS-42/43/44/45/80/82/85/86/96).
>
> **Execution slice 6** (2026-06-19): closed the first performance batch:
> workshop order lists are paginated and use a batch summary builder, worker queues
> request server-filtered assignments, branch context is cached/invalidation-based,
> and inventory transaction ledgers are date-filtered, paginated, and lazy-loaded
> per tab (WS-11/12/30/31/32).
>
> **Execution slice 7** (2026-06-19): closed the first P1 UX/state batch:
> cutting-plan and production-report screens are Uzbek, ProjectDropdown uses clamped
> viewport positioning, catalog loads have dedicated error state, and the dashboard
> reports partial load failures while its sales chart uses real daily finance data
> with wired period controls (WS-13/16/17/19/20).
>
> **Execution slice 8** (2026-06-19): closed the topbar branch-scope flow:
> the workshop topbar branch selector is now shared through the workshop store,
> page-level branch filters sync with it, and dashboard/orders/inventory/catalog/
> finance screens refocus their data when it changes (WS-15).
>
> **Execution slice 9** (2026-06-19): closed small completeness defects:
> cutting-plan and production-report routes are exposed through workshop navigation,
> the dead income view was removed, and workshop settings can upload, preview, remove,
> and save the profile logo through the existing file/settings APIs (WS-33/34/35).
>
> **Execution slice 10** (2026-06-19): restored prototype-style order-list actions:
> board cards and table rows now expose a gated status menu backed by shared action
> rules, confirmation/reason dialogs, and focused helper tests (WS-21).
>
> **Execution slice 11** (2026-06-19): wired workshop mutation feedback:
> the existing toast primitive now confirms successful order, production, catalog,
> inventory, finance, branch/settings, notification, and user-admin actions (WS-22).
>
> **Execution slice 12** (2026-06-19): fixed workshop tab semantics:
> shared `AppTabs` provides `tablist`/`tab` roles, selected state, roving keyboard
> focus, and linked tab panels across the five workshop tab screens (WS-23).
>
> **Execution slice 13** (2026-06-19): fixed permission-matrix checkbox names:
> create-user and user-detail grant matrices now announce permission + branch for
> every checkbox (WS-24).
>
> **Execution slice 14** (2026-06-19): fixed mobile drawer accessibility:
> workshop/admin drawers now lock body scroll, focus the drawer on open, trap Tab,
> close with Escape, and restore focus to the opener (WS-25).
>
> **Execution slice 15** (2026-06-19): fixed cutting-plan SVG tab-order noise:
> SVG placements remain mouse-selectable but are hidden from assistive tech and no
> longer enter keyboard focus; accessible placement buttons remain the keyboard path
> (WS-26).
>
> **Execution slice 16** (2026-06-19): made topbar search real:
> the workshop topbar search now opens with ⌘K/Ctrl+K, queries allowed order/staff/
> catalog/stock sources without mutating page stores, shows result groups/partial
> errors, and lands list shortcuts on pages that honor `?search=` (WS-36).
>
> **Execution slice 17** (2026-06-19): fixed production-only landing:
> dashboard now treats `process_production` as a real workspace mode with cutting/
> banding shortcuts and assigned-work counts, hides order-management summaries from
> production-only staff, and queue empty states explain manager assignment (WS-38).
>
> **Execution slice 18** (2026-06-19): completed discount correction UX:
> order detail now has an explicit remove-discount action, zero-discount backend
> requests clear discount metadata, and API/helper tests cover the removal path (WS-39).
>
> **Execution slice 19** (2026-06-19): fixed queue completion credit:
> owner queue cards now load per-branch worker options and ask "Kim bajardi" before
> completing cutting/banding on behalf; staff still credit the assigned worker (WS-40).
>
> **Execution slice 20** (2026-06-19): added the missing cutting-plan not-found state:
> cutting-plan detail now renders a final empty state with a back link instead of a
> blank page when no plan/result is available and no explicit error exists (WS-47).
>
> **Execution slice 21** (2026-06-19): fixed workshop notification routing:
> stock/inventory and finance notifications now deep-link to inventory/finance
> surfaces, the inventory filter matches stock events, null destinations are not
> marked read, and focused tests cover the filter/deep-link logic (WS-48/105).
>
> **Execution slice 22** (2026-06-19): fixed dashboard low-stock/recent data:
> dashboard now aggregates low-stock items across the accessible inventory branch set
> (or the selected topbar branch) and loads recent orders separately from the active
> board list so completed/cancelled history can appear (WS-49).
>
> **Execution slice 23** (2026-06-19): restored material swatch variety:
> catalog, inventory, and dashboard low-stock rows now derive prototype-style swatch
> classes from material color/decor/name with stable fallbacks and focused helper
> coverage (WS-50).
>
> **Execution slice 24** (2026-06-19): restored assigned-worker identity chips:
> the orders board and table now render prototype-style cutter/edger chips with icons
> and initials, resolving names from the existing branch worker options and falling
> back safely when a worker record is unavailable (WS-51/77).
>
> **Execution slice 25** (2026-06-19): cleaned small visual/i18n drifts:
> cutting-plan SVGs now use the teal design tokens instead of hard-coded blue,
> workshop mobile chrome uses inline SVG menu/close icons, and remaining English
> fallback copy in cutting-plan material titles is localized (WS-54/55/56).
>
> **Execution slice 26** (2026-06-19): restored the dashboard sales chart:
> the sales card now uses an SVG chart with gridlines, dated x-axis labels, per-bar
> titles, Bugun/Eng yuqori/Boshqalar legend, `aria-pressed` range toggles, and a
> screen-reader summary of total/today/peak values (WS-52/61).
>
> **Execution slice 27** (2026-06-19): fixed narrow-screen order/table layout:
> the orders kanban stacks into one column on phones and card-contained tables now
> inherit the prototype's narrow-viewport horizontal-scroll fallback (WS-69/70).
>
> **Execution slice 28** (2026-06-19): tightened finance loading and tests:
> finance reports now load summary/income/production in parallel, the ledger page loads
> only the active tab and refreshes on tab/route changes, and focused tests cover
> finance route-tab mapping plus store loader/action mutation behavior (WS-58/103/109).
>
> **Execution slice 29** (2026-06-19): fixed workshop user creation loading ownership:
> create-user no longer manually clears a concurrent user-list spinner; it invalidates
> stale loads, upserts the created user, then reloads through `loadUsers()` while
> preserving the one-time temp password. Workshop store tests now cover user-list races,
> create-user loading, inventory errors, owner-only branch pricing, and stock-in reloads
> (WS-63/108).
>
> **Execution slice 30** (2026-06-19): closed small finance/notifications/security gaps:
> the finance report production card now includes Davr and Maosh yozish shortcuts,
> the notifications page surfaces load/action trace IDs and keeps navigation working
> after mark-read failures, and AuthFileImage revokes late stale object URLs with a
> regression test (WS-53/64/115).
>
> **Execution slice 31** (2026-06-19): tightened branch status/save feedback:
> branch status changes refresh the active-order count when closing and again just
> before submit, while the already-present create/settings success toasts and inline
> saved state are reflected in the backlog (WS-62/65).
>
> **Execution slice 32** (2026-06-19): closed the remaining small permission/deep-link
> polish: production queues now show no-permission empty states and branch-level
> button guards, dashboard-only staff no longer see or enter the Orders board,
> inventory/catalog branch links use neutral copy, and `/finance/income` is kept as
> an intentional deep-link backed by tab-route tests (WS-66/67/68/71).
>
> **Execution slice 33** (2026-06-19): closed the small performance/a11y/spec batch:
> inventory/catalog/users now use one server-filtered source of truth, workshop users
> expose last-login, finance/order inline forms move focus to opened panels, low-stock
> quantities include text cues, finance fallback states are friendly, and order
> timeline rows render production metadata (WS-02/57/59/60/76/95).
>
> **Execution slice 34** (2026-06-19): closed the remaining prototype-parity and E2E
> coverage batch: branch detail restored overview/staff/orders tabs and real KPIs,
> orders gained date filters and CSV export, order detail restored edge-material and
> price breakdowns, branch cards use real operational counts, staff profiles are
> editable, and the owner discount/finance/revert conflict browser specs were added
> (WS-87/89/90/91/92/94/110/111/112).
>
> **Execution slice 35** (2026-06-19): final browser/E2E hardening after Docker
> recovery: fixed concurrent order-number allocation under Postgres, stacked narrow
> order-detail discount actions, rendered readable linked-order labels in the income
> ledger, corrected branch staff links to `/workshop/settings/users`, made owner
> user-detail pages resilient to intentionally forbidden session management, and
> refreshed stale E2E selectors for the current Uzbek tab/action UI.

## Conventions

- **Priority** — `P1` do-first (high-leverage, blocks the order-production pipeline
  or breaks permission gating), `P2` important, `P3` nice-to-have.
- **Severity** — operator/staff impact. **Effort** — `S` ≤½ day · `M` ~1–2 days · `L` larger.
- **Category** — spec-conformance · permission-gating · correctness-bug · states-errors ·
  performance · design-parity · a11y · ux-flow · i18n-copy · completeness-stub ·
  responsive · testing · security · tech-debt.
- **Status** — `Open` · `WIP` · `Partial` · `Done` · `Won't`.
- Scope guard: in-v1 per [`docs/scope.md`](../docs/scope.md). Out-of-v1 (workshop-side
  audit viewer, operator order browsing, delivery, inter-branch transfer, payroll
  engine, online payments) excluded.
- **Security note:** client-side gating is UX, not the boundary — the FastAPI service
  enforces authz server-side. But showing buttons/screens that always 403 (WS-01/02)
  is a real UX bug *and* leaks the existence of sensitive surfaces.

## Counts

| | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| Tracked | 25 | 52 | 39 | **116** |

Status totals: Open 0 · Partial 0 · Done 116 · Won't 0.

By category: spec-conformance ~21 · testing ~15 · design-parity ~16 ·
correctness-bug ~13 · permission-gating ~12 · states-errors ~11 · performance ~9 ·
completeness-stub ~8 · i18n-copy ~6 · a11y ~7 · responsive ~3 · security ~3.

## Index

| ID | Pri | Cat | Sev | Eff | Status | Title |
|----|-----|-----|-----|-----|--------|-------|
| WS-01 | P1 | permission-gating | high | M | Done | Order-detail lifecycle actions now permission-gated |
| WS-02 | P1 | permission-gating | high | S | Done | Finance/production route gates exist; fallback states still need polish |
| WS-03 | P1 | permission-gating | high | M | Done | Finance/Dashboard now respect branch-scoped grants |
| WS-04 | P1 | permission-gating | med | M | Done | Shared workshop permissions helper/composable added |
| WS-05 | P1 | permission-gating | med | M | Done | Workshop routes enforce permission metadata |
| WS-06 | P1 | correctness-bug | high | S | Done | Metres render with comma decimal → 2.5m shows "2,500 m" |
| WS-07 | P1 | correctness-bug | high | S | Done | Inventory tx log formats edge-material quantities in display units |
| WS-08 | P1 | correctness-bug | high | M | Done | Discount re-entry no longer reuses computed discount amount |
| WS-09 | P1 | correctness-bug | high | M | Done | Version conflict refetch + friendly user copy |
| WS-10 | P1 | correctness-bug | high | S | Done | Finance dual-route tab doesn't react to income↔expenses nav |
| WS-11 | P1 | performance | high | L | Done | Workshop order list unbounded + server N+1 detail build |
| WS-12 | P1 | performance | high | M | Done | Stock transactions unbounded (client + server) |
| WS-13 | P1 | i18n-copy | high | M | Done | 3 screens fully English (cutting-plans, plan-detail, production) |
| WS-14 | P1 | i18n-copy | high | M | Done | Order/queue/finance/user action errors use localized copy |
| WS-15 | P1 | ux-flow | high | L | Done | Topbar branch dropdown is a dead control (drives only nav) |
| WS-16 | P1 | responsive | high | M | Done | ProjectDropdown popover double-counts scroll, no edge clamp |
| WS-17 | P1 | states-errors | high | S | Done | Catalog table: no loading/error state (silent empty) |
| WS-18 | P1 | states-errors | high | S | Done | Settings save: no error/busy/success |
| WS-19 | P1 | states-errors | high | M | Done | Dashboard swallows all load errors (.catch undefined) |
| WS-20 | P1 | completeness-stub | high | M | Done | Dashboard sales chart is hardcoded fabricated data |
| WS-21 | P2 | design-parity | high | L | Done | Order board/table lost per-card status-action kebab menu |
| WS-22 | P2 | design-parity | high | L | Done | No toast system — every successful mutation is silent |
| WS-23 | P2 | a11y | high | M | Done | 5 tab UIs lack tab/tablist/tabpanel ARIA |
| WS-24 | P2 | a11y | med | S | Done | Permission-matrix checkboxes have no accessible name |
| WS-25 | P2 | a11y | med | M | Done | Mobile drawer: no focus trap/Escape/scroll-lock |
| WS-26 | P2 | a11y | med | M | Done | Cutting-plan SVG rects focusable but unlabeled/no focus |
| WS-27 | P2 | correctness-bug | med | S | Done | complete cutting/banding require a credited worker |
| WS-28 | P2 | correctness-bug | med | S | Done | Order mutations patch the matching role list in place |
| WS-29 | P2 | correctness-bug | med | S | Done | Stock-in/adjustment post unvalidated quantities |
| WS-30 | P2 | performance | med | M | Done | Cut/band queues refetch full active list, filter client-side |
| WS-31 | P2 | performance | med | M | Done | loadBranchContext refetched on nearly every screen mount |
| WS-32 | P2 | performance | med | S | Done | Inventory eagerly fetches stock+all-tx+suppliers on mount |
| WS-33 | P2 | completeness-stub | med | S | Done | Cutting-plans & production screens unreachable (no nav) |
| WS-34 | P2 | completeness-stub | med | S | Done | Orphaned WorkshopFinanceIncomeView (English, ungated dead code) |
| WS-35 | P2 | completeness-stub | med | M | Done | Settings "Logo" file input is a dead control |
| WS-36 | P2 | completeness-stub | med | M | Done | Topbar global search + ⌘K are non-functional |
| WS-37 | P2 | states-errors | high | S | Done | "Mijoz olib ketdi" terminal action has no confirmation |
| WS-38 | P2 | ux-flow | high | M | Done | Fresh production staff land on an empty app (no awaiting list) |
| WS-39 | P2 | ux-flow | med | M | Done | Discount can only be added, never edited/removed |
| WS-40 | P2 | ux-flow | med | M | Done | Queue "done" can't credit who actually did the work |
| WS-41 | P2 | ux-flow | med | M | Done | Income entry can't show order's outstanding balance |
| WS-42 | P2 | states-errors | med | M | Done | PDF download store tracks failure/busy, but UI does not surface it |
| WS-43 | P2 | states-errors | med | S | Done | Branch settings/pricing save error never rendered (1st form) |
| WS-44 | P2 | states-errors | med | S | Done | Receipt upload failures show feedback |
| WS-45 | P2 | states-errors | med | S | Done | User/finance action errors omit trace_id |
| WS-46 | P3 | states-errors | low | S | Done | User-detail misreports context-load failure as "not found" |
| WS-47 | P3 | states-errors | med | S | Done | Cutting-plan detail blank when plan has no result |
| WS-48 | P3 | ux-flow | low | S | Done | Notifications can't deep-link finance/stock; inventory chip broken |
| WS-49 | P3 | correctness-bug | med | M | Done | Dashboard low-stock scoped to branchIds[0]; recent = active-only |
| WS-50 | P3 | design-parity | med | M | Done | Material swatches all render the same default gradient |
| WS-51 | P3 | design-parity | med | S | Done | Order board lost assigned-worker chips (icons + initials) |
| WS-52 | P3 | design-parity | med | M | Done | Dashboard chart dropped SVG/gridlines/tooltips/legend |
| WS-53 | P3 | design-parity | low | S | Done | Production report dropped period column + "Maosh yozish" shortcut |
| WS-54 | P3 | design-parity | low | S | Done | Cutting-plan SVG uses off-brand blue, not teal accent |
| WS-55 | P3 | design-parity | low | S | Done | Mobile chrome uses ☰/× glyphs instead of SVG icons |
| WS-56 | P3 | i18n-copy | med | S | Done | English fallback strings ("No material", etc.) |
| WS-57 | P3 | performance | low | M | Done | Inventory/Catalog/Users client-filter full list redundantly |
| WS-58 | P3 | performance | low | S | Done | Finance fires 3 sequential requests; expenses double-fetch |
| WS-59 | P3 | a11y | med | M | Done | Inline forms (void/assign/discount) far from trigger, no focus move |
| WS-60 | P3 | a11y | low | S | Done | Muted text fails AA; low-stock/destructive color-only |
| WS-61 | P3 | a11y | low | S | Done | Dashboard chart hidden from AT; range toggles no aria-pressed |
| WS-62 | P3 | correctness-bug | low | S | Done | Branch-close confirm uses a stale active-orders count |
| WS-63 | P3 | correctness-bug | low | S | Done | createUser force-clears loading + bumps request id |
| WS-64 | P3 | states-errors | low | S | Done | Notifications store captures failures, but page still hides action/load trace |
| WS-65 | P3 | ux-flow | low | S | Done | Branch create/settings saves give no success feedback |
| WS-66 | P3 | permission-gating | low | S | Done | Production queues empty-without-explanation; buttons ungated |
| WS-67 | P3 | permission-gating | low | S | Done | view_dashboard-only staff get full Orders management surface |
| WS-68 | P3 | permission-gating | low | S | Done | Inventory/Catalog deep-link staff with owner-flavoured CTAs |
| WS-69 | P3 | responsive | low | M | Done | Orders kanban: no phone breakpoint (5×210px h-scroll) |
| WS-70 | P3 | responsive | low | S | Done | Missing prototype's `card:has(.tbl)` overflow fallback |
| WS-71 | P3 | completeness-stub | low | S | Done | /finance/income route redundant (renders Expenses view) |
| WS-72 | P1 | spec-conformance | high | M | Done | Banding queue uses planned labelled edge-material metres |
| WS-73 | P2 | spec-conformance | med | M | Done | Cutting queue shows planned panel count before completion |
| WS-74 | P1 | spec-conformance | high | M | Done | Order detail supports assign/change cutter and edger |
| WS-75 | P2 | spec-conformance | med | S | Done | Revert action names the concrete target state |
| WS-76 | P3 | spec-conformance | low | M | Done | Timeline omits production stamps (credited worker/panels) |
| WS-77 | P3 | spec-conformance | low | S | Done | Board never renders WHO is assigned (cutter/edger identity) |
| WS-78 | P1 | spec-conformance | high | M | Done | Income/expense edit actions call existing PATCH endpoints |
| WS-79 | P1 | spec-conformance | high | M | Done | Production report shows labelled edge-material metres + thickness rollup |
| WS-80 | P2 | completeness-stub | med | M | Done | Production screen links rows to salary expense entry |
| WS-81 | P2 | spec-conformance | med | S | Done | Income order picker is scoped to selected branch |
| WS-82 | P2 | completeness-stub | med | M | Done | Finance forms upload and attach receipt scans |
| WS-83 | P2 | spec-conformance | med | S | Done | Future ledger dates blocked in UI and backend |
| WS-84 | P2 | spec-conformance | med | M | Done | Materials catalog lacks manufacturer/type filters (+backend) |
| WS-85 | P2 | spec-conformance | med | S | Done | Stock tx log shows actor names and notes |
| WS-86 | P3 | spec-conformance | low | S | Done | BranchDetail tx table shows order link, actor, and note |
| WS-87 | P2 | design-parity | high | L | Done | Branch detail dropped Overview/Staff/Orders tabs + KPI strip |
| WS-88 | P2 | completeness-stub | high | L | Done | Inventory screen lost stock-in/adjust/supplier actions |
| WS-89 | P2 | design-parity | med | M | Done | Orders screen dropped date filter + CSV export |
| WS-90 | P2 | design-parity | med | M | Done | Order item list drops per-side edge thickness + breakdown |
| WS-91 | P2 | design-parity | med | M | Done | Price card lost krom material/service split; header lost due date |
| WS-92 | P2 | design-parity | med | M | Done | Branch cards dropped low-stock KPI; fake material/staff counts |
| WS-93 | P2 | i18n-copy | med | S | Done | Finance reports show raw payment-method code |
| WS-94 | P2 | completeness-stub | med | M | Done | User-detail Profil tab is read-only (no edit form) |
| WS-95 | P3 | design-parity | low | S | Done | Users list dropped "Oxirgi kirish" column |
| WS-96 | P3 | design-parity | low | S | Done | Inventory tx table includes Filial column |
| WS-97 | P3 | completeness-stub | low | M | Done | Catalog rows lost hide-from-customers toggle |
| WS-98 | P3 | i18n-copy | low | S | Done | Profile grant rows show raw branch-id fragment |
| WS-99 | P2 | testing | high | S | Done | Test formatStockQuantity metres (ships w/ WS-06) |
| WS-100 | P2 | testing | high | S | Done | Test parseDisplayQuantity round-trip (ships w/ WS-07) |
| WS-101 | P2 | testing | high | M | Done | Test orders.patchOrder list isolation (ships w/ WS-28) |
| WS-102 | P2 | testing | high | M | Done | Test orders 409 conflict + refetch (ships w/ WS-09) |
| WS-103 | P2 | testing | med | M | Done | Test finance dual-route tab reactivity (ships w/ WS-10) |
| WS-104 | P2 | testing | high | M | Done | Test discount draft/re-entry safety (ships w/ WS-08/39) |
| WS-105 | P2 | testing | med | M | Done | Test notification filter + deep-link (ships w/ WS-48) |
| WS-106 | P2 | testing | high | M | Done | Test useWorkshopPermissions truth table (ships w/ WS-04) |
| WS-107 | P2 | testing | high | M | Done | Test permission route guard (ships w/ WS-05) |
| WS-108 | P3 | testing | med | M | Done | Test workshop store branch-context flows |
| WS-109 | P3 | testing | med | S | Done | Test finance store load + error capture |
| WS-110 | P3 | testing | med | M | Done | E2E: owner applies a discount, persists on reload |
| WS-111 | P3 | testing | med | M | Done | E2E: record income against order + standalone expense |
| WS-112 | P3 | testing | med | L | Done | E2E: revert/cancel-with-reason + 409 recovery |
| WS-113 | P1 | security | high | S | Done | Temp password cleared across user loads and logout reset |
| WS-114 | P2 | security | med | M | Done | Pinia session stores reset on logout |
| WS-115 | P3 | security | low | S | Done | AuthFileImage object-URL leak under rapid fileId change |
| WS-116 | P2 | testing | med | S | Done | E2E and backend tests are isolated from developer `.env` drift |

---

## P1 — do first (permission gating + pipeline correctness)

### WS-01 · Order-detail lifecycle actions now permission-gated — `permission-gating` · high · M · Done
**Files:** `views/WorkshopOrderDetailView.vue`, `docs/ref/features/orders.md`
**Why:** Order-detail lifecycle actions now derive branch-scoped capability through `useWorkshopPermissions`. Approve/assign/collect/revert/cancel/discount require `manage_orders`; cutting/banding completion requires `manage_orders` or an assigned worker with `process_production`; settlement data is hidden unless the user can view/manage finance.
**Fix:** Done. Remaining raw error-code copy belongs to WS-14/WS-09, not permission gating.

### WS-02 · Finance/production route gates exist; fallback states still need polish — `permission-gating` · high · S · Done
**Files:** `views/WorkshopFinanceView.vue`, `WorkshopFinanceProductionView.vue`, `apps/workshop/routes.ts`
**Why:** Routes now require `manage_finance`/`view_finance_reports`, and the report pages skip loads behind the shared permission helper. Expense/income write routes require `manage_finance`, and non-owner branch options are scoped to branches where that grant exists.
**Fix:** Done. Finance summary, production report, and the combined income/expense ledger now render friendly no-permission fallbacks when route guards normally prevent entry; write forms remain scoped to `manage_finance`.

### WS-03 · Finance/Dashboard now respect branch-scoped grants — `permission-gating` · high · M · Done
**Files:** `views/WorkshopFinanceExpensesView.vue`, `WorkshopDashboardView.vue`, `docs/access-patterns.md`
**Why:** Finance write branch options are now filtered by `manage_finance`, non-owners cannot write workshop-wide ledger entries, and dashboard finance/inventory/order affordances use the shared branch-aware helper instead of raw `grants.some()`.
**Fix:** Done for the named Finance/Dashboard drift.

### WS-04 · Shared workshop permissions helper/composable added — `permission-gating` · med · M · Done
**Files:** `WorkshopDashboardView.vue`, `WorkshopInventoryView.vue`, `WorkshopCatalogView.vue`, `WorkshopFinanceExpensesView.vue`, `WorkshopBranchDetailView.vue`
**Why:** `shared/app/workshopPermissions.ts` owns the pure permission rules, and `shared/composables/useWorkshopPermissions.ts` exposes the Vue-facing API for owner checks, branch grants, accessible branches, and route access. Dashboard, inventory, catalog, finance, and order detail now use the shared path.
**Fix:** Done.

### WS-05 · Workshop routes enforce permission metadata — `permission-gating` · med · M · Done
**Files:** `app/createRoleApp.ts`, `apps/workshop/routes.ts`
**Why:** Workshop routes now carry `meta.workshopAccess`, including owner-only routes and branch-param scoped routes. `createRoleApp` enforces the metadata after authentication/password-reset checks and redirects unauthorized workshop users back to `/workshop`.
**Fix:** Done. Route-guard behavior is covered by WS-107.

### WS-06 · Metres render with comma decimal → 2.5m shows "2,500 m" — `correctness-bug` · high · S
**Files:** `shared/formatters.ts`
**Why:** `formatStockQuantity` (`:23-31`) uses `Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 3, minimumFractionDigits: value%1000===0?0:3 }).format(value/1000)`. `uz-UZ` uses **comma** as the decimal separator, so 2500mm → "2,500 m" — visually identical to 2,500 metres for anyone reading comma as thousands grouping. Used across inventory, branch detail, dashboard low-stock, banding-queue.
**Fix:** Format metres with an explicit decimal point or drop the 3-digit zero-padding and show significant decimals (e.g. "2.5 m"), so edge-tape stock isn't misread by 1000×.

### WS-07 · Inventory tx log formats edge-material quantities in display units — `correctness-bug` · high · S · Done
**Files:** `views/WorkshopInventoryView.vue`
**Why:** `WorkshopInventoryView` now resolves each transaction's display unit from the current stock item and renders both transaction quantity and balance through `formatStockQuantity`, preserving the positive sign for stock-in. Edge stock now shows metres instead of raw millimetres.
**Fix:** Done. Backend-side transaction payload enrichment remains a possible future cleanup, but the visible defect is closed.

### WS-08 · Discount re-entry no longer reuses computed discount amount — `correctness-bug` · high · M · Done
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** `WorkshopOrderDetailView` now resets discount value from a pure `discountDraftFromOrder` helper instead of copying `discount_tiyin`. Existing discount reason is preserved as context, but changing the discount requires an explicit kind/value re-entry, so a percent discount cannot silently become a fixed computed amount.
**Fix:** Done for corruption prevention. Full edit/remove ergonomics remain WS-39.

### WS-09 · Version conflict refetch + friendly user copy — `correctness-bug` · high · M · Done
**Files:** `stores/orders.ts`, `views/WorkshopOrderDetailView.vue`
**Why:** The store still refetches on `order_version_conflict`, and `WorkshopOrderDetailView` now maps action errors through `workshopErrorMessage`, rendering a friendly "order changed, data refreshed, retry" message with trace_id when present.
**Fix:** Done. Broader cancel/revert 409 end-to-end coverage remains WS-112.

### WS-10 · Finance dual-route tab doesn't react to income↔expenses nav — `correctness-bug` · high · S
**Files:** `views/WorkshopFinanceExpensesView.vue`
**Why:** `:25` initializes `activeTab` once from `route.path` with **no watch**. One component serves both `/finance/income` and `/finance/expenses` (Vue Router reuses the instance), so navigating expenses→income doesn't re-run setup — the user lands on the income URL but sees the expenses tab. High-stakes for money work.
**Fix:** `watch(() => route.path, p => activeTab = p.endsWith('/income') ? 'income' : 'expense', { immediate: true })`, or a computed off `route.path`.

### WS-11 · Workshop order list unbounded + server N+1 — `performance` · high · L · Done
**Files:** `backend/app/modules/sales/service.py`, `stores/orders.ts`, `views/WorkshopOrdersView.vue`
**Why:** `orders.ts:258-274` `loadWorkshopOrders()` GETs `/workshop/orders` with no limit/offset, stores the whole array. Backend `list_workshop_orders` (`sales/service.py:329-342`) has **no `.limit()`** and does `[await _order_response(db, order, include_detail=False) for order in rows]` — one awaited DB call per order. `status='active'` caps it, but completed/cancelled/all return full history, downloaded, N+1-built, DOM-rendered at once. The app's most-used board.
**Fix:** Done. `/workshop/orders` now accepts clamped `limit/offset`; the workshop orders store appends pages and the view renders a load-more control. Client/workshop list endpoints use a page-level batch summary builder for clients, branches, workshops, items, cutting results, and stock-warning inputs instead of calling the full detail response builder per order.

### WS-12 · Stock transactions unbounded (client + server) — `performance` · high · M · Done
**Files:** `backend/app/modules/inventory/service.py`, `stores/workshop.ts`, `views/WorkshopInventoryView.vue`, `WorkshopBranchDetailView.vue`
**Why:** `workshop.ts:376-383` `loadStockTransactions()` fetches with only an optional `material_id` filter — no date range, no limit. Backend `list_transactions` (`inventory/service.py:133-153`) `order_by(created_at.desc())` with **no `.limit()`** returns every transaction ever. Both views render all (`WorkshopInventoryView:231`). After months a single branch's tx tab loads the entire ledger.
**Fix:** Done. The endpoint/query support `date_from`, `date_to`, `limit`, and `offset`; the store tracks append pagination and `stockTransactionsHasMore`. Standalone inventory defaults the transaction tab to the last 30 days and both inventory views expose load-more instead of rendering the full branch ledger.

### WS-13 · 3 screens fully English — `i18n-copy` · high · M · Done
**Files:** `WorkshopCuttingPlansView.vue`, `WorkshopCuttingPlanDetailView.vue`, `WorkshopFinanceProductionView.vue`, `apps/workshop/routes.ts`
**Why:** CuttingPlansView is 100% English (h1 "Cutting plans" `:19`), PlanDetailView English throughout (h1 "Read-only cutting plan" `:59`, tiles Waste/Panels/Edge/Cut length), ProductionView English (h1 "Worker production" `:50`, headers Worker/Panels cut/Cuts). Meanwhile `routes.ts` gives Uzbek `meta.title`s — so the browser tab contradicts the page heading. Every sibling view is Uzbek.
**Fix:** Done. Cutting plans, cutting plan detail, and finance production report copy now use the Uzbek workshop register for headings, states, filters, buttons, and table labels while keeping domain terms such as Panel/Krom where appropriate.

### WS-14 · Order/queue/finance/user action errors use localized copy — `i18n-copy` · high · M · Done
**Files:** `WorkshopOrderDetailView.vue`, `WorkshopCuttingQueueView.vue`, `WorkshopFinanceExpensesView.vue`, `WorkshopUserDetailView.vue`, `stores/orders.ts`
**Why:** `workshopUi.ts` now owns a shared `workshopErrorMessage` mapper. Order detail validation literals are Uzbek, and order detail, cutting queue, banding queue, finance expenses, and user detail actions render mapped recovery copy instead of raw action codes.
**Fix:** Done for the files named here. Other workshop raw-code pockets are tracked under their own items (for example WS-43/44/45/64).

### WS-15 · Topbar branch dropdown is a dead control — `ux-flow` · high · L · Done
**Files:** `components/AppShell.vue`, `WorkshopOrdersView.vue`, `WorkshopInventoryView.vue`, `WorkshopDashboardView.vue`
**Why:** AppShell renders a prominent branch ProjectDropdown bound to `selectedContext` (`:331-335`), persisted per-session. Its **only** consumer is `workshopNavItems(...selectedBranchId)` to choose which nav links show. Every data view keeps its own independent `branchId` ref (Orders `branchId='all'` `:22`, Inventory `selectedBranchId`, Finance `branchId='all'`); none read `selectedContext`. Dashboard low-stock is hardwired to `branchIds[0]`. Changing the topbar branch reshapes the menu but never refocuses the data — two competing notions of "current branch".
**Fix:** Done. `selectedBranchContext` now lives in the workshop store and syncs bidirectionally with AppShell. Orders, Inventory, Catalog, Finance, Finance Production, and Dashboard apply the shared branch when accessible and refresh their branch-scoped data on topbar changes; specific page filters still allow a local "all" override.

### WS-16 · ProjectDropdown popover double-counts scroll, no edge clamp — `responsive` · high · M · Done
**Files:** `components/ProjectDropdown.vue`
**Why:** `updatePopoverPosition` (`:37-45`) sets the teleported listbox to `position:fixed` but computes `top: rect.bottom + window.scrollY + 6`, `left: rect.left + window.scrollX` — with fixed (viewport-relative) positioning, adding scrollY/scrollX **double-counts**, so the panel jumps away from its trigger once the page scrolls. No clamp against `innerWidth`, so a 260px-min panel overflows the right edge on a 320-360px phone; recomputes only on 'resize' (`:113`), never 'scroll'. NotificationsMenu uses the correct `absolute right-0 w-[min(360px,calc(100vw-2rem))]`.
**Fix:** Done. The fixed popover now uses viewport coordinates, clamps width/left/max-height to the viewport, flips upward when needed, updates on scroll/resize/visualViewport resize, and has a regression test proving scroll offsets are not double-counted.

### WS-17 · Catalog table: no loading/error state (silent empty) — `states-errors` · high · S · Done
**Files:** `views/WorkshopCatalogView.vue`, `stores/workshop.ts`
**Why:** `refreshCatalog` calls `workshop.loadBranchMaterials`, but the store's `loadBranchMaterials` (`:313-322`) has **no try/catch** and never touches `setupLoading/setupError/setupTraceId`. The template's skeleton/error blocks (`:143-154`) bind to those refs, which only loadSettings/loadManagedBranches set — so a failed catalog load throws an unhandled rejection and renders the "Bu filialga material qo'shilmagan" empty row, indistinguishable from a genuinely empty branch.
**Fix:** Done. `loadBranchMaterials` owns `catalogLoading/catalogError/catalogTraceId`, preserves the previous rows on failure, and the catalog view binds its skeleton/error branches to those refs. Store tests pin failed catalog loads with trace IDs.

### WS-18 · Settings save: no error/busy/success — `states-errors` · high · S
**Files:** `views/WorkshopSettingsView.vue`, `stores/workshop.ts`
**Why:** `save()` (`:26-32`) calls `updateSettings()` with no try/catch, and `updateSettings` (`workshop.ts:224-227`) also has none. No `saving` ref, no error shown, no `:disabled` busy. A failed PATCH yields an unhandled rejection and the owner sees nothing change, assuming it saved.
**Fix:** Add saving/saveError refs, wrap `save()` in try/catch capturing `apiTraceId`, render error/success, bind `:disabled=saving` — mirror `WorkshopBranchesView.createBranch`.

### WS-19 · Dashboard swallows all load errors — `states-errors` · high · M · Done
**Files:** `views/WorkshopDashboardView.vue`
**Why:** `loadDashboard()` (`:49-58`) chains `.catch(() => undefined)` onto every call. The template has only a no-grant empty state + per-section empty/loading — **no error branch**. If orders or finance fails, KPIs render 0 (`?? 0`) and a "Buyurtma yo'q" empty row — indistinguishable from a genuinely empty workshop; "Yangilash" re-runs the same swallowed load.
**Fix:** Done. Dashboard loads record the first failed section as `dashboardError/traceId`, render a retryable top banner, show a low-stock section error when inventory fails, and keep partial data visible instead of pretending failures are empty states.

### WS-20 · Dashboard sales chart is hardcoded fabricated data — `completeness-stub` · high · M · Done
**Files:** `views/WorkshopDashboardView.vue`
**Why:** `:46` `const chartValues = [42,56,48,70,60,84,52,64,80,96,74,102,86,128]` is rendered as the 14-bar chart "Savdo · so'nggi 14 kun" (`:164-177`) — bars never reflect real data even though real income loads into the card sub-line. The 7K/14K/30K period buttons (`:151-159`) have **no @click** — decorative. Actively misinforms the primary decision-maker; identical for every workshop, every day.
**Fix:** Done. Finance summary now returns `daily_income`; dashboard requests the selected 7/14/30-day range, renders bars from that real series, shows real totals/empty state, and period buttons refetch the summary. Backend finance tests pin the daily series contract.

---

## P2 — important

### WS-21 · Order board/table lost per-card status-action kebab — `design-parity` · high · L · Done
**Files:** `views/WorkshopOrdersView.vue`, `prototype-full/workshop/orders.html`
**Why:** The prototype renders a `.menu-wrap` kebab on every board card (`:261-264`) and table row (`:287-292`) with per-state transitions (Tasdiqlash, Kesuvchi tayinlash, Kesish/Krom tugadi, Mijoz olib ketdi, revert/cancel). In Vue the board card (`:164-180`) is a bare RouterLink and the table's last cell is just "Tafsilotlar"; grep for menu-wrap returns nothing. The most-frequent workflow (advancing an order) became multi-step navigation.
**Fix:** Done. Board cards and table rows now expose a compact action menu. A shared pure helper owns status/permission/assigned-worker action rules, list actions use the real order store transitions, and confirm/reason dialogs protect lifecycle mutations.

### WS-22 · No toast system — every successful mutation is silent — `design-parity` · high · L · Done
**Files:** `WorkshopOrderDetailView.vue`, `WorkshopCuttingQueueView.vue`, `WorkshopNotificationsView.vue`
**Why:** Grep for toast/snackbar across `web/src` returns zero. The prototype fires `toast(...)` on essentially every mutation; in Vue successful actions are silent (only failures surface `actionError`). On a shop floor the absence of confirmation causes double-clicks and duplicate actions. (Shared with client CB-14 — build one primitive for both SPAs.)
**Fix:** Done. The shared toast primitive already exists in `AppShell`; successful workshop order, queue, branch/catalog, inventory, finance, settings, notification, and user-admin mutations now emit confirmation toasts while existing inline failure states remain.

### WS-23 · 5 tab UIs lack tab/tablist/tabpanel ARIA — `a11y` · high · M · Done
**Files:** OrderDetail, BranchDetail, UserDetail, FinanceExpenses, Inventory views
**Why:** Every workshop tab strip is `<button class="tab" :class="{on}">` with no role/aria (OrderDetail `:325-350`, Branch `:582-593`, User `:214-239`, Finance `:286-303`, Inventory `:102-127`); panels (`v-if=activeTab`) have no `role=tabpanel`/`aria-labelledby`. Grep confirms zero tab ARIA in any workshop view.
**Fix:** Done. Added shared `AppTabs` with `role=tablist`, `role=tab`, `aria-selected`, generated `aria-controls`, roving `tabindex`, and Arrow/Home/End navigation; converted the five workshop tab screens and linked their panels with `role=tabpanel`/`aria-labelledby`.

### WS-24 · Permission-matrix checkboxes have no accessible name — `a11y` · med · S · Done
**Files:** `WorkshopUserDetailView.vue`, `WorkshopUsersView.vue`
**Why:** The grants matrix renders a bare `<input type=checkbox>` per permission×branch cell with no label/aria (UserDetail `:314-322`, Users `:234-241`). The permission name is a `<td>` row header, the branch a column `<th>`, with no id/headers association — so every checkbox is announced as just "checkbox, checked" across 7 perms × N branches, on the core access-management flow.
**Fix:** Done. Both permission matrices now provide an `aria-label` per checkbox in the form `<permission label> — <branch name>`.

### WS-25 · Mobile drawer: no focus trap/Escape/scroll-lock — `a11y` · med · M · Done
**Files:** `components/AppShell.vue`, `web/src/assets/main.css`
**Why:** The workshop drawer (`:281-322`) is `role=dialog aria-modal=true` but nothing focuses into it, focus isn't trapped, no Escape handler, no focus restore (closeMobileNav just flips a boolean) — unlike ConfirmDialog. Opening it never toggles `body.modal-open`, so the long Orders/ledger page scrolls under the scrim. Same gaps in the admin drawer.
**Fix:** Done. Workshop/admin drawers now use the shared body scroll lock, focus the first drawer control on open, trap Tab inside the drawer, close on Escape, and restore focus to the mobile-menu trigger on close.

### WS-26 · Cutting-plan SVG rects focusable but unlabeled/no focus — `a11y` · med · M · Done
**Files:** `components/CuttingPanelSvg.vue`, `web/src/assets/main.css`
**Why:** `:52-66` renders each placement as `<rect role=button tabindex=0 @keydown.enter/.space>` so every placement is in the tab order, but no `aria-label` (part name is a sibling text), no SVG focus style, and the parent `svg` has `role=img` conflicting with interactive children. A many-part plan floods the tab sequence with unlabeled stops. OrderDetail/PlanDetail already render a parallel accessible button list. (Same family as client CB-07.)
**Fix:** Done. SVG placement groups are now `aria-hidden`, non-focusable, and mouse-selectable only. Keyboard users use the existing placement button list in each consuming view; a component regression test pins this behavior.

### WS-27 · complete cutting/banding require a credited worker — `correctness-bug` · med · S · Done
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** Order detail now computes `canSubmitCuttingCompletion` / `canSubmitBandingCompletion` and blocks submission unless either an assigned worker or an explicit "Kim bajardi" worker exists. Owner/on-behalf completion keeps the worker selector visible and disabled when no options exist; the submit path also validates before calling the store.
**Fix:** Done. Queue on-behalf crediting remains WS-40.

### WS-28 · Order mutations patch the matching role list in place — `correctness-bug` · med · S · Done
**Files:** `stores/orders.ts`
**Why:** `orders.mutate` now infers client/workshop scope from the API path. Client mutations only patch `clientOrders`; workshop mutations only patch `workshopOrders`. Existing rows are replaced in place so operator scan position is preserved; absent rows are prepended.
**Fix:** Done and pinned by WS-101.

### WS-29 · Stock-in/adjustment post unvalidated quantities — `correctness-bug` · med · S · Done
**Files:** `shared/formatters.ts`, `views/WorkshopBranchDetailView.vue`
**Why:** Branch-detail inventory forms parsed display quantities but did not reject `NaN`, negative stock-in quantities, or zero adjustments before posting.
**Fix:** Done. Branch-material price/min-stock, stock-in, and adjustment forms validate finite/non-negative or positive/non-zero values locally before calling the store. `formatters.ts` also accepts both `m` and backend `metre` display-unit aliases so edge metres round-trip to millimetres correctly.

### WS-30 · Cut/band queues refetch full active list, filter client-side — `performance` · med · M · Done
**Files:** `WorkshopCuttingQueueView.vue`, `WorkshopBandingQueueView.vue`, `stores/orders.ts`
**Why:** CuttingQueue `refresh()` calls `loadWorkshopOrders({status:'active'})` (`:27-29`) and `complete()` calls it again after each cuttingDone (`:38`); `queueOrders` then client-filters to `auth.me.principal_id` (`:16-23`). Banding identical. A cutter/edger on a low-end device pulls the entire active set (+ WS-11 N+1) every queue-open and job-finish, for their handful of rows.
**Fix:** Done. The backend filters by `assigned_cutter_user_id` / `assigned_edger_user_id`; queue screens request the current worker's assigned rows and rely on the mutation response to patch the list after completion instead of refetching the whole active set.

### WS-31 · loadBranchContext refetched on nearly every screen mount — `performance` · med · M · Done
**Files:** `components/AppShell.vue`, `stores/workshop.ts`, multiple views
**Why:** AppShell already calls `loadBranchContext()` when `canLoadWorkshopContext` flips true (`:185-191`), yet Dashboard/Orders/Inventory/Catalog/Users/Finance/FinanceExpenses each re-call it on mount. `loadBranchContext` (`workshop.ts:194-208`) always hits `/workshop/branch-context` with no freshness guard — re-fetched on every in-app navigation.
**Fix:** Done. The workshop store caches branch context after a successful load, exposes a force path for refresh, clears the flag on reset/failure, and branch status changes force-reload the context so navigation/data remain fresh after invalidating mutations.

### WS-32 · Inventory eagerly fetches stock+all-tx+suppliers on mount — `performance` · med · S · Done
**Files:** `stores/workshop.ts`, `WorkshopInventoryView.vue`, `WorkshopBranchDetailView.vue`
**Why:** `loadInventory()` (`:392-404`) does `Promise.all([loadStock, loadStockTransactions, loadSuppliers])`. Inventory defaults to the Stock tab but calls loadInventory on mount and every branch switch — so the unbounded transactions fetch (WS-12) + suppliers happen up-front even though Tx/Suppliers tabs are pure client renders.
**Fix:** Done. Standalone inventory now loads only stock on mount/branch switch, loads transactions or suppliers when those tabs activate, and loads supplier options on demand when the stock-in supplier picker is used. `loadInventory()` remains available for genuine all-three branch-detail cases, now backed by bounded transaction loading.

### WS-33 · Cutting-plans & production screens unreachable (no nav) — `completeness-stub` · med · S · Done
**Files:** `app/workshopNav.ts`, `WorkshopCuttingPlansView.vue`, `WorkshopFinanceProductionView.vue`, `WorkshopFinanceView.vue`
**Why:** `workshopNav.ts` has no 'cutting-plans' and no 'finance/production' entries. The routes + views exist and are complete (plans browser, per-worker salary report) but are reachable only by URL. The FinanceView "Xodimlar mehnati" card renders a preview with no "see full report" link to the dedicated screen.
**Fix:** Done. "Kesim rejalar" is exposed for owner/production users, "Xodimlar mehnati" is exposed for owner/finance users, and the finance production card links to the full report route.

### WS-34 · Orphaned WorkshopFinanceIncomeView (dead code) — `completeness-stub` · med · S · Done
**Files:** `WorkshopFinanceIncomeView.vue`, `apps/workshop/routes.ts`, `WorkshopFinanceExpensesView.vue`
**Why:** Grep for `WorkshopFinanceIncomeView` across `web/src` returns **zero** references — no route imports it; `/finance/income` lazy-loads the Expenses view instead. The orphan is a complete 11KB income screen, fully English ("Income", "Record income", raw enums), **no permission gating**, duplicating the live Uzbek "Tushumlar" tab. It will drift, inflates the bundle as a never-loaded chunk, and is a foot-gun if ever routed (ungated money writes).
**Fix:** Done. Deleted the orphan; live income entry remains the gated Uzbek tab in `WorkshopFinanceExpensesView.vue`.

### WS-35 · Settings "Logo" file input is a dead control — `completeness-stub` · med · M · Done
**Files:** `WorkshopSettingsView.vue`, `stores/workshop.ts`
**Why:** `:79-82` renders `<input type=file>` labeled "Logo" with no v-model/@change; `save()` (`:26-32`) sends only `{name, phone, address}`. The header advertises "nom, logo, telefon, manzil". The backend exposes `logo_file_id` (`workshop.ts:39`) — the slot exists but the upload path is unimplemented; the owner picks a file, clicks Saqlash, silent no-op.
**Fix:** Done. Settings now uploads via the files store, previews the authenticated image, allows removing the logo, and saves `logo_file_id` through the existing settings API.

### WS-36 · Topbar global search + ⌘K non-functional — `completeness-stub` · med · M · Done
**Files:** `components/AppShell.vue`
**Why:** `:337-345` renders the topbar search input (placeholder "Buyurtma, mijoz, xodim yoki material…") with a ⌘K badge, but no v-model/@input/@keydown and no global-search handler anywhere. The prototype wired it; the Vue version kept the chrome, dropped the behavior — a prominent broken affordance on every screen.
**Fix:** Done. Added an isolated `workshopSearch` store that queries only the allowed sources for the current branch (orders, owner-only users, catalog, stock) without mutating page-local stores. AppShell now supports ⌘K/Ctrl+K focus, result groups, partial-error copy/trace, outside-click/Escape close, and detail/list navigation. Orders, catalog, inventory, and users pages honor `?search=` so topbar shortcut links land with visible filtering.

### WS-37 · "Mijoz olib ketdi" terminal action has no confirmation — `states-errors` · high · S
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** `:725-733` renders the ready→completed button calling `markCollected()` directly (`:174-178`). Per `orders.md:76` completed is terminal, stamps picked_up_at, no revert. Only revert/cancel open a ConfirmDialog (`:811-830`); approve/assign/cutting-done/banding-done **and** mark-collected all execute on a single click. A misclick on a busy board permanently closes the order with no in-app undo.
**Fix:** Gate `markCollected` behind a ConfirmDialog summarizing the order + finality. Consider a lightweight confirm for cutting-done/banding-done too (they decrement stock, reversible only via revert).

### WS-38 · Fresh production staff land on an empty app — `ux-flow` · high · M · Done
**Files:** `app/workshopNav.ts`, `WorkshopCuttingQueueView.vue`, `WorkshopDashboardView.vue`
**Why:** `workshopNav.ts:53` gives cutting/banding nav to process_production but the orders link requires view_dashboard/manage_orders (`:50`). The cutting queue lists only orders assigned to `me` (`:16-23`), and assignment requires manage_orders. So before an owner assigns them, a cutter sees an empty queue (`:81-84`) and zero other actionable screen — logs in to an empty-feeling app with no way to discover waiting work.
**Fix:** Done. Docs keep cutter/edger workspaces assigned-only, so the fix avoids self-claiming. Dashboard now treats `process_production` as a real landing mode, loads active orders for assigned-work counts, shows cutting/banding queue shortcuts, and hides order-management summaries from production-only staff. Cutting/banding empty states now explain that a manager must assign the job before it appears.

### WS-39 · Discount can only be added, never edited/removed — `ux-flow` · med · M · Done
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** The discount card renders only while status is new/confirmed (`:766`) and only offers "Chegirma qo'shish"→applyDiscount (`:203-223`). Once a discount exists it shows as a read-only price-breakdown row (`:420-426`) with no control to change/clear, and the form disappears after confirmed. An owner who fat-fingers a value has no correction except cancel+re-order (changes the order number). Closely tied to WS-08.
**Fix:** Done. The existing discount endpoint remains the edit path while the form avoids unsafe computed-amount prefills. Order detail now shows an explicit remove action for discounted new/confirmed orders; the zero-discount backend path clears `discount_reason` and `discount_applied_by_user_id` while preserving audit details. API and helper tests cover the removal payload.

### WS-40 · Queue "done" can't credit who did the work — `ux-flow` · med · M · Done
**Files:** `WorkshopCuttingQueueView.vue`, `WorkshopBandingQueueView.vue`
**Why:** The queue cards' inline complete buttons hard-wire credit to the assignee: Cutting `:34-38` sends `assigned_cutter_user_id`; Banding `:31-35` `assigned_edger_user_id`. The order-detail flow exposes a "Kim bajardi" select so an owner can credit a different worker, and `orders.md:99-105` says the chosen user gets production-report credit (the salary input). When an owner clears the queue on behalf of staff, credit is wrong.
**Fix:** Done. Owner queue cards now preload worker options per branch and show a `Kim bajardi` selector for cutting/banding completion, defaulting to the assignee. Staff completion still credits the assigned worker. A shared helper pins selected-vs-assigned credit resolution.

### WS-41 · Income entry can't show order's outstanding balance — `ux-flow` · med · M · Done
**Files:** `WorkshopFinanceExpensesView.vue`, `WorkshopOrderDetailView.vue`
**Why:** The income form listed orders by number/total only and left payment amount fully manual, forcing accountants to cross-check order detail.
**Fix:** Done. Selecting an order fetches workshop order detail, shows total/recorded/balance with load/error state, and prefills the payment amount to the outstanding balance. A guarded request id prevents stale order-balance responses from overwriting the current selection.

### WS-42 · PDF download store tracks failure/busy, but UI does not surface it — `states-errors` · med · M · Done
**Files:** `stores/orders.ts`, `stores/cutting.ts`, OrderDetail/CuttingQueue/BandingQueue views
**Why:** The stores already had `downloadingId`, `downloadError`, and `downloadTraceId`, but the workshop views still called downloads with no visible busy/error feedback.
**Fix:** Done. Order detail, cutting queue, and banding queue now disable/show busy on the matching PDF button and render `downloadError` with `trace_id`.

### WS-43 · Branch settings/pricing save error never rendered (1st form) — `states-errors` · med · S · Done
**Files:** `views/WorkshopBranchDetailView.vue`
**Why:** `saveBranchSettings` did the pricing PUT and set `settingsError='branch_settings_save_failed'` on failure, but the first form rendered no error or success state.
**Fix:** Done. The branch-info/pricing form now shows failed-save feedback with `trace_id` and a success confirmation; the status form has its own matching feedback.

### WS-44 · Receipt upload failures show feedback — `states-errors` · med · S · Done
**Files:** `views/WorkshopBranchDetailView.vue`, `stores/files.ts`
**Why:** A failed receipt upload must not look attached.
**Fix:** Done. Branch-detail stock-in receipt upload is wrapped in try/catch, disables the input while uploading, accepts only allowed receipt types, and shows an inline failure message. Finance receipt uploads also surface through the page action error.

### WS-45 · User/finance action errors omit trace_id — `states-errors` · med · S · Done
**Files:** `WorkshopUserDetailView.vue`, `WorkshopFinanceExpensesView.vue`, `WorkshopUsersView.vue`, `stores/finance.ts`
**Why:** User and finance mutations rendered localized recovery copy but did not expose the server `trace_id`, making support/debugging hard for money and access-control failures.
**Fix:** Done. `finance` and `workshop` stores capture mutation `actionError/actionTraceId`; finance expenses, user detail, and user creation render the trace. Focused store tests pin both capture paths.

---

## P3 — nice-to-have

### WS-46 · User-detail misreports context-load failure as "not found" — `states-errors` · low · S
**Files:** `WorkshopUserDetailView.vue`, `stores/workshop.ts`
**Why:** `load()` (`:50-57`) awaits `loadBranchContext()` then `loadUser()`. `loadBranchContext` (`:194-208`) **throws** on failure, so if context fails loadUser never runs, `workshop.error` stays null, `selectedUser` stays null, and the template falls to the "Xodim topilmadi" empty state. A transient context failure makes an existing staffer appear deleted.
**Fix:** Wrap `load()` in try/catch (or `loadBranchContext().catch(()=>undefined)` like other views) and set a real error/traceId.

### WS-47 · Cutting-plan detail blank when plan has no result — `states-errors` · med · S · Done
**Files:** `WorkshopCuttingPlanDetailView.vue`, `stores/cutting.ts`
**Why:** Template branches are loading (`:74`), permission_denied (`:77`), error (`:81`), then `v-else-if=plan && result` (`:85`) with **no final v-else**. `loadWorkshopPlan` only sets error on a thrown ApiError; if the API returns 200 with a null result, or leaves `currentWorkshopPlan` null without error, the page shows only the header — no empty/not-found state.
**Fix:** Done. Added a final empty/not-found branch with a short explanation and a link back to the cutting-plans list so missing/null plan results no longer leave a blank detail page.

### WS-48 · Notifications can't deep-link finance/stock; inventory chip broken — `ux-flow` · low · S · Done
**Files:** `WorkshopNotificationsView.vue`
**Why:** `destination()` (`:42-46`) returns a route only for 'order'/'branch'; finance/stock notifications return null, so `openItem` marks them read but navigates nowhere. The 'inventory' filter chip (`:23-29`) matches `event_code.includes('inventory')` but stock codes use 'stock' — selecting "Ombor" returns an empty list despite stock alerts existing.
**Fix:** Done. Workshop notification routing now maps stock/inventory events to `/workshop/inventory` and finance/income/expense events to `/workshop/finance/expenses`, with ID-backed order/branch routes preserved. The inventory filter matches both `inventory` and `stock` event families. The full page now mirrors the bell behavior: no destination means warn and keep the row unread.

### WS-49 · Dashboard low-stock scoped to branchIds[0]; recent = active-only — `correctness-bug` · med · M · Done
**Files:** `WorkshopDashboardView.vue`
**Why:** `loadDashboard` (`:49-58`) loads stock only for `branchIds[0]` (`:55-57`) regardless of branch count, so "Pastdagi zaxiralar" under-reports for multi-branch owners while KPIs reflect all branches. `recentOrders` (`:43`) slices `workshopOrders` loaded with `status:'active'` (`:52`), so a just-completed order never appears in "recent".
**Fix:** Done. Workshop store now has a low-stock summary loader that aggregates all requested branches without replacing inventory-page `stockItems`; dashboard uses all accessible inventory branches or the selected topbar branch. Orders store now keeps `recentWorkshopOrders` separate from the active board list, and dashboard loads recent orders with `status=all`.

### WS-50 · Material swatches all render the same default gradient — `design-parity` · med · M · Done
**Files:** `WorkshopInventoryView.vue`, `WorkshopCatalogView.vue`, `web/src/assets/main.css`
**Why:** Inventory `:174` and Catalog `:174` render `<span class="sw">` with no `sw-N` modifier, so every material shows the single default `.sw` gradient (`main.css:2485-2492`). The prototype gives each material its own swatch (`inventory.html:203`) and main.css ports `sw-1..sw-6`, but nothing applies them because the material model carries no swatch/color field. The visual scanning cue is lost.
**Fix:** Done. Added a frontend material-swatch mapper that derives readable prototype-style swatch classes from material color, decor code, and name, with stable non-default fallbacks. Catalog rows, inventory rows, and dashboard low-stock rows now apply those classes, and focused tests pin the mapping.

### WS-51 · Order board lost assigned-worker chips — `design-parity` · med · S · Done
**Files:** `WorkshopOrdersView.vue`, `prototype-full/workshop/orders.html`
**Why:** The prototype renders worker chips via `workerChip()` (`orders.html:224-228`): `.pill p-cut` scissors+cutter initials, `.pill p-eb` layers+edger initials. Vue replaces this with plain text `assignedText()` (`:56-63`) on board cards (`:178`) and the table "Mas'ul" cell (`:214-216`). A manager can no longer see at a glance who's assigned.
**Fix:** Done. `WorkshopOrdersView` now loads branch worker options for visible orders and renders prototype-style cutter/edger pills with scissors/layers icons and initials on board cards and in the `Mas'ul` table column. The pure chip helper is covered by focused tests and falls back to a short worker id when the worker record is unavailable.

### WS-52 · Dashboard chart dropped SVG/gridlines/tooltips/legend — `design-parity` · med · M · Done
**Files:** `WorkshopDashboardView.vue`, `prototype-full/workshop/dashboard.html`
**Why:** The prototype (`dashboard.html:201-223`) renders an SVG chart with gridlines, baseline, dated x-ticks, per-bar `<title>` tooltips, and a Bugun/Eng yuqori/Boshqalar legend. Vue (`:163-183`) replaces all of it with plain spans — no SVG/gridlines/tooltips/legend; only date labels survive. Depends on WS-20 (real data first).
**Fix:** Done. The dashboard sales card now renders an SVG chart from real `daily_income` rows, with gridlines, baseline, dated x-axis labels, per-bar `<title>` tooltips, and a Bugun/Eng yuqori/Boshqalar legend using the Vue token names.

### WS-53 · Production report dropped period column + "Maosh yozish" — `design-parity` · low · S · Done
**Files:** `WorkshopFinanceView.vue`, `prototype-full/workshop/finance.html`
**Why:** The prototype "Xodimlar mehnati" table (`finance.html:96-99,184-193`) has Xodim/Davr/Panel/Krom(m) + a trailing "Maosh yozish" action jumping to expenses prefilled. Vue's production table (`:303-318`) has Xodim/Panel/Kesim/Krom — dropped the Davr column and the per-row payroll shortcut, though the card copy still tells the accountant to record salary as an expense.
**Fix:** Done. The finance report's production summary card now includes the selected Davr for each row and a `Maosh yozish` action that deep-links to the salary expense preset for that worker, matching the full production report route contract.

### WS-54 · Cutting-plan SVG uses off-brand blue, not teal — `design-parity` · low · S · Done
**Files:** `components/CuttingPanelSvg.vue`, `prototype-full/workshop/order-detail.html`
**Why:** `CuttingPanelSvg.vue` hardcodes a slate/blue palette: panel stroke `#334155` (`:49`), placement fill `#dbeafe`/active `#c8e8e3` stroke `#2563eb` (`:58-59`), label `#0f172a` (`:67`). The prototype's sheet uses the teal brand family (`--color-accent`). None of the brand tokens are used, so this signature screen reads in a generic blue. (Same component as client CB; coordinate.)
**Fix:** Done. Cutting panel SVGs now use design tokens for sheet fill, accent stroke, active/inactive placement fill, and text color instead of hard-coded slate/blue hex values.

### WS-55 · Mobile chrome uses ☰/× glyphs instead of SVG icons — `design-parity` · low · S · Done
**Files:** `components/AppShell.vue`
**Why:** The mobile menu trigger is a ☰ character (`:327`) and the drawer close is × (`:297`), whereas the prototype and the rest of the shell emit real SVG (desktop/mobile nav via `iconPath` at `:265/315`). On the small-screen floor surface they render as unstyled typographic chars.
**Fix:** Done. The workshop shell icon registry now includes menu/close paths, the mobile trigger renders an inline SVG plus Uzbek `Menyu` text, and the drawer close control uses the same SVG icon path.

### WS-56 · English fallback strings — `i18n-copy` · med · S · Done
**Files:** `stores/cutting.ts`, `WorkshopFinanceProductionView.vue`, `WorkshopCuttingPlanDetailView.vue`
**Why:** `cutting.ts` `materialLabel()` returns "No material" (`:142`) and builds "… mm edge" (`:147`); ProductionView `edgeLengths()` returns "No banding metres" (`:28`) shown in a table cell; PlanDetailView `panelTitle()` falls back to "Panel" (`:39`). English fragments render in empty/missing states on Uzbek pages. Overlaps WS-13.
**Fix:** Done. The material and production fallbacks already use `Material yo'q`, `mm krom`, and `Krom metri yo'q`; the remaining cutting-plan panel fallback now reads `Panel materiali`. Domain terms such as Panel/Krom remain English where the product vocabulary uses them.

### WS-57 · Inventory/Catalog/Users client-filter full list redundantly — `performance` · low · M · Done
**Files:** `WorkshopInventoryView.vue`, `WorkshopCatalogView.vue`, `WorkshopUsersView.vue`, `stores/workshop.ts`
**Why:** Inventory `filteredStock` (`:43-50`) re-filters client-side though `loadStock` accepts server `search/low_stock` (`workshop.ts:363-374`) the view never passes; Catalog `filteredRows` (`:59-65`) filters client-side **and** passes search to `loadBranchMaterials` on @input (`:135-136`) — double filtering; Users `filteredUsers` (`:62-81`) is client-only with no server filter. Each keystroke re-scans the whole list.
**Fix:** Done. Inventory stock search/low-stock filters are debounced into the stock endpoint, catalog trusts its already-filtered endpoint without a second client pass, and `/workshop/users` now accepts search/status/branch filters consumed by the users view. Backend tests pin user filters and last-login payload.

### WS-58 · Finance fires 3 sequential requests; expenses double-fetch — `performance` · low · S · Done
**Files:** `WorkshopFinanceView.vue`, `WorkshopFinanceExpensesView.vue`, `stores/finance.ts`
**Why:** FinanceView `refresh` (`:105-115`) awaits loadSummary THEN loadIncome THEN loadProduction sequentially (independent, separate store fields), on mount and every period/branch/refresh. FinanceExpenses `refresh` awaits loadExpenses then loadIncome regardless of activeTab — double-fetch on every Qo'llash. The store also advertises min/max amount params no UI surfaces.
**Fix:** Done. `WorkshopFinanceView.refresh()` parallelizes summary, recorded income, and production loading. `WorkshopFinanceExpensesView.refresh()` now loads only the active ledger tab, and tab/route changes trigger a refresh for the newly visible ledger instead of fetching both ledgers every time.

### WS-59 · Inline forms far from trigger, no focus move — `a11y` · med · M · Done
**Files:** `WorkshopFinanceExpensesView.vue`, `WorkshopOrderDetailView.vue`
**Why:** In finance, "Bekor qilish" on a row sets `voidTarget` rendering a void form at the page bottom (`:544-559`); focus stays on the scrolled-away trigger with no handoff. The Tushum/Xarajat buttons toggle a create form (`:305/346`) with no focus move; in order detail the discount/assign panels render in the aside (`:766-786,667-689`) without focusing the first field. Keyboard/SR staff must Tab through the whole table.
**Fix:** Done. Finance create/edit/void openers now scroll and focus the opened panel's first usable control and restore focus on close; order detail focuses the action panel after approval reveals assignment and focuses the relevant aside panel on validation errors.

### WS-60 ⚠ · Muted text fails AA; low-stock/destructive color-only — `a11y` · low · S · Done
**Files:** `web/src/assets/main.css`, `WorkshopInventoryView.vue`, `WorkshopBranchDetailView.vue`
**Why (verify):** `--color-ink-muted (#748196)` on `#f4f6f8`/white ≈ 3.4:1 — below 4.5:1 AA for the 11-12px text it's applied to. Low-stock cell recolors the number via warn-text with no non-color cue (`Inventory:182-184`); activate/deactivate toggles swap only border/background color (`BranchDetail:746-756,1069-1080`). **⚠ contrast not pixel-verified.** (Same token as client CB-34.)
**Fix:** Done. The muted token had already been darkened from the audited value; inventory/dashboard low-stock quantities now include a visible `Past zaxira` cue, and branch-detail stock/status controls already include text labels rather than color-only state.

### WS-61 · Dashboard chart hidden from AT; range toggles no aria-pressed — `a11y` · low · S · Done
**Files:** `WorkshopDashboardView.vue`
**Why:** `:163-184` renders the 14-day chart as `aria-hidden` spans (whole bar group hidden from AT, only three static dates labeled); the 7K/14K/30K range buttons (`:151-159`) have no `aria-pressed`. SR users get no info from the headline chart. Coupled with WS-20/WS-52.
**Fix:** Done. The chart exposes a concise accessible summary naming period total, today, and peak day, and the 7K/14K/30K controls now publish `aria-pressed`.

### WS-62 · Branch-close confirm uses a stale active-orders count — `correctness-bug` · low · S · Done
**Files:** `WorkshopBranchDetailView.vue`
**Why:** `changeBranchStatus` (`:408-423`) and the confirm checkbox warn with `selectedBranch?.active_orders_count` (`:1243`). `selectedBranch` is only loaded on mount/branchId change. If the operator leaves the settings tab idle while orders arrive, then closes the branch, the count is stale — they may close a branch with since-added active orders, surprising clients mid-production.
**Fix:** Done. Switching the status form away from active refreshes the branch, and submit refreshes the branch again before sending the status change. The checkbox copy now shows a refresh-in-progress state and notes that the count is refreshed before submit.

### WS-63 · createUser force-clears loading + bumps request id — `correctness-bug` · low · S · Done
**Files:** `stores/workshop.ts`
**Why:** `loadUsers` uses a request-id guard correctly (`:461-481`), but `createUser` (`:483-495`) does `usersLoadRequestId+=1; loading=false; upsertUser(...)` outside any try/finally, no awaited reload, no error capture. Force-setting `loading=false` can flip a genuine loadUsers spinner off prematurely; a failed POST leaves `error` null while the caller's await rejects. Edge-timing only.
**Fix:** Done. `createUser()` invalidates stale user-list responses, upserts the created user, stores the one-time temp password, then reloads through `loadUsers({ preserveTempPassword: true })` so the list loader owns `loading` cleanup without clearing the temp password.

### WS-64 · Notifications store captures failures, but page still hides action/load trace — `states-errors` · low · S · Done
**Files:** `WorkshopNotificationsView.vue`, `stores/notifications.ts`
**Why:** The store now keeps `traceId` and `actionError`, and tests cover mark-read/mark-all failures. The notifications page still renders a load error without trace_id and never shows `notifications.actionError`, so failures remain invisible in the full-page workflow even though the store has the data.
**Fix:** Done. The page now renders load trace IDs, shows page-level action failure feedback, emits trace-aware toasts for mark-read/mark-all failures, and still navigates to the notification destination when marking an unread row fails.

### WS-65 · Branch create/settings saves give no success feedback — `ux-flow` · low · S · Done
**Files:** `WorkshopBranchesView.vue`, `WorkshopBranchDetailView.vue`
**Why:** `createBranch` (`:42-65`) resets the form and closes the panel on success but no confirmation toast and no navigation to the new branch — the user is left scanning the list. `saveBranchSettings` (`:382-406`) silently writes branch info + pricing with no success feedback (only a mis-bound error path, WS-43). Owners can't tell whether a save persisted. Largely subsumed by WS-22.
**Fix:** Done. Branch create now shows a success toast after resetting/closing the form, and branch settings/status/material/supplier saves show success toasts plus the branch settings form has a persistent inline saved state.

### WS-66 · Production queues empty-without-explanation; buttons ungated — `permission-gating` · low · S · Done
**Files:** `WorkshopCuttingQueueView.vue`, `WorkshopBandingQueueView.vue`
**Why:** CuttingQueue `:16-23` / BandingQueue `:15-22` filter to orders assigned to `me` (good per-user scoping) but have **no process_production check**. A staffer without that permission always sees the generic empty state, and the "Kesish/Krom tugadi" buttons call cuttingDone/bandingDone with no permission guard. Per-user filter makes it largely harmless today, but direct URL still mounts the screen.
**Fix:** Done. Both queues render a tailored "Ishlab chiqarish ruxsati yo'q" empty state when the user has no production grant, and complete actions are guarded per order branch in the button state and submit handler.

### WS-67 · view_dashboard-only staff get full Orders management — `permission-gating` · low · S · Done
**Files:** `app/workshopNav.ts`, `WorkshopOrdersView.vue`
**Why:** `workshopNav.ts:50` adds "Buyurtmalar" when a branch has view_dashboard OR manage_orders, so a view-only-dashboard staffer gets the full orders link, but WorkshopOrdersView exposes detail/assignment flows intended for manage_orders. The view doesn't branch on view_dashboard vs manage_orders to restrict to read-only. Tied to WS-01.
**Fix:** Done. The Orders board route and navigation now require `manage_orders`; dashboard-only staff keep the dashboard but do not see or enter the management board. Focused nav/route tests pin the split.

### WS-68 · Inventory/Catalog deep-link staff with owner-flavoured CTAs — `permission-gating` · low · S · Done
**Files:** `WorkshopInventoryView.vue`, `WorkshopCatalogView.vue`, `WorkshopBranchDetailView.vue`
**Why:** Inventory shows "Filial omborini boshqarish" (`:81-87`) and per-row "Boshqarish" linking to `/workshop/branches/:id`; Catalog shows "Material qo'shish" (`:107-114`) for any staffer with manage_inventory/manage_catalog. BranchDetail re-gates correctly (so the destination is safe), but the CTA labels promise capabilities the user may only partially hold, and BranchesView itself is owner-only — making the breadcrumb context confusing. A papercut.
**Fix:** Done. The deep-links remain because BranchDetail re-gates the target, but inventory/catalog labels now use neutral copy such as "Filial omborini ochish", "Ombor kartasi", and "Filial katalogini ochish" instead of promising owner-only management powers.

### WS-69 · Orders kanban: no phone breakpoint — `responsive` · low · M · Done
**Files:** `WorkshopOrdersView.vue`, `web/src/assets/main.css`
**Why:** `.board` uses `repeat(5, minmax(210px, 1fr))` with `overflow-x:auto` (`main.css:2214-2228`) and renders all 5 columns unconditionally (`:158-185`). 5×210px ≈ 1050px, so on a 360px phone the default board is a wide horizontal-scroll strip with no breakpoint that stacks or switches to the table. (Mirrors the prototype, which also lacks a phone fallback.)
**Fix:** Done. At the existing phone breakpoint, `.board` now becomes a one-column vertical stack, horizontal board scroll is removed, and board columns release their fixed min-width.

### WS-70 · Missing prototype's `card:has(.tbl)` overflow fallback — `responsive` · low · S · Done
**Files:** `web/src/assets/main.css`, `prototype-full/assets/app.css`
**Why:** `.tbl { min-width: 680px }` and `.card { overflow: hidden }` (`main.css:1926/1621`) mean an unwrapped table in a card is clipped and forces horizontal page overflow. The prototype guards this with `@media (max-width:720px){ .card:has(> .tbl){ overflow-x:auto } }` (`app.css:305-311`); grep for `:has(`/`max-width: 720px` in main.css returns nothing. Latent (every `.tbl` is manually wrapped today) but a foot-gun.
**Fix:** Done. The Vue stylesheet now ports the prototype's `:has(> .tbl)` and `:has(> table.tbl)` narrow-screen overflow guard for both `.card` and `.card-b`, with a 640px table floor at small widths.

### WS-71 · /finance/income route redundant (renders Expenses view) — `completeness-stub` · low · S · Done
**Files:** `apps/workshop/routes.ts`, `WorkshopFinanceExpensesView.vue`
**Why:** Route `workshop-finance-income` (`/workshop/finance/income`, title "Tushum") maps to `WorkshopFinanceExpensesView` — same component as `/finance/expenses`; the view opens the income tab when the path ends `/income` (`:25` — but see WS-10 missing reactivity). workshopNav links only `/finance/expenses`, so the income route is reachable only by URL and redundant with the tab toggle.
**Fix:** Done. The route is intentionally kept as an explicit deep-link into the combined finance ledger view; `financeLedgerTabFromPath` plus route/tab tests make the dual-route behavior deliberate instead of accidental.

---

# Round 2 additions (WS-72 – WS-115)

Four lenses: spec-conformance (orders-production + finance/inventory/catalog) ·
proto-screens · testing · security. Many testing items are **regression guards
meant to ship with a specific R1 fix** — implement the named WS-fix and its test
together.

## P1 (round 2)

### WS-72 · Banding queue uses planned labelled edge-material metres — `spec-conformance` · high · M · Done
**Files:** `views/WorkshopBandingQueueView.vue`, `stores/orders.ts`
**Why:** The edger card must show pre-completion metres by shop edge material, not wait for `edge_length_snapshot`.
**Fix:** Done. Order summaries now include `planned_edge_lines` derived from the cutting result; the banding queue renders material label, thickness, color, and metres through tested `workshopQueueEdgeLine()`. Backend sales tests pin the summary contract. **Related:** WS-30/51/66.

### WS-74 · Order detail supports assign/change cutter and edger — `spec-conformance` · high · M · Done
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** The docs allow assignment changes until each job is done; the backend already supports partial assignment PATCH via the assignment endpoint.
**Fix:** Done. Confirmed orders can save/change the edger independently, cutting orders can save/change the cutter, and edge-banding orders can save/change the edger without firing completion. The existing `orders.assign` store path updates the detail response/version.

### WS-78 · Income/expense edit actions call existing PATCH endpoints — `spec-conformance` · high · M · Done
**Files:** `views/WorkshopFinanceExpensesView.vue`, `stores/finance.ts`
**Why:** Recorded ledger rows must support audited correction, not only void + re-record.
**Fix:** Done. The finance store exposes `updateIncome/updateExpense`; recorded rows show `Tahrir`, reopen the form prefilled, and save through PATCH. Income type/order remain fixed during edit; mutable fields are amount, method, date, note, and branch for non-order income. **Related:** WS-39.

### WS-79 · Production report shows labelled edge-material metres + thickness rollup — `spec-conformance` · high · M · Done
**Files:** `views/WorkshopFinanceProductionView.vue`, `backend/app/modules/finance/schemas.py`, `sales/service.py`
**Why:** The accountant needs material/thickness breakdowns; raw UUIDs defeat the report.
**Fix:** Done. Sales' public production records now include labelled edge lines and a thickness rollup; finance response schemas expose both while preserving the legacy raw map. The production view renders the labelled fields. Backend sales-flow tests pin labels, metres, and rollup.

### WS-113 · Temp password cleared across user loads and logout reset — `security` · high · S · Done
**Files:** `stores/workshop.ts`, `WorkshopUserDetailView.vue`, `WorkshopUsersView.vue`
**Why:** `lastTempPassword` is a one-time secret that must not survive user navigation or logout on a shared device.
**Fix:** Done. `loadUser()/loadUsers()` clear stale temp passwords, the workshop store exposes `reset()`, and `auth.clear()` invokes session-store resets on logout/refresh failure. The regression test seeds workshop/order/finance/notification state and asserts logout wipes it. **Related:** WS-63, WS-114.

## P2 (round 2)

### WS-73 · Cutting queue shows planned panel count before completion — `spec-conformance` · med · M · Done
**Files:** `WorkshopCuttingQueueView.vue`, `stores/orders.ts`
**Why:** The cutter needs panels needed before the completion snapshot exists.
**Fix:** Done. Order summaries include `planned_panels`; the cutting queue uses tested `workshopQueuePartsLine()` and falls back to the completion snapshot only if the planned value is absent. Backend sales tests pin summary output. **Related:** WS-30/66/72.

### WS-75 · Revert action names the concrete target state — `spec-conformance` · med · S · Done
**Files:** `WorkshopOrderDetailView.vue`
**Why:** Revert changes stock/stamps, so the operator must see the destination before confirming.
**Fix:** Done. The button and confirmation message compute the destination from `status` + `has_banding` and name tasdiqlangan/kesish/krom accordingly.

### WS-80 · Production screen links rows to salary expense entry — `completeness-stub` · med · M · Done
**Files:** `WorkshopFinanceProductionView.vue`
**Why:** The accountant should be able to jump from a worker's production row into the manual salary expense flow.
**Fix:** Done. Each production row has `Maosh yozish`, routing to the expense form with `category=salary`, worker name as vendor, and a salary description. Amount stays blank for the accountant. **Related:** WS-53.

### WS-81 · Income order picker is scoped to selected branch — `spec-conformance` · med · S · Done
**Files:** `WorkshopFinanceExpensesView.vue`
**Why:** The displayed branch and chosen order must not diverge.
**Fix:** Done. Order options filter by selected branch; choosing an order sets the branch to the order's branch, and changing branch clears an incompatible order selection.

### WS-82 · Finance forms upload and attach receipt scans — `completeness-stub` · med · M · Done
**Files:** `WorkshopFinanceExpensesView.vue`, `stores/finance.ts`
**Why:** Finance docs require optional receipt scans for income and expenses.
**Fix:** Done. Income/expense forms upload through `files.upload`, keep the returned id, send `receipt_file_id` on create/update, and render a receipt indicator in both ledgers. The backend now attaches/replaces finance receipt files and authorizes finance users to read them. Backend finance tests pin receipt attachment/read-back. **Related:** WS-44.

### WS-83 · Future ledger dates blocked in UI and backend — `spec-conformance` · med · S · Done
**Files:** `WorkshopFinanceExpensesView.vue`, `backend/app/modules/finance/service.py`
**Why:** Future-dated ledger rows shift reports into the wrong period.
**Fix:** Done. Income/expense create and update reject future dates with `future_date_not_allowed`, and the form date inputs set `max=today`. Backend finance tests pin create/update rejection.

### WS-84 · Materials catalog lacks manufacturer/type filters (+backend) — `spec-conformance` · med · M · Done
**Files:** `WorkshopCatalogView.vue`, `WorkshopBranchDetailView.vue`, `backend/app/modules/catalog/routes.py`
**Why:** The branch-materials endpoint and catalog page did not expose manufacturer or panel-type filtering required by the catalog/inventory spec.
**Fix:** Done. Workshop branch catalog option and branch-material endpoints accept `manufacturer_id` and `material_type`; CatalogView sends manufacturer/type filters. Backend catalog tests pin both filtered branch-material listing and picker filtering.

### WS-85 · Stock tx log shows actor names and notes — `spec-conformance` · med · S · Done
**Files:** `WorkshopInventoryView.vue`, `backend/app/modules/inventory/schemas.py`
**Why:** Adjustment reasons and human actors are core audit data.
**Fix:** Done. `StockTransactionResponse` includes `actor_name`; the standalone transaction table renders branch, supplier, actor name, note, and order link. Backend inventory tests pin actor names and note output. **Related:** WS-45/86.

### WS-87 · Branch detail dropped Overview/Staff/Orders tabs + KPI strip — `design-parity` · high · L · Done
**Files:** `WorkshopBranchDetailView.vue`, `prototype-full/workshop/branch-detail.html`
**Why:** The prototype renders a 4-tile KPI strip (Faol buyurtma/Materiallar/Past zaxira/Xodim, `:112-117`) and six tabs incl. Umumiy (`:128-137`), Xodimlar (branch staff→user-detail, `:172-181`), Buyurtmalar (branch orders, `:183-192`). `WorkshopBranchDetailView.vue` defines only materials/inventory/settings tabs (`:172-176`) with no KPI strip and no Overview/Staff/Orders tabs. An owner loses at-a-glance KPIs and branch staff/orders from the branch page.
**Fix:** Done. Branch detail now has the six-tab prototype structure with Umumiy, Materiallar, Ombor, Sozlamalar, Xodimlar, and Buyurtmalar. The header KPI strip shows active orders, material count, low-stock count, and staff count; the overview, staff, and branch-order tabs lazy-load their own data and stay permission-gated.

### WS-88 · Inventory screen lost stock-in/adjust/supplier actions — `completeness-stub` · high · L · Done
**Files:** `WorkshopInventoryView.vue`, `prototype-full/workshop/inventory.html`
**Why:** The standalone inventory page was read-mostly and forced managers into branch detail for stock-in, adjustments, and supplier maintenance.
**Fix:** Done. InventoryView now has stock-in and adjustment forms on the stock tab, receipt upload support, quantity validation, and supplier create/edit/activate/deactivate controls on the suppliers tab. **Related:** WS-68.

### WS-89 · Orders screen dropped date filter + CSV export — `design-parity` · med · M · Done
**Files:** `WorkshopOrdersView.vue`, `prototype-full/workshop/orders.html`
**Why:** The prototype exposes a date-range filter (Barcha/Bugun/Oxirgi 7 kun/oy, `:48-53`) and a CSV button (`:27`). The Vue filter row (`:125-132`) has only status/search/branch — no date filter — and the tools slot (`:99-122`) replaces CSV with a "Kesish navbati" link the prototype never has. Owners can't scope to today/last week or export.
**Fix:** Done. Workshop orders now support Barcha/Bugun/Oxirgi 7 kun/Oy filters through backend date bounds, route-aware branch filtering, and a CSV export endpoint using the same filters. The view exposes a CSV button with busy/error/trace feedback while preserving the production-queue shortcut outside the export control.

### WS-90 · Order item list drops per-side edge thickness + breakdown — `design-parity` · med · M · Done
**Files:** `WorkshopOrderDetailView.vue`, `prototype-full/workshop/order-detail.html`
**Why:** The prototype "Buyurtma tarkibi" renders per-side edge labels with thickness ("T: 2 mm", "B: 0.8 mm (mijoz)", `:105-113`) and a separate edge-material list (manufacturer+thickness+color+metres, `:117-122`). `edgeSummary` (`:69-83`) emits only side letter + source and never reads thickness; the template (`:374-389`) has no edge-material rows. `OrderItem.edge_*` are `Record<string,unknown>` (`orders.ts:38-41`) so thickness is in the payload but unused. The floor can't see which band thickness per side.
**Fix:** Done. Order-detail item cards now render per-side Krom labels with side, thickness/color/name, metres, and customer/workshop source. A separate Krom sarfi breakdown summarizes planned edge lines by material/thickness/color/metres.

### WS-91 · Price card lost krom split; header lost due date — `design-parity` · med · M · Done
**Files:** `WorkshopOrderDetailView.vue`, `prototype-full/workshop/order-detail.html`
**Why:** The prototype "Narx tafsiloti" splits Krom into Krom(metres)/Krom materiali/Krom yopishtirish xizmati (`:174-176`) and the header shows a "Muddat: <dueAt>" chip (`:145`). The Vue version collapses krom into one row with no metres/split (`:403-419`) and the header (`:285-299`) has no due-date; `orders.ts` exposes no due_at field. (Due-date needs the API to surface the field first — medium confidence.)
**Fix:** Done. The price card now splits Krom into material and gluing service rows and shows consumed/planned Krom metres alongside the totals. The header includes a due-date chip that renders a safe "Muddat: belgilanmagan" fallback until the API exposes an actual due date.

### WS-92 · Branch cards dropped low-stock KPI; fake counts — `design-parity` · med · M · Done
**Files:** `WorkshopBranchesView.vue`, `prototype-full/workshop/branches.html`
**Why:** Prototype branch cards show four numeric KPIs (Faol buyurtma/Past zaxira/Materiallar/Xodimlar, `:98-103`). The Vue kpi-grid (`:218-235`) keeps only the orders count; the other three tiles render literal text ("OK"/"!", "Boshqarish", "Ruxsatlar") — the low-stock count is gone and material/staff counts are fabricated labels. An owner can't compare branches by low-stock pressure/breadth/headcount.
**Fix:** Done. Branch list responses now include operational counts for active orders, branch materials, low-stock stock items, and staff. Branch cards render all four numeric KPIs with a visible low-stock text cue instead of fabricated labels. **Related:** WS-49.

### WS-93 · Finance reports show raw payment-method code — `i18n-copy` · med · S
**Files:** `WorkshopFinanceView.vue`, `prototype-full/workshop/finance.html`
**Why:** `:223` renders `{{ income.method }}` raw in the "Usul" column — the user sees "cash"/"bank_transfer". The prototype maps to Naqd/Bank·karta/Boshqa (`:162,167`), and the sibling expenses view already maps it (`methodLabel` in `FinanceExpensesView:146`) — only the reports screen regressed.
**Fix:** Import/add the method label map and render the localized label. **Related:** WS-56.

### WS-94 · User-detail Profil tab is read-only — `completeness-stub` · med · M · Done
**Files:** `WorkshopUserDetailView.vue`, `prototype-full/workshop/user-detail.html`
**Why:** The prototype Profil tab has editable F.I.O/Telefon/Login/Asosiy filial + Saqlash (`:73-89`). The Vue profile tab (`:241-279`) renders the four fields read-only + a Status card; there is no form/save — only grants/password-reset/block are mutable. An owner can't correct a staff member's name/phone/login/home branch.
**Fix:** Done. Non-owner staff profiles now expose editable F.I.O, phone, login, and main branch fields with owner-gated save feedback and traceable errors. The backend user-update endpoint accepts login changes with uniqueness validation and supports clearing/changing `home_branch_id`.

### WS-99 · Test formatStockQuantity metres — `testing` · high · S · ships with WS-06
**Files:** `formatters.ts`, `shared/__tests__/formatters.spec.ts`
**Why:** `formatters.spec.ts` tests formatTiyin/formatDate but not `formatStockQuantity` — the live render path for stock/banding/production metres, and the WS-06 comma-decimal root cause has no test pinning the /1000 conversion.
**Fix:** Cases: `formatStockQuantity(18000,'m')` ends " m" + contains "18" no fraction; 18500 → 3 decimals; a non-'m' unit renders integer + raw unit with no scaling. Use `.toMatch/.toContain` for locale-robustness. **Related:** WS-06.

### WS-100 · Test parseDisplayQuantity round-trip — `testing` · high · S · ships with WS-07
**Files:** `formatters.ts`, `shared/__tests__/formatters.spec.ts`
**Why:** `parseDisplayQuantity` (`:33-38`) is the inverse of formatStockQuantity and the WS-07 raw-mm root cause; nothing tests it — a refactor could mis-store stock-in by 1000×.
**Fix:** `parseDisplayQuantity('12,5','m')===12500`; `('3','piece')===3`; `('abc','m')` NaN; a parse→format round-trip for integers divisible by 100. **Related:** WS-06/07.

### WS-101 · Test orders.patchOrder list isolation — `testing` · high · M · ships with WS-28 · Done
**Files:** `stores/orders.ts`, `stores/__tests__/orders.spec.ts` (new)
**Why:** `stores/__tests__/orders.spec.ts` now covers workshop mutation isolation and client mutation isolation: the non-owning list is untouched, and an existing row is replaced in place instead of jumping to the top.
**Fix:** Done. **Related:** WS-28.

### WS-102 · Test orders 409 conflict + refetch — `testing` · high · M · ships with WS-09 · Done
**Files:** `stores/orders.ts`, `WorkshopOrderDetailView.vue`
**Why:** `stores/__tests__/orders.spec.ts` now mocks a 409 `order_version_conflict`, asserts the current order is refetched to the server version, and asserts the conflict remains an action error instead of collapsing the detail page into a load error.
**Fix:** Done for the store regression. Remaining user-visible conflict copy belongs to WS-09, and end-to-end recovery still belongs to WS-112.

### WS-103 · Test finance dual-route tab reactivity — `testing` · med · M · ships with WS-10 · Done
**Files:** `WorkshopFinanceExpensesView.vue`, `apps/workshop/routes.ts`
**Why:** `:25` reads activeTab once at setup with no watch; both `/finance/income` and `/finance/expenses` map to this component, so navigating reuses the instance and activeTab never updates (WS-10). No test pins it.
**Fix:** Done. Added a shared `financeLedgerTabFromPath()` seam used by the component's initial state and route watcher, with focused tests pinning `/finance/income` to the income tab and other finance ledger paths to expenses. **Related:** WS-10/71.

### WS-104 · Test discount draft/re-entry safety — `testing` · high · M · ships with WS-08/39 · Done
**Files:** `WorkshopOrderDetailView.vue`, `stores/orders.ts`
**Why:** `shared/app/__tests__/workshopOrderDetail.spec.ts` now pins the pure discount draft/parse seam: computed discount amounts are not copied into the form, percent/fixed submissions are parsed deliberately, and invalid values/reasons return localized copy.
**Fix:** Done. Full remove/edit UX remains WS-39. **Related:** WS-08/39.

### WS-105 · Test notification filter + deep-link — `testing` · med · M · ships with WS-48 · Done
**Files:** `WorkshopNotificationsView.vue`, `stores/notifications.ts`
**Why:** The filter predicate (`:23-27`) uses option value 'inventory' while stock codes contain 'stock' → the chip matches nothing; `to()` (`:43-44`) returns paths only for order/branch (WS-48). No test pins either.
**Fix:** Done. Added `workshopNotifications` pure helpers and tests proving stock/inventory events match the inventory filter and stock/finance/order notifications route to the right workshop surfaces. **Related:** WS-48.

### WS-106 · Test useWorkshopPermissions truth table — `testing` · high · M · ships with WS-04 · Done
**Files:** `WorkshopDashboardView.vue`, `stores/auth.ts`, `app/workshopNav.ts`
**Why:** `shared/app/__tests__/workshopPermissions.spec.ts` now covers owner access, branch-scoped grants, empty grants, workshop-wide grants, accessible-branch derivation, owner-only route denial for staff, and branch-param route allowance.
**Fix:** Done. Additional nav alias tests can still be added if WS-67 expands dashboard-only behavior.

### WS-107 · Test permission route guard — `testing` · high · M · ships with WS-05 · Done
**Files:** `app/createRoleApp.ts`, `apps/workshop/routes.ts`
**Why:** `routeMatrix.spec.ts` now covers `roleRoutePermissionAllowed`: inventory-only staff are rejected from finance and owner-only settings, allowed into inventory and branch detail when scoped, and owners pass.
**Fix:** Done. `e2e/tests/access-and-provisioning.spec.ts` also covers the direct-URL behavior in-browser.

### WS-114 · Pinia session stores reset on logout — `security` · med · M · Done
**Files:** `stores/auth.ts`, `stores/workshop.ts`, `ProfileView.vue`
**Why:** Pinia setup stores keep module-level refs alive across client-side route changes. Logout must clear tenant/user data, not only auth memory.
**Fix:** Done. Session-bearing stores now expose `reset()`, and `auth.clear()` resets every active non-auth store that implements it. Current Pinia stores covered: workshop, orders, finance, cutting, notifications, files, client profile/catalog, and admin. The logout regression covers the high-risk workshop/order/finance/notification residue path. **Related:** WS-28/113.

### WS-116 · E2E and backend tests are isolated from developer `.env` drift — `testing` · med · S · Done
**Files:** `e2e/playwright.config.ts`, `backend/tests/test_api_foundation.py`, `backend/tests/test_config.py`, `backend/app/core/config.py`, `backend/.env.dev.example`, `deploy/.env.dev.example`
**Why:** Local verification found two environment-sensitive paths: E2E file uploads could inherit developer MinIO credentials, and backend tests could inherit `DEBUG=true` or MinIO overrides from `backend/.env`.
**Fix:** Done. E2E pins the MinIO environment used by its booted backend. Config tests instantiate `Settings(..., _env_file=None)` and clear asserted MinIO env keys, while the API-foundation generic-error test pins `settings.DEBUG=false` before app creation.

## P3 (round 2)

### WS-76 · Timeline omits production stamps (credited worker/panels) — `spec-conformance` · low · M · Done
**Files:** `WorkshopOrderDetailView.vue`
**Why:** `orders.md:123`: production stamps are the sole input to worker-production reports; the backend writes `credited_user_id` into event metadata (`sales/service.py:661-664,706-708`). The Vue timeline (`:607-628`) renders only changed_at/status/reason — it ignores `event.metadata` (exists on `OrderEvent`, `orders.ts:56`), so who was credited (esp. on-behalf) and panel count are invisible. The prototype surfaces them. (Distinct from WS-27.)
**Fix:** Done. Order timeline rows now summarize production metadata from event payloads: credited worker, panel consumption, and edge metres. A pure helper test pins the text rendering.

### WS-77 · Board never renders WHO is assigned — `spec-conformance` · low · S · Done
**Files:** `WorkshopOrdersView.vue`
**Why:** `orders.md:288` requires the board card to show the assigned cutter/edger chip. `assignedText()` (`:56-63`) returns a single string stating only whether a worker exists, shows cutter OR edger by status (never both), never the identity; card (`:164-180`) and table (`:215`) reuse it. (Content gap; WS-51 is the chip styling.)
**Fix:** Done with WS-51. The board/table now render both assigned cutter and assigned edger identity chips when present, instead of a stage-only generic string.

### WS-86 · BranchDetail tx table shows order link, actor, and note — `spec-conformance` · low · S · Done
**Files:** `WorkshopBranchDetailView.vue`
**Why:** The branch-scoped transaction log must expose the same audit data as the standalone inventory view.
**Fix:** Done. Branch detail now renders order links, supplier, actor name, and note columns, using the same actor-name response field as WS-85. **Related:** WS-85.

### WS-95 ⚠ · Users list dropped "Oxirgi kirish" column — `design-parity` · low · S · Done
**Files:** `WorkshopUsersView.vue`, `prototype-full/workshop/users.html`
**Why (verify):** The prototype users table has an "Oxirgi kirish" column (`:47,121`). The Vue head (`:292-301`)/body (`:303-336`) have none. **⚠ depends on whether the workshop users payload carries last-login.**
**Fix:** Done. Workshop user responses now expose `last_login_at`, the users table restores `Oxirgi kirish`, and empty values render as `Hali yo'q`.

### WS-96 · Inventory tx table includes Filial column — `design-parity` · low · S · Done
**Files:** `WorkshopInventoryView.vue`, `prototype-full/workshop/inventory.html`
**Why:** The prototype transaction log includes branch context.
**Fix:** Done. The standalone inventory transaction table includes a `Filial` column using the active branch name.

### WS-97 · Catalog rows lost hide-from-customers toggle — `completeness-stub` · low · M · Done
**Files:** `WorkshopCatalogView.vue`, `prototype-full/workshop/catalog.html`
**Why:** The catalog page had no direct way to hide/show a branch material to customers.
**Fix:** Done. Catalog rows now expose an inline `Mijozdan yashirish` / `Mijozga ko'rsatish` action backed by the existing branch-material status endpoint, with row busy state and traceable error feedback. **Related:** WS-68.

### WS-98 · Profile grant rows show raw branch-id fragment — `i18n-copy` · low · S
**Files:** `ProfileView.vue`, `prototype-full/workshop/profile.html`
**Why:** The prototype resolves grant branches to names (`branchById(b).name`, `:101`). `workshopGrantRows` maps each grant to `grant.branch_id.slice(0,8)` (`:76-84`) and renders that 8-char UUID fragment in the Ruxsatlar card (`:494`) — a staff user sees "3f9a2c1b" instead of "Yunusobod".
**Fix:** Resolve `grant.branch_id` to the branch name via `workshop.branches`, falling back to the fragment only when not loaded.

### WS-108 · Test workshop store branch-context flows — `testing` · med · M · Done
**Files:** `stores/workshop.ts`
**Why:** The largest store (640 lines) has zero tests. Untested: `loadUsers` request-id race guard (`:462-481`), `createUser` bumping the id + clearing loading (`:490-491`, the WS-63 foot-gun), `loadInventory` Promise.all error capture (`:392-404`), `loadBranch` owner-only pricing fetch (`:257-262`), `recordStockIn` prepend-then-refetch (`:438-448`).
**Fix:** Done. `workshop.spec.ts` now covers out-of-order `loadUsers` responses, the WS-63 create-user/loading/temp-password path, inventory error trace capture, owner-only branch pricing fetches, and stock-in prepend plus stock reload. **Related:** WS-63/32/29.

### WS-109 · Test finance store load + error capture — `testing` · med · S · Done
**Files:** `stores/finance.ts`
**Why:** No finance-store test. `capture()` sets error+traceId; loaders set distinct codes; create prepends; void maps in place. None pinned; WS-58 lives in its callers.
**Fix:** Done. `finance.spec.ts` now covers loader error/trace capture with loading cleanup, create-prepend behavior, void-in-place replacement, and existing action-error capture. **Related:** WS-45/58.

### WS-110 · E2E: owner applies a discount, persists on reload — `testing` · med · M · Done
**Files:** `e2e/tests/order-production.spec.ts`, `WorkshopOrderDetailView.vue`
**Why:** order-production walks approve→…→collect but never touches the discount control; `applyDiscount` + form are unexercised e2e, and WS-08/39 live here. The owner-only flow changes what the customer pays with no coverage.
**Fix:** Done. `e2e/tests/workshop-order-hardening.spec.ts` provisions an order, logs in as the workshop owner, applies a fixed discount with a reason, reloads order detail, and asserts the discount persists. Local browser execution passed after Docker recovered; the full E2E suite is green. **Related:** WS-08/39.

### WS-111 · E2E: record income against order + standalone expense — `testing` · med · M · Done
**Files:** `e2e/tests/order-production.spec.ts`, `WorkshopFinanceExpensesView.vue`
**Why:** No e2e visits /workshop/finance/expenses or exercises createIncome/createExpense. The finance ledger path (income tied to order_id, expense with category) is untested through the browser; WS-10/41 sit on it.
**Fix:** Done. `e2e/tests/workshop-order-hardening.spec.ts` records an order-linked income, verifies it in the income ledger, switches to the expense tab, records a standalone expense, and verifies it in the expense ledger. Local browser execution passed after Docker recovered; the full E2E suite is green. **Related:** WS-10/41/44.

### WS-112 · E2E: revert/cancel-with-reason + 409 recovery — `testing` · med · L · Done
**Files:** `e2e/tests/order-production.spec.ts`, `WorkshopOrderDetailView.vue`, `stores/orders.ts`
**Why:** The reason-dialog actions (`:180-201`) and store revert/cancel (`orders.ts:307-313`) have no e2e; the 409 path (`run()` `:115-124`) is unexercised. order-production walks only forward. WS-09/37 regressions would surface only in prod.
**Fix:** Done. `e2e/tests/workshop-order-hardening.spec.ts` drives an order into production, reverts it with a reason, then exercises a stale cancel by changing the order out-of-band through the API and asserting the 409 recovery copy before retrying with fresh data. Local browser execution passed after Docker recovered; the full E2E suite is green. **Related:** WS-09/37.

### WS-115 ⚠ · AuthFileImage object-URL leak under rapid fileId change — `security` · low · S · Done
**Files:** `components/AuthFileImage.vue`, `stores/files.ts`
**Why (verify):** `AuthFileImage.vue:27-40` `watch(fileId)` calls `revoke()` (current src only) then awaits `files.loadObjectUrl`; `files.ts:43-48` creates a fresh URL with no internal revoke. If fileId changes again before a prior await resolves, the stale resolution assigns a new URL over src without revoking the superseded one. **⚠ Latent — grep shows zero consumers mount AuthFileImage today.**
**Fix:** Done. `AuthFileImage` now uses a per-load sequence guard, revokes stale late-resolving handles immediately, ignores stale failures, and increments the guard on unmount. A component test resolves file loads out of order and proves the superseded URL is revoked. **Related:** WS-44.
