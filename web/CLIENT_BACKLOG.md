# Client SPA — Improvement Backlog

A living, engineering-owned backlog for the **client SPA** (the customer-facing
`app.` storefront). This is implementation/tracking — **not** product canon, so it
lives here under `web/` rather than `docs/` (no `docs_uz/` mirror, no canon
frontmatter). `docs/` stays the source of truth for *what* the product is; this
file tracks *fixes/polish* against the current Vue implementation.

> Seeded 2026-06-10 from an automated multi-lens audit (UX/flow, responsive,
> i18n/copy, design-parity vs `web/prototypes/prototype-full`, a11y, correctness,
> performance, states/errors, completeness). **Re-verify each item against current
> code before implementing** — line numbers are point-in-time. Items the audit
> flagged as possibly-already-handled carry a ⚠ marker.
>
> **Round 2 (2026-06-10):** added CB-59…CB-104 from four further lenses —
> editor-touch (phone ergonomics of the cutting editor), auth-profile (login/OTP +
> profile flows vs spec), spec-cutting (clause-by-clause `docs/ref/features/cutting.md`
> conformance), code-health (tech-debt that slows client work). The three ⚠ items
> were verified against current code: CB-48 partial (corrected), CB-49 refuted
> (→ Won't), CB-56 partial (downgraded to cleanup).
>
> **Round 3 (2026-06-10):** added CB-105…CB-131 from the four lenses that session
> limits had blocked in round 2 — spec-orders-notify (orders.md/notifications.md
> conformance), proto-screens (per-screen prototype diff), testing (coverage gaps),
> security (storage/object-URL/redirect sweep). 12 of these are **testing** items;
> seven are regression tests meant to ship **with** a specific in-flight fix
> (noted in each). All bug/spec citations were re-verified against current code.
> All four planned lenses are now complete.

## Conventions

- **Priority** — `P1` do-first (high-leverage, on the core cut→order→notify path),
  `P2` important, `P3` nice-to-have.
- **Severity** — user-facing impact. **Effort** — `S` ≤½ day · `M` ~1–2 days · `L` larger.
- **Category** — `ux-flow` · `responsive` · `i18n-copy` · `design-parity` · `a11y` ·
  `correctness-bug` · `performance` · `states-errors` · `completeness-stub`.
- **Status** — `Open` · `WIP` · `Done` · `Won't` (update as we go).
- Scope guard: items here are **in v1** per [`docs/scope.md`](../docs/scope.md);
  out-of-v1 ideas (delivery, payments, order-edit, reorder, ratings…) are excluded.

## Counts

| | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| Open (incl. partial) | 7 | 51 | 24 | **82** |
| Done | 25 | 17 | 8 | **50** |
| Won't | — | — | 2 (CB-49, CB-80) | **2** |

> Progress (2026-06-18, R5c): states / session / PDF batch. **CB-08** (the API
> client now intercepts 401 on an authed call: one deduped silent `/auth/refresh`
> + retry; on failure the auth store clears and the app bounces to login with a
> "Sessiya tugadi" notice — wired via a `configureSession` bridge, covered by
> `client.spec.ts`). **CB-10** (`NotificationsMenu` polls the unread count every
> ~45s while the tab is visible and a session exists). **CB-17** + **CB-111** (one
> shared `downloadBlob` helper that attaches the anchor and async-revokes the
> object URL so Firefox/Safari stop aborting the download; both stores wrap it
> with a per-id busy flag + transient error/trace, surfaced in the editor and
> order-detail PDF buttons).

> Progress (2026-06-18, R5b): editor a11y + responsive batch. **CB-06** (Tab/
> Shift-Tab focus-trap inside the edge modal, mirroring `ConfirmDialog`). **CB-07**
> (placement rects are now `<g role="button">` with an `aria-label` and a
> scale-independent `:focus-visible` ring; the SVG keeps `role="img"` so the
> placement list stays the SR-primary affordance). **CB-62** (edge modal uses
> `dvh` sizing and becomes a bottom-sheet with a safe-area sticky footer at
> ≤520px; the fixed edge diagram shrinks at ≤360px so it stops clipping). **CB-60**
> (sub-`lg` part rows: the three dimensions share one row and the row actions sit
> 2-up via `lg:contents`/`lg:grid-cols-1`, leaving the desktop grid unchanged).

> Progress (2026-06-18, R5): editor-correctness batch. **CB-15** + **CB-108**
> (autosave timing extracted into a pure, unit-tested `autosaveController`: edits
> coalesce, `flush()` runs on optimize and on unmount so navigating away within
> the 700ms window no longer drops the edit, and the `currentDraft` watcher only
> re-hydrates `parts` when the draft **id** changes so a save/optimize round-trip
> can't clobber an in-flight keystroke). **CB-03** (a draft bound to an order —
> any result with an `order_id` — is read-only: a non-dismissible banner links to
> the order and the whole editing region is gated via `<fieldset disabled>` +
> autosave gate).

> Progress (2026-06-18, R3): 30 Done. **CB-86** (per-row recovery: `bringOwn()`
> now flips only the not-carried panel/sides, a "Boshqa krom tanlash" button opens
> the picker, the warning names the branch, and the banner count no longer drops
> own-panel/not-carried-edge rows), **CB-11** (409 `order_version_conflict` refetches
> the order so a retry uses the fresh version, + `orders.spec.ts`).
> **CB-02 is blocked on the backend**, not done: the backend emits exactly one
> notification (`inventory.low_stock`, to workshop users) — no client order
> notifications exist yet, so there are no raw codes reaching clients to localize.
>
> Progress (2026-06-18, R2): 28 Done. **CB-65** (cutting SVG: normalized label
> size + suppress tiny labels + pinch-zoom), **CB-04** (order-new pre-selects the
> preferred branch with a "Tavsiya" chip), **CB-31** (order-detail tabs:
> tablist/tab/tabpanel roles + arrow-key navigation). Plans were produced by a
> parallel e2e-aware analysis workflow before implementing.
>
> Progress (2026-06-18, editor focus): 25 Done. This session — **CB-29** (result
> panel: "Joylashtirildi N/N" + per-edge-material metres), **CB-16** (optimize
> failures caught + inline banner with trace), **CB-50** (Optimise disabled until
> parts change / blocked for invalid rows), **CB-82**/**CB-121** (part-max
> validation + pure `partFitError()` test), **CB-01** (Uzbek `clientErrorLabel()`
> map), **CB-09** (createDraft + 50-draft cap; `apiErrorCode()`). Plus autosave now
> skips invalid rows, disabled `.mp-button`s now visibly dim, and a dev seeder at
> `deploy/seed-dev-data.sh`.

By category (approx): states-errors ~17 · spec-conformance ~14 · tech-debt ~16 ·
ux-flow ~12 · design-parity ~12 · testing ~12 · a11y ~10 · correctness-bug ~9 ·
performance ~7 · completeness-stub ~7 · i18n-copy ~6 · responsive ~4 · security ~2.

## Index

| ID | Pri | Cat | Sev | Eff | Status | Title |
|----|-----|-----|-----|-----|--------|-------|
| CB-01 | P1 | i18n-copy | high | M | Done | Translate raw backend error codes to Uzbek (order/profile/cutting-save) |
| CB-02 | P1 | i18n-copy | high | M | Blocked | Human-readable Uzbek notification titles (+body) in bell & list — backend emits no client notifications yet (only `inventory.low_stock` → workshop) |
| CB-03 | P1 | ux-flow | high | M | Done | Read-only mode + bound-order banner for confirmed drafts in editor |
| CB-04 | P1 | ux-flow | high | S | Done | Pre-select & badge preferred branch in order-new step |
| CB-05 | P1 | a11y | high | S | Done | Set client SPA `<html lang="uz">` |
| CB-06 | P1 | a11y | high | M | Done | Focus-trap the cutting-editor edge-banding modal |
| CB-07 | P1 | a11y | high | M | Done | Keyboard-operable placement rects (name + visible focus) |
| CB-08 | P1 | states-errors | high | L | Done | 401/session-expired: silent refresh then login redirect |
| CB-09 | P1 | states-errors | high | S | Done | Surface createDraft failures incl. 50-draft cap |
| CB-10 | P1 | completeness-stub | high | S | Done | Poll notification unread count (~45s) |
| CB-11 | P1 | correctness-bug | high | M | Done | 409 cancel conflict: refetch order + actionable message |
| CB-12 | P1 | performance | high | M | Open | Batch checkout quote instead of per-branch fan-out |
| CB-13 | P1 | performance | high | M | Open | Kill per-branch materials N+1 on Branches list |
| CB-14 | P1 | design-parity | high | M | Open | Shared toast/snackbar primitive + wire critical events |
| CB-15 | P1 | correctness-bug | med | M | Done | Flush autosave on unmount; stop clobbering edits mid-optimize |
| CB-16 | P1 | states-errors | med | S | Done | Surface optimize failures inline (+trace_id) |
| CB-17 | P1 | states-errors | med | S | Done | Handle PDF download failures with feedback |
| CB-18 | P1 | ux-flow | med | S | Open | Pre-check draft usability on entering order wizard |
| CB-19 | P2 | states-errors | med | M | Open | "No branch carries the set" recovery panel |
| CB-20 | P2 | correctness-bug | med | M | Open | Per-branch quote error labeling uses real per-call error |
| CB-21 | P2 | states-errors | med | M | Open | Page-level error+retry when all checkout quotes fail |
| CB-22 | P2 | states-errors | med | M | Open | Extract shared ClientErrorState; add trace_id to notifications |
| CB-23 | P2 | states-errors | med | M | Open | Fault-tolerant per-branch material loads (allSettled+retry) |
| CB-24 | P2 | states-errors | med | M | Open | Handle cancel-order / delete-draft failures in dialogs |
| CB-25 | P2 | states-errors | med | M | Open | Loading + error/empty state on client profile load |
| CB-26 | P2 | states-errors | med | S | Partial | Rollback + surface failures on mark-read / mark-all-read |
| CB-27 | P2 | correctness-bug | med | S | Done | normalizeUzPhone must insert +998 (fixes display) |
| CB-28 | P2 | correctness-bug | med | S | Done | formatPercent: always ×100 the 0..1 fraction |
| CB-29 | P2 | completeness-stub | med | M | Done | Per-edge-material metres + parts-placed count in result |
| CB-30 | P2 | completeness-stub | med | S | Done | Show order notes (note_workshop/client) in Overview |
| CB-31 | P2 | a11y | med | M | Done | Valid tablist/tab/tabpanel + keyboard on order detail |
| CB-32 | P2 | a11y | med | M | Open | ARIA menu keyboard ops on notifications dropdown |
| CB-33 | P2 | a11y | med | M | Open | Keyboard-accessible whole-card targets (home/orders) |
| CB-34 | P2 | a11y | med | S | Done | Raise `--color-ink-muted` to WCAG AA contrast |
| CB-35 | P2 | design-parity | med | M | Done | Replace letter-glyph placeholders with prototype SVG icons |
| CB-36 | P2 | design-parity | med | S | Done | Add line icons to client header nav |
| CB-37 | P2 | design-parity | med | S | Open | Drop 5th "Profil" nav item; fix mobile profile reach |
| CB-38 | P2 | performance | med | M | Open | Paginate client orders list |
| CB-39 | P2 | performance | med | M | Open | Lightweight drafts-summary endpoint for list views |
| CB-40 | P2 | performance | med | M | Open | Scope/paginate editor catalog loads (not whole catalog) |
| CB-41 | P2 | completeness-stub | low | M | Open | Paginate notifications page; server-side unread filter |
| CB-42 | P2 | i18n-copy | med | S | Done | Localize English fallbacks (pickers/summary/SearchCombobox) |
| CB-43 | P2 | responsive | low | S | Open | Lock background scroll when ConfirmDialog is open |
| CB-44 | P3 | design-parity | low | S | Done | Use `.tl` timeline with done/bad states in order history |
| CB-45 | P3 | design-parity | low | S | Done | Recolor branches info banner from warn-yellow to neutral |
| CB-46 | P3 | design-parity | low | S | Done | Full 5-phase model on home active-order progress |
| CB-47 | P3 | ux-flow | low | S | Done | Reliable home back-target on notifications/profile |
| CB-48 | P3 | responsive | low | S | Open ✓partial | Stack branches/notifications rows on small phones |
| CB-49 | P3 | responsive | low | S | **Won't** ✗refuted | ~~Fix two-column grid overflow in ~1024px band~~ |
| CB-50 | P3 | ux-flow | low | S | Done | Disable Optimise after a run until a part changes |
| CB-51 | P3 | ux-flow | low | M | Open | Two-pane workshop+branch picker in editor pre-filter |
| CB-52 | P3 | performance | low | S | Open | Cache/staleness reuse for home/notifications/branch-options |
| CB-53 | P3 | a11y | low | S | Open | Self-describing autosave live region (role=status) |
| CB-54 | P3 | a11y | low | S | Open | AuthFileImage: required alt + localized failure label |
| CB-55 | P3 | correctness-bug | low | S | Done | Idempotent markRead decrement (only when was unread) |
| CB-56 | P3 | correctness-bug | low | S | Open ✓partial | One defined quantity for order-detail "Krom" figure |
| CB-57 | P3 | states-errors | low | M | Open | Error feedback for chooseResult / preferred-branch save |
| CB-58 | P3 | completeness-stub | low | S | Open | Remove dead dupes (English status maps, i18nSeed, DashboardView) |
| CB-59 | P2 | ux-flow | med | S | Open | `inputmode=numeric` on dimension/quantity inputs |
| CB-60 | P1 | design-parity | high | M | Done | Port prototype's compact phone layout for part rows |
| CB-61 | P2 | a11y | med | S | Open | Raise sub-44px touch targets (chips, panel tabs, modal buttons) |
| CB-62 | P1 | responsive | high | M | Done | Edge modal: dvh sizing + bottom-sheet on phones |
| CB-63 | P2 | ux-flow | med | S | Open | iOS-proof modal scroll lock + overscroll containment |
| CB-64 | P2 | ux-flow | med | M | Open | Keyboard/container-aware combobox & select popovers |
| CB-65 | P1 | ux-flow | high | M | Done | Cutting SVG: normalized viewBox, label threshold, zoom |
| CB-66 | P3 | ux-flow | low | S | Open | `scroll-margin` for #cutting-results under sticky header |
| CB-67 | P3 | tech-debt | low | S | Open | Guard hover styles with `@media (hover:hover)` |
| CB-68 | P2 | responsive | med | S | Open | 16px form-control font on mobile (stop iOS auto-zoom) |
| CB-69 | P3 | ux-flow | low | S | Open | Per-side krom details visible on touch (not title-only) |
| CB-70 | P1 | security | high | S | Done | Gate the dev OTP hint "000000" to dev builds |
| CB-71 | P2 | states-errors | med | M | Done | Honor 429 `retry_after_seconds` with live resend countdown |
| CB-72 | P2 | design-parity | med | M | Open | Show attempts-remaining on `invalid_code` |
| CB-73 | P2 | ux-flow | med | S | Done | Un-dead-end the name step on `code_expired` |
| CB-74 | P3 | i18n-copy | low | S | Done | Add `account_blocked` to client login error map |
| CB-75 | P1 | security | med | S | Done | Block protocol-relative `?redirect` (open redirect) |
| CB-76 | P2 | spec-conformance | med | M | Open | Searchable preferred-branch selector |
| CB-77 | P3 | spec-conformance | low | S | Open | Selectable temporarily_closed branches; stale-pref state |
| CB-78 | P3 | correctness-bug | low | S | Open | Split profile PATCH payloads (branch save vs name form) |
| CB-79 | P2 | correctness-bug | med | S | Partial | Reject whitespace-only name on registration step |
| CB-80 | P3 | ux-flow | low | S | Won't | Surface OTP 5-min expiry on the code step |
| CB-81 | P3 | i18n-copy | low | S | Open | Uzbek session-row labels ("active"/"Browser") |
| CB-82 | P1 | spec-conformance | high | M | Done | Validate part max against panel − 2× edge trim |
| CB-83 | P2 | spec-conformance | med | S | Open | 100-part cap + blocking roll-up under the parts table |
| CB-84 | P2 | spec-conformance | high | L | Open | Panel picker filters (manufacturer/type/thickness) + sort |
| CB-85 | P2 | spec-conformance | med | S | Open | Grain indicator on the panel chip |
| CB-86 | P1 | spec-conformance | high | M | Done | Fix per-row recovery: scoped bring-own + pick-different-material |
| CB-87 | P2 | spec-conformance | med | M | Open | Material tab strip in visualiser; dimensions in legend |
| CB-88 | P2 | spec-conformance | med | M | Open | Drafts list: branch chip + material label pre-optimise |
| CB-89 | P2 | spec-conformance | med | L | Open | Per-row attribution of optimiser/stale-catalog errors |
| CB-90 | P3 | spec-conformance | low | S | Open | Algo compare: cut-length column, algo name, closed default |
| CB-91 | P3 | spec-conformance | low | S | Open | Name the tape in the Edges cell summary |
| CB-92 | P3 | tech-debt | low | S | Open | Delete unreachable "Fayldan" upload empty-state branch |
| CB-93 | P2 | tech-debt | high | L | Open | Decompose ClientCuttingEditorView along five seams |
| CB-94 | P2 | tech-debt | med | M | Open | Split LoginView into per-role views |
| CB-95 | P2 | tech-debt | med | M | Open | Split ProfileView; dedupe ClientBranchOption type |
| CB-96 | P2 | tech-debt | med | M | Open | useListboxControl/useStableId composables for dropdowns |
| CB-97 | P2 | tech-debt | med | S | Open | Single authInit()/token injection (8 copies) |
| CB-98 | P2 | tech-debt | med | S | Open | One shared withQuery() (6 copies, divergent semantics) |
| CB-99 | P3 | tech-debt | low | S | Open | Extract shared downloadBlob() (2 copies) |
| CB-100 | P2 | tech-debt | med | S | Open | Unify captureApiError() (3 divergent variants) |
| CB-101 | P2 | tech-debt | med | M | Open | Typed notification payload + shared presenter |
| CB-102 | P3 | tech-debt | low | S | Open | Centralize magic numbers (debounces, limits, 50 mm) |
| CB-103 | P2 | tech-debt | med | S | Open | Fix stale AGENTS.md API-client path + phantom dirs |
| CB-104 | P3 | tech-debt | low | S | Open | Remove dead quote surface in orders store |
| CB-105 | P1 | testing | high | S | Done | Regression test: normalizeUzPhone (ships w/ CB-27) |
| CB-106 | P1 | testing | high | S | Done | Regression test: notifications markRead idempotency (CB-55) |
| CB-107 | P1 | testing | high | M | Open | Test per-branch quote error attribution (CB-20) |
| CB-108 | P1 | testing | high | M | Done | Test autosave debounce + hydration guard (CB-15) |
| CB-109 | P1 | testing | high | S | Done | Test login redirect guard rejects external (CB-75) |
| CB-110 | P1 | testing | high | M | Open | Cover client OTP auth path in auth store |
| CB-111 | P1 | states-errors | med | S | Done | PDF download: async revoke + attach anchor (silent fail) |
| CB-112 | P2 | spec-conformance | med | M | Open | Branch working hours in picker / Review / Pickup |
| CB-113 | P2 | spec-conformance | med | M | Open | Order-detail Timeline: 5 client phases, not raw events |
| CB-114 | P2 | completeness-stub | med | M | Open | Per-session revoke ("Yopish") in profile sessions |
| CB-115 | P2 | states-errors | med | M | Open | Aggregate "no branch carries this set" empty state |
| CB-116 | P2 | states-errors | low | M | Open | Order-new: split already-used vs no-chosen-result bail |
| CB-117 | P2 | design-parity | med | L | Open | Itemized branch-card / checkout price lines |
| CB-118 | P2 | design-parity | med | M | Done | Order-detail Krom material-vs-service split + metres |
| CB-119 | P2 | correctness-bug | low | S | Open | Orders 'active' filter: expand to status set or filter client-side |
| CB-120 | P2 | testing | med | S | Done | Pin formatPercent boundary (ships w/ CB-28) |
| CB-121 | P2 | testing | med | M | Done | Test part validation bounds (ships w/ CB-82/83) |
| CB-122 | P2 | testing | med | L | Open | E2E: client order cancel + 409 recovery |
| CB-123 | P2 | testing | med | L | Open | E2E: client notifications (open/mark-read/badge) |
| CB-124 | P2 | testing | med | M | Open | Test branch-carry recovery detection (rowNotCarried) |
| CB-125 | P2 | states-errors | low | S | Open | Null-destination notification: "not available", not silent |
| CB-126 | P2 | spec-conformance | low | S | Open | Bell rows: event-family icon, drop raw event_code subtext |
| CB-127 | P3 | completeness-stub | low | S | Done | Cancelled banner shows cancellation reason |
| CB-128 | P3 | design-parity | low | M | Open | Orders-list card meta: pickup/due date not part count |
| CB-129 | P3 | completeness-stub | low | M | Open ⚠ | Order-detail "Taxminiy sana" estimated-ready row |
| CB-130 | P3 | testing | low | M | Open | Test edge ranking/recommendation helpers |
| CB-131 | P3 | tech-debt | low | S | Open | files.loadObjectUrl: ownable revoke contract (leak footgun) |
| CB-132 | P2 | ux-flow | med | S | Done | Login phone/OTP inputs reject non-numeric typing (user-found) |
| CB-133 | P2 | design-parity | med | S | Done | Login errors → client-banner + SVG icon + danger/warn tone split (user-review) |
| CB-134 | P2 | i18n-copy | med | S | Done | Login: `novalidate` + JS guards → Uzbek alerts, not native English validation (user-found) |

---

## P1 — do first (core cut → order → notify path)

### CB-01 · Translate raw backend error codes to Uzbek (order/profile/cutting-save) — `i18n-copy` · high · M
**Files:** `stores/orders.ts`, `views/ClientOrdersView.vue`, `ClientOrderDetailView.vue`, `ClientOrderNewView.vue`, `ProfileView.vue`, `ClientCuttingEditorView.vue`
**Why:** `orders.ts` `captureError` sets `error.value` to the raw backend code, rendered verbatim at the highest-stakes moments — `ClientOrdersView.vue:194` `{{ actionError }} · trace …`, `ClientOrderDetailView.vue:586`, `ClientOrderNewView.vue:565`. `ProfileView.vue:123` sets `error.value='profile_update_failed'` shown raw at `:307`; `ClientCuttingEditorView.vue:558/568` hardcode English save errors shown at `:1051`. An Uzbek customer sees English machine codes (`order_cancel_failed`, `permission_denied`) right when placing/cancelling.
**Fix:** Add a shared `orderErrorLabel(code)` Uzbek map (mirror the existing `quoteErrorLabel` `ClientOrderNewView.vue:106` and `LoginView` `clientErrorText`), pass store errors through it, fall back to a generic "Amal bajarilmadi. Qayta urinib ko'ring.", and Uzbek-ify the two hardcoded save strings.

### CB-02 · Human-readable Uzbek notification titles (+body) in bell & list — `i18n-copy` · high · M
**Files:** `components/NotificationsMenu.vue`, `views/ClientNotificationsView.vue`, `app/clientUi.ts`
**Why:** `NotificationsMenu.vue:183` always renders the raw code (`{{ item.event_code }} · {{ formatDate }}`) and `title()` falls back to `event_code` (`:29`); `ClientNotificationsView.vue:33` same. Buyers see snake_case like `order_status_changed` — a parity regression vs the prototype (`client-shell.js:19,53`). Bell also omits the body line the list already computes.
**Fix:** Add `clientNotificationTitle(item)` + reuse `body()` in `clientUi.ts` (mirror `adminNotificationTitle`); use in both `NotificationsMenu.title()` and the list; render a muted body line in the bell; drop the raw code sub-line.

### CB-03 · Read-only mode + bound-order banner for confirmed drafts in editor — `ux-flow` · high · M
**Files:** `views/ClientCuttingEditorView.vue`, `stores/cutting.ts`
**Why:** Editor has no read-only guard; inputs, add/delete/duplicate, and `watch(parts, scheduleSave, {deep:true})` (`:644`) are always active, and `CuttingDraft` (`cutting.ts:75-84`) doesn't expose `order_id/status`. Re-opening `/c/cutting/:id` after ordering shows a fully editable surface firing `updateDraft` on each keystroke — violates `cutting.md` §"Read-only view".
**Fix:** Surface `order_id/status` on `CuttingDraft`; when bound, disable inputs/actions, skip the autosave watcher, show a non-dismissible banner "Bu chizma &lt;order_number&gt; buyurtmasiga bog'langan" linking to `/c/orders/:id`.

### CB-04 · Pre-select & badge preferred branch in order-new step — `ux-flow` · high · S
**Files:** `views/ClientOrderNewView.vue`
**Why:** `selectedBranchId` starts null (`:21`); `onMounted` (`:189-195`) never seeds from `draft.preferred_branch_id`; `branchRows` (`:37-46`) only sorts has-quote up, no "recommended" marker. Client must re-find their preferred branch at checkout — `orders.md` §UX wants it pre-selected with a chip.
**Fix:** After quotes load, set `selectedBranchId` to `preferred_branch_id` when it has a valid quote; pin first; render a "Tavsiya — afzal filialingiz" chip.

### CB-05 · Set client SPA `<html lang="uz">` — `a11y` · high · S
**Files:** `web/client/index.html`
**Why:** `client/index.html:2` declares `<html lang="en">` while all copy is Uzbek; no runtime override. Screen readers use English phonetics for the whole UI — WCAG 3.1.1 (A) failure.
**Fix:** `<html lang="uz">` (align workshop/admin entries to their content too); per-element `lang` only for genuinely mixed screens.

### CB-06 · Focus-trap the cutting-editor edge-banding modal — `a11y` · high · M
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** Edge picker (`:1258-1436`) is `role=dialog aria-modal=true`, focuses panel on open (`:454`), handles Escape (`:537`), locks scroll (`:661`) — but has **no Tab/Shift-Tab trap** (unlike `ConfirmDialog.vue:47-62`). Keyboard/SR users can Tab onto the obscured part rows behind the scrim in the busiest flow.
**Fix:** Reuse the ConfirmDialog Tab-wrap logic within the edge dialog ref.

### CB-07 · Keyboard-operable placement rects (name + visible focus) — `a11y` · high · M
**Files:** `components/CuttingPanelSvg.vue`
**Why:** `CuttingPanelSvg.vue:53-66` gives each `<rect>` `tabindex=0 role=button` + handlers but no accessible name (sibling `<text>` `:67` unassociated), no focus-visible, and `role=button` on SVG rect is unreliably exposed. SR users hear only "button"; rects are below ~44px touch with no list fallback.
**Fix:** Add `:aria-label="label(placement)"` (or wrap rect+text in `<g role=button aria-label>`), a `:focus-visible` stroke, pair tap with the existing placement list as the primary touch affordance, consider roving-tabindex.

### CB-08 · 401/session-expired: silent refresh then login redirect — `states-errors` · high · L
**Files:** `api/client.ts`, `stores/auth.ts`, `app/createRoleApp.ts`
**Why:** `client.ts:47` throws `ApiError(401)` but nothing handles 401 anywhere; `auth.restore()` only refreshes once at boot. After the access token expires, every call surfaces as a generic "Ulanishda xatolik" with a retry that keeps failing — client locked out with no sign-in prompt.
**Fix:** On 401 from an authed call, try one silent `/auth/refresh` + retry; on failure `auth.clear()` + redirect to `loginPath` with "sessiya tugadi, qayta kiring". Centralize in `client.ts`.

### CB-09 · Surface createDraft failures incl. 50-draft cap — `states-errors` · high · S
**Files:** `stores/cutting.ts`, `views/ClientHomeView.vue`, `DraftsView.vue`
**Why:** `cutting.ts` `createDraft` (`:194-204`) is try/finally with no catch, never sets error/traceId; callers `newCutting` (`ClientHomeView.vue:47-55`, `DraftsView.vue:61-69`) are catch-less, so failure just flips the button back with an unhandled rejection. Covers API-down **and** backend `draft_limit_exceeded` (`cutting/service.py:52` `DRAFT_LIMIT=50`) — the "X / 50" counter implies a hard limit the UI never communicates.
**Fix:** Give `createDraft` a `captureError`+traceId path (mirror `optimizeDraft`); catch in both handlers with inline error/toast; on `draft_limit_exceeded` show "Saqlangan chizmalar chegarasi (50) to'ldi — eskisini o'chiring" (optionally disable at cap).

### CB-10 · Poll notification unread count (~45s) — `completeness-stub` · high · S
**Files:** `components/NotificationsMenu.vue`, `stores/notifications.ts`
**Why:** `NotificationsMenu.vue:85-91` calls `loadUnreadCount` once in a watch with `{immediate:true}`; no poll anywhere. Notifications are the **only** v1 channel, so an order reaching "ready"/cancelled shows a stale badge until manual reload. `notifications.md:21` mandates ~30–60s polling.
**Fix:** `setInterval(~45s)` in `onMounted` calling `loadUnreadCount` while a token exists, cleared `onBeforeUnmount`, gated on `document.visibilityState`.

### CB-11 · 409 cancel conflict: refetch order + actionable message — `correctness-bug` · high · M
**Files:** `views/ClientOrderDetailView.vue`, `ClientOrdersView.vue`, `stores/orders.ts`
**Why:** Backend raises 409 `order_version_conflict` (`sales/service.py:1724-1731`) with `details.current_version`; client sends cached version (`ClientOrderDetailView.vue:109`, `ClientOrdersView.vue:60`) and `captureError` sets raw code (`orders.ts:193-195`). Views render verbatim and never refetch — stale version reused, every retry fails identically, recoverable only by hard reload.
**Fix:** On 409 / `order_version_conflict`, call `loadClientOrder(id)` to refresh `version`, show "Buyurtma holati o'zgardi — yangilab qayta urinib ko'ring." (via CB-01 map).

### CB-12 · Batch checkout quote instead of per-branch fan-out — `performance` · high · M
**Files:** `views/ClientOrderNewView.vue`, `stores/orders.ts`, `backend/app/modules/sales/routes.py`
**Why:** `ClientOrderNewView.vue:140-152` `loadQuotes` does `Promise.all` over every active branch, each hitting `GET /client/orders/quote` with one `branch_id` (`orders.ts:215-220`; backend `sales/routes.py:70` takes one) and re-pricing the whole result per branch. `activeBranches` is unbounded — the "Choose workshop" screen blocks behind M requests and hammers the optimizer M× per order as the platform grows.
**Fix:** Add a batch quote endpoint (POST with `branch_ids`, or quote-all-eligible) pricing the draft against all candidates in one request; short-term cap concurrency and render branches progressively.

### CB-13 · Kill per-branch materials N+1 on Branches list — `performance` · high · M
**Files:** `views/ClientBranchesView.vue`, `stores/clientCatalog.ts`, `backend/app/modules/client_portal/routes.py`
**Why:** `ClientBranchesView.vue:22-24` does `Promise.all(branches.map(loadMaterialsForBranch))` — one full `GET /branches/{id}/materials` per branch (`clientCatalog.ts:108-115`, no limit) just to show ≤4 labels (`:146-150`). The 250ms search watcher (`:48-51`) re-runs the whole 1+N cycle per keystroke.
**Fix:** Return a small inline materials preview from `GET /branches` (or a bulk preview keyed by `branch_ids`) so the page needs one request; on search re-run only `loadBranches`, fetch materials only for newly-visible uncached branches.

### CB-14 · Shared toast/snackbar primitive + wire critical events — `design-parity` · high · M
**Files:** `components/NotificationsMenu.vue`, `views/ClientOrderNewView.vue`, `ClientOrdersView.vue`, `app/AppShell.vue`
**Why:** No toast primitive in Vue (grep for toast/snackbar/useToast = 0 non-test hits) although the prototype defines `.toast` (`app.css:444-448`) and fires it across flows (`order-new.html:431` on placement, `orders.html:156` on cancel, `client-shell.js:98` on mark-all-read). `ClientOrderNewView.vue:181` navigates away on success with no confirmation. `notifications.md:43` requires toasts for critical client events.
**Fix:** Build a shared `MpToast` (`.toast` parity: success/warn/danger, auto-dismiss, bottom-center) + `useToast()` + a `<ToastHost>` in AppShell; wire into placement/cancel, profile-reset, mark-all-read, and a critical-event toast when a new ready/cancelled row is detected.

### CB-15 · Flush autosave on unmount; stop clobbering edits mid-optimize — `correctness-bug` · med · M
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** Autosave debounces 700ms (`:644`). `optimize()` (`:580-588`) awaits `saveParts` then `optimizeDraft`, which reassigns `currentDraft`; the watcher (`:624-642`) sets `hydrating=true` and overwrites `parts.value` wholesale, so a keystroke between save resolving and hydrate is discarded (`scheduleSave` early-returns while hydrating, `:548`). `onBeforeUnmount` (`:654-658`) clears the timer but never flushes — navigating away within 700ms loses the edit. Silent data loss in the core editor.
**Fix:** Flush a pending save in `onBeforeUnmount` (await `saveParts()` if `saveState==='editing'`); in the `currentDraft` watcher avoid clobbering local parts when a save is in flight / there are unsaved edits (merge, or skip re-hydration unless the draft id changed).

### CB-16 · Surface optimize failures inline (+trace_id) — `states-errors` · med · S
**Files:** `views/ClientCuttingEditorView.vue`, `stores/cutting.ts`
**Why:** `optimize()` (`:580-588`) awaits `optimizeDraft` with no try/catch; the store captures error/traceId but the page-level `cutting.error` branch (`:733`) is unreachable once a draft loads (`v-else-if="draft"` `:740`). An optimize failure (timeout, invalid parts, 500) sets a store error the UI never shows — the button just spins and resets.
**Fix:** In `optimize()`, catch and render an inline error banner near the results section with the failure copy + `cutting.traceId`.

### CB-17 · Handle PDF download failures with feedback — `states-errors` · med · S
**Files:** `stores/cutting.ts`, `stores/orders.ts`, `views/ClientOrderDetailView.vue`, `ClientCuttingEditorView.vue`
**Why:** `downloadPdf` in both stores (`cutting.ts:350-358`, `orders.ts:370-378`) calls `api.blob` with no try/catch; `api.blob` throws on non-2xx (`client.ts:62-67`). Views bind the promise directly (`ClientOrderDetailView.vue:223`, `ClientCuttingEditorView.vue:1215`). On 403/404/500 the user gets an uncaught rejection — no spinner, no error, no download.
**Fix:** Wrap `downloadPdf` in try/catch, set a transient store download error + trace, surface a toast/inline message, add a per-button busy state.

### CB-18 · Pre-check draft usability on entering order wizard — `ux-flow` · med · S
**Files:** `views/ClientOrderNewView.vue`
**Why:** `onMounted` (`:189-195`) loads draft+quotes but never checks if the draft is already confirmed/bound; the only guard is the `!draft || !chosenResult` empty state (`:230`). `placeOrder` (`:158-187`) only catches the server error after the user fills contact info. A back-nav to a stale draft walks the whole wizard then hits a raw error at submit — `orders.md` §UX requires pre-checking.
**Fix:** On mount, if the draft is confirmed/has an `order_id`, redirect to `/c/orders/:id` (or `/c/cutting/:id`) with a short toast instead of rendering the wizard.

### CB-60 · Port prototype's compact phone layout for part rows — `design-parity` · high · M
**Files:** `views/ClientCuttingEditorView.vue`, `prototypes/prototype-full/client/cutting.html`
**Why:** The row grid (`:872`) is `lg:grid-cols-[34px_minmax(240px,1.6fr)_90px_90px_76px_minmax(280px,1fr)_96px]` — below 1024px there is **no intermediate layout**, so every field stacks into one column ≈500-600px tall per part (incl. full-width Nusxa/O'chirish at `:1016-1031`). The prototype defines a dedicated ≤760px layout (`cutting.html:51-63`): three number inputs share one line (`flex: 1 1 72px`), the edges button becomes a labeled full-width strip, row actions collapse into a ⋯ menu. On a 390px phone a 20-part list is ~10-12 screens of scrolling — on the make-or-break screen.
**Fix:** Port the compact sub-lg layout: dims on one shared line (`grid-cols-3` at <lg), material + source chips on one line, Krom as a slim full-width strip, Nusxa/O'chirish as a compact inline pair or overflow menu.

### CB-62 · Edge modal: dvh sizing + bottom-sheet on phones — `responsive` · high · M
**Files:** `web/src/assets/main.css`, `views/ClientCuttingEditorView.vue`
**Why:** `.client-edge-modal` is center-fixed with `max-height: 90vh` (`main.css:747-764`), `94vh` at ≤520px (`:1202-1205`). On iOS/Android 100vh exceeds the visible viewport under browser toolbars, so the footer (Bekor qilish / Qo'llash, `:1427-1434`) lands behind the bottom bar; when the keyboard opens for `.ep-search` the modal doesn't reflow — Qo'llash can become unreachable. The edge diagram is fixed ~308px wide (`main.css:903-921,968-975`) vs ~272px available at a 320px viewport — it clips.
**Fix:** `max-height: 90dvh` (vh fallback); at ≤520px switch to a bottom-sheet (`inset: auto 0 0 0`, no transform, top radius) with a sticky footer inside; scale the diagram with `max-width: 100%`.

### CB-65 · Cutting SVG: normalized viewBox, label threshold, zoom — `ux-flow` · high · M
**Files:** `components/CuttingPanelSvg.vue`, `prototypes/prototype-full/client/cutting.html`
**Why:** `CuttingPanelSvg.vue:19` sets the viewBox to raw panel mm (e.g. 2800×2070) and `:70` draws every label at `font-size="14"` in those units — ≈1.8 CSS px on a 360px phone; a 200×80mm part is a ~26×10px tap target. Labels draw unconditionally even on tiny rects; no pinch-zoom/pan/fullscreen. The prototype normalizes to an 800-unit viewBox (`cutting.html:1714-1716`), draws labels only when the rect exceeds 80×30px, and pairs the sheet with a color legend. The optimisation result — the payoff of the whole flow — is an unreadable thumbnail on a phone.
**Fix:** Normalize the viewBox to a fixed unit width, suppress labels below a size threshold (rely on a color-coded legend), add basic zoom (`touch-action: pinch-zoom` + tap-to-enlarge or zoom buttons). Distinct from CB-07 (rect ARIA) — this is geometry/legibility/zoom.

### CB-70 · Gate the dev OTP hint "000000" to dev builds — `security` · high · S
**Files:** `views/LoginView.vue`
**Why:** `LoginView.vue:238-240` shows `Dev rejimda test kodi: 000000` gated only on `resendAfter` (set on every successful OTP send, `:104`) — there is **no `import.meta.env.DEV` check**, so the hint renders in production. Per `docs/ref/features/access-management.md:117-121` prod may currently run with `ALLOW_PROD_OTP_DEV_CODES=true` (commit 9ad96aa), where any dev code logs in as ANY phone — the prod login screen advertises an account-takeover bypass; even after dev codes are removed it misleads real users into burning attempts.
**Fix:** Gate on `import.meta.env.DEV` (`v-if="isDev && resendAfter"`); never ship dev-code copy in prod bundles; optionally drive the hint text from a VITE_ var instead of hardcoding 000000.

### CB-75 · Block protocol-relative `?redirect` (open redirect) — `security` · med · S
**Files:** `views/LoginView.vue`
**Why:** `redirectTo` validates only `redirect.startsWith('/')` (`LoginView.vue:27-30`), which passes `//evil.com` and `/\\evil.com`; `finish()` then `router.replace(redirectTo.value)` (`:72-74`). A phishing link to the genuine login page can carry a hostile redirect param — bounce a freshly-authenticated client off-origin (or at minimum strand them on a failed replace).
**Fix:** Standard same-origin path guard: `redirect.startsWith('/') && !redirect.startsWith('//') && !redirect.startsWith('/\\')`, falling back to `config.homePath`.

### CB-82 · Validate part max against panel − 2× edge trim — `spec-conformance` · high · M
**Files:** `views/ClientCuttingEditorView.vue`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:207` requires L/W "validated against the part-min / part-max bounds of the chosen panel"; the Limits table (`:143-144`) defines part max = panel − 2× edge trim. The editor only checks the 50mm minimum — `partIsInvalid()` (`:221-231`) tests `< 50`, inputs carry only `min="50"`. `panel_length_mm`/`panel_width_mm` are loaded (`stores/cutting.ts:96-97`) but never used for an upper bound. A 3000×2000 part on a 2750×1830 panel sails through to a raw backend `part_too_large` failure.
**Fix:** Compute max L/W from the selected panel material (− 2× `EDGE_TRIM_MM`, either orientation for non-grained panels), set the input `max`, danger class, and an inline message naming the max size per `cutting.md:336-338`.

### CB-86 · Fix per-row recovery: scoped bring-own + pick-different-material — `spec-conformance` · high · M
**Files:** `views/ClientCuttingEditorView.vue`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:255-262` mandates two inline buttons per affected row — "I'll bring my own" (flips only the affected panel **or side**) and "Pick a different material" (opens the picker pre-filtered to the branch). Today: (a) the row warning (`:1034-1045`) has only "O'zim olib kelaman" and no branch name; (b) `bringOwn()` (`:540-545`) flips the panel source AND **every** banded edge side to 'own' — even sides whose tape IS carried, silently changing what the client is billed for; (c) `notCarriedRows` (`:86-88`) filters `material_source === 'shop'`, so a row with an own panel but a not-carried shop edge shows a row warning yet is excluded from the banner's "N qator" count — the counts disagree.
**Fix:** Scope `bringOwn()` to only the not-carried panel/sides from `rowNotCarried()`; add a "Boshqa material tanlash" button opening the right picker with the affected side active; name the branch in the warning; base the banner count on `rowNotCarried(part).length > 0`.

---

## P2 — important

### CB-19 · "No branch carries the set" recovery panel — `states-errors` · med · M
**Files:** `views/ClientOrderNewView.vue`
**Why:** When a branch can't fulfil the cut, `loadQuotes` (`:134-156`) stores a generic string and disables the card (`:268`). If every branch fails, the only empty state is `activeBranches.length===0` (`:249`) — a wall of greyed cards with no way forward. `orders.md` §UX wants an inline panel naming offending materials + a "flip to I'll bring it" link.
**Fix:** On `branch_does_not_carry_*` (or all-unquotable), render a recovery panel naming the not-carried materials and link back to `/c/cutting/:draftId`.

### CB-20 · Per-branch quote error labeling uses real per-call error — `correctness-bug` · med · M
**Files:** `views/ClientOrderNewView.vue`, `stores/orders.ts`
**Why:** `loadQuotes` fires per-branch quotes concurrently (`:140-152`); each catch does `quoteErrors[id] = quoteErrorLabel(orders.error)`. But `quoteForDraft` (`orders.ts:215-220`) never sets `orders.error` — it's shared module state mutated by concurrent requests — so each branch reads an unrelated/stale value and can't tell 403 (closed) from 422 (materials unavailable).
**Fix:** Capture the real per-call error in the catch (`catch (e) { quoteErrors[id] = quoteErrorLabel(e instanceof ApiError && e.status===403 ? 'permission_denied' : null) }`).

### CB-21 · Page-level error+retry when all checkout quotes fail — `states-errors` · med · M
**Files:** `views/ClientOrderNewView.vue`
**Why:** `loadQuotes` (`:134-156`) catches per-branch failures into a card line but there's no page-level error/trace/retry; top-level only handles `cutting.loading/error` and `!draft`. If quoting is broken platform-wide, every workshop shows "—" with no trace and no retry.
**Fix:** Track `quotesFailedAll`; when every active branch fails, render a `client-error` block with `orders.traceId` and a "Qayta urinish" re-running `loadQuotes` (ideally atop CB-22).

### CB-22 · Extract shared ClientErrorState; add trace_id to notifications — `states-errors` · med · M
**Files:** `views/ClientHomeView.vue`, `ClientOrdersView.vue`, `ClientOrderDetailView.vue`, `ClientNotificationsView.vue`, `stores/notifications.ts`
**Why:** The same client-error block is hand-copied across `ClientHomeView.vue:138-146`, `ClientOrdersView.vue:101-113`, `ClientOrderDetailView.vue:156-168`, `DraftsView.vue:133-141`, `ClientBranchesView.vue:95-103`, with inconsistent trace labels; the notifications store has no `traceId`, so `ClientNotificationsView.vue:103-114` and the bell omit trace.
**Fix:** Extract a `ClientErrorState` component (title/traceId/@retry); add `traceId` to the notifications store (via `apiTraceId` in both catches) and render it.

### CB-23 · Fault-tolerant per-branch material loads (allSettled+retry) — `states-errors` · med · M
**Files:** `views/ClientBranchesView.vue`, `stores/clientCatalog.ts`
**Why:** `refreshBranches` (`:18-28`) `Promise.all` over `loadMaterialsForBranch` (`clientCatalog.ts:108-115`, rethrows) — one branch failing rejects the whole batch, partially populates `materialsByBranch`, and the unhandled rejection leaves every branch stuck on "Materiallar yuklanmoqda…". Store `materialsError/materialsTraceId` (`:101-102`) never read.
**Fix:** `Promise.allSettled` / per-branch try/catch, per-branch error flag, render "Materiallarni yuklab bo'lmadi" + trace + retry on the affected row.

### CB-24 · Handle cancel-order / delete-draft failures in dialogs — `states-errors` · med · M
**Files:** `views/DraftsView.vue`, `ClientOrdersView.vue`
**Why:** `DraftsView` `confirmDeleteDraft` (`:79-89`) is try/finally with no catch and `deleteDraft` (`cutting.ts:239-243`) captures nothing, so failure leaves the dialog open with an unhandled rejection. `ClientOrdersView` `confirmCancel` (`:55-66`) catches but renders raw `orders.error` (`:193-194`).
**Fix:** Catch in `confirmDeleteDraft` showing an inline error + trace in the dialog slot; map order action codes via the CB-01 map.

### CB-25 · Loading + error/empty state on client profile load — `states-errors` · med · M
**Files:** `views/ProfileView.vue`
**Why:** `onMounted` (`:181-191`) runs `Promise.all([loadSessions, loadClientProfile, loadClientOrders, …])` with no try/catch; `loadClientProfile` (`:90-98`)/`loadSessions` throw without capture. No page-level loading/error for the client profile (only inline save message `:307`) — a failed fetch yields a half-populated card with no name, empty branch dropdown, no trace, no retry.
**Fix:** Add loading + error state with trace + retry; guard the `Promise.all`.

### CB-26 · Rollback + surface failures on mark-read / mark-all-read — `states-errors` · med · S
**Files:** `stores/notifications.ts`, `views/ClientNotificationsView.vue`, `components/NotificationsMenu.vue`
**Why:** `notifications.ts` `markRead` (`:56-65`) / `markAllRead` (`:67-74`) have no try/catch — they optimistically mutate `items/unread` and throw on failure; callers await without catch. A failed mark-read shows "read" while the server still has it unread.
**Fix:** Wrap in try/catch, roll back the optimistic update on failure, surface a small toast/inline error.

### CB-27 · normalizeUzPhone must insert +998 (fixes display) — `correctness-bug` · med · S
**Files:** `app/clientUi.ts`, `views/ClientOrderNewView.vue`
**Why:** `clientUi.ts:47-51` — `normalizeUzPhone` strips non-digits then prefixes `+` in both branches, never adding `998`, so `901234567` → `+901234567`. The `isUzPhone` gate blocks submit, but the same normalizer feeds `formatPhone` (`:53-57`) for display, so the confirmation/pickup card renders a mangled phone for any value missing the prefix.
**Fix:** Strip leading zeros and prepend `+998` for a 9-digit national number; unit-test `901234567`, `0901234567`, `998901234567`, `+998901234567`.

### CB-28 · formatPercent: always ×100 the 0..1 fraction — `correctness-bug` · med · S
**Files:** `app/clientUi.ts`
**Why:** `clientUi.ts:76` — `formatPercent` uses `numeric <= 1 ? numeric*100 : numeric`. Backend constrains `waste_percentage` to [0,1] (`cutting/models.py:42`) and the PDF multiplies ×100 (`rendering.py:75`), so the contract is always a fraction. The `>1` branch is dead and would silently mis-scale future percent-shaped values; the waste figure clients choose on is a guess.
**Fix:** `return `${(numeric*100).toFixed(2)}%`` (keep null/NaN guards).

### CB-29 · Per-edge-material metres + parts-placed count in result — `completeness-stub` · med · M
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** The result panel shows a single rolled-up edge total via `metres(consumedShop+consumedOwn)` (`:1119-1122`) and a one-line shop/own split (`:1219-1224`); no per-edge-material list, no "parts placed N/N" (`:1072-1245`). A job where parts didn't place looks identical to a full one — `cutting.md` §"result panel" requires both.
**Fix:** Add a "Krom (material bo'yicha)" list over `edge_consumed_shop/own_by_material`, and a "Joylashtirildi N/N" chip (placements vs requested), red + list when N < total.

### CB-30 · Show order notes (note_workshop/client) in Overview — `completeness-stub` · med · S
**Files:** `views/ClientOrderDetailView.vue`, `stores/orders.ts`
**Why:** `OrderSummary` carries `note_client`/`note_workshop` (`orders.ts:99`) and `orders.md:270-271` lists "notes" in the client Overview, but the Overview tab (`:276-384`) never references either. A workshop pickup instruction is silently dropped.
**Fix:** Add an "Izoh" card in Overview rendering `note_workshop` (and `note_client`) when non-null.

### CB-31 · Valid tablist/tab/tabpanel + keyboard on order detail — `a11y` · med · M
**Files:** `views/ClientOrderDetailView.vue`
**Why:** `:239` sets `role="tablist"` but the four buttons (`:240-271`) lack `role=tab`/`aria-selected`/`aria-controls` and panels (`:276,386,462,501`) lack `role=tabpanel`/`aria-labelledby`; arrow-nav unwired. Invalid ARIA — SR hears "tab list" then generic buttons.
**Fix:** Add `role=tab`+`:aria-selected`+`:aria-controls` to buttons, `role=tabpanel`+`aria-labelledby`+`tabindex=0` to panels, arrow handling; or drop `role=tablist` and use `aria-pressed`.

### CB-32 · ARIA menu keyboard ops on notifications dropdown — `a11y` · med · M
**Files:** `components/NotificationsMenu.vue`
**Why:** Advertises `aria-haspopup=menu` (`:104`)/`role=menu` (`:138`)/`role=menuitem` (`:176`) but no Escape-close, no arrow-nav, no focus move on open (`toggle()` `:50` flips a boolean; close is pointer-only). The `role=menu` keyboard promise is unmet on the client's primary alert surface.
**Fix:** Move focus to first menuitem on open; Escape (close+return focus); Up/Down roam; make footer actions menuitems or move them out of `role=menu`.

### CB-33 · Keyboard-accessible whole-card targets (home/orders) — `a11y` · med · M
**Files:** `views/ClientHomeView.vue`, `ClientOrdersView.vue`
**Why:** `ClientHomeView.vue:257-261`/`:345-349` and `ClientOrdersView.vue:126-131` make cards clickable via `@click=router.push` with `cursor-pointer` but no `tabindex`/`role` — not focusable, no role. On completed/cancelled rows (no inner button), the primary "open" affordance is mouse-only.
**Fix:** Remove `@click` from the article and rely on a focusable `RouterLink`/button inside, or convert each card to a single focusable `RouterLink`.

### CB-34 · Raise `--color-ink-muted` to WCAG AA contrast — `a11y` · med · S
**Files:** `web/src/assets/main.css`
**Why:** `main.css:15` `--color-ink-muted: #748196` = 3.64:1 on bg `#f4f6f8`, 3.95:1 on white — below 4.5:1 AA. It carries small text across most screens (dates, counts, waste %, captions), e.g. `ClientHomeView.vue:268`, `ClientOrderDetailView.vue:198` — WCAG 1.4.3 failure.
**Fix:** Darken to ~`#5b6675` or darker (≥4.5:1 on `#f4f6f8`; `ink-soft #475569` = 7.58:1 reference); re-verify the few darker-tint placements.

### CB-35 · Replace letter-glyph placeholders with prototype SVG icons — `design-parity` · med · M
**Files:** `ClientHomeView.vue`, `ClientOrdersView.vue`, `ClientOrderDetailView.vue`, `ClientNotificationsView.vue`, `ClientCuttingEditorView.vue`, `ClientBranchesView.vue`, `DraftsView.vue`
**Why:** The prototype uses real SVG icons in empty/error states and stat tiles (`orders.html:126`, `home.html:259`, `home.html:172-180` via MP_ICONS), but the Vue ports substitute bare letters/symbols — `ClientOrdersView.vue:116` 'B', `ClientHomeView.vue:248/336` 'B'/'C' and stat badges `:156/171/187/204`, `ClientNotificationsView.vue:117` '✓', `ClientCuttingEditorView.vue:847/855/1090` '↑/+/∑', `ClientBranchesView.vue:106` 'U', `ClientOrderDetailView.vue:494` 'L'. ~21 placeholders look unfinished.
**Fix:** Add a small Vue `Icon` component / shared `iconPath` carrying the prototype MP_ICONS set; swap each glyph for the matching SVG.

### CB-36 · Add line icons to client header nav — `design-parity` · med · S
**Files:** `app/roleConfig.ts`, `components/AppShell.vue`
**Why:** Prototype renders an inline SVG before each client nav label (`client-shell.js:109-112`, styled `app.css:572-577`), but `clientConfig.nav` (`roleConfig.ts:76-82`) has no `icon` and `AppShell.vue:215-219` renders client nav text-only — while workshop/admin branches DO render icons via `iconPath` (`:264-266`), making client the lone outlier.
**Fix:** Add icon keys (home, scissors, orders, store) to `clientConfig.nav` and render via the existing `iconPath` map (extend with home/store).

### CB-37 · Drop 5th "Profil" nav item; fix mobile profile reach — `design-parity` · med · S
**Files:** `app/roleConfig.ts`, `web/src/assets/main.css`, `components/AppShell.vue`
**Why:** `clientConfig.nav` has FIVE items incl. Profil (`roleConfig.ts:81`) vs the prototype's FOUR (`client-shell.js:108-113`, Profil via the user pill). To compensate, two CSS hacks fire ≤680px: `.client-nav a:last-child {display:none}` (`main.css:1183-1185`) AND `.client-user-pill .client-user-name {display:none}` (`:1187-1189`) — so on a phone the only path to profile/logout is a ~30px unlabeled avatar (`AppShell.vue:223-226`).
**Fix:** Remove the Profil entry (still reachable via the pill at all sizes), delete the `last-child {display:none}` rule, give the pill a discoverable label/aria-label on mobile.

### CB-38 · Paginate client orders list — `performance` · med · M
**Files:** `views/ClientOrdersView.vue`, `stores/orders.ts`, `backend/app/modules/sales/routes.py`
**Why:** `orders.ts:234-248` `loadClientOrders` sends only status+search and assigns the whole array; backend `client_orders_index` (`sales/routes.py:47-54`) accepts no limit/offset; the view renders every order (`:125-176`) and reloads on each cancel (`:62`). A long-time customer re-downloads their entire history every visit.
**Fix:** Add limit/offset (or cursor) to `GET /client/orders` + store; render a first page with load-more, defaulting to recent/active.

### CB-39 · Lightweight drafts-summary endpoint for list views — `performance` · med · M
**Files:** `views/DraftsView.vue`, `ClientHomeView.vue`, `stores/cutting.ts`
**Why:** `cutting.ts:181-192` `loadDrafts` fetches all drafts with no params, and `CuttingDraft` embeds full `results[]` incl. `parts_snapshot`, `material_snapshots`, per-panel placements (`:48-84`), so each list card carries its whole optimization payload. `DRAFT_CAP=50` is display-only (`DraftsView.vue:10,119`); `ClientHomeView.vue:58` reloads the full list for 4 recent.
**Fix:** Add a drafts-summary endpoint (or `?fields=`/`?limit=`) omitting `results.panels/placements`; home requests only the few summaries it renders.

### CB-40 · Scope/paginate editor catalog loads (not whole catalog) — `performance` · med · M
**Files:** `views/ClientCuttingEditorView.vue`, `stores/cutting.ts`, `backend/app/modules/sales/routes.py`
**Why:** `ClientCuttingEditorView.vue:596-609` `loadMaterials` calls panel+edge with `carriedOnly:false` and `branchId = preferred_branch_id` (undefined for a new draft), so `GET /client/catalog/materials` returns the entire platform catalog (`cutting.ts:284-307`, no limit). Full arrays drive client-side filtering + re-rank on every edge-picker open; `setPreferredBranch` (`:572-578`) re-downloads identical lists with no per-branch cache.
**Fix:** Default the query to the draft's branch (or `carried_only`), add server-side search-driven loading + a page limit (fetch more only on search / "show all"), cache by `(kind, branchId)`.

### CB-41 · Paginate notifications page; server-side unread filter — `completeness-stub` · low · M
**Files:** `views/ClientNotificationsView.vue`, `stores/notifications.ts`
**Why:** `ClientNotificationsView.vue:65` calls `loadList(50)`; store (`notifications.ts:43-54`) accepts only a flat limit (no offset/cursor/since), and the read/unread filter (`:21-27`) is client-side over the first 50. A client with >50 can't reach older ones and the unread filter only spans page 1 — `notifications.md:30,42` require pagination + server unread filter + since.
**Fix:** Add offset/cursor (or since) to `loadList` + a "Load more"; move unread filtering to a query param.

### CB-42 · Localize English fallbacks (pickers/summary/SearchCombobox) — `i18n-copy` · med · S
**Files:** `stores/cutting.ts`, `views/ClientCuttingEditorView.vue`, `components/SearchCombobox.vue`, `ClientOrderNewView.vue`
**Why:** English fallbacks leak: `cutting.ts:142` 'No material', `:146` '… mm edge' (shown in order summary `ClientOrderNewView.vue:521` and editor labels); `branchOptions/panelChoices` meta 'active branch'/'temporarily closed'/'not at branch' (`ClientCuttingEditorView.vue:62-65,77`); `SearchCombobox` defaults 'Search'/'No matching options' (`:17,20`) not overridden by the editor picker (`:877-884`).
**Fix:** Return Uzbek fallbacks ("Material yo'q", "mm krom", "faol filial", "vaqtincha yopiq", " · filialda yo'q") and Uzbek-default the SearchCombobox `placeholder`/`:no-results-text`.

### CB-43 · Lock background scroll when ConfirmDialog is open — `responsive` · low · S
**Files:** `components/ConfirmDialog.vue`, `web/src/assets/main.css`
**Why:** The edge-picker toggles `body.modal-open` (`ClientCuttingEditorView.vue:660-662`) using `body.modal-open {overflow:hidden}` (`main.css:50-52`), but `ConfirmDialog` (cancel order, clear parts, delete draft, logout) only renders a fixed overlay (`:95`) without freezing body. On mobile, scrolling over it drags the page underneath.
**Fix:** Watch `open` in ConfirmDialog and toggle `document.body.classList.toggle('modal-open', open)`, cleared on unmount.

### CB-59 · `inputmode=numeric` on dimension/quantity inputs — `ux-flow` · med · S
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** The Uzunlik/Eni/Soni inputs (`:911-942`) are `type="number"` with no `inputmode` — on iOS Safari that opens the full QWERTY keyboard, not the digit pad. The repo already uses `inputmode="numeric"` elsewhere (`WorkshopFinanceIncomeView.vue:168`, `LoginView.vue:231`); the editor — the highest-frequency numeric-entry screen (~60 numbers per 20-part draft) — is the outlier.
**Fix:** Add `inputmode="numeric"` (+ `enterkeyhint="next"`) to the three inputs; keep `type=number` for desktop spinners.

### CB-61 · Raise sub-44px touch targets (chips, panel tabs, modal buttons) — `a11y` · med · S
**Files:** `views/ClientCuttingEditorView.vue`, `web/src/assets/main.css`
**Why:** `.mp-chip` is `min-height: 24px` (`main.css:170-182`) yet used as tappable buttons: per-row Ustaxona/O'zim toggles (`:890-906`) and the panel selector tabs in results (`:1183-1191`). The Algoritm solishtirish toggle is a bare text button ~21px tall (`:1136-1142`); the edge-modal close is 34×34 (`main.css:783-794`) and `.edge-btn.h` is 32px (`:968-971`). Mistaps on the most-used per-part controls.
**Fix:** Raise interactive chips to min-height 36-44px on touch (or tap-target extension), give the toggle `min-h-11 px-3`, bump the close to 44×44 and `.edge-btn.h` to ≥40px.

### CB-63 · iOS-proof modal scroll lock + overscroll containment — `ux-flow` · med · S
**Files:** `web/src/assets/main.css`, `views/ClientCuttingEditorView.vue`
**Why:** The only lock is `body.modal-open { overflow: hidden }` (`main.css:50-52`) — on iOS Safari that does not block touch-scrolling the page behind a fixed modal. The modal has two nested scrollers (`.client-edge-modal-b` `:802-809`, `.ep-edge-list` `:1002-1008`) with no `overscroll-behavior`, so reaching the end of the krom list chains scroll to the background page; after closing, the user lands elsewhere in the 20-part list. (Distinct from CB-43 — ConfirmDialog has no lock at all.)
**Fix:** Add `overscroll-behavior: contain` to both scrollers; harden the body lock for iOS (`position: fixed` + `top: -scrollY`, restored on close) in the shared modal-open toggle.

### CB-64 · Keyboard/container-aware combobox & select popovers — `ux-flow` · med · M
**Files:** `components/SearchCombobox.vue`, `components/FormSelect.vue`, `views/ClientCuttingEditorView.vue`
**Why:** SearchCombobox renders its listbox `absolute mt-1 max-h-72` strictly below the input and opens on focus (`:173,177-184`); the only aid is `scrollIntoView({block:'nearest'})` (`:68-74`) which scrolls the layout viewport, not the keyboard-shrunk visual viewport — no flip-up, no available-space clamp. The Qalinlik FormSelect sits inside the edge modal's scroll container (`:1391-1396`; modal `overflow: hidden` `main.css:756`), so its 288px dropdown is clipped. The two pickers at the heart of part entry are fiddly or partially unusable on phones.
**Fix:** Clamp listbox max-height to available space (`min(18rem, 40dvh)` / visualViewport) and flip above when needed; for FormSelect inside modals, teleport the listbox to a fixed layer or auto-scroll it fully into view.

### CB-68 · 16px form-control font on mobile (stop iOS auto-zoom) — `responsive` · med · S
**Files:** `web/src/assets/main.css`, `components/SearchCombobox.vue`, `web/client/index.html`
**Why:** body is 14px (`main.css:44`), `.mp-input` inherits it, SearchCombobox input is `text-sm` (14px, `:161`), `.ep-search` is 13px (`:982-992`); the viewport meta has no maximum-scale (`client/index.html:10`). iOS Safari auto-zooms ~15-25% on every focus of sub-16px fields and often leaves the layout zoomed/pannable after blur — every dimension/material/krom entry jolts the page.
**Fix:** `@media (max-width: 768px) { .mp-input, .ep-search, [role=combobox] { font-size: 16px } }` — do NOT add maximum-scale=1 (blocks accessibility zoom).

### CB-71 · Honor 429 `retry_after_seconds` with live resend countdown — `states-errors` · med · M
**Files:** `views/LoginView.vue`, `stores/auth.ts`
**Why:** Backend returns `details.retry_after_seconds` on rate limit (`otp.py:370-375`); the store's `errorCode()` extracts only `body.code` and discards details (`auth.ts:54-59`). LoginView shows static copy (`:59`) and the `sendOtp` catch (`:107-108`) never calls `startCooldown`, so the resend button is immediately re-enabled and the user can spam 429s. Spec (`access-management.md:134-135,330-331`) requires "Try again in N s" with a disabled countdown.
**Fix:** Surface `details.retry_after_seconds` from ApiError, render "… N soniyadan keyin urinib ko'ring", and `startCooldown(retry_after_seconds)` in the catch when code is `code_send_rate_limited`.

### CB-72 · Show attempts-remaining on `invalid_code` — `design-parity` · med · M
**Files:** `views/LoginView.vue`, `backend/app/modules/access/otp.py`
**Why:** clientErrorText maps invalid_code to bare "Kod noto'g'ri." (`:60`); the prototype renders `Kod noto'g'ri. Qolgan urinishlar: N.` (`login.html:144`) and the spec requires it (`access-management.md:137-138,327`). The backend raises invalid_code with no details payload (`otp.py:222`), so the count isn't even available — the client guesses blind until the 5th attempt burns the challenge.
**Fix:** Backend: add `details={"attempts_remaining": …}` to the invalid_code error. Frontend: read it from `ApiError.body.details` and render the prototype copy.

### CB-73 · Un-dead-end the name step on `code_expired` — `ux-flow` · med · S
**Files:** `views/LoginView.vue`
**Why:** The name-step form (`:273-308`) re-submits phone+code but has no "edit phone"/"resend" affordance (those exist only on the code step, `:258-270`). OTP TTL is 5 min; if it lapses while a first-time client types their name, verify fails with "Kod muddati tugadi. Yangi kod oling." (`:61`) while offering **no control to get a new code** — the only escape is a full page reload, on the registration conversion path.
**Fix:** Add "← Raqamni o'zgartirish" to the name step; on code_expired/too_many_attempts auto-return to the phone/code step with otpCode cleared and resend focused.

### CB-76 · Searchable preferred-branch selector — `spec-conformance` · med · M
**Files:** `views/ProfileView.vue`, `components/FormSelect.vue`
**Why:** Spec: "preferred branch selector with **searchable** workshop + branch options" (`access-management.md:143-145`). ProfileView uses plain FormSelect (`:272-278`) — arrow-key listbox only, no filter/typeahead; all branches across all workshops render as one flat list (`:53-63`). Past a handful of workshops this is the slowest control on the profile, on a phone.
**Fix:** Swap to the existing SearchCombobox (filter on workshop + branch name), keep the clear action.

### CB-79 · Reject whitespace-only name on registration step — `correctness-bug` · med · S
**Files:** `views/LoginView.vue`, `backend/app/modules/access/otp.py`
**Why:** Spaces pass the HTML `required` (`:284-291`); backend `_normalize_name` turns blank into None and verify returns `{is_new:true}` again (`otp.py:225-228`) instead of the spec's `name_required` (`access-management.md:100-102`). The view's `if ('is_new' in response)` keeps clientStep at 'name' with no error (`:123-126`) — pressing "Davom etish" visibly does nothing; the mapped name_required copy (`:63`) is unreachable.
**Fix:** Frontend: trim and show name_required locally before calling verify. Backend: raise `name_required` when a supplied name normalizes to None.

### CB-83 · 100-part cap + blocking roll-up under the parts table — `spec-conformance` · med · S
**Files:** `views/ClientCuttingEditorView.vue`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:145` caps parts per optimisation at ≤100; `:244-245` requires "a single roll-up message below the table when something blocks the optimiser". Optimise is disabled only on `optimizing || parts.length === 0` (`:1064`); `totalQuantity` (`:114-116`) is computed but never compared to 100; the footer (`:1049-1060`) shows the English saveError or a neutral count — no enumeration of blockers. 120 parts → raw backend `too_many_parts` only after tapping Optimise.
**Fix:** Computed blockers list (invalid rows, total > 100) rendered as one Uzbek roll-up; disable Optimise while blockers exist, naming the cap.

### CB-84 · Panel picker filters (manufacturer/type/thickness) + sort — `spec-conformance` · high · L
**Files:** `views/ClientCuttingEditorView.vue`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:206` requires dropdown filters above the panel picker — Manufacturer (multi-select), Type, Thickness — and sort by relevance/decor/manufacturer; user story `:167-168` (Egger vs Kronospan). The implementation is a bare SearchCombobox (`:72-80,877-884`) with zero filter controls; `manufacturer_name`/`type`/`thickness_mm` exist on the option type (`stores/cutting.ts:89-93`) but no UI uses them. (The edge picker HAS search + thickness — only the panel picker lacks its filters.) Pairs with CB-40's scoped loading but is a distinct UI surface.
**Fix:** Add a filter row (manufacturer multi-select, type, thickness) feeding the combobox options, plus a sort control, per the parts-table spec.

### CB-85 · Grain indicator on the panel chip — `spec-conformance` · med · S
**Files:** `views/ClientCuttingEditorView.vue`, `stores/cutting.ts`
**Why:** Spec `cutting.md:213-214`: a small arrow appears **on the panel chip** when the chosen panel has grain — a passive cue. `grain_direction` is delivered (`stores/cutting.ts:98`) but "grain" appears nowhere in the editor — the selected-panel area renders only a swatch + source chips (`:885-906`). Clients can't anticipate why a part won't rotate or why a run fails with impossible_grain.
**Fix:** When `materialById(part.material_id)?.grain_direction`, render a small arrow with an accessible label ("Tola yo'nalishi bor — qism burilmaydi") next to the swatch.

### CB-87 · Material tab strip in visualiser; dimensions in legend — `spec-conformance` · med · M
**Files:** `views/ClientCuttingEditorView.vue`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:300-306`: a material tab strip (`DSP H1334 18mm · 2750×1830 · 3 panels`) with panel tabs within a material; the legend shows part #, **dimensions**, quantity index, rotation. The implementation renders one flat chip per panel across all materials (`panelTitle()` `:615-618,1181-1192`) with no grouping/size/count; the Joylashuvlar legend (`:1225-1242`) shows only `part_ref #index` + 'R'. On a multi-material job the chip row is an undifferentiated list.
**Fix:** Group `chosenResult.panels` by material_id into a first-level tab strip labelled `name · L×W · N panels` (from material_snapshots + panels_used_by_material), panel tabs inside; add `length×width` to legend rows.

### CB-88 · Drafts list: branch chip + material label pre-optimise — `spec-conformance` · med · M
**Files:** `views/DraftsView.vue`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:320-322`: each row shows the dominant panel material, relative time, **the preferred branch chip when set**, delete. DraftsView never reads `preferred_branch_id`, and `materialName()` (`:43-46`) resolves names only from `chosenResult(draft)?.material_snapshots` — so any never-optimised draft titles as "Material tanlanmagan" (`:58`) even with every part's material picked. Several such drafts are indistinguishable.
**Fix:** Render a branch chip when set; derive the dominant material from parts_snapshot ids resolved against the catalog (or fold both into the CB-39 drafts-summary endpoint).

### CB-89 · Per-row attribution of optimiser/stale-catalog errors — `spec-conformance` · med · L
**Files:** `views/ClientCuttingEditorView.vue`, `stores/cutting.ts`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:334-340,348-351,360-363`: material_not_found/impossible_grain/part_too_large **flag the offending row**; a catalog change while a draft sits flags the row on next open; a deactivated edge material clears that side with a one-tap replacement. Today `partIsInvalid()` checks only emptiness/mins — an unresolvable material_id shows no flag; `optimizeDraft` collapses every failure into one 'cutting_optimize_failed' string with no part_ref mapping; no on-open stale scan exists. On a 30-row draft the client bisects rows by hand. (Distinct from CB-16 — that adds the generic inline error surface; this is per-row attribution.)
**Fix:** On open, mark rows whose material/edge ids don't resolve (danger border + replacement affordance); parse the optimiser error's part reference (extend backend details with part_ref if absent), set a per-row error naming the limit, scroll the first offender into view.

### CB-93 · Decompose ClientCuttingEditorView along five seams — `tech-debt` · high · L
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** 1438 lines holding five separable concerns: edge-picker modal (state `:43-49`, computeds `:118-174`, mutators `:430-545`, template `:1258-1436` — ~450 self-contained lines); parts-table rows (template `:865-1046` incl. a 50-line inline SVG preview); results/algorithms section (`:1072-1245`); autosave machinery (`:547-570,624-644`); pure edge ranking/label/color helpers (`:253-342`). Every cutting-flow change — and CB-03/15/16/50/82/86/89 — lands in one giant file.
**Fix:** Incremental extraction, one seam per PR: CuttingEdgePickerModal.vue, CuttingPartRow.vue, CuttingResultsSection.vue, useDraftAutosave() composable (natural home for CB-15/50), cuttingEdgeDisplay.ts pure module (unit-testable without mounting).

### CB-94 · Split LoginView into per-role views — `tech-debt` · med · M
**Files:** `views/LoginView.vue`, `apps/*/routes.ts`
**Why:** 432 lines branching on `config.role`: client OTP flow (`:16-25,93-155,163-310`), admin form (`:312-362`), workshop form (`:364-431`), plus two parallel error maps (`:32-67`) that must be kept in sync (already drifted into mixed English/Uzbek — structural cause of CB-01/42 symptoms). Each SPA bundle ships the other two roles' dead login markup.
**Fix:** ClientLoginView/AdminLoginView/WorkshopLoginView registered per app's routes.ts (role statically known); share a useResendCooldown() composable; per-role error maps live next to their view. One role per commit.

### CB-95 · Split ProfileView; dedupe ClientBranchOption type — `tech-debt` · med · M
**Files:** `views/ProfileView.vue`, `stores/cutting.ts`
**Why:** 581 lines: client branch (`:195-366`) vs workshop tabs (`:368-580`) gated by principal_type, with disjoint state sets coexisting (`:39-50`). Re-declares ClientProfile/ClientBranchOption locally (`:16-30`) — ClientBranchOption duplicates `cutting.ts:105-112` field-for-field — and fetches `/client/profile` + `/client/branch-options` with raw `api.get` outside any store (`:92-95`). CB-25's loading/error work must navigate workshop tab logic.
**Fix:** ClientProfileView + WorkshopProfileView per app; move the profile fetch/patch into a store slice; import ClientBranchOption from one shared location.

### CB-96 · useListboxControl/useStableId composables for dropdowns — `tech-debt` · med · M
**Files:** `components/FormSelect.vue`, `SearchCombobox.vue`, `MultiSelectFilter.vue`, `ProjectDropdown.vue`, `ConfirmDialog.vue`
**Why:** Four components re-implement open/close + activeIndex + arrow/Enter/Escape/Tab keydown + document pointerdown outside-close + `Math.random()` ids (~250 duplicated lines; cites in each file). Drift is already real: FormSelect/SearchCombobox skip disabled options via firstEnabledIndex while MultiSelectFilter (`:54-60`) and ProjectDropdown (`:70-78`) use plain modulo — keyboard nav lands on disabled options there. Every a11y fix must be applied four times.
**Fix:** Extract `useListboxControl({options, onChoose})` (open state, disabled-skipping move(), shared keydown, outside-close teardown) + `useStableId(prefix)`; migrate one component per PR.

### CB-97 · Single authInit()/token injection (8 copies) — `tech-debt` · med · S
**Files:** all stores under `stores/`
**Why:** The identical `authInit()` exists in 8 stores (`cutting.ts:171`, `orders.ts:186`, `notifications.ts:26`, `admin.ts:241`, `clientCatalog.ts:62`, `finance.ts:114`, `auth.ts:199`, `workshop.ts:186`) and ProfileView builds the init object by hand (`:92-95`). The CB-08 silent-refresh work would touch all of them; forgetting authInit on a new endpoint produces a silent 401.
**Fix:** One exported authInit() (or token injection inside the api client from the auth store); delete the 8 copies.

### CB-98 · One shared withQuery() (6 copies, divergent semantics) — `tech-debt` · med · S
**Files:** `stores/cutting.ts`, `orders.ts`, `workshop.ts`, `admin.ts`, `clientCatalog.ts`, `finance.ts`
**Why:** Six private copies with two behaviors: cutting/orders/workshop keep booleans via explicit null/undefined/'' checks; admin/clientCatalog/finance differ — `clientCatalog.ts:43` uses truthy `if (value)`, silently dropping `false` or `'0'` params. A future boolean filter on those endpoints would never reach the backend.
**Fix:** One `withQuery(path, params)` in `shared/api/client.ts` with a unit test for false/empty-string handling; delete the six copies.

### CB-100 · Unify captureApiError() (3 divergent variants) — `tech-debt` · med · S
**Files:** `stores/orders.ts`, `stores/cutting.ts`, `stores/clientCatalog.ts`
**Why:** `orders.ts:190-197` preserves the backend `body.code` for non-403 errors; `cutting.ts:175-179` collapses everything non-403 to the fallback; clientCatalog inlines a third pattern with no 403 handling (`:81-83,100-102`). Whether a backend error code reaches the UI depends on which store handled the request — and CB-01's translation layer has no single choke point.
**Fix:** One `captureApiError(error, fallback): {code, traceId}` next to apiTraceId, orders.ts semantics as canonical; replace the three variants. (CB-01 sits on top.)

### CB-101 · Typed notification payload + shared presenter — `tech-debt` · med · M
**Files:** `stores/notifications.ts`, `views/ClientNotificationsView.vue`, `components/NotificationsMenu.vue`
**Why:** `NotificationItem.payload` is `Record<string, unknown>` (`notifications.ts:14`), so title()/body()/destination() probing is duplicated across the bell and the page with different coverage (`ClientNotificationsView.vue:29-51` orders-only vs `NotificationsMenu.vue:25-48` order/branch/workshop) — the same notification can render differently in the two surfaces, and CB-02's Uzbek-title map would have to be written twice.
**Fix:** A NotificationPayload interface + `shared/app/notificationPresenter.ts` exporting notificationTitle/Body/Destination(item, role); both components import it; CB-02 lands in exactly one file.

### CB-103 · Fix stale AGENTS.md API-client path + phantom dirs — `tech-debt` · med · S
**Files:** `AGENTS.md`, `web/AGENTS.md`, `web/src/api/client.ts`
**Why:** Root `AGENTS.md:122` and `web/AGENTS.md:40,112` direct work through `web/src/api/client.ts` — now a one-line re-export with **zero importers** that also misses apiTraceId/blob/postForm; following the documented path yields a broken subset. `web/AGENTS.md`'s layout block lists `src/stores/`, `src/composables/`, `src/components/` — none exist. "Docs are the source of truth" makes this actively harmful for future sessions.
**Fix:** Delete the shim; point both AGENTS.md files at `web/src/shared/api/client.ts`; fix the layout tree to the real `shared/{api,app,components,stores,views}` structure.

---

## P3 — nice-to-have

### CB-44 · Use `.tl` timeline with done/bad states in order history — `design-parity` · low · S
**Files:** `views/ClientOrderDetailView.vue`, `web/src/assets/main.css`
**Why:** `main.css` ships a `.tl` timeline with state-colored dots (`.tl .step.done/.step.bad` `:2456-2462`), but `ClientOrderDetailView.vue:504-517` hand-rolls history with a uniform `bg-accent` dot — done/cancelled/current are indistinguishable.
**Fix:** Render events as `<ol class="tl"><li class="step" :class="{done:…, bad: to_status==='cancelled'}">`.

### CB-45 · Recolor branches info banner from warn-yellow to neutral — `design-parity` · low · S
**Files:** `views/ClientBranchesView.vue`
**Why:** Prototype's advisory is a neutral sunk/ink banner (`branches.html:44-46`), but the Vue port uses `client-banner warn` (`:65`), amber via `--color-warning-*` (`main.css:649-653`). A purely informational "reference-only" note reads as a warning.
**Fix:** Render as a neutral note (sunk bg, ink-soft) via a neutral banner variant.

### CB-46 · Full 5-phase model on home active-order progress — `design-parity` · low · S
**Files:** `views/ClientHomeView.vue`, `app/clientUi.ts`
**Why:** Home stepper renders `clientPhaseLabels.slice(0,4)` (`:279`) and stops the connector at `index<3` (`:298`) — 4 dots, dropping the 5th "Topshirildi" — while `clientPhaseLabels` has 5 (`clientUi.ts:13-19`) and order-detail renders all 5. Home disagrees with detail (4 vs 5).
**Fix:** Drop `slice(0,4)` for consistency (or document the 4-phase choice deliberately).

### CB-47 · Reliable home back-target on notifications/profile — `ux-flow` · low · S
**Files:** `views/ClientNotificationsView.vue`, `ProfileView.vue`
**Why:** Back control calls `$router.back()` (`ClientNotificationsView.vue:71`, `ProfileView.vue:196`). Via deep link / direct URL / refresh, history may be empty — `back()` does nothing or bounces out of the SPA.
**Fix:** Use a `RouterLink` to `config.homePath` (or `/c`), or fall back to home when history has no in-app entry.

### CB-48 · Stack branches/notifications rows on small phones — `responsive` · low · S · **verified: partial**
**Files:** `views/ClientBranchesView.vue`, `ClientNotificationsView.vue`
**Why (verified 2026-06-10):** Real rows already use `minmax(0,1fr)` middles (`ClientBranchesView.vue:115` `grid-cols-[50px_minmax(0,1fr)_auto]`, `ClientNotificationsView.vue:131` `grid-cols-[38px_minmax(0,1fr)_auto]`) — no min-content overflow, that part of the original claim was wrong. What holds: (a) **no small-screen stacking breakpoint** on these card grids while `.client-row-item` stacks at ≤520px (`main.css:1193-1196`) — the middle column gets squeezed beside the status pill on narrow phones; (b) the **skeletons differ from the real rows** (`:83` `[50px_1fr_auto]`, `:92` `[38px_1fr_64px]`) — minor loading/loaded layout mismatch.
**Fix:** Add a stacking breakpoint consistent with `.client-row-item`; align skeleton grid templates with the real rows.

### CB-49 · ~~Fix two-column grid overflow in ~1024px band~~ — **Won't · refuted 2026-06-10**
**Files:** `views/ClientOrderDetailView.vue`
**Verification:** The claimed mechanism is wrong. `lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.85fr)]` (`:274`) gives the **main column a 0 minimum**, so total track minimum = 280px aside + 24px gap ≈ 304px — far below the ≥992px content width at the lg breakpoint (container `min(100%-32px,1280px)`). The grid cannot overflow from track math; at 1024px the 0.85fr share (~366px) doesn't even hit the 280px floor. No fix needed.

### CB-50 · Disable Optimise after a run until a part changes — `ux-flow` · low · S
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** Optimise is disabled only while `cutting.optimizing || parts.length===0` (`:1064`), so after a successful run it's immediately re-clickable on identical input — encouraging redundant slow re-runs. `cutting.md` §"result panel" wants it disabled until a row changes.
**Fix:** Track a "dirty since last optimise" flag (true on any change, false after success) and add to `:disabled`.

### CB-51 · Two-pane workshop+branch picker in editor pre-filter — `ux-flow` · low · M
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** The branch pre-filter is a flat `FormSelect` of every branch as "workshop · branch" (`:773-785`, `branchOptions` `:57-66`) with no grouping; `temporarily_closed` distinguished only by a meta string. `cutting.md` §"Branch pre-filter" specifies a two-pane workshop-left/branches-right picker.
**Fix:** Replace the flat select with a two-pane picker grouping branches under their workshop, marking `temporarily_closed`, keeping `setPreferredBranch` wiring.

### CB-52 · Cache/staleness reuse for home/notifications/branch-options — `performance` · low · S
**Files:** `views/ClientHomeView.vue`, `components/NotificationsMenu.vue`, `ClientOrderNewView.vue`, `stores/cutting.ts`
**Why:** Several mounts refetch unconditionally despite Pinia holding the data: `ClientHomeView.vue:109-111` re-runs `reloadHome` (two unbounded lists) every visit; `NotificationsMenu.vue:50-53` hits the network on every bell open (and after mark-all-read); `ClientCuttingEditorView.vue:649` and `ClientOrderNewView.vue:193` both `loadBranchOptions` on mount, fetching the same list twice on editor→checkout (`cutting.ts:277-282` overwrites).
**Fix:** Add a staleness guard (timestamp/"loaded" flag, ~30s for the bell) so loads reuse store state; pairs with pagination.

### CB-53 · Self-describing autosave live region (role=status) — `a11y` · low · S
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** The autosave chip has `aria-live="polite"` (`:705-716`) and toggles bare words "Saqlangan"/"Saqlanmoqda"/"Saqlash xatosi" (`saveLabel` `:348-353`) with no `role=status` and no context — SR users hear an unanchored "error"; the save-error state is conveyed only by chip + color.
**Fix:** Add `role="status"` and self-describing text, e.g. "Chizma saqlandi" / "Saqlanmoqda" / "Saqlash xatosi — qayta urinib ko'ring".

### CB-54 · AuthFileImage: required alt + localized failure label — `a11y` · low · S
**Files:** `components/AuthFileImage.vue`
**Why:** `alt` defaults to '' (`:11-13`); the load-failure branch (`:47-53`) renders a literal English "image" span with no aria-label/relationship. A meaningful image without alt is hidden from AT; on failure SR users get a bare untranslated "image".
**Fix:** Make `alt` required (or warn when omitted for non-decorative), localize the fallback, give the failure span an aria-label including the intended alt.

### CB-55 · Idempotent markRead decrement (only when was unread) — `correctness-bug` · low · S
**Files:** `stores/notifications.ts`
**Why:** `notifications.ts:56-65` `markRead` always runs `unread = Math.max(0, unread-1)` regardless of prior read state. Today's callers guard with `read_at===null`, so it's correct now, but not idempotent — a double-tap race or future unguarded caller drives the badge below the true value.
**Fix:** Capture `wasUnread` before the call and decrement only if true, or recompute `unread` from `items` after refresh.

### CB-56 · One defined quantity for order-detail "Krom" figure — `correctness-bug` · low · S · **verified: partial (downgraded to cleanup)**
**Files:** `views/ClientOrderDetailView.vue`
**Why (verified 2026-06-10):** `:53-60` does `return consumed || current.total_edge_length_mm`. The two quantities ARE different semantics — backend `_edge_metrics` (`optimizer.py:491-524`) computes `consumed = (edge_length + EDGE_OVERHANG_MM) × qty` vs geometric `total_edge_length_mm = edge_length × qty` — **but the fallback branch is unreachable in practice**: both sums are built from the same banded sides in the same pass, so `consumed === 0 ⟺ total === 0`. Not a user-facing bug; it's misleading dead-fallback code.
**Fix:** Drop the `|| current.total_edge_length_mm` fallback (the consumed sum is the right client-facing figure, matching the editor's metres); keep as a tiny cleanup.

### CB-57 · Error feedback for chooseResult / preferred-branch save — `states-errors` · low · M
**Files:** `stores/cutting.ts`, `views/ClientCuttingEditorView.vue`
**Why:** `chooseResult` (`cutting.ts:266-275`) and the preferred-branch `updateDraft` (`:220-237`) capture no error, and `choose()` (`ClientCuttingEditorView.vue:590-594`) / `setPreferredBranch()` (`:572-578`) await them with no catch (only the debounced parts save has `saveState='error'`). Picking a result or switching branch can throw an unhandled rejection while local state updates — draft chosen-result silently disagrees with the server.
**Fix:** Give `chooseResult`/branch `updateDraft` a `captureError` path; have `choose()`/`setPreferredBranch()` catch and surface an inline error + trace (or reuse `saveState='error'`).

### CB-58 · Remove dead dupes (English status maps, i18nSeed, DashboardView) — `completeness-stub` · low · S
**Files:** `stores/orders.ts`, `web/src/shared/i18n.ts`, `views/DashboardView.vue`, `web/src/shared/__tests__/formatters.spec.ts`
**Why:** `orders.ts:145-163` exports English `clientStatusLabel`/`workshopStatusLabel` while every client view imports the Uzbek `clientStatusLabel` from `clientUi.ts:3-11` — a wrong-import trap; `i18n.ts` exports an English-only `i18nSeed` consumed only by `formatters.spec.ts`, masquerading as an i18n seam; `DashboardView.vue` is a generic readiness scaffold no SPA routes to.
**Fix:** Delete the English status maps from `orders.ts` (after confirming no imports), delete `i18nSeed` + its test assertion (or grow it into a real i18n seam separately), remove orphaned `DashboardView.vue` and any `config.states` scaffolding only it consumes.

### CB-66 · `scroll-margin` for #cutting-results under sticky header — `ux-flow` · low · S
**Files:** `views/ClientCuttingEditorView.vue`, `web/src/assets/main.css`
**Why:** Post-optimize `scrollIntoView({block:'start'})` (`:586-588`) lands `#cutting-results` under the sticky `.client-header` (`main.css:202-209`, ~100px tall at ≤860px where it wraps to two rows); no `scroll-margin`/`scroll-padding` exists anywhere. The results heading and part of the KPI strip end up hidden right after tapping Optimallashtirish.
**Fix:** `scroll-mt-24` (or breakpoint-matched `scroll-margin-top`) on `#cutting-results`.

