# Admin SPA — Improvement Backlog

A living, engineering-owned backlog for the **admin SPA** (the platform-operator
surface). This is implementation/tracking — **not** product canon, so it lives
here under `web/` rather than `docs/` (no `docs_uz/` mirror, no canon
frontmatter). `docs/` stays the source of truth for *what* the product is; this
file tracks *fixes/polish* against the current Vue implementation.

> Seeded 2026-06-20 from an automated multi-lens audit (UX/flow, responsive,
> i18n/copy, design-parity vs `web/prototypes/prototype-full`, a11y, correctness,
> performance, states/errors, completeness, security/RBAC, spec-conformance,
> tech-debt, testing). **Re-verify each item against current code before
> implementing** — line numbers are point-in-time.
>
> **Audit round 1 (2026-06-20):** read the project law (`AGENTS.md`, `web/AGENTS.md`,
> `e2e/AGENTS.md`), the complex playbook, the full docs canon, the admin prototype
> reference, the in-scope admin views/store/API surface, admin-used shared components,
> and the relevant `/api/v1/platform/*` backend. Fan-out review covered all 13 lenses,
> followed by skeptical verification and deduplication into AB-001…AB-060.
>
> **Refuted before entry:** `/platform/overview` is guarded by
> `require_platform_operator()` in service code; stale `AdminCatalogView.vue` strings are
> not routed; the Jobs screen already has a log modal; the Notifications page already has
> read/unread filters; broad "all lists must paginate" was narrowed to concrete dashboard
> overfetch and audit-index findings. These do not get backlog IDs.

## Conventions

- **Priority** — `P1` do-first (admin destructive/security/platform-ops path), `P2`
  important, `P3` nice-to-have.
- **Severity** — user-facing or operational impact. **Effort** — `S` <= 1/2 day ·
  `M` ~1-2 days · `L` larger.
- **Category** — `ux-flow` · `responsive` · `i18n-copy` · `design-parity` · `a11y` ·
  `correctness-bug` · `performance` · `states-errors` · `completeness-stub` ·
  `security-rbac` · `spec-conformance` · `tech-debt` · `testing`.
- **Status** — `Open` · `WIP` · `Done` · `Won't` (update as we go).
- Scope guard: items here are **admin SPA only** per [`docs/scope.md`](../docs/scope.md)
  and [`docs/ref/features/platform.md`](../docs/ref/features/platform.md). Client SPA is
  closed; Workshop SPA is separate ownership. Backend changes are listed only where admin
  correctness genuinely requires them.

## Counts

| | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| Open (incl. partial) | 19 | 38 | 3 | **60** |
| Done | 0 | 0 | 0 | **0** |
| Won't | — | — | — | **0** |

> Category totals (Open): security-rbac 3 · correctness-bug 6 · a11y 9 · ux-flow 7 ·
> i18n-copy 8 · states-errors 3 · design-parity 2 · responsive 5 · spec-conformance 7 ·
> completeness-stub 5 · performance 2 · testing 2 · tech-debt 1.

> Progress (2026-06-20, admin-finish audit): **AB-001…AB-060 seeded as Open** after
> multi-lens audit and adversarial verification. No implementation has started; wait for
> explicit approval before changing application code.

## Index

| ID | Priority | Category | Severity | Effort | Status | Title |
|---|---|---|---|---|---|---|
| AB-001 | P1 | security-rbac | high | M | Open | One-time temp secrets persist without copy/close lifecycle |
| AB-002 | P1 | security-rbac | high | M | Open | Platform-user password reset runs without confirmation |
| AB-003 | P1 | security-rbac | high | M | Open | Last active platform-operator guard is race-prone |
| AB-004 | P1 | correctness-bug | high | M | Open | Job `running` state is never persisted as server truth |
| AB-005 | P1 | correctness-bug | high | M | Open | Error 24 h / 7 d counters are lifetime increments |
| AB-006 | P1 | correctness-bug | high | S | Open | Edge material edit sends panel-only null fields and fails |
| AB-007 | P1 | correctness-bug | high | M | Open | Workshop provisioning ships hardcoded coordinates and lacks coordinate validation |
| AB-008 | P1 | a11y | high | L | Open | Admin custom dialogs lack focus trap, Escape, restore, and scroll lock |
| AB-009 | P1 | ux-flow | high | M | Open | Catalog activate/deactivate actions run without confirmation or feedback |
| AB-010 | P1 | ux-flow | high | M | Open | Manual job run/retry runs without confirmation or result feedback |
| AB-011 | P1 | ux-flow | high | M | Open | Error resolve runs without confirmation and weakens incident review |
| AB-012 | P1 | ux-flow | high | S | Open | Workshop/operator unblock actions run immediately |
| AB-013 | P1 | i18n-copy | high | M | Open | Native browser validation leaks non-Uzbek form errors |
| AB-014 | P1 | i18n-copy | high | S | Open | Staff login errors are English and lack the documented lockout treatment |
| AB-015 | P1 | states-errors | high | M | Open | Permission-denied and operation failures collapse into generic errors |
| AB-016 | P1 | design-parity | high | S | Open | Material kind remains editable after creation |
| AB-017 | P1 | correctness-bug | high | M | Open | Material image upload can race against Save |
| AB-018 | P1 | responsive | high | S | Open | Admin notification dropdown can render off-screen at small widths |
| AB-019 | P1 | spec-conformance | high | L | Open | Audit viewer is not investigation-capable |
| AB-020 | P2 | ux-flow | med | S | Open | Password-reset-required users land on the wrong profile tab |
| AB-021 | P2 | completeness-stub | med | M | Open | Admin profile sessions omit per-session revoke |
| AB-022 | P2 | completeness-stub | med | S | Open | Admin password change lacks confirm field and strength feedback |
| AB-023 | P2 | a11y | med | M | Open | Manual tablists do not implement the tab pattern |
| AB-024 | P2 | a11y | med | M | Open | Route changes do not move focus to page content |
| AB-025 | P2 | a11y | med | S | Open | Admin shell has no skip link |
| AB-026 | P2 | a11y | med | S | Open | Filters rely on placeholder-only visible labels |
| AB-027 | P2 | a11y | med | M | Open | Async success and failure states are not consistently announced |
| AB-028 | P2 | a11y | med | M | Open | Repeated row action names lack row context |
| AB-029 | P2 | a11y | med | S | Open | Hairline control borders fail non-text contrast |
| AB-030 | P2 | a11y | med | S | Open | Mobile admin drawer dialog has no accessible name |
| AB-031 | P2 | responsive | med | S | Open | Mobile admin drawer stays open after route navigation |
| AB-032 | P2 | responsive | low | S | Open | Docs/API links disappear from mobile navigation |
| AB-033 | P2 | responsive | med | M | Open | Admin modals are not mobile scroll-safe |
| AB-034 | P2 | responsive | med | S | Open | Admin form controls risk iOS auto-zoom |
| AB-035 | P2 | spec-conformance | med | M | Open | Workshop list lacks operator-critical columns and row actions |
| AB-036 | P2 | spec-conformance | med | M | Open | Workshop detail tabs and blocked state diverge from spec/prototype |
| AB-037 | P2 | completeness-stub | med | M | Open | Workshop first-branch working hours are hidden defaults |
| AB-038 | P2 | spec-conformance | med | S | Open | Manufacturer country filter is missing |
| AB-039 | P2 | spec-conformance | med | M | Open | Materials filters are incomplete |
| AB-040 | P2 | design-parity | med | M | Open | Materials table lacks image/swatch/usage parity |
| AB-041 | P2 | completeness-stub | med | M | Open | Material dimension defaults and edge guidance are unfinished |
| AB-042 | P2 | spec-conformance | med | M | Open | Error monitor filters/detail are incomplete |
| AB-043 | P2 | ux-flow | med | M | Open | Error notifications lose incident context on navigation |
| AB-044 | P2 | spec-conformance | med | M | Open | Notifications page is fixed-size and does not mark rows read on open |
| AB-045 | P2 | states-errors | med | S | Open | Dashboard refresh only reloads overview, leaving sections stale |
| AB-046 | P2 | states-errors | med | M | Open | Dashboard partial-load failures are hidden by shared loading/error state |
| AB-047 | P2 | performance | med | M | Open | Dashboard overfetches full admin collections |
| AB-048 | P2 | performance | med | S | Open | Latest audit-log reads lack time-oriented indexes |
| AB-049 | P2 | correctness-bug | med | S | Open | Skipped job runs are optimistically presented as latest result |
| AB-050 | P2 | ux-flow | med | S | Open | Last-active platform-operator block flow is only rejected after submit |
| AB-051 | P2 | i18n-copy | med | M | Open | Raw enum/status labels leak across admin views |
| AB-052 | P2 | i18n-copy | med | M | Open | Dashboard and Jobs copy mixes Uzbek and English debug terms |
| AB-053 | P2 | i18n-copy | med | S | Open | Admin notifications copy is mixed and dropdown action stays English |
| AB-054 | P2 | i18n-copy | med | M | Open | Catalog/material forms retain English operator-facing labels |
| AB-055 | P2 | i18n-copy | med | S | Open | Error monitor uses English fallback/action strings |
| AB-056 | P2 | testing | high | M | Open | Destructive admin flows lack E2E coverage |
| AB-057 | P2 | testing | high | M | Open | Admin store/backend invariants lack regression tests |
| AB-058 | P3 | tech-debt | med | L | Open | Admin duplicates modal/action/error patterns instead of using shared primitives |
| AB-059 | P3 | i18n-copy | low | S | Open | Shared control defaults are English when admin does not override them |
| AB-060 | P3 | completeness-stub | low | S | Open | Admin topbar global search is inert and out of operator scope |

