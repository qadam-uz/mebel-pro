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

## Conventions

- **Priority** — `P1` do-first (high-leverage, blocks the order-production pipeline
  or breaks permission gating), `P2` important, `P3` nice-to-have.
- **Severity** — operator/staff impact. **Effort** — `S` ≤½ day · `M` ~1–2 days · `L` larger.
- **Category** — permission-gating · correctness-bug · states-errors · performance ·
  design-parity · a11y · ux-flow · i18n-copy · completeness-stub · responsive · tech-debt.
- **Status** — `Open` · `WIP` · `Done` · `Won't`.
- Scope guard: in-v1 per [`docs/scope.md`](../docs/scope.md). Out-of-v1 (workshop-side
  audit viewer, operator order browsing, delivery, inter-branch transfer, payroll
  engine, online payments) excluded.
- **Security note:** client-side gating is UX, not the boundary — the FastAPI service
  enforces authz server-side. But showing buttons/screens that always 403 (WS-01/02)
  is a real UX bug *and* leaks the existence of sensitive surfaces.

## Counts

| | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| Open | 25 | 51 | 39 | **115** |

By category: spec-conformance ~21 · testing ~14 · design-parity ~16 ·
correctness-bug ~13 · permission-gating ~12 · states-errors ~11 · performance ~9 ·
completeness-stub ~8 · i18n-copy ~6 · a11y ~7 · responsive ~3 · security ~3.

## Index

| ID | Pri | Cat | Sev | Eff | Status | Title |
|----|-----|-----|-----|-----|--------|-------|
| WS-01 | P1 | permission-gating | high | M | Open | Order-detail lifecycle actions completely ungated |
| WS-02 | P1 | permission-gating | high | S | Open | Finance/production screens have no in-screen permission gate |
| WS-03 | P1 | permission-gating | high | M | Open | Per-branch grants treated as workshop-wide (Finance/Dashboard) |
| WS-04 | P1 | permission-gating | med | M | Open | No shared permissions composable (divergent gating) |
| WS-05 | P1 | permission-gating | med | M | Open | No route-level permission guard |
| WS-06 | P1 | correctness-bug | high | S | Done | Metres render with comma decimal → 2.5m shows "2,500 m" |
| WS-07 | P1 | correctness-bug | high | S | Open | Inventory tx log shows raw mm for edge materials |
| WS-08 | P1 | correctness-bug | high | M | Open | Discount re-edit corrupts percent discounts |
| WS-09 | P1 | correctness-bug | high | M | Open | Version conflict: raw code, never refetches (retry loop) |
| WS-10 | P1 | correctness-bug | high | S | Done | Finance dual-route tab doesn't react to income↔expenses nav |
| WS-11 | P1 | performance | high | L | Open | Workshop order list unbounded + server N+1 detail build |
| WS-12 | P1 | performance | high | M | Open | Stock transactions unbounded (client + server) |
| WS-13 | P1 | i18n-copy | high | M | Open | 3 screens fully English (cutting-plans, plan-detail, production) |
| WS-14 | P1 | i18n-copy | high | M | Open | English validation msgs + raw error codes shown to users |
| WS-15 | P1 | ux-flow | high | L | Open | Topbar branch dropdown is a dead control (drives only nav) |
| WS-16 | P1 | responsive | high | M | Open | ProjectDropdown popover double-counts scroll, no edge clamp |
| WS-17 | P1 | states-errors | high | S | Open | Catalog table: no loading/error state (silent empty) |
| WS-18 | P1 | states-errors | high | S | Done | Settings save: no error/busy/success |
| WS-19 | P1 | states-errors | high | M | Open | Dashboard swallows all load errors (.catch undefined) |
| WS-20 | P1 | completeness-stub | high | M | Open | Dashboard sales chart is hardcoded fabricated data |
| WS-21 | P2 | design-parity | high | L | Open | Order board/table lost per-card status-action kebab menu |
| WS-22 | P2 | design-parity | high | L | Open | No toast system — every successful mutation is silent |
| WS-23 | P2 | a11y | high | M | Open | 5 tab UIs lack tab/tablist/tabpanel ARIA |
| WS-24 | P2 | a11y | med | S | Open | Permission-matrix checkboxes have no accessible name |
| WS-25 | P2 | a11y | med | M | Open | Mobile drawer: no focus trap/Escape/scroll-lock |
| WS-26 | P2 | a11y | med | M | Open | Cutting-plan SVG rects focusable but unlabeled/no focus |
| WS-27 | P2 | correctness-bug | med | S | Open | complete cutting/banding can post null completed_by |
| WS-28 | P2 | correctness-bug | med | S | Open | Order mutations pollute clientOrders + reorder both lists |
| WS-29 | P2 | correctness-bug | med | S | Open ⚠ | Stock-in/adjustment post unvalidated quantities |
| WS-30 | P2 | performance | med | M | Open | Cut/band queues refetch full active list, filter client-side |
| WS-31 | P2 | performance | med | M | Open | loadBranchContext refetched on nearly every screen mount |
| WS-32 | P2 | performance | med | S | Open | Inventory eagerly fetches stock+all-tx+suppliers on mount |
| WS-33 | P2 | completeness-stub | med | S | Open | Cutting-plans & production screens unreachable (no nav) |
| WS-34 | P2 | completeness-stub | med | S | Open | Orphaned WorkshopFinanceIncomeView (English, ungated dead code) |
| WS-35 | P2 | completeness-stub | med | M | Open | Settings "Logo" file input is a dead control |
| WS-36 | P2 | completeness-stub | med | M | Open | Topbar global search + ⌘K are non-functional |
| WS-37 | P2 | states-errors | high | S | Done | "Mijoz olib ketdi" terminal action has no confirmation |
| WS-38 | P2 | ux-flow | high | M | Open | Fresh production staff land on an empty app (no awaiting list) |
| WS-39 | P2 | ux-flow | med | M | Open | Discount can only be added, never edited/removed |
| WS-40 | P2 | ux-flow | med | M | Open | Queue "done" can't credit who actually did the work |
| WS-41 | P2 | ux-flow | med | M | Open | Income entry can't show order's outstanding balance |
| WS-42 | P2 | states-errors | med | M | Open | PDF download: no error/busy across queues & detail |
| WS-43 | P2 | states-errors | med | S | Open | Branch settings/pricing save error never rendered (1st form) |
| WS-44 | P2 | states-errors | med | S | Open | Receipt upload failure has no feedback |
| WS-45 | P2 | states-errors | med | S | Open | User/finance action errors omit trace_id |
| WS-46 | P3 | states-errors | low | S | Done | User-detail misreports context-load failure as "not found" |
| WS-47 | P3 | states-errors | med | S | Open | Cutting-plan detail blank when plan has no result |
| WS-48 | P3 | ux-flow | low | S | Open | Notifications can't deep-link finance/stock; inventory chip broken |
| WS-49 | P3 | correctness-bug | med | M | Open | Dashboard low-stock scoped to branchIds[0]; recent = active-only |
| WS-50 | P3 | design-parity | med | M | Open | Material swatches all render the same default gradient |
| WS-51 | P3 | design-parity | med | S | Open | Order board lost assigned-worker chips (icons + initials) |
| WS-52 | P3 | design-parity | med | M | Open | Dashboard chart dropped SVG/gridlines/tooltips/legend |
| WS-53 | P3 | design-parity | low | S | Open | Production report dropped period column + "Maosh yozish" shortcut |
| WS-54 | P3 | design-parity | low | S | Open | Cutting-plan SVG uses off-brand blue, not teal accent |
| WS-55 | P3 | design-parity | low | S | Open | Mobile chrome uses ☰/× glyphs instead of SVG icons |
| WS-56 | P3 | i18n-copy | med | S | Open | English fallback strings ("No material", etc.) |
| WS-57 | P3 | performance | low | M | Open | Inventory/Catalog/Users client-filter full list redundantly |
| WS-58 | P3 | performance | low | S | Open | Finance fires 3 sequential requests; expenses double-fetch |
| WS-59 | P3 | a11y | med | M | Open | Inline forms (void/assign/discount) far from trigger, no focus move |
| WS-60 | P3 | a11y | low | S | Partial | Muted text fails AA; low-stock/destructive color-only |
| WS-61 | P3 | a11y | low | S | Open | Dashboard chart hidden from AT; range toggles no aria-pressed |
| WS-62 | P3 | correctness-bug | low | S | Open | Branch-close confirm uses a stale active-orders count |
| WS-63 | P3 | correctness-bug | low | S | Open | createUser force-clears loading + bumps request id |
| WS-64 | P3 | states-errors | low | S | Partial | Notifications mark-read failures silent; load error no trace |
| WS-65 | P3 | ux-flow | low | S | Open | Branch create/settings saves give no success feedback |
| WS-66 | P3 | permission-gating | low | S | Open | Production queues empty-without-explanation; buttons ungated |
| WS-67 | P3 | permission-gating | low | S | Open | view_dashboard-only staff get full Orders management surface |
| WS-68 | P3 | permission-gating | low | S | Open | Inventory/Catalog deep-link staff with owner-flavoured CTAs |
| WS-69 | P3 | responsive | low | M | Open | Orders kanban: no phone breakpoint (5×210px h-scroll) |
| WS-70 | P3 | responsive | low | S | Open | Missing prototype's `card:has(.tbl)` overflow fallback |
| WS-71 | P3 | completeness-stub | low | S | Open | /finance/income route redundant (renders Expenses view) |
| WS-72 | P1 | spec-conformance | high | M | Open | Banding queue reads null snapshot → "krom rejasi"/raw UUIDs |
| WS-73 | P2 | spec-conformance | med | M | Open | Cutting queue never shows panels-needed (null snapshot) |
| WS-74 | P1 | spec-conformance | high | M | Open | No re-assign/change cutter or edger after confirmed |
| WS-75 | P2 | spec-conformance | med | S | Open | Revert button never names the concrete target |
| WS-76 | P3 | spec-conformance | low | M | Open | Timeline omits production stamps (credited worker/panels) |
| WS-77 | P3 | spec-conformance | low | S | Open | Board never renders WHO is assigned (cutter/edger identity) |
| WS-78 | P1 | spec-conformance | high | M | Open | Income/expense Edit absent (backend PATCH exists) |
| WS-79 | P1 | spec-conformance | high | M | Open | Production report renders raw edge-material UUIDs |
| WS-80 | P2 | completeness-stub | med | M | Open | Production screen lacks "record salary expense" shortcut |
| WS-81 | P2 | spec-conformance | med | S | Open | Income order picker not scoped to selected branch |
| WS-82 | P2 | completeness-stub | med | M | Open | Finance forms can't attach a receipt scan |
| WS-83 | P2 | spec-conformance | med | S | Open | No future-date guard on received_on/incurred_on (UI+backend) |
| WS-84 | P2 | spec-conformance | med | M | Open | Materials catalog lacks manufacturer/type filters (+backend) |
| WS-85 | P2 | spec-conformance | med | S | Open | Stock tx log shows raw actor UUID, omits note column |
| WS-86 | P3 | spec-conformance | low | S | Open | BranchDetail tx table drops order-link/actor/note |
| WS-87 | P2 | design-parity | high | L | Open | Branch detail dropped Overview/Staff/Orders tabs + KPI strip |
| WS-88 | P2 | completeness-stub | high | L | Open | Inventory screen lost stock-in/adjust/supplier actions |
| WS-89 | P2 | design-parity | med | M | Open | Orders screen dropped date filter + CSV export |
| WS-90 | P2 | design-parity | med | M | Open | Order item list drops per-side edge thickness + breakdown |
| WS-91 | P2 | design-parity | med | M | Open | Price card lost krom material/service split; header lost due date |
| WS-92 | P2 | design-parity | med | M | Open | Branch cards dropped low-stock KPI; fake material/staff counts |
| WS-93 | P2 | i18n-copy | med | S | Done | Finance reports show raw payment-method code |
| WS-94 | P2 | completeness-stub | med | M | Open | User-detail Profil tab is read-only (no edit form) |
| WS-95 | P3 | design-parity | low | S | Open ⚠ | Users list dropped "Oxirgi kirish" column |
| WS-96 | P3 | design-parity | low | S | Open | Inventory tx table dropped "Filial" column |
| WS-97 | P3 | completeness-stub | low | M | Open | Catalog rows lost hide-from-customers toggle |
| WS-98 | P3 | i18n-copy | low | S | Done | Profile grant rows show raw branch-id fragment |
| WS-99 | P2 | testing | high | S | Done | Test formatStockQuantity metres (ships w/ WS-06) |
| WS-100 | P2 | testing | high | S | Done | Test parseDisplayQuantity round-trip (ships w/ WS-07) |
| WS-101 | P2 | testing | high | M | Open | Test orders.patchOrder list isolation (ships w/ WS-28) |
| WS-102 | P2 | testing | high | M | Open | Test orders 409 conflict + refetch (ships w/ WS-09) |
| WS-103 | P2 | testing | med | M | Open | Test finance dual-route tab reactivity (ships w/ WS-10) |
| WS-104 | P2 | testing | high | M | Open | Test discount form pre-seed (ships w/ WS-08/39) |
| WS-105 | P2 | testing | med | M | Open | Test notification filter + deep-link (ships w/ WS-48) |
| WS-106 | P2 | testing | high | M | Open | Test useWorkshopPermissions truth table (ships w/ WS-04) |
| WS-107 | P2 | testing | high | M | Open | Test permission route guard (ships w/ WS-05) |
| WS-108 | P3 | testing | med | M | Open | Test workshop store branch-context flows |
| WS-109 | P3 | testing | med | S | Open | Test finance store load + error capture |
| WS-110 | P3 | testing | med | M | Open | E2E: owner applies a discount, persists on reload |
| WS-111 | P3 | testing | med | M | Open | E2E: record income against order + standalone expense |
| WS-112 | P3 | testing | med | L | Open | E2E: revert/cancel-with-reason + 409 recovery |
| WS-113 | P1 | security | high | S | Partial | Temp password never cleared — leaks across users/logout (loadUser/loadUsers clear done; logout-reset → WS-114) |
| WS-114 | P2 | security | med | M | Open | Pinia stores not reset on logout — tenant PII residue |
| WS-115 | P3 | security | low | S | Open ⚠ | AuthFileImage object-URL leak under rapid fileId change |