### CB-67 · Guard hover styles with `@media (hover:hover)` — `tech-debt` · low · S
**Files:** `web/src/assets/main.css`
**Why:** Zero `@media (hover: hover)` guards in main.css. On touch, sticky hover states masquerade as selection: `.client-edges-btn:hover` (`:680-683`) leaves the Krom button accent-highlighted after the modal closes; `.ep-pattern:hover`/`.ep-edge-opt:hover` (`:853-857,1024-1027`) make the last-tapped pattern/option look active when it isn't; `.mp-button:hover` (`:122-124`) leaves tapped buttons floating 1px up.
**Fix:** Wrap selection-like hover rules in `@media (hover: hover)`, keeping `.on`/`.set` classes as the only selected-state signal on touch.

### CB-69 · Per-side krom details visible on touch (not title-only) — `ux-flow` · low · S
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** The full per-side breakdown lives only in `:title="edgeCellTitle(part)"` (`:950`, builder `:302-310`) — `title` tooltips never appear on touch. The visible summary is just "N tomon" + a coarse source word (`:1009-1012`); the in-SVG thickness texts render at 6.5px (`main.css:709-714`). A phone user must open the modal for every part to review which tape is on which side.
**Fix:** Extend the summary second line with the dominant krom short-label (e.g. "AGT 0.8 · 2 tomon · ustaxonadan") or a small expandable section; keep `title` as a desktop bonus. (Complements CB-91, which names the tape per spec format.)