## P1 — do first (admin destructive/security/platform-ops path)

### AB-001 · One-time temp secrets persist without copy/close lifecycle — `security-rbac` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:336`, `web/src/shared/views/AdminPlatformUsersView.vue:245`, `web/src/shared/stores/admin.ts:211`, `web/src/shared/stores/admin.ts:215`, `web/src/shared/stores/admin.ts:273`, `web/src/shared/stores/admin.ts:432`, `web/src/shared/stores/admin.ts:448`  
**Spec / prototype:** `docs/ref/features/access-management.md:157`, `docs/ref/features/access-management.md:177`, `docs/ref/features/access-management.md:186`, `docs/ref/features/platform.md:88`, `docs/ref/features/platform.md:132`; prototype Platform users / Create workshop one-time-secret confirmations.  
**Why:** Provisioning and platform-user create/reset return temporary passwords that should be shared once. The UI leaves the latest secret in Pinia and on the page until logout/reset, with no explicit copy/close/clear lifecycle. On a privileged admin surface that is a real exposure window.  
**Fix:** Render the success as a focused confirmation with copy buttons, explicit close/dismiss, and store clearers (`clearLastProvision`, `clearLastPlatformUserSecret`). Clear stale secrets before new sensitive actions and on route leave where appropriate; add regression tests for clearing.

### AB-002 · Platform-user password reset runs without confirmation — `security-rbac` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminPlatformUsersView.vue:79`, `web/src/shared/views/AdminPlatformUsersView.vue:202`, `web/src/shared/stores/admin.ts:448`, `backend/app/modules/platform/routes.py:245`  
**Spec / prototype:** `docs/ref/features/platform.md:88`, `docs/ref/features/platform.md:123`, `docs/ref/features/platform.md:132`; prototype Platform users action menu.  
**Why:** Resetting a platform operator password revokes sessions and returns a one-time secret, but the current row button posts immediately. A misclick can force-reset another privileged operator.  
**Fix:** Gate reset behind an explicit Uzbek confirmation naming the operator and effect, then show the AB-001 one-time-secret confirmation. Keep backend audit logging; add E2E coverage for reset cancel/confirm.

### AB-003 · Last active platform-operator guard is race-prone — `security-rbac` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `backend/app/modules/platform/service.py:766`, `web/src/shared/views/AdminPlatformUsersView.vue:210`  
**Spec / prototype:** `docs/ref/features/platform.md:94`, `docs/ref/features/platform.md:145`.  
**Why:** The backend counts other active operators before blocking, but the check is not protected by row locks or an equivalent serializing mechanism. Two concurrent blocks can both observe another active operator and leave zero active operators. The UI only prevents self-block.  
**Fix:** Serialize the invariant in the backend (row locks/advisory lock/transaction-safe query) and expose a disabled explanatory UI state when only one active operator remains. Add a backend concurrency/invariant regression test.

### AB-004 · Job `running` state is never persisted as server truth — `correctness-bug` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `backend/app/modules/platform/scheduler.py:39`, `backend/app/modules/platform/scheduler.py:51`, `backend/app/modules/platform/scheduler.py:72`, `web/src/shared/views/AdminPlatformJobsView.vue:116`, `web/src/shared/stores/admin.ts:496`  
**Spec / prototype:** `docs/ref/features/platform.md:66`, `docs/ref/features/platform.md:116`, `docs/ref/features/platform.md:141`.  
**Why:** The scheduler writes a `JobRun(status=RUNNING)` but never sets `JobDefinition.running = true`; the Jobs view disables by `job.definition.running`, so another tab/process can still show "Run now" while the job is active. The backend has only an in-process lock, so the UI state is not trustworthy.  
**Fix:** Persist running truth on the definition or derive it from unfinished runs, return that truth from `/platform/jobs`, and refresh after run completion. Tests should cover already-running behavior and UI disabled copy.