---

## P1 — do first (permission gating + pipeline correctness)

### WS-01 · Order-detail lifecycle actions completely ungated — `permission-gating` · high · M
**Files:** `views/WorkshopOrderDetailView.vue`, `docs/ref/features/orders.md`
**Why:** All lifecycle actions are gated **only by `order.status`**, never by permission/branch — the only `is_owner` ref is cosmetic (`:44` worker label). `orders.md:298-302` requires approve/assign/collect/revert/cancel/discount → `manage_orders` and cutting/banding-done → `process_production`||`manage_orders`, all per-branch. A view-only or production-only staffer sees the full owner toolbar; every click 403s with a raw error.
**Fix:** Derive `order.branch_id`, compute per-branch caps from `workshop.branches.find(b=>b.id===order.branch_id).permissions` (or `is_owner`): `canManageOrders`, `canCompleteJob`. Wrap each button in a `v-if` + a "view-only" note. Centralize via WS-04.

### WS-02 · Finance/production screens have no in-screen permission gate — `permission-gating` · high · S
**Files:** `views/WorkshopFinanceView.vue`, `WorkshopFinanceProductionView.vue`, `apps/workshop/routes.ts`
**Why:** `WorkshopFinanceView.vue` has **zero** permission references; `onMounted` fires loadSummary/loadIncome/loadProduction for any workshop user. ProductionView loads on mount (`:33,40`) with no guard. The router guard checks only principal_type and routes carry no permission meta, so both are reachable by direct URL — exposing workshop-wide P&L and per-worker salary input as a raw error/blank (unlike Inventory/Catalog which show a clean no-access state).
**Fix:** Add `canViewFinance = is_owner || grants(manage_finance/view_finance_reports)` to both; render "Bu sahifa uchun ruxsatingiz yo'q" and skip loads when false (mirror WorkshopInventoryView). Also translate ProductionView (WS-13).

### WS-03 · Per-branch grants treated as workshop-wide (Finance/Dashboard) — `permission-gating` · high · M
**Files:** `views/WorkshopFinanceExpensesView.vue`, `WorkshopDashboardView.vue`, `docs/access-patterns.md`
**Why:** `WorkshopFinanceExpensesView.vue:56` `canManageFinance` is a workshop-wide `grants.some` with **no branch check**, while `branchOptions` (`:61-66`) enumerates every branch — so a staffer with manage_finance on branch A can pick branch B and the write 403s. Dashboard's canFinance/canInventory/canOrders also use workshop-wide `grants.some`. `access-patterns.md:121`: staff scope is "only branches they hold a relevant grant on"; `WorkshopBranchDetailView.vue:114-119` (`contextBranch.permissions.includes`) is the correct per-branch model.
**Fix:** Restrict finance write `branchOptions` to branches where the user holds the grant (or is_owner); hide the workshop-wide option for non-owners. Audit all `grants.some()` checks and switch branch-scoped ones to per-branch.

### WS-04 · No shared permissions composable (divergent gating) — `permission-gating` · med · M
**Files:** `WorkshopDashboardView.vue`, `WorkshopInventoryView.vue`, `WorkshopCatalogView.vue`, `WorkshopFinanceExpensesView.vue`, `WorkshopBranchDetailView.vue`
**Why:** The `is_owner || grants.some(g=>g.permission===X)` idiom is re-implemented inline across Dashboard/Inventory/Catalog/FinanceExpenses, with a **different** per-branch variant (`contextBranch.permissions.includes`) in BranchDetail (`:114-120`). No `src/composables/` and no `usePermissions` exist — this divergence is the root cause behind WS-01/02/03 and recurs on every new screen.
**Fix:** Add `shared/composables/useWorkshopPermissions.ts` exposing `canOnBranch(perm, branchId)`, `accessibleBranches(perm)`, `canWorkshopWide(perm)`, `isOwner` from `auth.me` + `workshop.branches`. Refactor the six screens onto it; per-branch is the default, workshop-wide an explicit opt-in. **Foundation for WS-01/02/03/05.**

### WS-05 · No route-level permission guard — `permission-gating` · med · M
**Files:** `app/createRoleApp.ts`, `apps/workshop/routes.ts`
**Why:** `createRoleApp.ts:94-108` `beforeEach` gates only on `isAllowedFor(role)` + `password_reset_required` — no permission check — and routes carry no `meta.permission`. A no-grant staffer can type `/workshop/settings`, `/workshop/finance`, `/workshop/branches` and the component mounts; only the in-screen `v-if` (where present) saves it — the single point of failure behind WS-01/02.
**Fix:** Add optional `meta.requires` (permission list / owner flag) per workshop route; enforce centrally in `beforeEach` from `auth.me.grants/is_owner`, redirecting unauthorized to `/workshop`. Keep in-screen empty states as the friendly fallback.

### WS-06 · Metres render with comma decimal → 2.5m shows "2,500 m" — `correctness-bug` · high · S
**Files:** `shared/formatters.ts`
**Why:** `formatStockQuantity` (`:23-31`) uses `Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 3, minimumFractionDigits: value%1000===0?0:3 }).format(value/1000)`. `uz-UZ` uses **comma** as the decimal separator, so 2500mm → "2,500 m" — visually identical to 2,500 metres for anyone reading comma as thousands grouping. Used across inventory, branch detail, dashboard low-stock, banding-queue.
**Fix:** Format metres with an explicit decimal point or drop the 3-digit zero-padding and show significant decimals (e.g. "2.5 m"), so edge-tape stock isn't misread by 1000×.

### WS-07 · Inventory tx log shows raw mm for edge materials — `correctness-bug` · high · S
**Files:** `views/WorkshopInventoryView.vue`
**Why:** In the Tranzaksiyalar tab, `:250` `{{ tx.quantity }}` and `:252` `{{ tx.balance_after }}` render raw mm (stock_unit) for edge materials, while the same view's stock columns correctly use `formatStockQuantity(item.on_hand, item.display_unit)` (`:183/186`) and BranchDetail does it right via `formatTransactionQuantity`. So `/inventory` shows "+3000" for a 3 m edge stock-in while the branch page shows "3 m".
**Fix:** Resolve each tx's `display_unit` via the material's StockItem (match `tx.material_id`) and wrap quantity/balance in `formatStockQuantity`, mirroring `formatTransactionQuantity`; keep the +/- sign.

### WS-08 · Discount re-edit corrupts percent discounts — `correctness-bug` · high · M
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** `discountKind` defaults to 'fixed' (`:29`) and the order watcher prefills from the resolved monetary value: `:240` `if (value.discount_tiyin > 0) discountValue = String(value.discount_tiyin)`. `discount_tiyin` is the computed amount, not the original input — a 10% discount reopens as a fixed tiyin sum with kind='fixed'; `applyDiscount` then submits `{kind:'fixed', value:<tiyin>}`, silently converting the percentage to a fixed amount that diverges on any later total change. No stored `discount_kind` exists to restore the mode.
**Fix:** Don't prefill from `discount_tiyin` — leave blank (force deliberate re-entry of kind+value) or surface the original `discount_kind/discount_value` from the API. At minimum reset `discountKind` to neutral and require an explicit kind pick. (Pairs with WS-39.)

### WS-09 · Version conflict: raw code, never refetches (retry loop) — `correctness-bug` · high · M
**Files:** `stores/orders.ts`, `views/WorkshopOrderDetailView.vue`
**Why:** All state-machine actions send `version: current.version`. `orders.mutate→captureError` (`:190-197`) maps only 403→'permission_denied' and otherwise sets `error.value` to `body.code`; it never special-cases a 409/version_conflict and never refetches. On conflict `currentOrder` keeps the stale version, buttons stay enabled, every retry conflicts again; the view renders the raw code. `orders.md:331,370` requires "this order changed — refresh and try again".
**Fix:** Detect the conflict status/code in captureError, set a dedicated `order_version_conflict` message, and re-run `loadWorkshopOrder(id)` so version refreshes. Render the friendly copy. (Mirror of client CB-11.)

### WS-10 · Finance dual-route tab doesn't react to income↔expenses nav — `correctness-bug` · high · S
**Files:** `views/WorkshopFinanceExpensesView.vue`
**Why:** `:25` initializes `activeTab` once from `route.path` with **no watch**. One component serves both `/finance/income` and `/finance/expenses` (Vue Router reuses the instance), so navigating expenses→income doesn't re-run setup — the user lands on the income URL but sees the expenses tab. High-stakes for money work.
**Fix:** `watch(() => route.path, p => activeTab = p.endsWith('/income') ? 'income' : 'expense', { immediate: true })`, or a computed off `route.path`.

### WS-11 · Workshop order list unbounded + server N+1 — `performance` · high · L
**Files:** `backend/app/modules/sales/service.py`, `stores/orders.ts`, `views/WorkshopOrdersView.vue`
**Why:** `orders.ts:258-274` `loadWorkshopOrders()` GETs `/workshop/orders` with no limit/offset, stores the whole array. Backend `list_workshop_orders` (`sales/service.py:329-342`) has **no `.limit()`** and does `[await _order_response(db, order, include_detail=False) for order in rows]` — one awaited DB call per order. `status='active'` caps it, but completed/cancelled/all return full history, downloaded, N+1-built, DOM-rendered at once. The app's most-used board.
**Fix:** Server-side pagination (limit/offset or cursor, default ~50, keep status filter), eager-load the relationships `_order_response` needs (selectinload/joinedload) to kill the N+1, paged/load-more table in the view.

### WS-12 · Stock transactions unbounded (client + server) — `performance` · high · M
**Files:** `backend/app/modules/inventory/service.py`, `stores/workshop.ts`, `views/WorkshopInventoryView.vue`, `WorkshopBranchDetailView.vue`
**Why:** `workshop.ts:376-383` `loadStockTransactions()` fetches with only an optional `material_id` filter — no date range, no limit. Backend `list_transactions` (`inventory/service.py:133-153`) `order_by(created_at.desc())` with **no `.limit()`** returns every transaction ever. Both views render all (`WorkshopInventoryView:231`). After months a single branch's tx tab loads the entire ledger.
**Fix:** Server-side pagination + date-range filter on the endpoint and query; page the table; default to recent N / last 30 days.

### WS-13 · 3 screens fully English — `i18n-copy` · high · M
**Files:** `WorkshopCuttingPlansView.vue`, `WorkshopCuttingPlanDetailView.vue`, `WorkshopFinanceProductionView.vue`, `apps/workshop/routes.ts`
**Why:** CuttingPlansView is 100% English (h1 "Cutting plans" `:19`), PlanDetailView English throughout (h1 "Read-only cutting plan" `:59`, tiles Waste/Panels/Edge/Cut length), ProductionView English (h1 "Worker production" `:50`, headers Worker/Panels cut/Cuts). Meanwhile `routes.ts` gives Uzbek `meta.title`s — so the browser tab contradicts the page heading. Every sibling view is Uzbek.
**Fix:** Translate all three to the app register ("Kesim rejalar", "PDF yuklab olish", tiles "Chiqindi"/"Panel"/"Krom"/"Kesim uzunligi", "Xodimlar mehnati"…); reuse the shared st-error/st-empty/card layout.