### CB-74 · Add `account_blocked` to client login error map — `i18n-copy` · low · S
**Files:** `views/LoginView.vue`
**Why:** Backend returns `account_blocked` (403) for a blocked client after a correct code (`otp.py:232-238`); clientErrorText (`:55-64`) has no entry, so it falls to generic "Kirish amalga oshmadi." (`:65`) — the client retypes codes and burns attempts instead of contacting the workshop. (Complements CB-01.)
**Fix:** Add `account_blocked: "Hisobingiz bloklangan. Ustaxona bilan bog'laning."` to the map.

### CB-77 · Selectable temporarily_closed branches; stale-pref state — `spec-conformance` · low · S
**Files:** `views/ProfileView.vue`, `components/FormSelect.vue`
**Why:** `branchChoiceOptions` disables temporarily_closed options (`:61`) though the spec includes them in the selectable set (`access-management.md:144-145` — closure is temporary, the preference durable). And when `preferred_branch_id` no longer appears in branch-options (branch went inactive), FormSelect falls back to the placeholder — the control reads "Tanlanmagan" while a preference is actually still set (`FormSelect.vue:32,37`; `ProfileView.vue:277`).
**Fix:** Render temporarily_closed selectable with the closed_reason meta; when the saved id has no option, show an explicit "Avvalgi filial endi mavjud emas" state prompting re-choose/clear.