### AB-005 · Error 24 h / 7 d counters are lifetime increments — `correctness-bug` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `backend/app/modules/platform/errors.py:47`, `backend/app/modules/platform/errors.py:48`, `backend/app/modules/platform/service.py:613`, `web/src/shared/views/AdminPlatformErrorsView.vue:121`, `web/src/shared/views/AdminDashboardView.vue:98`  
**Spec / prototype:** `docs/ref/features/platform.md:74`, `docs/ref/features/platform.md:80`, `docs/ref/features/platform.md:119`, `docs/ref/features/platform.md:142`.  
**Why:** `count_24h` and `count_7d` are incremented forever instead of being rolling-window counts. Dashboard incident KPIs, spike notifications, and operator triage become increasingly false over time.  
**Fix:** Compute rolling counts from occurrences or maintain bucketed counters with expiry semantics. Backfill API/tests so the dashboard and error monitor cannot regress to lifetime counts.

### AB-006 · Edge material edit sends panel-only null fields and fails — `correctness-bug` · high · S

**Priority:** P1 · **Severity:** high · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminMaterialsView.vue:162`, `web/src/shared/views/AdminMaterialsView.vue:176`, `backend/app/modules/catalog/service.py:313`  
**Spec / prototype:** `docs/ref/features/catalog-inventory.md:45`, `docs/ref/features/catalog-inventory.md:52`, `docs/ref/features/platform.md:39`.  
**Why:** The material form sends `type`, `panel_length_mm`, `panel_width_mm`, and `grain_direction` keys as `null` for edge materials. The backend correctly treats any panel-only key in the patch payload as invalid for edge materials and rejects the update.  
**Fix:** Build kind-specific payloads that omit non-applicable fields, especially on edit. Add store/view tests for edge update payload shape.

### AB-007 · Workshop provisioning ships hardcoded coordinates and lacks coordinate validation — `correctness-bug` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:25`, `web/src/shared/views/AdminWorkshopsView.vue:79`, `web/src/shared/views/AdminWorkshopsView.vue:281`, `backend/app/modules/platform/schemas.py:31`  
**Spec / prototype:** `docs/ref/features/access-management.md:152`, `docs/ref/features/access-management.md:177`.  
**Why:** Every new workshop starts with Tashkent defaults (`41.2995`, `69.2401`) and the backend schema accepts arbitrary Decimals without lat/lon range validation. Operators can accidentally create real branches at the wrong location or hit deeper DB errors for invalid coordinates.  
**Fix:** Remove hidden defaults or make them an explicit operator choice, validate lat/lon on the client, and add backend Pydantic range validation (`-90..90`, `-180..180`) with tests.

### AB-008 · Admin custom dialogs lack focus trap, Escape, restore, and scroll lock — `a11y` · high · L

**Priority:** P1 · **Severity:** high · **Effort:** L · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:219`, `web/src/shared/views/AdminWorkshopDetailView.vue:250`, `web/src/shared/views/AdminManufacturersView.vue:197`, `web/src/shared/views/AdminMaterialsView.vue:331`, `web/src/shared/views/AdminPlatformJobsView.vue:145`, `web/src/shared/views/AdminPlatformErrorsView.vue:168`, `web/src/shared/views/AdminPlatformUsersView.vue:270`, `web/src/shared/views/AdminPlatformUsersView.vue:334`  
**Spec / prototype:** `docs/ref/features/access-management.md:186`, `docs/ref/features/platform.md:132`, `docs/ref/features/catalog-inventory.md:192`.  
**Why:** Admin modals are hand-rolled per view. They set `role="dialog"` but do not move focus in, trap Tab, close on Escape, return focus to the trigger, or consistently lock background scroll. This breaks keyboard operation exactly where admin performs destructive actions.  
**Fix:** Move admin dialogs to a shared accessible primitive or adapt `ConfirmDialog` with explicit Uzbek labels. Replace literal `x` buttons with icon buttons, keep body scroll locked, and cover focus behavior with component/E2E tests.

### AB-009 · Catalog activate/deactivate actions run without confirmation or feedback — `ux-flow` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminManufacturersView.vue:80`, `web/src/shared/views/AdminManufacturersView.vue:176`, `web/src/shared/views/AdminMaterialsView.vue:207`, `web/src/shared/views/AdminMaterialsView.vue:313`  
**Spec / prototype:** `docs/ref/features/platform.md:48`, `docs/ref/features/platform.md:132`, `docs/ref/features/catalog-inventory.md:30`, `docs/ref/features/catalog-inventory.md:56`.  
**Why:** Manufacturer/material status toggles affect what workshops can newly select and what clients can see, but row buttons post immediately and failures are not surfaced as row-level feedback.  
**Fix:** Use an action menu + confirmation naming the material/manufacturer and consequence. Add success/error toast or inline status, and update affected E2E locators when labels change.

### AB-010 · Manual job run/retry runs without confirmation or result feedback — `ux-flow` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminPlatformJobsView.vue:18`, `web/src/shared/views/AdminPlatformJobsView.vue:116`, `web/src/shared/stores/admin.ts:496`  
**Spec / prototype:** `docs/ref/features/platform.md:69`, `docs/ref/features/platform.md:116`, `docs/ref/features/platform.md:132`.  
**Why:** `Run now` and failed-job retry fire immediately. Jobs can perform cleanup or notification work; operators need a confirmation, busy state grounded in server truth, and a clear result.  
**Fix:** Add a confirm dialog/drawer action, refresh the job row after completion, and show success/failure feedback with trace/log link. Pair with AB-004.

### AB-011 · Error resolve runs without confirmation and weakens incident review — `ux-flow` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminPlatformErrorsView.vue:58`, `web/src/shared/views/AdminPlatformErrorsView.vue:202`, `backend/app/modules/platform/service.py:656`  
**Spec / prototype:** `docs/ref/features/platform.md:74`, `docs/ref/features/platform.md:119`, `docs/ref/features/platform.md:132`.  
**Why:** Resolving an error code is an incident-triage action, but the modal button mutates immediately and the UI has no confirmation or post-action review state. Misclicks can hide active incidents.  
**Fix:** Confirm resolve with code/module/count context, keep the detail visible after resolution, and toast/audit-link the result.

### AB-012 · Workshop/operator unblock actions run immediately — `ux-flow` · high · S

**Priority:** P1 · **Severity:** high · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopDetailView.vue:39`, `web/src/shared/views/AdminWorkshopDetailView.vue:93`, `web/src/shared/views/AdminPlatformUsersView.vue:112`, `web/src/shared/views/AdminPlatformUsersView.vue:221`  
**Spec / prototype:** `docs/ref/features/access-management.md:162`, `docs/ref/features/platform.md:88`, `docs/ref/features/platform.md:132`.  
**Why:** Unblocking restores a workshop/user's ability to sign in, but current buttons post directly. Destructive-style confirmations exist for block only.  
**Fix:** Add Uzbek confirmations for unblock actions that name the entity and the effect. Keep server audit logs and surface failures.

### AB-013 · Native browser validation leaks non-Uzbek form errors — `i18n-copy` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:238`, `web/src/shared/views/AdminProfileView.vue:143`, `web/src/shared/views/AdminManufacturersView.vue:218`, `web/src/shared/views/AdminMaterialsView.vue:350`, `web/src/shared/views/AdminPlatformUsersView.vue:284`, `web/src/shared/views/AdminPlatformUsersView.vue:353`  
**Spec / prototype:** `docs/index.md` v1 app language policy; `docs/ref/features/platform.md:132`; `docs/ref/features/access-management.md:68`.  
**Why:** Admin forms rely on native `required`/`minlength` validation. Browser-generated messages follow the browser locale, not the product's Uzbek operator copy policy, so validation can appear in English/Russian/system language.  
**Fix:** Add `novalidate` and explicit Uzbek inline validation for admin forms, preserving backend codes for final truth. Cover one modal with E2E to prevent native bubbles returning.