### WS-14 · English validation msgs + raw error codes shown to users — `i18n-copy` · high · M
**Files:** `WorkshopOrderDetailView.vue`, `WorkshopCuttingQueueView.vue`, `WorkshopFinanceExpensesView.vue`, `WorkshopUserDetailView.vue`, `stores/orders.ts`
**Why:** OrderDetail shows English validation literals ("Choose a cutter." `:136`, "Enter a non-negative integer discount value.") rendered at `:760-761`. Worse, `captureError` (`orders.ts:194`) copies `body.code` straight into the banner: CuttingQueue renders `cutting_complete_failed` (`:88`), FinanceExpenses `expense_save_failed`/`income_save_failed`/`ledger_void_failed` (`:562`), UserDetail `grants_save_failed`/`password_reset_failed` (`:378`) — raw dev tokens on Uzbek pages.
**Fix:** Translate the validation literals; add a shared Uzbek code→message map (extend `workshopUi.ts`), render the mapped sentence + trace_id as secondary. Never surface the raw code. (Workshop twin of client CB-01.)

### WS-15 · Topbar branch dropdown is a dead control — `ux-flow` · high · L
**Files:** `components/AppShell.vue`, `WorkshopOrdersView.vue`, `WorkshopInventoryView.vue`, `WorkshopDashboardView.vue`
**Why:** AppShell renders a prominent branch ProjectDropdown bound to `selectedContext` (`:331-335`), persisted per-session. Its **only** consumer is `workshopNavItems(...selectedBranchId)` to choose which nav links show. Every data view keeps its own independent `branchId` ref (Orders `branchId='all'` `:22`, Inventory `selectedBranchId`, Finance `branchId='all'`); none read `selectedContext`. Dashboard low-stock is hardwired to `branchIds[0]`. Changing the topbar branch reshapes the menu but never refocuses the data — two competing notions of "current branch".
**Fix:** Pick one source of truth: either make `selectedContext` the shared branch scope views read as their default filter (re-load on change), or relabel/hide it as a staff-nav permission selector. Make nav + data agree. (Ties to WS-49.)

### WS-16 · ProjectDropdown popover double-counts scroll, no edge clamp — `responsive` · high · M
**Files:** `components/ProjectDropdown.vue`
**Why:** `updatePopoverPosition` (`:37-45`) sets the teleported listbox to `position:fixed` but computes `top: rect.bottom + window.scrollY + 6`, `left: rect.left + window.scrollX` — with fixed (viewport-relative) positioning, adding scrollY/scrollX **double-counts**, so the panel jumps away from its trigger once the page scrolls. No clamp against `innerWidth`, so a 260px-min panel overflows the right edge on a 320-360px phone; recomputes only on 'resize' (`:113`), never 'scroll'. NotificationsMenu uses the correct `absolute right-0 w-[min(360px,calc(100vw-2rem))]`.
**Fix:** Drop `scrollX/scrollY` from the fixed math; clamp `left` to `Math.min(rect.left, innerWidth - panelWidth - 8)` with a bottom flip-up; recompute/close on scroll. Or switch to the NotificationsMenu pattern.

### WS-17 · Catalog table: no loading/error state (silent empty) — `states-errors` · high · S
**Files:** `views/WorkshopCatalogView.vue`, `stores/workshop.ts`
**Why:** `refreshCatalog` calls `workshop.loadBranchMaterials`, but the store's `loadBranchMaterials` (`:313-322`) has **no try/catch** and never touches `setupLoading/setupError/setupTraceId`. The template's skeleton/error blocks (`:143-154`) bind to those refs, which only loadSettings/loadManagedBranches set — so a failed catalog load throws an unhandled rejection and renders the "Bu filialga material qo'shilmagan" empty row, indistinguishable from a genuinely empty branch.
**Fix:** Give `loadBranchMaterials` its own `catalogLoading/catalogError/traceId` refs; set them in refreshCatalog; bind the view's skeleton/error to those.

### WS-18 · Settings save: no error/busy/success — `states-errors` · high · S
**Files:** `views/WorkshopSettingsView.vue`, `stores/workshop.ts`
**Why:** `save()` (`:26-32`) calls `updateSettings()` with no try/catch, and `updateSettings` (`workshop.ts:224-227`) also has none. No `saving` ref, no error shown, no `:disabled` busy. A failed PATCH yields an unhandled rejection and the owner sees nothing change, assuming it saved.
**Fix:** Add saving/saveError refs, wrap `save()` in try/catch capturing `apiTraceId`, render error/success, bind `:disabled=saving` — mirror `WorkshopBranchesView.createBranch`.

### WS-19 · Dashboard swallows all load errors — `states-errors` · high · M
**Files:** `views/WorkshopDashboardView.vue`
**Why:** `loadDashboard()` (`:49-58`) chains `.catch(() => undefined)` onto every call. The template has only a no-grant empty state + per-section empty/loading — **no error branch**. If orders or finance fails, KPIs render 0 (`?? 0`) and a "Buyurtma yo'q" empty row — indistinguishable from a genuinely empty workshop; "Yangilash" re-runs the same swallowed load.
**Fix:** Track `dashboardError/traceId` (set if any non-context critical load rejects); render a top-of-page error banner with trace_id + retry instead of universally swallowing.

### WS-20 · Dashboard sales chart is hardcoded fabricated data — `completeness-stub` · high · M
**Files:** `views/WorkshopDashboardView.vue`
**Why:** `:46` `const chartValues = [42,56,48,70,60,84,52,64,80,96,74,102,86,128]` is rendered as the 14-bar chart "Savdo · so'nggi 14 kun" (`:164-177`) — bars never reflect real data even though real income loads into the card sub-line. The 7K/14K/30K period buttons (`:151-159`) have **no @click** — decorative. Actively misinforms the primary decision-maker; identical for every workshop, every day.
**Fix:** Drive the bars from a real per-day income series (add a daily breakdown to the finance summary endpoint) and wire the period buttons to refetch, or remove the chart until a real source exists. (See WS-52/WS-61.)

---

## P2 — important

### WS-21 · Order board/table lost per-card status-action kebab — `design-parity` · high · L
**Files:** `views/WorkshopOrdersView.vue`, `prototype-full/workshop/orders.html`
**Why:** The prototype renders a `.menu-wrap` kebab on every board card (`:261-264`) and table row (`:287-292`) with per-state transitions (Tasdiqlash, Kesuvchi tayinlash, Kesish/Krom tugadi, Mijoz olib ketdi, revert/cancel). In Vue the board card (`:164-180`) is a bare RouterLink and the table's last cell is just "Tafsilotlar"; grep for menu-wrap returns nothing. The most-frequent workflow (advancing an order) became multi-step navigation.
**Fix:** Build a shared `.menu-wrap/.menu/.mi` dropdown primitive (keyboard-supported) and wire per-state transitions onto board cards + table rows, gated by WS-04. Pairs with WS-01.

### WS-22 · No toast system — every successful mutation is silent — `design-parity` · high · L
**Files:** `WorkshopOrderDetailView.vue`, `WorkshopCuttingQueueView.vue`, `WorkshopNotificationsView.vue`
**Why:** Grep for toast/snackbar across `web/src` returns zero. The prototype fires `toast(...)` on essentially every mutation; in Vue successful actions are silent (only failures surface `actionError`). On a shop floor the absence of confirmation causes double-clicks and duplicate actions. (Shared with client CB-14 — build one primitive for both SPAs.)
**Fix:** Shared toast primitive (Pinia store + fixed-position renderer in AppShell); emit success toasts after each mutation, mirroring the prototype copy.

### WS-23 · 5 tab UIs lack tab/tablist/tabpanel ARIA — `a11y` · high · M
**Files:** OrderDetail, BranchDetail, UserDetail, FinanceExpenses, Inventory views
**Why:** Every workshop tab strip is `<button class="tab" :class="{on}">` with no role/aria (OrderDetail `:325-350`, Branch `:582-593`, User `:214-239`, Finance `:286-303`, Inventory `:102-127`); panels (`v-if=activeTab`) have no `role=tabpanel`/`aria-labelledby`. Grep confirms zero tab ARIA in any workshop view.
**Fix:** Extract one shared TabList/Tab component (role=tablist/tab + `:aria-selected` + roving tabindex + ids; role=tabpanel + aria-labelledby; arrow-key focus); reuse across the five.

### WS-24 · Permission-matrix checkboxes have no accessible name — `a11y` · med · S
**Files:** `WorkshopUserDetailView.vue`, `WorkshopUsersView.vue`
**Why:** The grants matrix renders a bare `<input type=checkbox>` per permission×branch cell with no label/aria (UserDetail `:314-322`, Users `:234-241`). The permission name is a `<td>` row header, the branch a column `<th>`, with no id/headers association — so every checkbox is announced as just "checkbox, checked" across 7 perms × N branches, on the core access-management flow.
**Fix:** `:aria-label="`${permissionLabels[permission]} — ${branch.name}`"` per checkbox (labels in scope), or add scope/id to headers + `:headers` to each td.

### WS-25 · Mobile drawer: no focus trap/Escape/scroll-lock — `a11y` · med · M
**Files:** `components/AppShell.vue`, `web/src/assets/main.css`
**Why:** The workshop drawer (`:281-322`) is `role=dialog aria-modal=true` but nothing focuses into it, focus isn't trapped, no Escape handler, no focus restore (closeMobileNav just flips a boolean) — unlike ConfirmDialog. Opening it never toggles `body.modal-open`, so the long Orders/ledger page scrolls under the scrim. Same gaps in the admin drawer.
**Fix:** On open: move focus to the drawer, trap Tab, `@keydown.esc=closeMobileNav`, restore focus on close, toggle `body.modal-open`. Reuse ConfirmDialog's approach or a shared composable.

### WS-26 · Cutting-plan SVG rects focusable but unlabeled/no focus — `a11y` · med · M
**Files:** `components/CuttingPanelSvg.vue`, `web/src/assets/main.css`
**Why:** `:52-66` renders each placement as `<rect role=button tabindex=0 @keydown.enter/.space>` so every placement is in the tab order, but no `aria-label` (part name is a sibling text), no SVG focus style, and the parent `svg` has `role=img` conflicting with interactive children. A many-part plan floods the tab sequence with unlabeled stops. OrderDetail/PlanDetail already render a parallel accessible button list. (Same family as client CB-07.)
**Fix:** Make the rects non-focusable (`tabindex=-1`, drop role/handlers) and rely on the existing accessible placement list; or add `:aria-label` per rect, a `:focus` stroke, and drop `role=img`.

### WS-27 · complete cutting/banding can post null completed_by — `correctness-bug` · med · S
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** `completeCutting` (`:152-161`) sends `completed_by_user_id: completedById || current.assigned_cutter_user_id`. For an unassigned order (on-behalf completion allowed, `orders.md:376-378`) with empty `workerOptions`, the "Kim bajardi" select is hidden (`v-if workerOptions.length>0` `:692`), so both are null — the action posts null. `completeBanding` same shape. Production credit lost or opaque failure.
**Fix:** When both are null, require a worker pick before enabling "Kesish/Krom tugadi" (render the select even on-behalf) or default the completer to the acting user; validate non-null. (Pairs with WS-40.)

### WS-28 · Order mutations pollute clientOrders + reorder both lists — `correctness-bug` · med · S
**Files:** `stores/orders.ts`
**Why:** `patchOrder` (`:365-368`) prepends the mutated order to **both** `clientOrders` and `workshopOrders`; called from `mutate` (`:355`) for every workshop action. A workshop order gets inserted into `clientOrders` (cache pollution that can leak into the client SPA), and the workshopOrders row jumps to position 0 regardless of sort/filter, breaking the operator's scan position.
**Fix:** Split into role-specific patchers: workshop mutations update the existing `workshopOrders` row in place (map by id, no reorder) and don't touch `clientOrders`; mirror for client. (Related to client CB-104.)