### CB-78 · Split profile PATCH payloads (branch save vs name form) — `correctness-bug` · low · S
**Files:** `views/ProfileView.vue`
**Why:** `saveClientProfile` always sends both `name` and `preferred_branch_id` (`:105-110`) and is invoked from the name form (`:225`) AND the branch row's type=button Saqlash (`:287-294`) which bypasses the name form's `required`. Saving a branch while the name editor holds a cleared/half-typed value silently PATCHes the mangled name too, then force-closes the editor (`:121`).
**Fix:** Send only `{preferred_branch_id}` from the branch save and only `{name}` from the name form (or skip the name field when its form isn't being submitted).

### CB-80 · Surface OTP 5-min expiry on the code step — `ux-flow` · low · S
**Files:** `views/LoginView.vue`, `stores/auth.ts`
**Why:** `requestClientOtp` returns `expires_at` (`auth.ts:129-140`) but `sendOtp` consumes only `resend_after_seconds` (`:103-106`) — the code step (`:219-222`) gives no validity window; the user discovers the 5-min TTL only via `code_expired` on submit.
**Fix:** Keep `expires_at`, render "Kod 5 daqiqa amal qiladi" or a live mm:ss countdown; on lapse swap the helper to "Kod muddati tugadi — qayta yuboring" and emphasize resend.

### CB-81 · Uzbek session-row labels ("active"/"Browser") — `i18n-copy` · low · S
**Files:** `views/ProfileView.vue`
**Why:** The client sessions list renders `{{ session.is_current ? '—' : 'active' }}` (`:340`) — a bare English word in a fully-Uzbek, trust-sensitive security card — and deviceLabel falls back to English 'Browser' paired with Uzbek 'Qurilma' (`:156-165`), producing "Browser · Qurilma". (Different surface from CB-42.)
**Fix:** 'faol' (or drop the uninformative column) and an Uzbek browser fallback ("Brauzer · Qurilma").

### CB-90 · Algo compare: cut-length column, algo name, closed default — `spec-conformance` · low · S
**Files:** `views/ClientCuttingEditorView.vue`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:295-297`: headline metrics include the chosen **algorithm name** plus a "Compare algorithms" link → expander with per-algorithm name, waste %, panels, **cut length**. The metric cards (`:1106-1129`) never show algorithm_name; the comparison table (`:1144-1177`) has no cut-length column; `algorithmsOpen = ref(true)` (`:37`) renders it expanded by default instead of behind a link. The panels-vs-cut-length trade the comparison exists for is missing its axis.
**Fix:** Add the chosen algorithm_name to headline metrics with a toggle link (default closed); add a `metres(total_cut_length_mm)` column.

### CB-91 · Name the tape in the Edges cell summary — `spec-conformance` · low · S
**Files:** `views/ClientCuttingEditorView.vue`, `docs/ref/features/cutting.md`
**Why:** Spec `cutting.md:210` wants one-line labels like `H1334 · 0.4 mm` / `Mixed · 2 edges` / `None`. `edgeSummary()/edgeSourceSummary()` (`:237-251`) emit only side count + source ("4 tomon / ustaxonadan") — the tape's identity appears nowhere visible (only the hover title and 6.5px SVG numbers). Reviewing "did I put the 2 mm on the fronts?" requires opening every row's picker.
**Fix:** When all banded sides share one material, `edgeShortLabel(material) · N tomon`; when mixed, `Aralash · N tomon`; keep "Krom yo'q" — reuse the existing `edgeShortLabel` helper (`:287-295`).

### CB-92 · Delete unreachable "Fayldan" upload empty-state branch — `tech-debt` · low · S
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** The disabled-with-"tez kunda"-pill upload button **is correct v1 behavior** per spec `cutting.md:198-199`. But the button is `disabled`, so its `@click="entryMode = 'upload'"` can never fire and `entryMode` (`:36`) is permanently 'manual' — the whole `v-if="entryMode === 'upload'"` empty-state block (`:845-851`, "Import hali yoqilmagan") is unreachable dead template code with copy that already drifted from the pill's.
**Fix:** Delete the dead branch and the `@click` on the disabled button; keep the disabled-with-pill control exactly as spec'd.

### CB-99 · Extract shared downloadBlob() (2 copies) — `tech-debt` · low · S
**Files:** `stores/cutting.ts`, `stores/orders.ts`
**Why:** `cutting.ts:350-358` and `orders.ts:370-378` contain the identical downloadPdf (api.blob → createObjectURL → anchor.click → revoke), consumed by four wrappers; neither copy has error handling, so the CB-17 failure-feedback fix would be written twice.
**Fix:** One `downloadBlob(path, filename, init)` in `shared/api/client.ts` (or the files store) — the single place for CB-17's error surfacing.

### CB-102 · Centralize magic numbers (debounces, limits, 50 mm) — `tech-debt` · low · S
**Files:** `views/ClientCuttingEditorView.vue`, `ClientOrdersView.vue`, `ClientBranchesView.vue`, `stores/notifications.ts`, `views/ClientNotificationsView.vue`
**Why:** Autosave 700ms (`:551`); search 250ms duplicated (`ClientOrdersView.vue:33-36`, `ClientBranchesView.vue:50`); notification limit literal 50 three times (`ClientNotificationsView.vue:61,65,110`) vs store default 10; badge cap '9+' inline. The 50mm part minimum is encoded **three independent times in one file** (`:83`, `:223-225`, template `min="50"` `:914,926`) — input and validator can drift apart.
**Fix:** `shared/app/constants.ts` (AUTOSAVE_DEBOUNCE_MS, SEARCH_DEBOUNCE_MS, NOTIFICATIONS_PAGE_LIMIT, MIN_PART_MM); derive validators and input attrs from MIN_PART_MM.

### CB-104 · Remove dead quote surface in orders store — `tech-debt` · low · S
**Files:** `stores/orders.ts`, `views/ClientOrderNewView.vue`
**Why:** `orders.loadQuote` (`:199-213`) and `quoteLoading` (`:181`) are exported with **zero call sites** — checkout builds its own per-branch quoting via quoteForDraft with local state; `currentQuote` (`:177`) is written once (`ClientOrderNewView.vue:119`) and never read. Two parallel quote mechanisms confuse the CB-12 batch-quote work about which path is live. (Beyond CB-58's dead code.)
**Fix:** Remove loadQuote/quoteLoading/currentQuote (and the write at `:119`) — or fold quoting into the store when CB-12's batch endpoint lands; keep exactly one path.

---

# Round 3 additions (CB-105 – CB-131)

Four lenses: spec-orders-notify · proto-screens · testing · security. Many testing
items are **regression guards meant to ship with a specific fix** — implement the
named CB-fix and its test together.

## P1 (round 3)

### CB-105 · Regression test: normalizeUzPhone — `testing` · high · S · ships with CB-27
**Files:** `app/clientUi.ts`, `app/__tests__/clientUi.spec.ts`
**Why:** `normalizeUzPhone` (`:47-51`) has **identical** if/else branches (both `return '+'+digits`) — verified — so `901234567` → `+901234567` and `8 998 90…` keeps the leading 8; `isUzPhone` (`:59-61`) then rejects valid national numbers and blocks checkout (`ClientOrderNewView.vue:179`). The only existing test (`clientUi.spec.ts:14-16`) feeds an already-`+998` string, so locally-natural inputs have zero coverage and the CB-27 fix could regress while green.
**Fix:** Table-driven `describe('normalizeUzPhone')`: `901234567`→`+998901234567`; `8 998…`/`998…`/`+998…` collapse to one `+998`; `isUzPhone` true only for the 12-digit form. Pure logic → Vitest, mock-free.

### CB-106 · Regression test: notifications markRead idempotency — `testing` · high · S · ships with CB-55
**Files:** `stores/notifications.ts`, `stores/__tests__/notifications.spec.ts` (new)
**Why:** `markRead` always runs `unread = Math.max(0, unread-1)` regardless of the item's prior `read_at` — a double-tap drives the badge below the true count. There is **no notifications store test** (only `auth.spec.ts`); markAllRead and the loadUnreadCount catch (unread=0) are also uncovered.
**Fix:** New `notifications.spec.ts` (mock `@/api/client` like auth.spec): seed unread=2 with one read row; markRead(read)→still 2 (post-CB-55); markRead(unread)→1; markAllRead→0 stamping only previously-unread; loadUnreadCount catch→unread=0+error.

### CB-107 · Test per-branch quote error attribution — `testing` · high · M · ships with CB-20
**Files:** `views/ClientOrderNewView.vue`, `stores/orders.ts`
**Why:** `loadQuotes` (`:134-156`) fans out in Promise.all and each catch reads the **shared singleton** `orders.error` via `quoteErrorLabel(orders.error)`, while `quoteForDraft` never sets `orders.error` — so the label a branch shows is whatever the last failing call left behind (the CB-20 race). No test exercises this; a client can see the wrong reason pinned to a branch that actually succeeded.
**Fix:** With CB-20: make `quoteForDraft` throw a typed error carrying its own code; unit-test the reducer with a mock that resolves A, rejects B/C with distinct codes, asserting each branch maps to its own code and A survives. Component+mocked-store → Vitest (keep out of e2e).

### CB-108 · Test autosave debounce + hydration guard — `testing` · high · M · ships with CB-15
**Files:** `views/ClientCuttingEditorView.vue`, `stores/cutting.ts`
**Why:** `scheduleSave` early-returns while `hydrating`, sets a 700ms timer; the `currentDraft` watcher sets `hydrating=true` and rewrites `parts.value`; `optimize()` also calls `saveParts` synchronously. None of this debounce/guard/flush interplay is tested (no `cutting.spec.ts`; e2e is happy-path), so a mistimed flush can persist a stale/half-hydrated snapshot and lose edits — exactly CB-15.
**Fix:** Extract into a `useDraftAutosave` composable (the CB-93 seam) or test with `vi.useFakeTimers`: (a) edits within 700ms → one updateDraft, (b) mutations during hydration → no save, (c) optimize() flushes before optimizeDraft. Timing logic → Vitest.

### CB-109 · Test login redirect guard rejects external targets — `testing` · high · S · ships with CB-75
**Files:** `views/LoginView.vue`
**Why:** `redirectTo` (`:27-30`) accepts any `?redirect` that `startsWith('/')`, letting `//evil.com` through (the CB-75 open redirect). No test covers the guard, so the hardening could ship without asserting bad inputs are rejected.
**Fix:** Extract the sanitizing predicate to a pure function; unit-test `/c/orders` kept; `//evil.com`, `/\evil.com`, `https://evil.com`, `javascript:…`, absent → fall back to `homePath`. Pure guard → Vitest.

### CB-110 · Cover client OTP auth path in auth store — `testing` · high · M
**Files:** `stores/auth.ts`, `stores/__tests__/auth.spec.ts`
**Why:** `auth.spec.ts` tests only platformLogin/restore/logout; `requestClientOtp` (`:129-140`) and `verifyClientOtp` (`:142-161`) — incl. the `'is_new' in response` branch (returns without a token, status='anonymous') and the `lastError=errorCode(error)` mapping that drives LoginView's clientErrorText — have **zero** unit coverage. The only client sign-in path is untested.
**Fix:** Add to `auth.spec.ts` (api.post already mocked): requestClientOtp returns resend_after_seconds + clears lastError; verify `{is_new:true}` keeps token null + anonymous; a TokenResponse applies the token; ApiError maps to the expected lastError code. Store logic → Vitest.

### CB-111 · PDF download: async revoke + attach anchor — `states-errors` · med · S
**Files:** `stores/orders.ts`, `stores/cutting.ts`, `views/ClientOrderDetailView.vue`, `ClientCuttingEditorView.vue`
**Why:** `orders.ts:370-378` (and identical `cutting.ts:350-358`) do `link.click(); URL.revokeObjectURL(url)` on consecutive lines with the anchor **never appended to the DOM**. The blob read is async, so same-tick revoke can abort the download on Firefox/Safari, and a detached `<a download>` click is a no-op in Firefox. Callers bind the promise with no catch (`ClientOrderDetailView.vue:223/393`, `ClientCuttingEditorView.vue:1215`) — the client taps "Chizmani PDF olish" and intermittently gets nothing. The cutting plan is the deliverable they take to the workshop.
**Fix:** One shared helper (also the CB-99 `downloadBlob`): `appendChild(link); link.click(); link.remove(); setTimeout(() => revokeObjectURL(url), 0)`. CB-17's try/catch then wraps the same helper. **Related:** CB-17, CB-99.

## P2 (round 3)

### CB-112 · Branch working hours in picker / Review / Pickup — `spec-conformance` · med · M
**Files:** `views/ClientOrderNewView.vue`, `ClientOrderDetailView.vue`, `stores/orders.ts`, `stores/cutting.ts`
**Why:** `orders.md:241` requires each branch-pick card show "name, address, **today's hours**, and a price breakdown" and `:253` the Review show "pickup branch (address + hours)". Verified: neither `ClientBranchOption` (`cutting.ts:105-112`) nor `OrderQuote` (`orders.ts:17-27`) nor `OrderSummary` carries an hours field — the data is absent end-to-end; cards render name+address+phone, never hours. The prototype shows an "Ish vaqti" row (`order-detail.html:183,247`). A pickup-only client can't see if the branch is open today. (Merges the order-new + checkout + order-detail hours gaps.)
**Fix:** Add a `today_hours` field to branch-options / quote / order payloads; render on each branch card, the Review pickup block, and the order-detail "Olib ketish" card. **Related:** CB-04, CB-30, CB-76, CB-77.

### CB-113 · Order-detail Timeline: 5 client phases, not raw events — `spec-conformance` · med · M
**Files:** `views/ClientOrderDetailView.vue`
**Why:** `orders.md:268-270` mandates five client phases (Placed→Confirmed→In production→Ready→Done), collapsing cutting/edge_banding into "In production". Verified: the Holatlar tarixi tab (`:504-517`) iterates **raw** `order.events` and labels both ends via `clientStatusLabel` (which maps both cutting and edge_banding to "Ishlab chiqarishda"), so a cutting→edge_banding transition renders "Ishlab chiqarishda → Ishlab chiqarishda" and an operator revert shows a backward arrow — exposing internal workshop states the model hides.
**Fix:** Render the five client phases with done/now styling (prototype `order-detail.html:275-299`), cancelled as a single terminal step with reason, instead of mapping each raw event. **Related:** CB-44, CB-46.

### CB-114 · Per-session revoke ("Yopish") in profile sessions — `completeness-stub` · med · M
**Files:** `views/ProfileView.vue`, `stores/auth.ts`
**Why:** `access-management.md:64` ("list their sessions and revoke one or all") and `:78` ("revoke per row") put per-session revoke in v1; prototype `profile.html:64,71` shows a per-row "Yopish". `ProfileView.vue:327-342` renders rows with only a label and no close button; `auth.ts` exposes only logoutCurrent/logoutEverywhere — no single-session DELETE. A client spotting an unfamiliar device can only log out everywhere (incl. themselves). *(Note: the backend already has `DELETE /auth/sessions/{id}` per the API map — wiring is client+store only.)*
**Fix:** Add a `revokeSession(id)` action hitting `DELETE /auth/sessions/{id}` and a per-row "Yopish" button (optimistic removal + rollback) in both client and workshop session lists. **Related:** CB-81, CB-95.

### CB-115 · Aggregate "no branch carries this set" empty state — `states-errors` · med · M
**Files:** `views/ClientOrderNewView.vue`
**Why:** `:249-251` handles only `activeBranches.length===0`; when branches exist but none can fulfil the material set, every branch falls into the per-card error path — the client sees a wall of identical greyed cards with no aggregate explanation. The prototype (`order-new.html:224-236`) names the unstocked materials and links back to the editor to convert them to "own" or pick different. (CB-19 covers the recovery-panel concept; this is the named-materials aggregate-empty distinct from per-card and no-active-branches.)
**Fix:** When all active branches fail to quote, render an aggregate empty state listing the unstocked materials + a "Chizmaga qaytish" link. **Related:** CB-19, CB-20, CB-21, CB-86.

### CB-116 · Order-new: split already-used vs no-chosen-result bail — `states-errors` · low · M
**Files:** `views/ClientOrderNewView.vue`
**Why:** Prototype `order-new.html:188-204` runs explicit entry pre-checks: missing cutting → "Chizma topilmadi"; status≠draft → toast + redirect to read-only cutting; no chosen result → toast + redirect to optimise. Vue handles only `cutting.error` and a generic `!draft || !chosenResult` empty state — no distinct already-used handling, so a deep-link to a used draft hits a generic dead-end. (CB-18 covers pre-checking; this adds the already-used-vs-no-result split.)
**Fix:** Mirror the prototype: distinguish "draft already used" (redirect to read-only cutting/order + toast) from "no chosen result" (back to editor), each with its own copy. **Related:** CB-18, CB-03.

### CB-117 · Itemized branch-card / checkout price lines — `design-parity` · med · L
**Files:** `views/ClientOrderNewView.vue`, `stores/orders.ts`
**Why:** `OrderQuote` (`orders.ts:17-27`) exposes only three flat subtotals + total. Prototype `order-new.html:264-267` branch card shows "Kesish xizmati (N panel × rate)", per-material lines, conditional "Krom yopishtirish", "Jami"; the review (`:357-374`) expands per-material + separate edge-material + edge-service lines. The Vue card/checkout show only the three lump sums — the client can't see how the cutting fee scales with panels or which materials drive cost, losing the prototype's comparison-friendly pricing.
**Fix:** Extend the quote payload with panel count, per-panel rate, per-material lines, and edge material/service split; render itemized lines in the card + expanded review. Pairs with CB-12's batch-quote endpoint. **Related:** CB-12, CB-20, CB-104.

### CB-118 · Order-detail Krom material-vs-service split + metres — `design-parity` · med · M
**Files:** `views/ClientOrderDetailView.vue`, `stores/orders.ts`
**Why:** Prototype `order-detail.html:155-157` renders three rows when edge banding exists — "Krom" (metres subtext), "Krom materiali", "Krom yopishtirish xizmati". Vue (`:298-306`) renders a **single** "Krom" row (`subtotal_edge_banding_tiyin`) with no material-vs-service split and no metres — the client can't see how the charge breaks down or how many metres were consumed.
**Fix:** When `subtotal_edge_banding_tiyin > 0`, render the three-row split (metres from `edge_consumed_*` sums; add split fields to the order-detail response if absent). **Related:** CB-29.

### CB-119 · Orders 'active' filter: expand or filter client-side — `correctness-bug` · low · S
**Files:** `views/ClientOrdersView.vue`, `stores/orders.ts`
**Why:** `orders.md:262` defines Active = union of new/confirmed/cutting/edge_banding/ready (`clientUi.ts:21-27`). Verified: ClientOrdersView passes `status.value` ('active'/…) verbatim to `loadClientOrders` (`:34`) which forwards it as a raw `?status=` query (`orders.ts:234-248`) with no expansion, and `visibleOrders` (`:28`) applies no client-side filter. If the backend doesn't special-case the synthetic 'active', the Active tab silently returns nothing/everything. *(Confirm backend behavior first — may be a no-op if the API already handles 'active'.)*
**Fix:** Expand 'active' into the explicit status set the API understands, or apply the `activeClientStatuses` union client-side; add a contract test pinning Active to the five statuses. **Related:** CB-38.

### CB-120 · Pin formatPercent boundary — `testing` · med · S · ships with CB-28
**Files:** `app/clientUi.ts`, `app/__tests__/clientUi.spec.ts`
**Why:** `formatPercent` (`:72-78`) branches on `numeric <= 1 ? numeric*100 : numeric`. The existing test checks only `0.1234`/`18.5`/null. The ambiguous `1` (100% vs 1%), `0`, `''`, non-finite are unpinned, even though backend `waste_percentage` feeds `resultWaste` (`ClientCuttingEditorView.vue:113`) — if a low-waste plan ever sends `1`, the heuristic shows 100.00%.
**Fix:** Extend the describe with `1`→(lock the documented intent), `0`→'0.00%', `''`→'-', `'abc'`/Infinity→'-'; tie to CB-28. **Related:** CB-28.

### CB-121 · Test part validation bounds — `testing` · med · M · ships with CB-82/83
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** `partIsInvalid` (`:221-231`) and `hasPersistableParts` (`:81-85`) enforce only lower bounds (≥50, qty≥1) + finiteness; no upper cap (CB-82) or row/quantity cap (CB-83), inputs set only `min`. No test exercises these predicates, so CB-82/83's caps would have no test pinning their thresholds.
**Fix:** Extract the predicates into a pure helper; unit-test the boundary matrix (49/50, 0/1, NaN, and post-CB-82/83 the max-dimension + 100-row/total-quantity caps). **Related:** CB-82, CB-83, CB-09.

### CB-122 · E2E: client order cancel + 409 recovery — `testing` · med · L
**Files:** `e2e/tests/`, `views/ClientOrderDetailView.vue`, `stores/orders.ts`
**Why:** Verified: the e2e suite (access/catalog/cutting/order-production/smoke) covers login, optimize+PDF, placement+production, but **no spec cancels an order** — neither the dialog, the toast, nor the 409 path (CB-11). Client-initiated cancellation (core v1) and its conflict recovery can break end-to-end uncaught.
**Fix:** E2E: place (reuse order-production seeding), cancel with reason, see cancelled+toast; second case mutates server-side first → UI hits 409 + recovery message. Playwright (seed via API). **Related:** CB-11, CB-24, CB-14.

### CB-123 · E2E: client notifications — `testing` · med · L
**Files:** `e2e/tests/`, `views/ClientNotificationsView.vue`, `stores/notifications.ts`
**Why:** Verified: the notifications store and ClientNotificationsView are never touched by any e2e — order-production ends at the completed order, never the notification it generates. Notifications are the client's only async order-ready channel, so a broken badge/list/mark-read ships unnoticed.
**Fix:** E2E: drive an order to emit a client notification, then assert the bell badge, open list, mark one read (decrements), mark all read (clears). Keep the idempotency arithmetic in CB-106's unit spec. **Related:** CB-10, CB-26, CB-02, CB-41.

### CB-124 · Test branch-carry recovery detection — `testing` · med · M
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** `rowNotCarried` (`:208-219`), `notCarriedRows` (`:86-88`), `showRecovery` (`:117`), `bringOwn` (`:540-545`) are the CB-19/CB-86 recovery logic with **no unit test** — e2e only optimizes where every material is carried. A regression lets a client checkout against a branch that doesn't stock their material, discovered only at quote stage.
**Fix:** Extract `rowNotCarried` into a pure helper `(part, branchId, panelOptions, edgeOptions)`; unit-test: shop panel not carried→flagged; own panel→not; carried panel + uncarried shop edge→flagged on that side; no preferred branch→never; bringOwn clears it. **Related:** CB-19, CB-86, CB-57.

### CB-125 · Null-destination notification: "not available", not silent — `states-errors` · low · S
**Files:** `views/ClientNotificationsView.vue`, `components/NotificationsMenu.vue`
**Why:** `notifications.md:42` says a click "navigates and marks read"; `:62-63` says a notification linking to an entity the principal can no longer see should "resolve to a not-available state rather than leaking". In `openItem` (`ClientNotificationsView.vue:53-57`, `NotificationsMenu.vue:55-60`), when `destination()` is null the row is marked read but nothing navigates and no feedback shows — the tap appears to do nothing.
**Fix:** When `destination()` is null, keep the row unread or show a toast/inline "no longer available"; only mark read on real navigation or explicit dismissal. **Related:** CB-02, CB-26, CB-101, CB-14.

### CB-126 · Bell rows: event-family icon, drop raw event_code subtext — `spec-conformance` · low · S
**Files:** `components/NotificationsMenu.vue`
**Why:** `notifications.md:40-41` wants bell rows with "an icon per event family, a one-line summary, a relative timestamp". Dropdown rows (`:171-189`) render a title + the **raw event_code** + date in monospace subtext (`:182-184`) + unread dot — no icon. The full page already renders a colored icon block (`:135-141`), so the dropdown is inconsistent with both spec and page. (Distinct from CB-02's Uzbek titles — this is the missing icon + raw-code subtext.)
**Fix:** Add the same per-event-family icon to dropdown rows; replace the raw event_code subtext with the relative timestamp + localized summary. Lands on CB-101 presenter + CB-35 icons. **Related:** CB-02, CB-35, CB-101.

## P3 (round 3)

### CB-127 · Cancelled banner shows cancellation reason — `completeness-stub` · low · S
**Files:** `views/ClientOrderDetailView.vue`
**Why:** Prototype `order-detail.html:133-138` cancel banner reads "Buyurtma bekor qilindi · {date}. Sabab: {reason}". Vue (`:230-237`) renders only the date with no reason, though the reason is on the cancel event (`OrderEvent.reason`, `orders.ts:55`). The client sees that it happened but not why unless they open Tarix.
**Fix:** Find the cancel event (`to_status==='cancelled'`) in `order.events` and append "· Sabab: {reason}" when present. **Related:** CB-11, CB-24.

### CB-128 · Orders-list card meta: pickup/due date not part count — `design-parity` · low · M
**Files:** `views/ClientOrdersView.vue`, `stores/orders.ts`
**Why:** Prototype `orders.html:137` card meta is "{city} {name} · {placedAt} · olib ketish {dueAt}". Vue (`:140-143`) shows "{workshop} · {relativeDate} · {N} qism" — item count, never a pickup date (`OrderSummary` has no due field). On the list the client can't see when each active order is expected; the part-count substitution is lower-value at this altitude.
**Fix:** When an estimated-ready/due date exists, append "· olib ketish {date}" to active-order meta; keep item count secondary. Shares the date-payload work with CB-112/CB-129. **Related:** CB-38.

### CB-129 ⚠ · Order-detail "Taxminiy sana" estimated-ready row — `completeness-stub` · low · M
**Files:** `views/ClientOrderDetailView.vue`, `stores/orders.ts`
**Why:** Prototype `order-detail.html:174-186` "Olib ketish" card shows a conditional "Taxminiy sana" (estimated date) row; Vue (`:364-383`) renders only branch name/address/phone + contact — no estimated-date row, and `OrderSummary/OrderDetail` expose no due field. **⚠ depends on whether the backend has an estimated-ready date at all** — confirm before building (may be out of scope / not modeled in v1).
**Fix:** If the backend exposes an estimated-ready date, render the conditional "Taxminiy sana" row. **Related:** CB-30, CB-112.

### CB-130 · Test edge ranking/recommendation helpers — `testing` · low · M
**Files:** `views/ClientCuttingEditorView.vue`
**Why:** `edgeRankForPart` (`:257-263`) ranks 0 (decor match)/1 (color match)/2; `rankedEdgesForPart` (`:265-277`) sorts by rank→thickness→name; `recommendedEdgeForPart` (`:279-285`) prefers current→remembered→top-ranked. This drives the "Mos" badge and default edge; no unit test (e2e picks an explicit edge by name), so a regression surfaces the wrong default edge banding.
**Fix:** Extract the ranking into a pure helper (CB-93's `cuttingEdgeDisplay.ts`); unit-test decor>color>neither, tie-break thickness then name, and `recommendedEdgeForPart` honoring the remembered id. **Related:** CB-84, CB-85, CB-93.

### CB-131 · files.loadObjectUrl: ownable revoke contract — `tech-debt` · low · S
**Files:** `stores/files.ts`, `components/AuthFileImage.vue`
**Why:** `files.ts:43-48` `loadObjectUrl` returns a bare `createObjectURL(blob)` string with **no paired revoke and no lifecycle ownership** — verified. Today only AuthFileImage consumes it (and revokes correctly), but the API carries no signal the caller MUST revoke; the moment a second consumer ships (attachment/thumbnail previews), each rendered file pins its decoded blob for the page lifetime, degrading long sessions on low-RAM phones.
**Fix:** Return a disposable `{ url, revoke }` or expose a `useObjectUrl(fileId)` composable owning create+revoke via `onScopeDispose`; keep AuthFileImage on the same primitive. Add a doc comment stating caller-owns-revocation until then. **Related:** CB-54, CB-99.

---

# User-found (during live review)

### CB-132 · Login phone/OTP inputs reject non-numeric typing — `ux-flow` · med · S · **Done**
**Files:** `views/LoginView.vue`
**Why:** The client-login phone input is `type="tel"`, which HTML intentionally does **not** restrict to digits — a user could type letters into the number field. CB-27 only validated `isUzPhone` on submit (`invalid_phone` error), so bad input was caught late and the field itself accepted letters.
**Fix (done):** `@input` sanitizers in LoginView — `sanitizePhone()` live-formats to `+998 XX XXX XX XX` and **caps at 9 national digits** (letters/extra chars stripped, the `+998` country code is sticky); `sanitizeOtp()` keeps only digits (maxlength 6). Verified gate green + page renders.

### CB-133 · Login errors → client-banner + icon + tone split — `design-parity` · med · S · **Done**
**Files:** `views/LoginView.vue`
**Why:** The client login rendered errors as a one-off `bold-red soft box`, inconsistent with the app's own `.client-banner` alert pattern used everywhere else, and treated connection errors ("Serverga ulanib bo'lmadi") identically to user-validation errors ("Kod noto'g'ri") — both alarming red, all-bold, no icon.
**Fix (done):** All 3 client-login error blocks now use `.client-banner` with an inline SVG alert-circle icon and normal-weight text; tone splits via `errorTone` computed — validation → `danger` (red), connection/`code_send_rate_limited` → `warn` (amber). Network copy de-teched ("API bilan aloqa yo'q" → "Serverga ulanib bo'lmadi — qayta urinib ko'ring."). Helper paragraph kept per user. Verified gate green. (Admin/workshop login still use the old box — extend later, ties to CB-22.)

### CB-134 · Login: native browser validation → Uzbek in-app alerts — `i18n-copy` · med · S · **Done**
**Files:** `views/LoginView.vue`
**Why:** The client-login inputs carried HTML `required`, so submitting an empty field (e.g. empty name on the "Tanishib olaylik" step) fired the **browser's native validation popup in English** before any app code ran — CB-79's whitespace guard only caught spaces, not the empty case (the browser blocked submit first).
**Fix (done):** Added `novalidate` to all three client-login forms (`required` kept for screen-reader semantics) so validation flows through the app's JS + the Uzbek `client-banner` alert (CB-133). Added a `clientStep === 'code'` guard requiring 6 digits before calling the API; empty phone/name/code now show "Telefon raqami noto'g'ri…" / "Ismingizni kiriting." / "Kod noto'g'ri." Verified gate green.

> **Also fixed (infra, not a SPA-backlog item):** the Docker dev API proxy. `vite.config.ts` hardcoded the `/api` proxy target to `localhost:8000`, which inside the web container points at itself, not the backend → every `/api` call failed as `network_error` ("API bilan aloqa yo'q"). Made the target env-driven (`API_PROXY_TARGET`, default `localhost:8000`) and set `API_PROXY_TARGET=http://backend:8000` in `deploy/compose.yaml`. `:5173/api/*` now reaches the backend.