### AB-014 · Staff login errors are English and lack the documented lockout treatment — `i18n-copy` · high · S

**Priority:** P1 · **Severity:** high · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/composables/useStaffLogin.ts:8`, `web/src/shared/views/AdminLoginView.vue`, `web/src/shared/views/WorkshopLoginView.vue`  
**Spec / prototype:** `docs/ref/features/access-management.md:19`, `docs/ref/features/access-management.md:25`, `docs/ref/features/access-management.md:70`.  
**Why:** The shared staff-login composable returns English messages (`Credentials do not match...`, `API is not reachable...`). It also flattens lockout into a static message instead of the documented lockout banner. This affects admin and workshop because the code is shared.  
**Fix:** Localize staff-login copy to the agreed Uzbek policy, keep generic bad-credential semantics, and add lockout-specific banner/timing if the API exposes it. Treat the shared edit as a cross-SPA decision and update workshop tests if selectors change.

### AB-015 · Permission-denied and operation failures collapse into generic errors — `states-errors` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/stores/admin.ts:320`, `web/src/shared/stores/admin.ts:418`, `web/src/shared/stores/admin.ts:482`, `web/src/shared/stores/admin.ts:507`, `web/src/shared/stores/admin.ts:542`, `web/src/shared/views/AdminPlatformUsersView.vue:153`, `web/src/shared/views/AdminPlatformJobsView.vue:55`, `web/src/shared/views/AdminPlatformErrorsView.vue:101`, `web/src/shared/views/AdminAuditView.vue:85`  
**Spec / prototype:** `docs/ref/features/platform.md:132`; `docs/ref/features/access-management.md:29`.  
**Why:** Catalog loaders preserve `permission_denied`, but platform users/jobs/errors/audit use generic `*_load_failed` codes and views render endpoint-failed text. A real 403, expired gate, or permission issue is indistinguishable from backend outage. Action failures are similarly generic.  
**Fix:** Use a shared `captureApiError` path for all admin store operations, render a distinct permission-denied/no-access state, and include trace IDs and retry/action guidance.

### AB-016 · Material kind remains editable after creation — `design-parity` · high · S

**Priority:** P1 · **Severity:** high · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminMaterialsView.vue:127`, `web/src/shared/views/AdminMaterialsView.vue:353`  
**Spec / prototype:** `docs/ref/features/catalog-inventory.md:45`, `docs/ref/features/catalog-inventory.md:52`; prototype Materials edit dialog.  
**Why:** `kind` is part of a material's identity and determines valid fields. The edit dialog still exposes the kind selector, which can desynchronize UI intent from backend behavior and trigger AB-006.  
**Fix:** Lock kind on edit and show it as read-only text/chip. Only creation chooses kind.

### AB-017 · Material image upload can race against Save — `correctness-bug` · high · M

**Priority:** P1 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminMaterialsView.vue:151`, `web/src/shared/views/AdminMaterialsView.vue:429`, `web/src/shared/views/AdminMaterialsView.vue:443`  
**Spec / prototype:** `docs/ref/features/catalog-inventory.md:47`, `docs/ref/features/platform.md:39`, `docs/ref/features/platform.md:132`.  
**Why:** File upload is asynchronous, but Save is disabled only by `saving`, not `files.uploading`. Operators can save before `image_file_id` is set and silently lose the image association. Upload failures also lack actionable feedback.  
**Fix:** Disable Save while uploading, surface upload errors, and add a success indicator for the attached image. Test the race with store/component coverage.

### AB-018 · Admin notification dropdown can render off-screen at small widths — `responsive` · high · S

**Priority:** P1 · **Severity:** high · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/components/NotificationsMenu.vue:239`, `web/src/shared/components/AppShell.vue:898`  
**Spec / prototype:** `docs/ref/features/notifications.md:38`, `docs/ref/features/notifications.md:46`, `docs/ref/features/notifications.md:50`.  
**Why:** The dropdown is `absolute right-0` relative to the bell wrapper. In the admin topbar the bell can sit away from the viewport right edge, so the fixed 360px menu can overflow at narrow widths.  
**Fix:** Make the popover viewport-aware for admin, or render it as a mobile sheet below a breakpoint. Verify desktop and narrow screenshots.

### AB-019 · Audit viewer is not investigation-capable — `spec-conformance` · high · L

**Priority:** P1 · **Severity:** high · **Effort:** L · **Status:** Open  
**Files:** `web/src/shared/views/AdminAuditView.vue:52`, `web/src/shared/views/AdminAuditView.vue:57`, `web/src/shared/views/AdminAuditView.vue:60`, `web/src/shared/views/AdminAuditView.vue:122`, `web/src/shared/stores/admin.ts:542`, `backend/app/modules/platform/routes.py:300`  
**Spec / prototype:** `docs/ref/features/platform.md:127`; `docs/ref/features/workshop.md` audit viewer section; prototype Audit screen.  
**Why:** Audit is the admin's cross-workshop accountability surface, but the UI has one client-side text query, an inert CSV button, invalid tab semantics, truncated JSON details, and no entity links. Store calls do not pass filters/limits even though backend has some query params.  
**Fix:** Add server-backed filters (workshop, branch, actor/action/entity/time/limit as supported/extended), expandable detail rows, entity deep links, working CSV export or remove the button, and accessible tabs. Add E2E for filtering/export affordance.

## P2 — important

### AB-020 · Password-reset-required users land on the wrong profile tab — `ux-flow` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/app/createRoleApp.ts:138`, `web/src/shared/views/AdminProfileView.vue:11`, `web/src/shared/views/AdminProfileView.vue:87`  
**Spec / prototype:** `docs/ref/features/access-management.md:29`, `docs/ref/features/access-management.md:74`.  
**Why:** The route guard sends reset-required users to `/admin/profile`, whose default tab is Profile. The warning tells them to change the password but does not open or link the password tab.  
**Fix:** Route with a query/hash for the password tab or make the banner button set `tab = 'password'`. Mirror any shared behavior needed for workshop profile.