### WS-29 ⚠ · Stock-in/adjustment post unvalidated quantities — `correctness-bug` · med · S
**Files:** `shared/formatters.ts`, `views/WorkshopBranchDetailView.vue`
**Why (verify):** `parseDisplayQuantity` (`:33-44`, reportedly already returns NaN for non-finite) still produces -5000 for "-5 m" and 0 is a valid finite parse. `recordStockIn` (`:306-308`) posts `parseDisplayQuantity(...)` with no >0/finite check; recordAdjustment/saveBranchMaterial min_stock same. A user can submit a 0 no-op tx, a negative quantity, or NaN (opaque server reject). **⚠ confirm current parseDisplayQuantity behavior first.**
**Fix:** Validate the parsed quantity (`Number.isFinite` and, for stock-in, `>0`), surfacing a field error before calling the store.

### WS-30 · Cut/band queues refetch full active list, filter client-side — `performance` · med · M
**Files:** `WorkshopCuttingQueueView.vue`, `WorkshopBandingQueueView.vue`, `stores/orders.ts`
**Why:** CuttingQueue `refresh()` calls `loadWorkshopOrders({status:'active'})` (`:27-29`) and `complete()` calls it again after each cuttingDone (`:38`); `queueOrders` then client-filters to `auth.me.principal_id` (`:16-23`). Banding identical. A cutter/edger on a low-end device pulls the entire active set (+ WS-11 N+1) every queue-open and job-finish, for their handful of rows.
**Fix:** Server-side `assigned_cutter_user_id`/`assigned_edger_user_id` filter (or a per-worker `/workshop/orders/queue`); at minimum patch the single mutated order returned by cuttingDone/bandingDone instead of full-refetching.

### WS-31 · loadBranchContext refetched on nearly every screen mount — `performance` · med · M
**Files:** `components/AppShell.vue`, `stores/workshop.ts`, multiple views
**Why:** AppShell already calls `loadBranchContext()` when `canLoadWorkshopContext` flips true (`:185-191`), yet Dashboard/Orders/Inventory/Catalog/Users/Finance/FinanceExpenses each re-call it on mount. `loadBranchContext` (`workshop.ts:194-208`) always hits `/workshop/branch-context` with no freshness guard — re-fetched on every in-app navigation.
**Fix:** Cache branch-context with a loaded flag / short TTL; views call `ensureBranchContext()` (no-op when populated); AppShell owns the initial load; mutations (setBranchStatus) invalidate.

### WS-32 · Inventory eagerly fetches stock+all-tx+suppliers on mount — `performance` · med · S
**Files:** `stores/workshop.ts`, `WorkshopInventoryView.vue`, `WorkshopBranchDetailView.vue`
**Why:** `loadInventory()` (`:392-404`) does `Promise.all([loadStock, loadStockTransactions, loadSuppliers])`. Inventory defaults to the Stock tab but calls loadInventory on mount and every branch switch — so the unbounded transactions fetch (WS-12) + suppliers happen up-front even though Tx/Suppliers tabs are pure client renders.
**Fix:** Lazy per tab: stock on mount; transactions/suppliers only when those tabs first activate. Keep `loadInventory` for genuine all-three cases.

### WS-33 · Cutting-plans & production screens unreachable (no nav) — `completeness-stub` · med · S
**Files:** `app/workshopNav.ts`, `WorkshopCuttingPlansView.vue`, `WorkshopFinanceProductionView.vue`, `WorkshopFinanceView.vue`
**Why:** `workshopNav.ts` has no 'cutting-plans' and no 'finance/production' entries. The routes + views exist and are complete (plans browser, per-worker salary report) but are reachable only by URL. The FinanceView "Xodimlar mehnati" card renders a preview with no "see full report" link to the dedicated screen.
**Fix:** Add a "Kesim rejalar" nav entry (gated process_production/owner) and a Moliya nav item for the production report (gated view_finance_reports/manage_finance); link the production card to the full screen. Decide whether the standalone cutting-plans browser is wanted vs the per-order Chizma tab.