### AB-021 · Admin profile sessions omit per-session revoke — `completeness-stub` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminProfileView.vue:35`, `web/src/shared/views/AdminProfileView.vue:173`, `web/src/shared/views/AdminProfileView.vue:190`  
**Spec / prototype:** `docs/ref/features/access-management.md:39`, `docs/ref/features/access-management.md:60`, `docs/ref/features/access-management.md:77`.  
**Why:** Admin profile lists sessions and offers logout-everywhere, but no per-row revoke action. There is also no loading/error state for session fetch.  
**Fix:** Add per-session revoke with confirmation, current-session labeling, loading/error/retry states, and tests against the auth store/API.

### AB-022 · Admin password change lacks confirm field and strength feedback — `completeness-stub` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminProfileView.vue:139`, `web/src/shared/views/AdminProfileView.vue:154`  
**Spec / prototype:** `docs/ref/features/access-management.md:21`, `docs/ref/features/access-management.md:77`.  
**Why:** The password form has current and new password only. The docs require password complexity and the profile UX calls for a strength meter; a mistyped new password is easy.  
**Fix:** Add confirm-new-password, strength/requirements feedback, and Uzbek validation. Keep backend as source of truth.

### AB-023 · Manual tablists do not implement the tab pattern — `a11y` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopDetailView.vue:112`, `web/src/shared/views/AdminProfileView.vue:97`, `web/src/shared/views/AdminAuditView.vue:60`  
**Spec / prototype:** `docs/ref/features/platform.md:132`; WAI-ARIA tab pattern.  
**Why:** Containers use `role="tablist"`, but buttons lack `role="tab"`, `aria-selected`, `aria-controls`, keyboard roving, and matching `tabpanel`s. Screen readers receive an incomplete widget.  
**Fix:** Implement a small admin tabs primitive or add the full pattern in each view.

### AB-024 · Route changes do not move focus to page content — `a11y` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/components/AppShell.vue:907`, `web/src/shared/app/createRoleApp.ts:147`  
**Spec / prototype:** `docs/ref/features/platform.md:132`; `docs/ref/features/notifications.md:50`.  
**Why:** After navigation, focus remains on the old link/button. Keyboard and screen-reader users do not get a clear page-change cue in this SPA shell.  
**Fix:** Focus the main heading or a `tabindex="-1"` page container after route changes, without stealing focus during modal/dialog interactions.

### AB-025 · Admin shell has no skip link — `a11y` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/components/AppShell.vue:747`, `web/src/shared/components/AppShell.vue:879`, `web/src/shared/components/AppShell.vue:907`  
**Spec / prototype:** `docs/ref/features/platform.md:132`.  
**Why:** The admin sidebar has many nav items before content. Keyboard users need a skip link to bypass repeated navigation.  
**Fix:** Add a visually-hidden/focus-visible "Asosiy kontentga o'tish" link targeting the admin main/page container.

### AB-026 · Filters rely on placeholder-only visible labels — `a11y` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:148`, `web/src/shared/views/AdminManufacturersView.vue:104`, `web/src/shared/views/AdminMaterialsView.vue:231`, `web/src/shared/views/AdminPlatformUsersView.vue:137`, `web/src/shared/views/AdminPlatformErrorsView.vue:86`, `web/src/shared/views/AdminAuditView.vue:52`  
**Spec / prototype:** `docs/ref/features/platform.md:132`; `docs/ref/features/catalog-inventory.md:192`.  
**Why:** Search/filter fields hide labels in `sr-only` and depend on placeholder text visually. Placeholders disappear as soon as users type and are a weaker form label for dense admin filtering.  
**Fix:** Use visible compact labels or labeled filter chips consistent with the prototype.

### AB-027 · Async success and failure states are not consistently announced — `a11y` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminPlatformUsersView.vue:238`, `web/src/shared/views/AdminPlatformJobsView.vue:138`, `web/src/shared/views/AdminPlatformErrorsView.vue:161`, `web/src/shared/views/AdminMaterialsView.vue:432`, `web/src/shared/views/AdminProfileView.vue:168`  
**Spec / prototype:** `docs/ref/features/platform.md:132`; `docs/ref/features/notifications.md:50`.  
**Why:** Many action outcomes render as plain paragraphs without `role="alert"`/`aria-live`, and successful destructive actions often have no announced success state.  
**Fix:** Route all admin action outcomes through ToastHost/status regions with accessible live announcements and trace-aware errors.

### AB-028 · Repeated row action names lack row context — `a11y` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminManufacturersView.vue:169`, `web/src/shared/views/AdminMaterialsView.vue:306`, `web/src/shared/views/AdminPlatformUsersView.vue:195`, `web/src/shared/views/AdminPlatformErrorsView.vue:146`  
**Spec / prototype:** `docs/ref/features/platform.md:132`; prototype row action menus.  
**Why:** Buttons such as "Tahrirlash", "Faollashtirish", and "Tafsilotlar" repeat in tables. Screen-reader users cannot easily tell which row each action affects.  
**Fix:** Add contextual `aria-label`s or move to named row action menus.

### AB-029 · Hairline control borders fail non-text contrast — `a11y` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/styles/admin.css`, `web/src/shared/views/Admin*.vue` controls using `border-hairline` / `border-hairline-strong`  
**Spec / prototype:** `docs/ref/features/platform.md:132`; WCAG non-text contrast.  
**Why:** Admin controls often rely on very light borders against white/elevated backgrounds; the audit measured representative hairlines below 3:1. In a dense admin UI, boundaries and focus affordances must remain legible.  
**Fix:** Raise admin control border/focus token contrast and verify screenshots for tables, filters, dialogs, and cards.

### AB-030 · Mobile admin drawer dialog has no accessible name — `a11y` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/components/AppShell.vue:830`, `web/src/shared/components/AppShell.vue:843`, `web/src/shared/components/AppShell.vue:855`  
**Spec / prototype:** `docs/ref/features/platform.md:132`.  
**Why:** The mobile drawer has `role="dialog"` and `aria-modal="true"` but no `aria-label`/`aria-labelledby`. Assistive tech announces an unnamed dialog.  
**Fix:** Add a stable title and `aria-labelledby`, or an explicit Uzbek `aria-label`.

### AB-031 · Mobile admin drawer stays open after route navigation — `responsive` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/components/AppShell.vue:855`, `web/src/shared/components/AppShell.vue:862`  
**Spec / prototype:** `docs/ref/features/platform.md:100`; prototype admin mobile navigation.  
**Why:** Desktop/sidebar nav links close mobile nav, but the drawer's mobile `RouterLink`s do not call `closeMobileNav`. A selected route can render behind the still-open drawer.  
**Fix:** Add close handling to mobile links and cover with a mobile E2E or component test.

### AB-032 · Docs/API links disappear from mobile navigation — `responsive` · low · S

**Priority:** P2 · **Severity:** low · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/components/AppShell.vue:790`, `web/src/shared/components/AppShell.vue:855`  
**Spec / prototype:** `docs/ref/features/platform.md:107`.  
**Why:** Desktop admin nav includes `/docs`, `/api-docs`, and `/api-redoc` links with the second-login note. The mobile drawer only renders grouped admin nav and omits these operator resources.  
**Fix:** Include the docs/API group in the drawer with the same labeling and external-link behavior.

### AB-033 · Admin modals are not mobile scroll-safe — `responsive` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:219`, `web/src/shared/views/AdminMaterialsView.vue:331`, `web/src/shared/views/AdminPlatformErrorsView.vue:168`, `web/src/shared/styles/admin.css`  
**Spec / prototype:** `docs/ref/features/access-management.md:186`; `docs/ref/features/catalog-inventory.md:192`.  
**Why:** Large admin dialogs use custom overlays but lack `dvh` sizing, overscroll containment, and body scroll lock. On smaller screens, headers/footers and required fields can become awkward or trapped under browser chrome.  
**Fix:** Solve together with AB-008 using a responsive dialog primitive.

### AB-034 · Admin form controls risk iOS auto-zoom — `responsive` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/styles/admin.css`, `web/src/shared/views/AdminWorkshopsView.vue:238`, `web/src/shared/views/AdminMaterialsView.vue:350`, `web/src/shared/views/AdminPlatformUsersView.vue:284`  
**Spec / prototype:** prototype mobile admin forms; `docs/ref/features/platform.md:132`.  
**Why:** Several compact admin inputs/selects inherit sub-16px text classes. iOS Safari can zoom on focus, which breaks smaller-width admin workflows.  
**Fix:** Keep mobile input font-size at least 16px while preserving desktop density.

### AB-035 · Workshop list lacks operator-critical columns and row actions — `spec-conformance` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:180`, `web/src/shared/views/AdminWorkshopsView.vue:197`, `backend/app/modules/platform/schemas.py:58`, `backend/app/modules/platform/service.py:114`  
**Spec / prototype:** `docs/ref/features/access-management.md:148`, `docs/ref/features/platform.md:102`; prototype Workshops table.  
**Why:** The list shows owner UUID prefix instead of owner name/phone, and omits branch count/recent-order or incident columns/action menu that the prototype uses for operator triage. Some data is not present in the summary API.  
**Fix:** Extend the platform workshop summary intentionally, then update table columns and row action menu. Avoid cross-workshop order browsing; only include scoped summary metrics allowed by docs.

### AB-036 · Workshop detail tabs and blocked state diverge from spec/prototype — `spec-conformance` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopDetailView.vue:13`, `web/src/shared/views/AdminWorkshopDetailView.vue:112`, `web/src/shared/views/AdminWorkshopDetailView.vue:185`, `web/src/shared/views/AdminWorkshopDetailView.vue:225`  
**Spec / prototype:** `docs/ref/features/access-management.md:162`, `docs/ref/features/access-management.md:167`, `docs/ref/features/access-management.md:183`; prototype Workshop detail.  
**Why:** The detail view has `Profile / Branches / Users`, but Users is a read-only stub and block/unblock is a header button. The blocked state lacks a persistent banner explaining revoked sessions/open-order freeze.  
**Fix:** Align tabs with the prototype/spec intent (Profile, Branches, Block/Status) or make Users real only if canon adds it. Add a blocked banner and unblock confirmation.

### AB-037 · Workshop first-branch working hours are hidden defaults — `completeness-stub` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:50`, `web/src/shared/views/AdminWorkshopsView.vue:104`  
**Spec / prototype:** `docs/ref/features/access-management.md:152`, `docs/ref/features/access-management.md:177`; `docs/ref/features/workshop.md` branch settings.  
**Why:** Provisioning requires first-branch `working_hours`, but the UI silently submits fixed hours. Operators cannot verify or correct the first branch schedule.  
**Fix:** Expose a compact working-hours editor or an explicit "use default hours" choice that is visible before submit.

### AB-038 · Manufacturer country filter is missing — `spec-conformance` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminManufacturersView.vue:14`, `web/src/shared/views/AdminManufacturersView.vue:104`, `web/src/shared/stores/admin.ts:308`  
**Spec / prototype:** `docs/ref/features/platform.md:34`, `docs/ref/features/catalog-inventory.md:26`.  
**Why:** The docs require status and country filters for Manufacturers. The UI has search/status only, and the store/API query does not expose country filtering.  
**Fix:** Add country filter options derived from data or server-side country query support, then wire the view.

### AB-039 · Materials filters are incomplete — `spec-conformance` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminMaterialsView.vue:27`, `web/src/shared/views/AdminMaterialsView.vue:231`, `web/src/shared/stores/admin.ts:331`  
**Spec / prototype:** `docs/ref/features/platform.md:39`, `docs/ref/features/catalog-inventory.md:160`, `docs/ref/features/catalog-inventory.md:183`.  
**Why:** Materials require kind, manufacturer multi-select, type, thickness, and status filters. Current UI has kind/manufacturer single/status/search and no type/thickness filter.  
**Fix:** Add the missing filters, preferably with server query support where it reduces payload. Use `MultiSelectFilter` if the shared component can be made admin-safe.

### AB-040 · Materials table lacks image/swatch/usage parity — `design-parity` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminMaterialsView.vue:266`, `web/src/shared/views/AdminMaterialsView.vue:283`, `web/src/shared/views/AdminMaterialsView.vue:305`  
**Spec / prototype:** `docs/ref/features/platform.md:39`, `docs/ref/features/catalog-inventory.md:47`; prototype Materials table.  
**Why:** The table is text-heavy and lacks the image thumbnail, color/decor swatch, manufacturer chip, branch-usage/action parity, and action menu expected for material triage.  
**Fix:** Add visual material identity and usage-safe fields without leaking workshop finances. Keep action controls keyboard-operable.

### AB-041 · Material dimension defaults and edge guidance are unfinished — `completeness-stub` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminMaterialsView.vue:37`, `web/src/shared/views/AdminMaterialsView.vue:119`, `web/src/shared/views/AdminMaterialsView.vue:136`, `web/src/shared/views/AdminMaterialsView.vue:401`  
**Spec / prototype:** `docs/ref/features/catalog-inventory.md:45`, `docs/ref/features/catalog-inventory.md:208`.  
**Why:** New panels default to `2800 x 2070`, edit fallback uses the same magic values, and the UI does not explain or validate `length >= width` / grain direction. Edge material units are described only as "metres" copy, not a form model.  
**Fix:** Make dimensions explicit, validate `length >= width`, explain edge vs panel fields, and remove hidden fallback defaults on edit.

### AB-042 · Error monitor filters/detail are incomplete — `spec-conformance` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminPlatformErrorsView.vue:16`, `web/src/shared/views/AdminPlatformErrorsView.vue:86`, `web/src/shared/views/AdminPlatformErrorsView.vue:187`, `web/src/shared/stores/admin.ts:507`, `backend/app/modules/platform/routes.py:165`  
**Spec / prototype:** `docs/ref/features/platform.md:74`, `docs/ref/features/platform.md:119`.  
**Why:** The monitor lacks time-range and count-threshold filters, and the detail modal shows occurrences but not first-class affected workshop/user rows where known. The store always loads the whole default list.  
**Fix:** Add filters supported by backend query params (extend if needed), add affected-entity sections and links, and keep masked context/stack inspectable.