### WS-34 · Orphaned WorkshopFinanceIncomeView (dead code) — `completeness-stub` · med · S
**Files:** `WorkshopFinanceIncomeView.vue`, `apps/workshop/routes.ts`, `WorkshopFinanceExpensesView.vue`
**Why:** Grep for `WorkshopFinanceIncomeView` across `web/src` returns **zero** references — no route imports it; `/finance/income` lazy-loads the Expenses view instead. The orphan is a complete 11KB income screen, fully English ("Income", "Record income", raw enums), **no permission gating**, duplicating the live Uzbek "Tushumlar" tab. It will drift, inflates the bundle as a never-loaded chunk, and is a foot-gun if ever routed (ungated money writes).
**Fix:** Delete it (capability lives in the expenses view's income tab). If a dedicated income screen is wanted, wire + gate + translate deliberately. Confirm against `finance.md` first. (Ties to WS-10/WS-71.)

### WS-35 · Settings "Logo" file input is a dead control — `completeness-stub` · med · M
**Files:** `WorkshopSettingsView.vue`, `stores/workshop.ts`
**Why:** `:79-82` renders `<input type=file>` labeled "Logo" with no v-model/@change; `save()` (`:26-32`) sends only `{name, phone, address}`. The header advertises "nom, logo, telefon, manzil". The backend exposes `logo_file_id` (`workshop.ts:39`) — the slot exists but the upload path is unimplemented; the owner picks a file, clicks Saqlash, silent no-op.
**Fix:** Wire the input through the files store/blob upload to get a file id, send `logo_file_id` in updateSettings, show the current logo (mirror the receipt upload in BranchDetail). If out of scope, remove the input + "logo" wording.

### WS-36 · Topbar global search + ⌘K non-functional — `completeness-stub` · med · M
**Files:** `components/AppShell.vue`
**Why:** `:337-345` renders the topbar search input (placeholder "Buyurtma, mijoz, xodim yoki material…") with a ⌘K badge, but no v-model/@input/@keydown and no global-search handler anywhere. The prototype wired it; the Vue version kept the chrome, dropped the behavior — a prominent broken affordance on every screen.
**Fix:** Implement a global search wired to the list endpoints behind ⌘K, or remove the input + ⌘K hint until built.

### WS-37 · "Mijoz olib ketdi" terminal action has no confirmation — `states-errors` · high · S
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** `:725-733` renders the ready→completed button calling `markCollected()` directly (`:174-178`). Per `orders.md:76` completed is terminal, stamps picked_up_at, no revert. Only revert/cancel open a ConfirmDialog (`:811-830`); approve/assign/cutting-done/banding-done **and** mark-collected all execute on a single click. A misclick on a busy board permanently closes the order with no in-app undo.
**Fix:** Gate `markCollected` behind a ConfirmDialog summarizing the order + finality. Consider a lightweight confirm for cutting-done/banding-done too (they decrement stock, reversible only via revert).

### WS-38 · Fresh production staff land on an empty app — `ux-flow` · high · M
**Files:** `app/workshopNav.ts`, `WorkshopCuttingQueueView.vue`, `WorkshopDashboardView.vue`
**Why:** `workshopNav.ts:53` gives cutting/banding nav to process_production but the orders link requires view_dashboard/manage_orders (`:50`). The cutting queue lists only orders assigned to `me` (`:16-23`), and assignment requires manage_orders. So before an owner assigns them, a cutter sees an empty queue (`:81-84`) and zero other actionable screen — logs in to an empty-feeling app with no way to discover waiting work.
**Fix:** Surface a read-only "awaiting assignment" list to production staff, or strengthen the empty-queue copy ("A manager must assign you a job…") and add a dashboard tile so the landing isn't blank.

### WS-39 · Discount can only be added, never edited/removed — `ux-flow` · med · M
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** The discount card renders only while status is new/confirmed (`:766`) and only offers "Chegirma qo'shish"→applyDiscount (`:203-223`). Once a discount exists it shows as a read-only price-breakdown row (`:420-426`) with no control to change/clear, and the form disappears after confirmed. An owner who fat-fingers a value has no correction except cancel+re-order (changes the order number). Closely tied to WS-08.
**Fix:** Allow editing the existing discount (prefill kind/value/reason — coordinate with WS-08) and a "remove discount" action while still new/confirmed.

### WS-40 · Queue "done" can't credit who did the work — `ux-flow` · med · M
**Files:** `WorkshopCuttingQueueView.vue`, `WorkshopBandingQueueView.vue`
**Why:** The queue cards' inline complete buttons hard-wire credit to the assignee: Cutting `:34-38` sends `assigned_cutter_user_id`; Banding `:31-35` `assigned_edger_user_id`. The order-detail flow exposes a "Kim bajardi" select so an owner can credit a different worker, and `orders.md:99-105` says the chosen user gets production-report credit (the salary input). When an owner clears the queue on behalf of staff, credit is wrong.
**Fix:** Add an optional "who did it" selector to the queue cards (at least for owners), mirroring the detail FormSelect, defaulting to the assignee.

### WS-41 · Income entry can't show order's outstanding balance — `ux-flow` · med · M
**Files:** `WorkshopFinanceExpensesView.vue`, `WorkshopOrderDetailView.vue`
**Why:** The income form's order picker (`:79-89`) lists orders by number/total only, amount is free entry with hint "to'liq yoki qisman". The order's settlement (total/recorded/balance, `OrderSettlement` `orders.ts:69-73`, shown on order detail) is never surfaced in the income form — so an accountant recording a partial payment must cross-check the order detail in another tab to avoid double-recording.
**Fix:** When an order is selected, fetch/display its settlement balance and prefill/cap the amount to the outstanding (with an explicit overpayment override).

### WS-42 · PDF download: no error/busy across queues & detail — `states-errors` · med · M
**Files:** `stores/orders.ts`, `stores/cutting.ts`, OrderDetail/CuttingQueue/BandingQueue views
**Why:** `downloadPdf` (`orders.ts:370-378`, `cutting.ts:350-358`) calls `api.blob` and throws on non-2xx with no try/catch; every call site invokes it bare in `@click` with no loading flag (OrderDetail `:318/581`, CuttingQueue `:121/168`, BandingQueue `:125`). On failure the worker clicks and nothing downloads — no spinner, no error. (Same root as client CB-17/CB-111 — fold into a shared downloadBlob with attach-anchor + async revoke.)
**Fix:** Add `pdfLoading/pdfError`, wrap in try/catch capturing `apiTraceId`, disable while in flight, surface an inline error.

### WS-43 · Branch settings/pricing save error never rendered (1st form) — `states-errors` · med · S
**Files:** `views/WorkshopBranchDetailView.vue`
**Why:** `saveBranchSettings` (`:382-406`) does the pricing PUT and sets `settingsError='branch_settings_save_failed'` on failure, but the only template binding of `settingsError` is inside the **second** form ("Mijozlarga ko'rinish" `:1253-1258`). The first form ("Filial ma'lumotlari va narxlar" `:1126-1216`) renders no error — a failed branch-info/pricing save shows nothing and the owner believes pricing updated (risking wrong client quotes). Store `updateBranchPricing` also has no try/catch.
**Fix:** Render the error at the bottom of the first form too (or a dedicated `detailsError` ref) with trace_id; add success feedback.

### WS-44 · Receipt upload failure has no feedback — `states-errors` · med · S
**Files:** `views/WorkshopBranchDetailView.vue`, `stores/files.ts`
**Why:** `onReceiptFile` (`:425-431`) calls `await files.upload(...)` with no try/catch. `files.upload` (`files.ts:26-41`) sets `files.error` and rethrows, but the view never reads `files.error`/`files.uploading` — a failed receipt upload is an unhandled rejection and the input is silently left without a receipt id. The storekeeper submits believing the receipt attached.
**Fix:** Wrap `onReceiptFile` in try/catch, show `files.error` (or a local error) near the input, reflect `files.uploading` as disabled/busy.

### WS-45 · User/finance action errors omit trace_id — `states-errors` · med · S
**Files:** `WorkshopUserDetailView.vue`, `WorkshopFinanceExpensesView.vue`, `WorkshopUsersView.vue`, `stores/finance.ts`
**Why:** User mutations (replaceGrants/blockUser/resetPassword/revoke) render `{{ actionError }}` with no trace (`UserDetail:377-379`) and the store never captures a traceId (`workshop.ts:514-565`). Finance create/void render a static code with no trace (`FinanceExpenses:561-563`) and the finance store never sets `finance.traceId` — even though the same screen's list-load error DOES show it. Security/money failures support can't trace. Overlaps WS-14.
**Fix:** Have the user/finance store mutations capture `apiTraceId` into a dedicated ref on failure (or rethrow ApiError) and render the trace alongside the message, as the order/queue views do.

---

## P3 — nice-to-have

### WS-46 · User-detail misreports context-load failure as "not found" — `states-errors` · low · S
**Files:** `WorkshopUserDetailView.vue`, `stores/workshop.ts`
**Why:** `load()` (`:50-57`) awaits `loadBranchContext()` then `loadUser()`. `loadBranchContext` (`:194-208`) **throws** on failure, so if context fails loadUser never runs, `workshop.error` stays null, `selectedUser` stays null, and the template falls to the "Xodim topilmadi" empty state. A transient context failure makes an existing staffer appear deleted.
**Fix:** Wrap `load()` in try/catch (or `loadBranchContext().catch(()=>undefined)` like other views) and set a real error/traceId.

### WS-47 · Cutting-plan detail blank when plan has no result — `states-errors` · med · S
**Files:** `WorkshopCuttingPlanDetailView.vue`, `stores/cutting.ts`
**Why:** Template branches are loading (`:74`), permission_denied (`:77`), error (`:81`), then `v-else-if=plan && result` (`:85`) with **no final v-else**. `loadWorkshopPlan` only sets error on a thrown ApiError; if the API returns 200 with a null result, or leaves `currentWorkshopPlan` null without error, the page shows only the header — no empty/not-found state.
**Fix:** Add a final `v-else` empty/not-found block ("Kesim reja topilmadi").

### WS-48 · Notifications can't deep-link finance/stock; inventory chip broken — `ux-flow` · low · S
**Files:** `WorkshopNotificationsView.vue`
**Why:** `destination()` (`:42-46`) returns a route only for 'order'/'branch'; finance/stock notifications return null, so `openItem` marks them read but navigates nowhere. The 'inventory' filter chip (`:23-29`) matches `event_code.includes('inventory')` but stock codes use 'stock' — selecting "Ombor" returns an empty list despite stock alerts existing.
**Fix:** Map stock→`/workshop/inventory`, finance→`/workshop/finance/expenses`; make the inventory filter match `'stock'`; add a unit test over the filter predicate; don't pretend-navigate on null destination.

### WS-49 · Dashboard low-stock scoped to branchIds[0]; recent = active-only — `correctness-bug` · med · M
**Files:** `WorkshopDashboardView.vue`
**Why:** `loadDashboard` (`:49-58`) loads stock only for `branchIds[0]` (`:55-57`) regardless of branch count, so "Pastdagi zaxiralar" under-reports for multi-branch owners while KPIs reflect all branches. `recentOrders` (`:43`) slices `workshopOrders` loaded with `status:'active'` (`:52`), so a just-completed order never appears in "recent".
**Fix:** Compute low-stock from a workshop-wide summary (or scope the card to the selected branch and label it — ties to WS-15); load "recent orders" without the active-only filter.

### WS-50 · Material swatches all render the same default gradient — `design-parity` · med · M
**Files:** `WorkshopInventoryView.vue`, `WorkshopCatalogView.vue`, `web/src/assets/main.css`
**Why:** Inventory `:174` and Catalog `:174` render `<span class="sw">` with no `sw-N` modifier, so every material shows the single default `.sw` gradient (`main.css:2485-2492`). The prototype gives each material its own swatch (`inventory.html:203`) and main.css ports `sw-1..sw-6`, but nothing applies them because the material model carries no swatch/color field. The visual scanning cue is lost.
**Fix:** Add a swatch/color descriptor to the material model and map to the existing `sw-1..sw-N` classes (or a CSS custom property).

### WS-51 · Order board lost assigned-worker chips — `design-parity` · med · S
**Files:** `WorkshopOrdersView.vue`, `prototype-full/workshop/orders.html`
**Why:** The prototype renders worker chips via `workerChip()` (`orders.html:224-228`): `.pill p-cut` scissors+cutter initials, `.pill p-eb` layers+edger initials. Vue replaces this with plain text `assignedText()` (`:56-63`) on board cards (`:178`) and the table "Mas'ul" cell (`:214-216`). A manager can no longer see at a glance who's assigned.
**Fix:** Render assigned cutter/edger as colored pills (p-cut/p-eb) with stage icon + initials on board cards and in the Mas'ul column.

### WS-52 · Dashboard chart dropped SVG/gridlines/tooltips/legend — `design-parity` · med · M
**Files:** `WorkshopDashboardView.vue`, `prototype-full/workshop/dashboard.html`
**Why:** The prototype (`dashboard.html:201-223`) renders an SVG chart with gridlines, baseline, dated x-ticks, per-bar `<title>` tooltips, and a Bugun/Eng yuqori/Boshqalar legend. Vue (`:163-183`) replaces all of it with plain spans — no SVG/gridlines/tooltips/legend; only date labels survive. Depends on WS-20 (real data first).
**Fix:** Port the prototype's SVG chart structure once wired to real data (WS-20).

### WS-53 · Production report dropped period column + "Maosh yozish" — `design-parity` · low · S
**Files:** `WorkshopFinanceView.vue`, `prototype-full/workshop/finance.html`
**Why:** The prototype "Xodimlar mehnati" table (`finance.html:96-99,184-193`) has Xodim/Davr/Panel/Krom(m) + a trailing "Maosh yozish" action jumping to expenses prefilled. Vue's production table (`:303-318`) has Xodim/Panel/Kesim/Krom — dropped the Davr column and the per-row payroll shortcut, though the card copy still tells the accountant to record salary as an expense.
**Fix:** Add the period column and a "Maosh yozish" action linking to `/workshop/finance/expenses` prefilled for that worker.

### WS-54 · Cutting-plan SVG uses off-brand blue, not teal — `design-parity` · low · S
**Files:** `components/CuttingPanelSvg.vue`, `prototype-full/workshop/order-detail.html`
**Why:** `CuttingPanelSvg.vue` hardcodes a slate/blue palette: panel stroke `#334155` (`:49`), placement fill `#dbeafe`/active `#c8e8e3` stroke `#2563eb` (`:58-59`), label `#0f172a` (`:67`). The prototype's sheet uses the teal brand family (`--color-accent`). None of the brand tokens are used, so this signature screen reads in a generic blue. (Same component as client CB; coordinate.)
**Fix:** Replace the raw hex with `var(--color-accent)`, `var(--color-accent-tint)`, `var(--color-ink)`.

### WS-55 · Mobile chrome uses ☰/× glyphs instead of SVG icons — `design-parity` · low · S
**Files:** `components/AppShell.vue`
**Why:** The mobile menu trigger is a ☰ character (`:327`) and the drawer close is × (`:297`), whereas the prototype and the rest of the shell emit real SVG (desktop/mobile nav via `iconPath` at `:265/315`). On the small-screen floor surface they render as unstyled typographic chars.
**Fix:** Replace ☰/× with the inline menu/x SVG icons used elsewhere.

### WS-56 · English fallback strings — `i18n-copy` · med · S
**Files:** `stores/cutting.ts`, `WorkshopFinanceProductionView.vue`, `WorkshopCuttingPlanDetailView.vue`
**Why:** `cutting.ts` `materialLabel()` returns "No material" (`:142`) and builds "… mm edge" (`:147`); ProductionView `edgeLengths()` returns "No banding metres" (`:28`) shown in a table cell; PlanDetailView `panelTitle()` falls back to "Panel" (`:39`). English fragments render in empty/missing states on Uzbek pages. Overlaps WS-13.
**Fix:** Uzbek fallbacks ("Material yo'q", "… mm krom", "Krom metri yo'q"); keep domain terms (panel, krom) per the English-canon term rule. Fold into WS-13 where files overlap.

### WS-57 · Inventory/Catalog/Users client-filter full list redundantly — `performance` · low · M
**Files:** `WorkshopInventoryView.vue`, `WorkshopCatalogView.vue`, `WorkshopUsersView.vue`, `stores/workshop.ts`
**Why:** Inventory `filteredStock` (`:43-50`) re-filters client-side though `loadStock` accepts server `search/low_stock` (`workshop.ts:363-374`) the view never passes; Catalog `filteredRows` (`:59-65`) filters client-side **and** passes search to `loadBranchMaterials` on @input (`:135-136`) — double filtering; Users `filteredUsers` (`:62-81`) is client-only with no server filter. Each keystroke re-scans the whole list.
**Fix:** Pick one filtering layer per list — prefer debounced server-side for lists that grow (stock/catalog/users) and drop the redundant client recompute, or keep client-only and stop passing server params.

### WS-58 · Finance fires 3 sequential requests; expenses double-fetch — `performance` · low · S
**Files:** `WorkshopFinanceView.vue`, `WorkshopFinanceExpensesView.vue`, `stores/finance.ts`
**Why:** FinanceView `refresh` (`:105-115`) awaits loadSummary THEN loadIncome THEN loadProduction sequentially (independent, separate store fields), on mount and every period/branch/refresh. FinanceExpenses `refresh` awaits loadExpenses then loadIncome regardless of activeTab — double-fetch on every Qo'llash. The store also advertises min/max amount params no UI surfaces.
**Fix:** `Promise.all` the independent fetches; load only the active tab's ledger on refresh (lazy the other on tab switch); expose or remove the unused min/max params.

### WS-59 · Inline forms far from trigger, no focus move — `a11y` · med · M
**Files:** `WorkshopFinanceExpensesView.vue`, `WorkshopOrderDetailView.vue`
**Why:** In finance, "Bekor qilish" on a row sets `voidTarget` rendering a void form at the page bottom (`:544-559`); focus stays on the scrolled-away trigger with no handoff. The Tushum/Xarajat buttons toggle a create form (`:305/346`) with no focus move; in order detail the discount/assign panels render in the aside (`:766-786,667-689`) without focusing the first field. Keyboard/SR staff must Tab through the whole table.
**Fix:** On open, focus the form's first field (ref + nextTick), scroll into view, restore focus on cancel/submit. For the void flow, reuse the focus-managed ConfirmDialog.

### WS-60 ⚠ · Muted text fails AA; low-stock/destructive color-only — `a11y` · low · S
**Files:** `web/src/assets/main.css`, `WorkshopInventoryView.vue`, `WorkshopBranchDetailView.vue`
**Why (verify):** `--color-ink-muted (#748196)` on `#f4f6f8`/white ≈ 3.4:1 — below 4.5:1 AA for the 11-12px text it's applied to. Low-stock cell recolors the number via warn-text with no non-color cue (`Inventory:182-184`); activate/deactivate toggles swap only border/background color (`BranchDetail:746-756,1069-1080`). **⚠ contrast not pixel-verified.** (Same token as client CB-34.)
**Fix:** Darken `--color-ink-muted` to ≥4.5:1 (or restrict to large/bold text); add a non-color indicator (icon/text) to low-stock cells and the toggles.

### WS-61 · Dashboard chart hidden from AT; range toggles no aria-pressed — `a11y` · low · S
**Files:** `WorkshopDashboardView.vue`
**Why:** `:163-184` renders the 14-day chart as `aria-hidden` spans (whole bar group hidden from AT, only three static dates labeled); the 7K/14K/30K range buttons (`:151-159`) have no `aria-pressed`. SR users get no info from the headline chart. Coupled with WS-20/WS-52.
**Fix:** Add an aria-label/sr-only summary (or data table) to the chart container and `:aria-pressed` to the range buttons. Best resolved with WS-20/WS-52.

### WS-62 · Branch-close confirm uses a stale active-orders count — `correctness-bug` · low · S
**Files:** `WorkshopBranchDetailView.vue`
**Why:** `changeBranchStatus` (`:408-423`) and the confirm checkbox warn with `selectedBranch?.active_orders_count` (`:1243`). `selectedBranch` is only loaded on mount/branchId change. If the operator leaves the settings tab idle while orders arrive, then closes the branch, the count is stale — they may close a branch with since-added active orders, surprising clients mid-production.
**Fix:** Re-fetch the branch (or `active_orders_count`) when the settings/status form opens, or display "as of <load time>" and re-validate server-side.

### WS-63 · createUser force-clears loading + bumps request id — `correctness-bug` · low · S
**Files:** `stores/workshop.ts`
**Why:** `loadUsers` uses a request-id guard correctly (`:461-481`), but `createUser` (`:483-495`) does `usersLoadRequestId+=1; loading=false; upsertUser(...)` outside any try/finally, no awaited reload, no error capture. Force-setting `loading=false` can flip a genuine loadUsers spinner off prematurely; a failed POST leaves `error` null while the caller's await rejects. Edge-timing only.
**Fix:** Keep the id bump but stop manually setting loading in createUser; re-run `loadUsers()` (which owns loading) after a successful create, or wrap in proper error capture.

### WS-64 · Notifications mark-read failures silent; load error no trace — `states-errors` · low · S
**Files:** `WorkshopNotificationsView.vue`, `stores/notifications.ts`
**Why:** `openItem` (`:48-52`) calls markRead with no try/catch then navigates; `markAll` (`:54-57`) no try/catch. Store markRead/markAllRead (`:56-74`) have no try/catch and never set error. The list error block (`:88-91`) shows a generic message with **no trace_id**, unlike every other workshop screen. (Same family as client CB-26.)
**Fix:** Add a `traceId` ref to the notifications store and surface it; wrap markRead/markAllRead so failures surface a small inline toast (WS-22).

### WS-65 · Branch create/settings saves give no success feedback — `ux-flow` · low · S
**Files:** `WorkshopBranchesView.vue`, `WorkshopBranchDetailView.vue`
**Why:** `createBranch` (`:42-65`) resets the form and closes the panel on success but no confirmation toast and no navigation to the new branch — the user is left scanning the list. `saveBranchSettings` (`:382-406`) silently writes branch info + pricing with no success feedback (only a mis-bound error path, WS-43). Owners can't tell whether a save persisted. Largely subsumed by WS-22.
**Fix:** Add a success affordance after createBranch (toast or auto-navigate to `/workshop/branches/:id`) and a transient "saved" state after saveBranchSettings/saveSupplier/saveBranchMaterial. Resolve with WS-22.

### WS-66 · Production queues empty-without-explanation; buttons ungated — `permission-gating` · low · S
**Files:** `WorkshopCuttingQueueView.vue`, `WorkshopBandingQueueView.vue`
**Why:** CuttingQueue `:16-23` / BandingQueue `:15-22` filter to orders assigned to `me` (good per-user scoping) but have **no process_production check**. A staffer without that permission always sees the generic empty state, and the "Kesish/Krom tugadi" buttons call cuttingDone/bandingDone with no permission guard. Per-user filter makes it largely harmless today, but direct URL still mounts the screen.
**Fix:** Show a tailored empty state ("Ishlab chiqarish ruxsati yo'q") when the user lacks process_production on any branch, and gate the complete buttons on the order's branch.

### WS-67 · view_dashboard-only staff get full Orders management — `permission-gating` · low · S
**Files:** `app/workshopNav.ts`, `WorkshopOrdersView.vue`
**Why:** `workshopNav.ts:50` adds "Buyurtmalar" when a branch has view_dashboard OR manage_orders, so a view-only-dashboard staffer gets the full orders link, but WorkshopOrdersView exposes detail/assignment flows intended for manage_orders. The view doesn't branch on view_dashboard vs manage_orders to restrict to read-only. Tied to WS-01.
**Fix:** Decide whether view_dashboard alone should expose the orders list; if yes, render the view read-only for non-manage_orders holders; if no, gate the nav item on manage_orders only.

### WS-68 · Inventory/Catalog deep-link staff with owner-flavoured CTAs — `permission-gating` · low · S
**Files:** `WorkshopInventoryView.vue`, `WorkshopCatalogView.vue`, `WorkshopBranchDetailView.vue`
**Why:** Inventory shows "Filial omborini boshqarish" (`:81-87`) and per-row "Boshqarish" linking to `/workshop/branches/:id`; Catalog shows "Material qo'shish" (`:107-114`) for any staffer with manage_inventory/manage_catalog. BranchDetail re-gates correctly (so the destination is safe), but the CTA labels promise capabilities the user may only partially hold, and BranchesView itself is owner-only — making the breadcrumb context confusing. A papercut.
**Fix:** Keep the deep-links; soften CTA copy for staff ("Filial omborini ochish") and ensure the BranchDetail back/breadcrumb doesn't route staff to the owner-only branches list.

### WS-69 · Orders kanban: no phone breakpoint — `responsive` · low · M
**Files:** `WorkshopOrdersView.vue`, `web/src/assets/main.css`
**Why:** `.board` uses `repeat(5, minmax(210px, 1fr))` with `overflow-x:auto` (`main.css:2214-2228`) and renders all 5 columns unconditionally (`:158-185`). 5×210px ≈ 1050px, so on a 360px phone the default board is a wide horizontal-scroll strip with no breakpoint that stacks or switches to the table. (Mirrors the prototype, which also lacks a phone fallback.)
**Fix:** Default Orders to table mode on small viewports, or `@media (max-width:640px)` collapsing `.board` to a single column with status headers as dividers.

### WS-70 · Missing prototype's `card:has(.tbl)` overflow fallback — `responsive` · low · S
**Files:** `web/src/assets/main.css`, `prototype-full/assets/app.css`
**Why:** `.tbl { min-width: 680px }` and `.card { overflow: hidden }` (`main.css:1926/1621`) mean an unwrapped table in a card is clipped and forces horizontal page overflow. The prototype guards this with `@media (max-width:720px){ .card:has(> .tbl){ overflow-x:auto } }` (`app.css:305-311`); grep for `:has(`/`max-width: 720px` in main.css returns nothing. Latent (every `.tbl` is manually wrapped today) but a foot-gun.
**Fix:** Port the prototype's `@media (max-width:720px) .card:has(> .tbl) { overflow-x:auto }` into main.css.

### WS-71 · /finance/income route redundant (renders Expenses view) — `completeness-stub` · low · S
**Files:** `apps/workshop/routes.ts`, `WorkshopFinanceExpensesView.vue`
**Why:** Route `workshop-finance-income` (`/workshop/finance/income`, title "Tushum") maps to `WorkshopFinanceExpensesView` — same component as `/finance/expenses`; the view opens the income tab when the path ends `/income` (`:25` — but see WS-10 missing reactivity). workshopNav links only `/finance/expenses`, so the income route is reachable only by URL and redundant with the tab toggle.
**Fix:** Drop the redundant route (the tab toggle covers income), or keep it as an explicit deep-link and document that both finance routes resolve to the combined view. Resolve with WS-10/WS-34.

---

# Round 2 additions (WS-72 – WS-115)

Four lenses: spec-conformance (orders-production + finance/inventory/catalog) ·
proto-screens · testing · security. Many testing items are **regression guards
meant to ship with a specific R1 fix** — implement the named WS-fix and its test
together.

## P1 (round 2)

### WS-72 · Banding queue reads null snapshot → "krom rejasi"/raw UUIDs — `spec-conformance` · high · M
**Files:** `views/WorkshopBandingQueueView.vue`, `stores/orders.ts`
**Why:** `orders.md:328` requires the edger card to show metres by shop edge material. `edgeLine()` (`:41-45`) reads `order.edge_length_snapshot`, which the backend only sets at edge_banding→ready (`sales/service.py:699`) — so for every not-yet-banded order in this queue it is null → `:43` always returns "krom rejasi". Even when populated, `:44` renders the raw edge-material **UUID** as the key. The correct source (`cutting_result.edge_consumed_shop_by_material`, `cutting.ts:65`) lives only on OrderDetail.
**Fix:** Source per-material metres from the order's cutting result, resolve each `material_id` to a "thickness mm color" label via the snapshot — add the fields to OrderSummary or lazily load the result for queue cards. **Related:** WS-30/51/66.

### WS-74 · No re-assign/change cutter or edger after confirmed — `spec-conformance` · high · M
**Files:** `views/WorkshopOrderDetailView.vue`
**Why:** `orders.md:105` allows re-assignment until the job is done; `:299` lists "Assign / change edger" as a distinct confirmed action. The confirmed block (`:667-689`) renders only one "Tayinlash va boshlash" button that always assigns the cutter AND fires the cutting transition; the cutting/edge_banding blocks (`:691-723`) expose only the completer picker + done/revert/cancel — **no change-cutter/edger control**. The backend already permits assign while status ∈ {CONFIRMED, CUTTING, EDGE_BANDING} (`sales/service.py:551`) — a pure missing UI affordance blocking a documented operation.
**Fix:** Add a "change cutter"/"change edger" control (FormSelect + `orders.assign` without transition) in the cutting and edge_banding states; at confirmed allow assigning/changing the edger independently of the cutter-assigns-and-starts action.

### WS-78 · Income/expense Edit absent (backend PATCH exists) — `spec-conformance` · high · M
**Files:** `views/WorkshopFinanceExpensesView.vue`, `stores/finance.ts`
**Why:** `finance.md:44,70` and `entities/finance.md:40-41,72` require an audited "Edit while recorded"; the UX (`finance.md:114-120`) lists "Row actions: Edit · Void". The ledger renders only a void button (`:461-467` expenses, `:524-531` income); the store (`finance.ts:104-261`) has create/void but **no update**. The backend already implements both edits (`finance/routes.py:97` PATCH /income/{id}, `:156` PATCH /expenses/{id}). The accountant's primary correction path is missing — only void+re-record.
**Fix:** Add `updateIncome/updateExpense` to `finance.ts` calling the existing PATCH endpoints + a "Tahrir" row action that reopens the form pre-filled and PATCHes when `status==='recorded'`. **Related:** WS-39.

### WS-79 · Production report renders raw edge-material UUIDs — `spec-conformance` · high · M
**Files:** `views/WorkshopFinanceProductionView.vue`, `backend/app/modules/finance/schemas.py`, `sales/service.py`
**Why:** `finance.md:84-86` requires banding metres broken down by edge material and rolled up by thickness. `WorkerProductionRow` (`finance/schemas.py:114-120`) carries only `edge_length_by_material: dict[str,int]` keyed by raw `material_id` (`sales/service.py:427-428`) with no name/thickness, and the view renders the UUID key verbatim (`:26-30`). The accountant sees "a1b2c3d4-…: 12 m" — defeating the report's per-material/per-thickness salary purpose. **Distinct from WS-53.**
**Fix:** Resolve each edge `material_id` to name + thickness in the service, return a by-material(name) breakdown + a by-thickness rollup; update `WorkerProductionRow` and the view.

### WS-113 · Temp password never cleared — leaks across users/logout — `security` · high · S
**Files:** `stores/workshop.ts`, `WorkshopUserDetailView.vue`, `WorkshopUsersView.vue`
**Why:** `workshop.ts:173` `lastTempPassword` is set at `:493` (createUser) and `:534` (resetPassword) but **never reset** (grep: only those writes + 3 reads). It renders as a "Yangi vaqtinchalik parol" banner gated only on truthiness (`UsersView:260`, `UserDetailView:371`); `loadUser()` doesn't clear it, so opening user B's detail still shows user A's secret **mislabelled**. The Pinia store is a session-wide singleton; logout (`auth.clear`) does no `$reset`/reload — so a one-time secret becomes a persistent, misattributed, cross-session on-screen disclosure on the supported shared-device scenario. A real exploit path.
**Fix:** Clear `lastTempPassword` at the start of `loadUser()/loadUsers()` and in a store reset; add a workshop-store reset invoked from `auth.clear()`/logout (see WS-114). At minimum gate the banner on the password belonging to the currently-loaded user and auto-clear after first render / on route leave. **Related:** WS-63, WS-114.

## P2 (round 2)

### WS-73 · Cutting queue never shows panels-needed (null snapshot) — `spec-conformance` · med · M
**Files:** `WorkshopCuttingQueueView.vue`, `stores/orders.ts`
**Why:** `orders.md:322-323` mandates "panels needed" on the cutting card. `partsLine()` (`:44-46`) appends "· N panel" only when `order.panels_used_snapshot` is truthy, but that field is set at cutting→next (`sales/service.py:648`) — so on confirmed/in-progress cards it's null and the count is dropped exactly where prep matters. The real figure (`cutting_result.panels_used_by_material`) is OrderDetail-only.
**Fix:** Derive panels-needed from the cutting result (sum of `panels_used_by_material`) instead of post-cut `panels_used_snapshot`. **Related:** WS-30/66/72.

### WS-75 · Revert button never names the concrete target — `spec-conformance` · med · S
**Files:** `WorkshopOrderDetailView.vue`
**Why:** `orders.md:302`: the ready revert target branches on whether banded (edge_banding vs cutting), computed by the backend gateway (`sales/service.py:766-776`). `:742-750` renders one "Bir qadam orqaga" button for cutting/edge_banding/ready, and the confirm dialog (`:815-818`) never states the destination. The operator triggers a stock-re-incrementing, stamp-clearing revert blind to where it lands.
**Fix:** Compute the target from `status` + `has_banding`; surface it in the button label and confirm dialog ("Tasdiqlanganga/Kesishga/Kromga qaytarish").

### WS-80 · Production screen lacks "record salary expense" shortcut — `completeness-stub` · med · M
**Files:** `WorkshopFinanceProductionView.vue`
**Why:** `finance.md:121-125` requires `/workshop/finance/production` to have a "record salary expense" shortcut opening the Expense form pre-set to `category=salary` for that worker. The screen renders only a read-only table (`:87-112`) + Refresh — no per-row salary action. (WS-53 noted the dropped shortcut on the FinanceView preview; the canonical screen also lacks it.)
**Fix:** Per-row "Maosh yozish" button routing to `/workshop/finance/expenses` with `category=salary` + worker pre-filled, amount blank. **Related:** WS-53.

### WS-81 · Income order picker not scoped to selected branch — `spec-conformance` · med · S
**Files:** `WorkshopFinanceExpensesView.vue`
**Why:** `finance.md:36-38,114` require the order_payment picker scoped to a branch in scope. The income form has a Branch field (`:365`) and order picker (`:354-359`), but `orderOptions` (`:79-89`) lists every non-cancelled order regardless of `incomeForm.branchId`. The backend then silently uses the order's branch_id (`finance/service.py:106-109`), so displayed and saved branch can diverge with no indication.
**Fix:** Filter `orderOptions` by `incomeForm.branchId` when `type==='order_payment'` (and/or set branchId from the chosen order).

### WS-82 · Finance forms can't attach a receipt scan — `completeness-stub` · med · M
**Files:** `WorkshopFinanceExpensesView.vue`, `stores/finance.ts`
**Why:** `finance.md:38-39,69` list an optional receipt scan on income/expense; the backend create requests accept `receipt_file_id` (`finance/schemas.py:20,39`). Neither form has a file input and `createExpense/createIncome` never send it. The shared upload flow already exists (`BranchDetail:425-431`). The receipt indicator the Expenses table should show (`finance.md:117`) can never populate.
**Fix:** Add a receipt file input to both forms via `files.upload`, store the id, pass `receipt_file_id` in the create payloads. **Related:** WS-44.

### WS-83 · No future-date guard on received_on/incurred_on — `spec-conformance` · med · S
**Files:** `WorkshopFinanceExpensesView.vue`, `backend/app/modules/finance/service.py`
**Why:** `entities/finance.md:46,76` state "not in the future" as invariants. The date inputs are plain `type=date` with no `:max` (`:333` incurred_on, `:368` received_on), and the backend never validates it (`create_income`/`create_expense` only call `_positive_amount`). A future-dated entry shifts its reporting period. **(Backend fix needed too.)**
**Fix:** Add a not-in-the-future check in create/update income+expense (raise APIError) and `:max=today` on the date inputs.

### WS-84 · Materials catalog lacks manufacturer/type filters (+backend) — `spec-conformance` · med · M
**Files:** `WorkshopCatalogView.vue`, `WorkshopBranchDetailView.vue`, `backend/app/modules/catalog/routes.py`
**Why:** `catalog-inventory.md:162-163` specifies kind/manufacturer/type filters. CatalogView offers only search/branch/kind/status (`:51-55`), the BranchDetail materials tab only search+status (`:670-694`), and the branch-materials endpoint accepts only kind + status_filter (`catalog/routes.py:263-269`) — **no manufacturer_id/type even in the API**. A branch with dozens of materials can't be narrowed by Egger vs Kronospan or DSP vs MDF.
**Fix:** Add `manufacturer_id` + panel-type params to the branch-materials endpoint and surface manufacturer + type dropdowns in CatalogView and the BranchDetail materials tab.

### WS-85 · Stock tx log shows raw actor UUID, omits note column — `spec-conformance` · med · S
**Files:** `WorkshopInventoryView.vue`, `backend/app/modules/inventory/schemas.py`
**Why:** `catalog-inventory.md:177-179` requires the tx log to show type, signed qty, balance-after, order link, supplier, **actor, note**, date. The standalone tx table (`:216-274`) shows the actor as the raw `{{ tx.actor_user_id ?? 'System' }}` UUID (`:264`) and has **no note column** — so an adjust's mandatory reason note (the core write-off audit field) is never displayed. `StockTransactionResponse` carries only `actor_user_id` with no name (`inventory/schemas.py:84`).
**Fix:** Add `actor_name` to the response (resolve from the workshop user) and render it; add a Note column. **Related:** WS-45/86.

### WS-87 · Branch detail dropped Overview/Staff/Orders tabs + KPI strip — `design-parity` · high · L
**Files:** `WorkshopBranchDetailView.vue`, `prototype-full/workshop/branch-detail.html`
**Why:** The prototype renders a 4-tile KPI strip (Faol buyurtma/Materiallar/Past zaxira/Xodim, `:112-117`) and six tabs incl. Umumiy (`:128-137`), Xodimlar (branch staff→user-detail, `:172-181`), Buyurtmalar (branch orders, `:183-192`). `WorkshopBranchDetailView.vue` defines only materials/inventory/settings tabs (`:172-176`) with no KPI strip and no Overview/Staff/Orders tabs. An owner loses at-a-glance KPIs and branch staff/orders from the branch page.
**Fix:** Restore the 4-KPI header row and add Umumiy/Xodimlar/Buyurtmalar tabs to match the six-tab layout.

### WS-88 · Inventory screen lost stock-in/adjust/supplier actions — `completeness-stub` · high · L
**Files:** `WorkshopInventoryView.vue`, `prototype-full/workshop/inventory.html`
**Why:** The prototype has page-level "± Tuzatish"/"Kirim yozish" buttons (`:25-26`), stock-in/adjust/supplier modals, per-row kebab actions (`:208-215`), and a Suppliers tab with add (`:66-67`) + edit/deactivate (`:307`). `WorkshopInventoryView.vue` has only a "Filial omborini boshqarish" deep-link (`:80-88`), rows expose only "Boshqarish" (`:193-201`), and the suppliers tab (`:277-308`) is **read-only**. A manage_inventory staffer can perform no inventory mutation on the global screen — everything bounces to per-branch detail. (Confidence: medium — confirm whether branch-detail is the intended single home.)
**Fix:** Bring the stock-in/adjustment/supplier-create affordances onto the global screen (mirror BranchDetail), or confirm branch-detail is the intended home; at minimum add supplier add/edit/deactivate. **Related:** WS-68.

### WS-89 · Orders screen dropped date filter + CSV export — `design-parity` · med · M
**Files:** `WorkshopOrdersView.vue`, `prototype-full/workshop/orders.html`
**Why:** The prototype exposes a date-range filter (Barcha/Bugun/Oxirgi 7 kun/oy, `:48-53`) and a CSV button (`:27`). The Vue filter row (`:125-132`) has only status/search/branch — no date filter — and the tools slot (`:99-122`) replaces CSV with a "Kesish navbati" link the prototype never has. Owners can't scope to today/last week or export.
**Fix:** Add a date-range ProjectDropdown wired to the orders query + a CSV export button; drop/relocate the "Kesish navbati" link.

### WS-90 · Order item list drops per-side edge thickness + breakdown — `design-parity` · med · M
**Files:** `WorkshopOrderDetailView.vue`, `prototype-full/workshop/order-detail.html`
**Why:** The prototype "Buyurtma tarkibi" renders per-side edge labels with thickness ("T: 2 mm", "B: 0.8 mm (mijoz)", `:105-113`) and a separate edge-material list (manufacturer+thickness+color+metres, `:117-122`). `edgeSummary` (`:69-83`) emits only side letter + source and never reads thickness; the template (`:374-389`) has no edge-material rows. `OrderItem.edge_*` are `Record<string,unknown>` (`orders.ts:38-41`) so thickness is in the payload but unused. The floor can't see which band thickness per side.
**Fix:** Extend `edgeSummary` to show per-side thickness; add the edge-material breakdown rows to the card.

### WS-91 · Price card lost krom split; header lost due date — `design-parity` · med · M
**Files:** `WorkshopOrderDetailView.vue`, `prototype-full/workshop/order-detail.html`
**Why:** The prototype "Narx tafsiloti" splits Krom into Krom(metres)/Krom materiali/Krom yopishtirish xizmati (`:174-176`) and the header shows a "Muddat: <dueAt>" chip (`:145`). The Vue version collapses krom into one row with no metres/split (`:403-419`) and the header (`:285-299`) has no due-date; `orders.ts` exposes no due_at field. (Due-date needs the API to surface the field first — medium confidence.)
**Fix:** Render krom material+service sub-rows with metres; add a due-date line once the API surfaces it.

### WS-92 · Branch cards dropped low-stock KPI; fake counts — `design-parity` · med · M
**Files:** `WorkshopBranchesView.vue`, `prototype-full/workshop/branches.html`
**Why:** Prototype branch cards show four numeric KPIs (Faol buyurtma/Past zaxira/Materiallar/Xodimlar, `:98-103`). The Vue kpi-grid (`:218-235`) keeps only the orders count; the other three tiles render literal text ("OK"/"!", "Boshqarish", "Ruxsatlar") — the low-stock count is gone and material/staff counts are fabricated labels. An owner can't compare branches by low-stock pressure/breadth/headcount.
**Fix:** Restore the four numeric KPIs; extend the managed-branches payload if the counts aren't present. **Related:** WS-49.

### WS-93 · Finance reports show raw payment-method code — `i18n-copy` · med · S
**Files:** `WorkshopFinanceView.vue`, `prototype-full/workshop/finance.html`
**Why:** `:223` renders `{{ income.method }}` raw in the "Usul" column — the user sees "cash"/"bank_transfer". The prototype maps to Naqd/Bank·karta/Boshqa (`:162,167`), and the sibling expenses view already maps it (`methodLabel` in `FinanceExpensesView:146`) — only the reports screen regressed.
**Fix:** Import/add the method label map and render the localized label. **Related:** WS-56.

### WS-94 · User-detail Profil tab is read-only — `completeness-stub` · med · M
**Files:** `WorkshopUserDetailView.vue`, `prototype-full/workshop/user-detail.html`
**Why:** The prototype Profil tab has editable F.I.O/Telefon/Login/Asosiy filial + Saqlash (`:73-89`). The Vue profile tab (`:241-279`) renders the four fields read-only + a Status card; there is no form/save — only grants/password-reset/block are mutable. An owner can't correct a staff member's name/phone/login/home branch.
**Fix:** Add an editable profile form (name/phone/login/home_branch_id) + save, owner-gated, backed by the user-update endpoint (or flag the missing endpoint).

### WS-99 · Test formatStockQuantity metres — `testing` · high · S · ships with WS-06
**Files:** `formatters.ts`, `shared/__tests__/formatters.spec.ts`
**Why:** `formatters.spec.ts` tests formatTiyin/formatDate but not `formatStockQuantity` — the live render path for stock/banding/production metres, and the WS-06 comma-decimal root cause has no test pinning the /1000 conversion.
**Fix:** Cases: `formatStockQuantity(18000,'m')` ends " m" + contains "18" no fraction; 18500 → 3 decimals; a non-'m' unit renders integer + raw unit with no scaling. Use `.toMatch/.toContain` for locale-robustness. **Related:** WS-06.

### WS-100 · Test parseDisplayQuantity round-trip — `testing` · high · S · ships with WS-07
**Files:** `formatters.ts`, `shared/__tests__/formatters.spec.ts`
**Why:** `parseDisplayQuantity` (`:33-38`) is the inverse of formatStockQuantity and the WS-07 raw-mm root cause; nothing tests it — a refactor could mis-store stock-in by 1000×.
**Fix:** `parseDisplayQuantity('12,5','m')===12500`; `('3','piece')===3`; `('abc','m')` NaN; a parse→format round-trip for integers divisible by 100. **Related:** WS-06/07.

### WS-101 · Test orders.patchOrder list isolation — `testing` · high · M · ships with WS-28
**Files:** `stores/orders.ts`, `stores/__tests__/orders.spec.ts` (new)
**Why:** `patchOrder` (`:365-368`) writes the mutated order into both `clientOrders` and `workshopOrders` and prepends on every mutation; zero orders-store test exists. WS-28 names exactly this cross-pollution + reorder.
**Fix:** New `orders.spec.ts` (mock `@/api/client`): seed workshopOrders only, call approve() returning an OrderDetail, assert clientOrders stays empty, workshopOrders contains it once, an existing order is replaced not duplicated. **Related:** WS-28.

### WS-102 · Test orders 409 conflict + refetch — `testing` · high · M · ships with WS-09
**Files:** `stores/orders.ts`, `WorkshopOrderDetailView.vue`
**Why:** `captureError` (`:190-197`) maps 403 only; `run()` (`:115-124`) catches, sets actionError, never refetches → stale version persists. No test pins the 409 mapping nor the missing refetch.
**Fix:** Store test: mock api.post to throw `ApiError(409,{code:'version_conflict',trace_id})`; assert approve() rejects, error is the code, traceId captured. Component test: after a 409 the view refetches + re-enables with the fresh version (ships with WS-09). **Related:** WS-09.

### WS-103 · Test finance dual-route tab reactivity — `testing` · med · M · ships with WS-10
**Files:** `WorkshopFinanceExpensesView.vue`, `apps/workshop/routes.ts`
**Why:** `:25` reads activeTab once at setup with no watch; both `/finance/income` and `/finance/expenses` map to this component, so navigating reuses the instance and activeTab never updates (WS-10). No test pins it.
**Fix:** Component test + mock router: mount at /finance/expenses (expense tab), push to /finance/income, await nextTick, assert income tab. Fails today, passes with WS-10. **Related:** WS-10/71.

### WS-104 · Test discount form pre-seed — `testing` · high · M · ships with WS-08/39
**Files:** `WorkshopOrderDetailView.vue`, `stores/orders.ts`
**Why:** `discountKind='fixed'`, `discountValue=''` (`:28-30`); applyDiscount (`:203-223`) sends kind/value/reason but these are never seeded from the loaded order — re-opening a percent discount defaults to fixed/empty and re-submitting re-classifies (WS-08/39). No test pins the mapping.
**Fix:** Component test: mount with currentOrder having `discount_tiyin>0` + reason; assert inputs reflect the persisted discount (fails today, ships with WS-08). Plus a pure assertion applyDiscount sends `kind:'percent'` for the percent option and rejects negative/non-integer. **Related:** WS-08/39.

### WS-105 · Test notification filter + deep-link — `testing` · med · M · ships with WS-48
**Files:** `WorkshopNotificationsView.vue`, `stores/notifications.ts`
**Why:** The filter predicate (`:23-27`) uses option value 'inventory' while stock codes contain 'stock' → the chip matches nothing; `to()` (`:43-44`) returns paths only for order/branch (WS-48). No test pins either.
**Fix:** Extract predicate + `to()` to pure helpers; test a stock notification matches the 'inventory' filter, a finance one matches 'finance', and `to()` returns stock/finance paths. Fails today, passes with WS-48. **Related:** WS-48.

### WS-106 · Test useWorkshopPermissions truth table — `testing` · high · M · ships with WS-04
**Files:** `WorkshopDashboardView.vue`, `stores/auth.ts`, `app/workshopNav.ts`
**Why:** No permissions composable exists; checks are inlined and branch-blind (Dashboard `:23-37` ignores `grant.branch_id` → WS-03) while `workshopNav.ts:44-71` DOES scope by selectedBranchId — the two surfaces disagree.
**Fix:** When the WS-04 composable lands, spec `can(perm, branchId)`: owner→true everywhere; staff with {manage_finance, branch-A}→true for A, false for B/workshop-wide; empty grants→false; pin the nav alias rules. **Related:** WS-04/03/67.

### WS-107 · Test permission route guard — `testing` · high · M · ships with WS-05
**Files:** `app/createRoleApp.ts`, `apps/workshop/routes.ts`
**Why:** `beforeEach` (`:94-108`) checks only `isAllowedFor(role)` + password_reset_required; routes declare no `meta.permission`, so a manage_inventory-only staffer can direct-URL into /workshop/finance, /settings/users, /branches (WS-05). `routeMatrix.spec.ts` asserts nothing about gating.
**Fix:** Add route `meta.permission`, then test the extracted guard: a manage_inventory-only principal is redirected for /finance and /settings/users but allowed for /inventory; owner allowed everywhere; unauthenticated → login. **Related:** WS-05/02/66/68.

### WS-114 · Pinia stores not reset on logout — tenant PII residue — `security` · med · M
**Files:** `stores/auth.ts`, `stores/workshop.ts`, `ProfileView.vue`
**Why:** `auth.clear()` (`:80-84`) nulls only token/me/status; logout (`:185-197`) calls clear() and returns; ProfileView (`:146-154`) does a client-side `router.replace` with no reload. The workshop store (`:160-173`) holds users (full_name/phone/login/grants), branches, suppliers, stock, settings, sessions in module-level refs that **outlive logout** — the next login on the same device reuses the same Pinia instance → tenant-data residue / cross-user exposure on the supported shared-device scenario. Broader companion to WS-113.
**Fix:** Add an explicit reset for workshop/orders/finance/cutting/notifications stores; invoke it from `auth.clear()`/logout; also wipe on login-as-different-principal. **Related:** WS-28/113.

## P3 (round 2)

### WS-76 · Timeline omits production stamps (credited worker/panels) — `spec-conformance` · low · M
**Files:** `WorkshopOrderDetailView.vue`
**Why:** `orders.md:123`: production stamps are the sole input to worker-production reports; the backend writes `credited_user_id` into event metadata (`sales/service.py:661-664,706-708`). The Vue timeline (`:607-628`) renders only changed_at/status/reason — it ignores `event.metadata` (exists on `OrderEvent`, `orders.ts:56`), so who was credited (esp. on-behalf) and panel count are invisible. The prototype surfaces them. (Distinct from WS-27.)
**Fix:** On cut/band completion events read `metadata.credited_user_id` (resolve via workerOptions) + snapshots; render on the matching rows. **Related:** WS-27.

### WS-77 · Board never renders WHO is assigned — `spec-conformance` · low · S
**Files:** `WorkshopOrdersView.vue`
**Why:** `orders.md:288` requires the board card to show the assigned cutter/edger chip. `assignedText()` (`:56-63`) returns a single string stating only whether a worker exists, shows cutter OR edger by status (never both), never the identity; card (`:164-180`) and table (`:215`) reuse it. (Content gap; WS-51 is the chip styling.)
**Fix:** Render assigned cutter and (when banded) edger identities as initials chips, both roles visible. **Related:** WS-51.

### WS-86 · BranchDetail tx table drops order-link/actor/note — `spec-conformance` · low · S
**Files:** `WorkshopBranchDetailView.vue`
**Why:** `catalog-inventory.md:177-179` requires order link, supplier, actor, note. The BranchDetail tx table (`:1095-1119`) shows only Sana/Material/Turi/Miqdor/Qoldiq/Yetkazib beruvchi — no order-link (so consume/restore rows can't be traced), no actor, no note. Same clause as WS-85, different table.
**Fix:** Add Order (link), Actor, Note columns mirroring the standalone view. **Related:** WS-85.

### WS-95 ⚠ · Users list dropped "Oxirgi kirish" column — `design-parity` · low · S
**Files:** `WorkshopUsersView.vue`, `prototype-full/workshop/users.html`
**Why (verify):** The prototype users table has an "Oxirgi kirish" column (`:47,121`). The Vue head (`:292-301`)/body (`:303-336`) have none. **⚠ depends on whether the workshop users payload carries last-login.**
**Fix:** Add an "Oxirgi kirish" column via `formatDate` if the payload carries it; otherwise flag the missing field.

### WS-96 · Inventory tx table dropped "Filial" column — `design-parity` · low · S
**Files:** `WorkshopInventoryView.vue`, `prototype-full/workshop/inventory.html`
**Why:** The prototype tx thead includes Filial (`:57`) with the branch per row (`:285`). The Vue tx head (`:219-228`) omits it, so under an all-branches filter a multi-branch owner can't see which branch each tx belongs to.
**Fix:** Add a Filial column rendering the branch name.

### WS-97 · Catalog rows lost hide-from-customers toggle — `completeness-stub` · low · M
**Files:** `WorkshopCatalogView.vue`, `prototype-full/workshop/catalog.html`
**Why:** The prototype row kebab offers a "Yashirish"/"Faol qilish" status toggle that hides/shows a material to customers while keeping stock (`:142-143`). The Vue rows replace the kebab with a single "Narx / min" deep-link (`:202-210`) — no per-row visibility toggle.
**Fix:** Add an inline activate/deactivate (hide/show) control to catalog rows, or confirm the branch-detail materials tab is the intended home. **Related:** WS-68.

### WS-98 · Profile grant rows show raw branch-id fragment — `i18n-copy` · low · S
**Files:** `ProfileView.vue`, `prototype-full/workshop/profile.html`
**Why:** The prototype resolves grant branches to names (`branchById(b).name`, `:101`). `workshopGrantRows` maps each grant to `grant.branch_id.slice(0,8)` (`:76-84`) and renders that 8-char UUID fragment in the Ruxsatlar card (`:494`) — a staff user sees "3f9a2c1b" instead of "Yunusobod".
**Fix:** Resolve `grant.branch_id` to the branch name via `workshop.branches`, falling back to the fragment only when not loaded.

### WS-108 · Test workshop store branch-context flows — `testing` · med · M
**Files:** `stores/workshop.ts`
**Why:** The largest store (640 lines) has zero tests. Untested: `loadUsers` request-id race guard (`:462-481`), `createUser` bumping the id + clearing loading (`:490-491`, the WS-63 foot-gun), `loadInventory` Promise.all error capture (`:392-404`), `loadBranch` owner-only pricing fetch (`:257-262`), `recordStockIn` prepend-then-refetch (`:438-448`).
**Fix:** New `workshop.spec.ts`: loadUsers ignores an out-of-order resolution; loadInventory sets inventoryError+traceId on one rejection; loadBranch calls pricing only when owner; recordStockIn prepends + reloads. **Related:** WS-63/32/29.

### WS-109 · Test finance store load + error capture — `testing` · med · S
**Files:** `stores/finance.ts`
**Why:** No finance-store test. `capture()` sets error+traceId; loaders set distinct codes; create prepends; void maps in place. None pinned; WS-58 lives in its callers.
**Fix:** `finance.spec.ts`: each loader sets its code + captures traceId on ApiError + clears loading; create prepends; void replaces without reordering. **Related:** WS-45/58.

### WS-110 · E2E: owner applies a discount, persists on reload — `testing` · med · M
**Files:** `e2e/tests/order-production.spec.ts`, `WorkshopOrderDetailView.vue`
**Why:** order-production walks approve→…→collect but never touches the discount control; `applyDiscount` + form are unexercised e2e, and WS-08/39 live here. The owner-only flow changes what the customer pays with no coverage.
**Fix:** E2E (reuse seed helpers): as owner on a confirmed order, apply a fixed discount + reason, assert total drops + line shows; reload + assert persistence; optionally re-open to guard WS-08. **Related:** WS-08/39.

### WS-111 · E2E: record income against order + standalone expense — `testing` · med · M
**Files:** `e2e/tests/order-production.spec.ts`, `WorkshopFinanceExpensesView.vue`
**Why:** No e2e visits /workshop/finance/expenses or exercises createIncome/createExpense. The finance ledger path (income tied to order_id, expense with category) is untested through the browser; WS-10/41 sit on it.
**Fix:** New `finance-ledger.spec.ts`: provision a completed order, record an order_payment income (assert listing), switch to the expense tab (touches WS-10), record an expense with category+vendor (assert listing). **Related:** WS-10/41/44.

### WS-112 · E2E: revert/cancel-with-reason + 409 recovery — `testing` · med · L
**Files:** `e2e/tests/order-production.spec.ts`, `WorkshopOrderDetailView.vue`, `stores/orders.ts`
**Why:** The reason-dialog actions (`:180-201`) and store revert/cancel (`orders.ts:307-313`) have no e2e; the 409 path (`run()` `:115-124`) is unexercised. order-production walks only forward. WS-09/37 regressions would surface only in prod.
**Fix:** E2E: drive to cutting, revert with reason (assert status back + reason), cancel another with reason (assert "Bekor qilingan"). For 409, mutate version out-of-band via the API fixture, trigger a UI action, assert a conflict message + (post-WS-09) refetch+retry. **Related:** WS-09/37.

### WS-115 ⚠ · AuthFileImage object-URL leak under rapid fileId change — `security` · low · S
**Files:** `components/AuthFileImage.vue`, `stores/files.ts`
**Why (verify):** `AuthFileImage.vue:27-40` `watch(fileId)` calls `revoke()` (current src only) then awaits `files.loadObjectUrl`; `files.ts:43-48` creates a fresh URL with no internal revoke. If fileId changes again before a prior await resolves, the stale resolution assigns a new URL over src without revoking the superseded one. **⚠ Latent — grep shows zero consumers mount AuthFileImage today.**
**Fix:** Guard the async assignment with a per-call token (capture fileId, ignore if changed) and revoke any URL about to be replaced, including superseded in-flight loads. **Related:** WS-44.