### AB-043 · Error notifications lose incident context on navigation — `ux-flow` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/app/adminUi.ts:132`, `web/src/shared/views/AdminNotificationsView.vue:92`, `web/src/shared/components/NotificationsMenu.vue:277`  
**Spec / prototype:** `docs/ref/features/notifications.md:23`, `docs/ref/features/notifications.md:38`, `docs/ref/features/platform.md:80`.  
**Why:** Admin notification destinations route broadly to Jobs or Errors, but not to a specific job/error record with detail opened or filtered. Operators lose the incident context from the notification payload.  
**Fix:** Include destination query/hash keyed by entity payload, open the relevant detail/filter on landing, and mark as read on open (with rollback on failure).

### AB-044 · Notifications page is fixed-size and does not mark rows read on open — `spec-conformance` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminNotificationsView.vue:31`, `web/src/shared/views/AdminNotificationsView.vue:40`, `web/src/shared/views/AdminNotificationsView.vue:84`, `web/src/shared/stores/notifications.ts`  
**Spec / prototype:** `docs/ref/features/notifications.md:30`, `docs/ref/features/notifications.md:40`, `docs/ref/features/notifications.md:41`, `docs/ref/features/notifications.md:43`.  
**Why:** The page loads a fixed 100 rows client-side, filters locally, and a row link does not mark the notification read. Critical platform toasts are not wired on this surface.  
**Fix:** Add pagination/load-more with unread server filter, mark-on-open with rollback, and platform critical toasts if not already emitted globally.

### AB-045 · Dashboard refresh only reloads overview, leaving sections stale — `states-errors` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminDashboardView.vue:25`, `web/src/shared/views/AdminDashboardView.vue:47`  
**Spec / prototype:** `docs/ref/features/platform.md:102`, `docs/ref/features/platform.md:132`.  
**Why:** Initial mount loads overview, workshops, jobs, errors, users, manufacturers, and materials. The Refresh button only calls `loadOverview`, so recent workshops, failed jobs, errors, and resource counts can remain stale.  
**Fix:** Refresh the dashboard's actual data set, or move to a single dashboard summary endpoint (AB-047) and refresh that.

### AB-046 · Dashboard partial-load failures are hidden by shared loading/error state — `states-errors` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminDashboardView.vue:20`, `web/src/shared/stores/admin.ts:221`, `web/src/shared/stores/admin.ts:223`, `web/src/shared/stores/admin.ts:482`, `web/src/shared/stores/admin.ts:507`  
**Spec / prototype:** `docs/ref/features/platform.md:102`, `docs/ref/features/platform.md:132`.  
**Why:** Dashboard mount fans out several loaders that share `loading`/`opsLoading` and `error`/`opsError`. One failure can be overwritten by another success, causing dashboard cards to show zero/empty instead of a partial-error state.  
**Fix:** Track dashboard section state independently or fetch a composed summary response with explicit partial errors.

### AB-047 · Dashboard overfetches full admin collections — `performance` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminDashboardView.vue:25`, `backend/app/modules/platform/service.py:121`, `backend/app/modules/catalog/service.py:185`  
**Spec / prototype:** `docs/ref/features/platform.md:102`.  
**Why:** The dashboard pulls full workshop, jobs, errors, platform users, manufacturers, and materials lists to render small counts/recent summaries. This is heavier than "platform health at a glance" needs and worsens AB-046.  
**Fix:** Expand `/platform/overview` or add a dashboard summary endpoint with recent workshops, failed job summaries, recent errors, and catalog/operator counts.

### AB-048 · Latest audit-log reads lack time-oriented indexes — `performance` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `backend/app/modules/support/audit.py:153`, `backend/app/modules/support/audit.py:171`, `backend/app/modules/support/models.py:65`  
**Spec / prototype:** `docs/architecture.md` append-only audit/read-heavy invariant; `docs/ref/features/platform.md:127`.  
**Why:** Audit endpoints are bounded, but latest reads order append-only logs by `created_at DESC` / `changed_at DESC` without dedicated time indexes. This will degrade as audit volume grows.  
**Fix:** Add migrations for latest-time indexes and composites matching filtered audit reads.

### AB-049 · Skipped job runs are optimistically presented as latest result — `correctness-bug` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `backend/app/modules/platform/scheduler.py:42`, `web/src/shared/stores/admin.ts:496`, `web/src/shared/views/AdminPlatformJobsView.vue:95`  
**Spec / prototype:** `docs/ref/features/platform.md:141`.  
**Why:** If the backend returns a `skipped` run for already-running, the store immediately writes `definition.last_result = skipped`. That may not be the durable job definition result and can replace the last real success/failure in the UI.  
**Fix:** Treat skipped as a transient run row and refetch the definition, or have backend return canonical summary after run attempt.

### AB-050 · Last-active platform-operator block flow is only rejected after submit — `ux-flow` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminPlatformUsersView.vue:210`, `web/src/shared/views/AdminPlatformUsersView.vue:355`, `backend/app/modules/platform/service.py:766`  
**Spec / prototype:** `docs/ref/features/platform.md:94`, `docs/ref/features/platform.md:145`.  
**Why:** The UI disables self-block only. If there is one other active operator, the destructive block flow still opens and fails after submit. That is a poor recovery path for a documented invariant.  
**Fix:** Compute active operator count in the view and disable/explain last-active block before opening the modal. Keep backend defensive guard from AB-003.

### AB-051 · Raw enum/status labels leak across admin views — `i18n-copy` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/app/adminUi.ts:79`, `web/src/shared/views/AdminWorkshopsView.vue:201`, `web/src/shared/views/AdminWorkshopDetailView.vue:82`, `web/src/shared/views/AdminManufacturersView.vue:162`, `web/src/shared/views/AdminMaterialsView.vue:300`, `web/src/shared/views/AdminPlatformUsersView.vue:189`  
**Spec / prototype:** v1 Uzbek UI policy; `docs/ref/features/platform.md:132`.  
**Why:** The app often renders raw enum values (`active`, `blocked`, `inactive`, `open`, `resolved`) or generic `statusLabel` passthrough. Operator copy becomes inconsistent and leaks internal API values.  
**Fix:** Centralize Uzbek status labels per domain while keeping machine values in code/tests.

### AB-052 · Dashboard and Jobs copy mixes Uzbek and English debug terms — `i18n-copy` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminDashboardView.vue:176`, `web/src/shared/views/AdminDashboardView.vue:192`, `web/src/shared/views/AdminPlatformJobsView.vue:41`, `web/src/shared/views/AdminPlatformJobsView.vue:89`, `web/src/shared/views/AdminPlatformJobsView.vue:126`, `web/src/shared/views/AdminPlatformJobsView.vue:178`  
**Spec / prototype:** v1 Uzbek UI policy; `docs/ref/features/platform.md:116`.  
**Why:** Operator-facing strings such as "Failed ish", "enabled", "failed", "No log", and "Qayta urinish (failed)" mix debug English into Uzbek screens.  
**Fix:** Decide and enforce one coherent Uzbek admin copy policy for job/dashboard states.

### AB-053 · Admin notifications copy is mixed and dropdown action stays English — `i18n-copy` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminNotificationsView.vue:49`, `web/src/shared/views/AdminNotificationsView.vue:89`, `web/src/shared/components/NotificationsMenu.vue:256`, `web/src/shared/app/adminUi.ts:132`  
**Spec / prototype:** `docs/ref/features/notifications.md:34`, `docs/ref/features/notifications.md:46`.  
**Why:** Admin notification rows show `new`/`read`, event codes, and English event-family wording; the shared dropdown uses `Mark all read` for admin because the Uzbek branch excludes `isAdmin`.  
**Fix:** Localize admin notification title/body/status/action copy and include admin in shared dropdown Uzbek labels.

### AB-054 · Catalog/material forms retain English operator-facing labels — `i18n-copy` · med · M

**Priority:** P2 · **Severity:** med · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue:246`, `web/src/shared/views/AdminWorkshopsView.vue:282`, `web/src/shared/views/AdminManufacturersView.vue:145`, `web/src/shared/views/AdminMaterialsView.vue:353`, `web/src/shared/views/AdminMaterialsView.vue:421`, `web/src/shared/views/AdminPlatformUsersView.vue:247`  
**Spec / prototype:** v1 Uzbek UI policy; `docs/ref/features/platform.md:32`, `docs/ref/features/access-management.md:175`.  
**Why:** Labels such as `Workshop code`, `Latitude`, `Country`, `Kind`, `Image`, `One-time secret`, and `Temp password` are visible in admin flows.  
**Fix:** Replace visible labels with the agreed Uzbek operator copy while preserving technical terms only where intentionally domain-standard.

### AB-055 · Error monitor uses English fallback/action strings — `i18n-copy` · med · S

**Priority:** P2 · **Severity:** med · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/views/AdminPlatformErrorsView.vue:43`, `web/src/shared/views/AdminPlatformErrorsView.vue:109`, `web/src/shared/views/AdminPlatformErrorsView.vue:140`, `web/src/shared/views/AdminPlatformErrorsView.vue:161`, `web/src/shared/views/AdminPlatformErrorsView.vue:202`  
**Spec / prototype:** `docs/ref/features/platform.md:119`, `docs/ref/features/platform.md:132`.  
**Why:** The error monitor contains `No context`, `No errors recorded - nice.`, `No preview`, `Error action bajarilmadi`, and `Tasdiqlash (resolve)`.  
**Fix:** Localize fallback/action strings and reserve raw technical values for monospace trace/code fields only.

### AB-056 · Destructive admin flows lack E2E coverage — `testing` · high · M

**Priority:** P2 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `e2e/tests/access-and-provisioning.spec.ts`, `e2e/tests/catalog-and-inventory.spec.ts`, missing admin specs for Jobs/Errors/Audit/Notifications  
**Spec / prototype:** `docs/ref/features/platform.md:132`; `e2e/AGENTS.md`.  
**Why:** Existing E2E touches provisioning/catalog creation but not reset-password confirmation, platform user block/unblock, job run confirmation, error resolve, audit filters/export, notification mark-on-open, or dialog focus basics. These are the riskiest admin flows.  
**Fix:** Add focused Playwright coverage in thematic batches as fixes land. When labels/dialogs change, grep/update role/text/label locators first.

### AB-057 · Admin store/backend invariants lack regression tests — `testing` · high · M

**Priority:** P2 · **Severity:** high · **Effort:** M · **Status:** Open  
**Files:** `web/src/shared/stores/admin.ts`, `web/src/shared/app/adminUi.spec.ts`, `backend/app/modules/platform/*` tests  
**Spec / prototype:** `docs/ref/features/platform.md:66`, `docs/ref/features/platform.md:94`, `docs/ref/features/platform.md:141`; testing-practices skill.  
**Why:** There are no dedicated admin store tests for secret clearing, permission-denied capture, kind-specific payloads, job skipped/running handling, or audit filters. Backend invariants for rolling error counts, coordinate validation, job running, and last-operator race also need tests with the implementation fixes.  
**Fix:** Add unit/store tests for pure/admin store behavior and backend tests for server-owned invariants in the same batches as the fixes.

## P3 — nice-to-have

### AB-058 · Admin duplicates modal/action/error patterns instead of using shared primitives — `tech-debt` · med · L

**Priority:** P3 · **Severity:** med · **Effort:** L · **Status:** Open  
**Files:** `web/src/shared/views/AdminWorkshopsView.vue`, `web/src/shared/views/AdminManufacturersView.vue`, `web/src/shared/views/AdminMaterialsView.vue`, `web/src/shared/views/AdminPlatformUsersView.vue`, `web/src/shared/views/AdminPlatformErrorsView.vue`, `web/src/shared/views/AdminPlatformJobsView.vue`  
**Spec / prototype:** `docs/ref/features/platform.md:132`; software-architecture skill for shared-component impact.  
**Why:** Every admin view reimplements modal chrome, action error handling, row actions, and busy state. This is why AB-008/009/010/011/012/027 repeat across files.  
**Fix:** After P1 behavior is clear, extract an admin-safe dialog/action-menu/action-result pattern. Because shared components can affect client/workshop, flag the decision and regression-check other SPAs.

### AB-059 · Shared control defaults are English when admin does not override them — `i18n-copy` · low · S

**Priority:** P3 · **Severity:** low · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/components/ProjectDropdown.vue`, `web/src/shared/components/FormSelect.vue`, `web/src/shared/components/MultiSelectFilter.vue`  
**Spec / prototype:** v1 Uzbek UI policy; `docs/ref/features/platform.md:132`.  
**Why:** Defaults such as `No context`, `Choose one`, `Any`, and `selected` can leak into admin if a caller misses an override. Current in-scope views override many, but not all future/edge states are safe.  
**Fix:** Require explicit labels for admin use or make shared defaults role-aware without regressing client/workshop copy.

### AB-060 · Admin topbar global search is inert and out of operator scope — `completeness-stub` · low · S

**Priority:** P3 · **Severity:** low · **Effort:** S · **Status:** Open  
**Files:** `web/src/shared/components/AppShell.vue:891`  
**Spec / prototype:** `docs/ref/features/platform.md:100`, `docs/ref/features/platform.md:127`, `docs/ref/features/platform.md:128`.  
**Why:** The topbar contains a focusable search input with placeholder "Ustaxona, mijoz, buyurtma yoki xatolik kodi..." but no behavior. It also suggests client/order search, while docs say there is no cross-workshop orders view in v1.  
**Fix:** Remove or disable until specified, or implement a scoped search limited to allowed admin entities (workshops, errors, audit IDs) with explicit docs alignment.
