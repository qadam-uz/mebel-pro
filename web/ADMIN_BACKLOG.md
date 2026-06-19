# Admin (Superadmin) SPA — Improvement Backlog

A living, engineering-owned backlog for the **admin / superadmin SPA** (the
platform-operator console — workshops, catalog, platform ops, audit). This is
implementation/tracking — **not** product canon, so it lives here under `web/`
rather than `docs/` (no `docs_uz/` mirror, no canon frontmatter). `docs/` stays
the source of truth for *what* the product is; this file tracks *fixes/polish*
against the current Vue implementation. It mirrors the discipline of
[`CLIENT_BACKLOG.md`](./CLIENT_BACKLOG.md) (now closed at 130 Done / 4 Won't).

> Seeded 2026-06-19 from a deep multi-lens audit (security/RBAC, correctness,
> states/errors, spec-conformance vs `docs/`, design-parity vs
> `web/prototypes/prototype-full/admin`, i18n/copy, a11y, ux-flow,
> completeness, performance, tech-debt, responsive, testing). 13 lens auditors
> fanned out in parallel; **each finding was adversarially re-checked against the
> current code before it entered this list** (the run hit a session limit during
> the final verification batch, so the surviving findings were also hand-verified
> at `file:line` against the live tree). **Re-verify each item against current
> code before implementing** — line numbers are point-in-time.
>
> Backend RBAC was audited independently and found **solid** — every `/platform/*`
> and `/platform/catalog/*` use-case is gated by `require_platform_operator()`
> (18 inline gates in `platform/service.py` + the two list/show workshop routes
> gating at the route level + the catalog mutators gating transitively via
> `get_manufacturer`/`get_material`), and the `cannot_block_self` /
> `last_platform_operator` guards exist server-side. No missing-gate privilege
> leak was found (see **AB-54, Won't**). The admin findings are therefore
> concentrated on the **frontend** (operator UX, one-time-secret handling,
> confirmations, dialog a11y, error rendering, copy) and a few correctness bugs.

## Conventions

- **Priority** — `P1` do-first (security-adjacent, correctness on
  destructive/privileged paths, blocking a11y/spec gaps), `P2` important,
  `P3` nice-to-have.
- **Severity** — operator-facing / security impact. **Effort** — `S` ≤½ day ·
  `M` ~1–2 days · `L` larger.
- **Category** — `security-rbac` · `correctness-bug` · `states-errors` ·
  `spec-conformance` · `design-parity` · `i18n-copy` · `a11y` · `ux-flow` ·
  `completeness-stub` · `performance` · `tech-debt` · `responsive` · `testing`.
- **Status** — `Open` · `WIP` · `Done` · `Won't` (update as we go).
- Scope guard: the admin SPA only — `web/src/apps/admin/*`, `web/src/shared/views/Admin*.vue`,
  `web/src/shared/stores/admin.ts`, and the shared shell/components/api **as used by admin**.
  A change to a truly shared file (e.g. `useStaffLogin`, `ConfirmDialog`) that could affect the
  **client** (closed) or **workshop** (separate owner) SPA is a **decision** — flagged in the
  item, verified for no cross-SPA regression. Backend changes only where admin correctness
  genuinely requires them, flagged as a decision. Out-of-v1 ideas are excluded per
  [`docs/scope.md`](../docs/scope.md).

## Counts

| | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| Open | 2 | 20 | 21 | **43** |
| Done | 5 | 4 | 1 | **10** |
| Won't | — | — | 1 (AB-54) | **1** |

> Progress (2026-06-19, admin-finish B3): **AB-01, AB-08, AB-28, AB-53 Done** — error/states
> foundation. New `components/AdminErrorState.vue` (title + trace + **Qayta urinish** retry +
> a dedicated permission-denied variant) replaces the 10 hand-copied `admin-error` blocks
> across every admin view, so the leaked "<X> endpoint javob bermadi" nicknames are gone, every
> failed load is retryable, and a 403 now reads "Kirish cheklangan — chiqib, qaytadan kiring"
> (AB-08). **AB-01:** the 7 remaining store loaders (workshops, overview, workshop, platform
> users, jobs, errors, audit) now run their error through `captureApiError`, so a revoked
> operator's 403 surfaces as `permission_denied` everywhere instead of a generic outage;
> `apiTraceId` is dropped from the import (now unused). **AB-28:** `AdminErrorState` carries
> `role="alert"`, the top-level action-failure notices (platform-users / jobs / errors /
> workshop-detail) gained `role="alert"`, and every loading skeleton now has
> `aria-live="polite"`. **AB-53:** new `stores/__tests__/admin.spec.ts` pins 403 →
> `permission_denied` (and a non-403 keeping its generic code) for the loaders. Web gate green:
> lint:check · format:check · typecheck · test **123** · build.

> Progress (2026-06-19, admin-finish B2): **AB-03, AB-04, AB-05, AB-10, AB-23 Done** —
> privileged-action safety + feedback. New `app/clipboard.ts` (`copyText`) and
> `components/AdminSecretModal.vue` — a focus-trapped one-time-secret modal with a warning
> banner, per-row **Nusxa** copy, **Hammasini nusxalash**, and **Yopdim · saqladim** dismiss.
> **AB-03:** store gained `clearSecrets()` + a watch on `auth.accessToken` → clears
> `lastProvision`/`lastPlatformUserSecret` the moment auth drops (logout / log-out-everywhere /
> session-expiry); the two views drive the secret modal from those refs and clear on close +
> `onBeforeUnmount`, so the temp password no longer lingers in the store or re-renders on
> revisit. **AB-04:** added `ConfirmDialog` (explicit Uzbek confirm/dismiss/busy labels) before
> run-job/retry (off-schedule trigger), reset-password (warns sessions are revoked, `danger`),
> error-resolve, and manufacturer/material activate-deactivate (deactivate names the
> client-facing consequence per `platform.md`). **AB-10:** wired `useToast` success/failure
> across provision, block/unblock workshop, create/edit/reset/block/unblock operator, run-job,
> resolve-error, and catalog save/toggle. **AB-05:** `onMaterialFile` now try/catches the
> upload (toast + reset the input + `uploadError` banner) and gained a thumbnail-id "Olib
> tashlash" remove control. **AB-23:** the swallowed catalog toggle failures now surface a
> danger toast. Web gate green: lint:check · format:check · typecheck · test **120** · build.
> Browser/visual + e2e locator updates for the new dialogs land with the AB-06/07/30 e2e batch.

> Progress (2026-06-19, admin-finish B1): **AB-02 Done** — dialog focus management.
> Added `composables/useFocusTrap.ts` (move focus in on open, trap Tab/Shift-Tab, Escape to
> close, return focus to the opener on close; ref-counted body-scroll lock — mirrors the proven
> `ConfirmDialog` contract that `access-management.md` mandates). Wired it into all **9**
> hand-rolled `.admin-modal` dialogs across 6 views — provision (AdminWorkshopsView),
> block-workshop (AdminWorkshopDetailView), create/edit-operator + block-operator
> (AdminPlatformUsersView), manufacturer create/edit (AdminManufacturersView), material
> create/edit + inline-manufacturer (AdminMaterialsView), job-log (AdminPlatformJobsView),
> error-detail (AdminPlatformErrorsView) — each panel got `ref`/`tabindex="-1"`/`@keydown`, and
> every scrim got `aria-hidden="true"`. Web gate green: lint:check · format:check · typecheck ·
> test **120** · build. Browser focus-order verification is deferred to an e2e a11y assertion
> (no browser here); the logic is a direct port of the gate-covered `ConfirmDialog` pattern.
> Related a11y items (AB-27 tabs, AB-28 live regions, AB-47 sr-only th) stay in B8.

## Index

| id | P | category | sev | eff | status | one-line |
|---|---|---|---|---|---|---|
| AB-01 | P1 | states-errors | high | M | Done | Route all 8 store loaders through `captureApiError` + render a dedicated permission-denied (403) state |
| AB-02 | P1 | a11y | high | M | Done | Focus-trap / focus-into / focus-return / Escape on every admin-modal dialog |
| AB-03 | P1 | security-rbac | high | M | Done | One-time-secret lifecycle: clear temp passwords on dismiss/unmount/logout; add copy + dismiss (secret modal) |
| AB-04 | P1 | ux-flow | high | M | Done | Gate privileged state-changing actions behind ConfirmDialog w/ Uzbek labels (run-job, reset-pw, resolve, activate/deactivate) |
| AB-05 | P1 | states-errors | high | S | Done | Material image-upload failure is swallowed (unhandled rejection, no feedback) |
| AB-06 | P1 | testing | high | M | Open | E2E: platform-user lifecycle (create+secret, reset, block, unblock) |
| AB-07 | P1 | testing | high | S | Open | E2E + UI guard: last-active-operator / self-block can't lock the platform out |
| AB-08 | P2 | tech-debt | med | M | Done | Extract shared `AdminErrorState`/empty/skeleton (retry + permission-denied), replace 9 hand-copied blocks |
| AB-09 | P2 | tech-debt | med | S | Open | Delete dead orphan `AdminCatalogView.vue` (660 lines, unrouted) + fix stale comment |
| AB-10 | P2 | states-errors | med | M | Done | Adopt `useToast` in admin views — success + failure signals on every mutation |
| AB-11 | P2 | i18n-copy | med | M | Open | Adopt one operator-copy policy; sweep mixed-language strings (dashboard/nav/route-meta/error copy) |
| AB-12 | P2 | i18n-copy | med | S | Open | Localize status pills (Faol/Bloklangan/Faol emas) + dot + `statusLabel` enum maps |
| AB-13 | P2 | i18n-copy | med | S | Open | Translate `useStaffLogin` English error map (decision: shared w/ workshop) |
| AB-14 | P2 | correctness-bug | med | M | Open | Dashboard concurrent loaders share one error/loading ref → race → false-"healthy" |
| AB-15 | P2 | correctness-bug | med | S | Open | Job run never surfaces `skipped`/"already running"; optimistic patch overwrites `failed`→`skipped` |
| AB-16 | P2 | correctness-bug | med | S | Open | Renaming a manufacturer leaves stale `manufacturer_name` on cached materials |
| AB-17 | P2 | spec-conformance | med | M | Open | Audit viewer: add spec'd filters (workshop/module/date/action) + pagination (silent 50-row cap) + wire/remove CSV |
| AB-18 | P2 | design-parity | med | M | Open | Platform-users: disable Block on last active operator + map error + 'Joriy' marker + operator-model banner |
| AB-19 | P2 | design-parity | med | M | Open | Workshops list: inline Block/Unblock row actions (with confirm) |
| AB-20 | P2 | design-parity | med | S | Open | Workshop detail: blocked danger banner + block reason on pill + operator-scope info banner |
| AB-21 | P2 | spec-conformance | med | S | Open | Profile sessions: per-row revoke + load-failure state + logout error handling + localize pills |
| AB-22 | P2 | design-parity | med | M | Open | Materials table/modal parity: image col, kind/status pills, dim validation, edge/kind hints |
| AB-23 | P2 | states-errors | med | S | Done | Catalog activate/deactivate failures swallowed — surface failure signal |
| AB-24 | P2 | design-parity | med | M | Open | Admin notifications: surface mark-read failures + per-kind icon + unread bg + drop raw `event_code` + poll |
| AB-25 | P2 | design-parity | med | M | Open | Error-detail modal: affected workshops/users + split context/stack + reopen + in-modal failure state |
| AB-26 | P2 | spec-conformance | med | M | Open | Error monitor: add count-threshold + time-range filters |
| AB-27 | P2 | a11y | med | S | Open | Tab strips: real `role=tab/tabpanel`, `aria-selected`, roving focus (WorkshopDetail/Profile/Audit) |
| AB-28 | P2 | a11y | med | S | Done | Live regions on load-error + action-failure surfaces; standardize skeleton `aria-live` |
| AB-29 | P2 | tech-debt | med | M | Open | Type the 7 `payload: unknown` store mutators with request DTOs |
| AB-30 | P2 | testing | med | M | Open | E2E: run-job + resolve-error operator journeys |
| AB-31 | P2 | testing | med | S | Open | Vitest: admin store `runJob` optimistic merge (find-by-name, prepend, slice-5) |
| AB-32 | P3 | correctness-bug | low | S | Open | `loadAudit` Promise.all → allSettled (partial-failure blanks both tabs) |
| AB-33 | P3 | correctness-bug | low | M | Open | Job `definition.running` disable-guard is dead (backend never sets it) — wire or drop |
| AB-34 | P3 | correctness-bug | low | S | Open | `createPlatformUser` unshift breaks server `(status, name)` sort until reload |
| AB-35 | P3 | completeness-stub | low | S | Open | Provision form hardcodes Tashkent lat/lon (dup literal) + no working-hours UI |
| AB-36 | P3 | spec-conformance | low | S | Open | Provision code field stops re-deriving from name after first auto-fill |
| AB-37 | P3 | design-parity | low | S | Open | Dashboard recent-workshops: owner login (not UUID) + Filial col + localized pill + re-run on failed-job card |
| AB-38 | P3 | design-parity | low | S | Open | Profile password tab: add 'Tasdiqlash' confirm field + strength meter |
| AB-39 | P3 | ux-flow | low | S | Open | Workshop-detail error state is a dead end — add back-link + retry |
| AB-40 | P3 | ux-flow | low | S | Open | Materials empty-state: add CTA + distinguish no-data vs filtered-to-zero |
| AB-41 | P3 | security-rbac | low | S | Open | Workshop block: second confirm + destructive button styling + "unblock won't restore sessions" note |
| AB-42 | P3 | spec-conformance | low | S | Open | Manufacturers: add the spec'd Country filter |
| AB-43 | P3 | security-rbac | low | S | Open | Error-detail renders context/stack verbatim — add render-time defense-in-depth (reveal-to-show) |
| AB-44 | P3 | performance | low | S | Open | `list_error_records` has no server-side limit — add defensive cap |
| AB-45 | P3 | performance | low | M | Open | Catalog views fetch full list + filter client-side; `CatalogFilters` server plumbing unused — wire or delete |
| AB-46 | P3 | performance | low | M | Open | Every view refetches on mount (no staleness guard); dashboard pre-pulls full catalog for a count |
| AB-47 | P3 | a11y | low | S | Open | Empty action-column `<th></th>` needs an sr-only label |
| AB-48 | P3 | responsive | low | S | Open | Provision modal stays 3-up between 620–920px — add a 2-up tablet step |
| AB-49 | P3 | responsive | low | S | Open | Admin filter-bar input is fixed 220px — make it fluid |
| AB-50 | P3 | responsive | low | S | Open | Button-dense tables hit the 680px floor → tall wrapped action rows; widen min-width |
| AB-51 | P3 | testing | low | M | Open | E2E/unit for the cross-workshop audit viewer (filter predicate) |
| AB-52 | P3 | testing | low | S | Open | Extend provisioning E2E with workshop unblock (only block is covered) |
| AB-53 | P3 | testing | low | S | Done | Bind a permission-denied regression test to the AB-01 fix |
| AB-54 | P3 | security-rbac | — | — | Won't | Backend privilege-gate audit — verified solid, nothing to fix |

---

## P1 — do first (security-adjacent, destructive-path correctness, blocking a11y)

### AB-01 · Route all 8 store loaders through `captureApiError` + render a dedicated permission-denied (403) state — `states-errors` · high · M — **Done (B3)**

**Files:** `stores/admin.ts:238/252/266/425/489/514/554` (the 7 hardcoded `*_load_failed` catches) vs `:323/346` (catalog uses `captureApiError`); every `Admin*.vue` error block.
**Why:** Only `loadManufacturers`/`loadMaterials` run errors through `captureApiError` (→ 403 becomes `permission_denied`). The other loaders — `loadWorkshops`, `loadOverview`, `loadWorkshop`, `loadPlatformUsers`, `loadJobs`, `loadErrors`, `loadAudit` — hardcode a generic `<area>_load_failed` and discard the 403. **No view renders a permission-denied branch at all** (the only one that does, `AdminCatalogView.vue:243`, is dead/unrouted — see AB-09). So an operator whose account is blocked/downgraded mid-session sees a misleading "endpoint javob bermadi / trace …" infrastructure error on every privileged screen — including the operator registry — instead of "access revoked, re-authenticate". This masks an RBAC condition as an outage. Spec: [`platform.md`](../docs/ref/features/platform.md) "error on every page"; [`access-patterns.md`](../docs/access-patterns.md) platform-operator scope.
**Fix:** Route all 8 loaders through `captureApiError(err, '<area>_load_failed')` (one-line each), capturing `code` + `traceId`. Render a distinct `permission_denied`/`password_reset_required` state (e.g. "Kirish bekor qilingan — qayta kiring") ahead of the generic error block — ideally via the shared `AdminErrorState` (AB-08). Ship the regression test (AB-53) with it.

### AB-02 · Focus-trap / focus-into / focus-return / Escape on every admin-modal dialog — `a11y` · high · M — **Done (B1)**

**Files:** every hand-rolled `<section class="admin-modal" role="dialog" aria-modal="true">` — `AdminWorkshopsView.vue:219`, `AdminPlatformUsersView.vue:270/334`, `AdminWorkshopDetailView.vue:250`, `AdminManufacturersView.vue:197`, `AdminMaterialsView.vue:331/451`, `AdminPlatformJobsView.vue:145`, `AdminPlatformErrorsView.vue:168`. Reference: `components/ConfirmDialog.vue:40-103` (already implements the contract).
**Why:** Every admin dialog is hand-rolled with **no focus management**: focus stays on the trigger behind the scrim on open, Tab/Shift-Tab walks out to the table behind, focus is never restored to the trigger on close, and Escape isn't handled (only a scrim `@click` + icon button). This is a direct, explicit violation of [`access-management.md`](../docs/ref/features/access-management.md) ("All provisioning, create-user, reset-password, and block dialogs move focus into the dialog, trap focus while open, and return focus to the trigger on close"). No admin view uses the shared `ConfirmDialog` (which already does this correctly).
**Fix:** Extract the trap/return/Escape logic from `ConfirmDialog.vue` into a shared `composables/useFocusTrap(panelRef, open)` and wire it into every admin-modal; on open focus the first field (or close button for read-only log/detail dialogs), on close restore focus to the opener, add an Escape handler, mark the scrim `aria-hidden="true"`. Admin-only views → no client/workshop regression. (Folds in AB-47-adjacent scrim a11y.)

### AB-03 · One-time-secret lifecycle: clear temp passwords on dismiss/unmount/logout; add copy + dismiss — `security-rbac` · high · M — **Done (B2)**

**Files:** `stores/admin.ts:211` (`lastProvision`), `:215` (`lastPlatformUserSecret`) — assigned in `provision`/`createPlatformUser`/`resetPlatformUserPassword`, **never cleared anywhere**; `AdminWorkshopsView.vue:336-363`, `AdminPlatformUsersView.vue:245-268` (inline "Share once" / "One-time secret" cards). Prototype: `assets/app.js:504` `showSecret()`, `workshops.html:131`, `platform-users.html:163`.
**Why:** The admin store is a Pinia singleton living for the whole SPA session; `lastProvision`/`lastPlatformUserSecret` are set but never nulled (grep confirms only the assignments), so the cleartext temp password keeps re-rendering in the "Share once" card every time the operator revisits `/admin/workshops` or `/admin/platform/users`, and **survives `auth.clear()`/logout** (logout never touches the admin store). The UI claims "shown once" but it persists until a hard reload. There is also **no copy button** (spec mandates one) and **no dismiss** — operators must hand-select the single most consequential value in provisioning (a mis-copied owner password locks the new owner out). The prototype uses a focus-trapped secret modal with per-row "Nusxa" + "Hammasini nusxalash" + "Yopdim · saqladim".
**Fix:** Build a shared `AdminSecretModal` (warning banner, per-row copy via `navigator.clipboard`, copy-all, "Yopdim · saqladim" close) triggered from the two store refs; add `clearLastProvision()`/`clearLastPlatformUserSecret()` and call them on modal close, on view unmount, **and in the auth `clear()`/logout path**. At minimum, never let the secret outlive the session.

### AB-04 · Gate privileged state-changing actions behind ConfirmDialog with Uzbek labels — `ux-flow` · high · M — **Done (B2)**

**Files:** `AdminPlatformJobsView.vue:116` (run/retry), `AdminPlatformUsersView.vue:202` (reset-password), `AdminPlatformErrorsView.vue:202` (resolve), `AdminManufacturersView.vue:176` + `AdminMaterialsView.vue:313` (activate/deactivate). Prototype: `jobs.html:79-81`, `platform-users.html:171-186`, `errors.html:129`, `manufacturers.html:127-129`.
**Why:** Five consequential operator actions fire immediately on click with **no confirmation**, violating [`platform.md`](../docs/ref/features/platform.md) "confirmation on every state-changing action" and the prototype's `confirmAction(...)` gating. Worst cases: **reset-password** silently invalidates the operator's sessions in one click, **run-job** triggers an off-schedule background job, and **activate/deactivate** mutates the client-facing catalog with no "names the consequence" copy the spec quotes verbatim ("Existing branch selections of this material will be hidden from clients."). No admin view currently imports `ConfirmDialog`.
**Fix:** Wrap each in the shared `ConfirmDialog` with **explicit Uzbek `confirm`/`dismiss`/`busy` labels** (the dialog defaults are English) matching the prototype copy. Reset-password → confirm then present the new temp password via AB-03's secret modal. (Activate/deactivate failure handling is AB-23; error-resolve reopen + affected context is AB-25.)

### AB-05 · Material image-upload failure is swallowed — unhandled rejection, no feedback — `states-errors` · high · S — **Done (B2)**

**Files:** `AdminMaterialsView.vue:151-156` (`onMaterialFile`), `:429` (only `files.uploading` shown), `stores/files.ts:31-41` (`upload` sets `error='file_upload_failed'` and **re-throws**).
**Why:** `onMaterialFile` does `const uploaded = await files.upload(target.files[0])` with **no try/catch**. `files.upload` re-throws on any failure (403, oversize, network), so the `await` rejects → unhandled promise rejection; the spinner vanishes, `form.imageFileId` stays unset, and the operator gets **zero feedback** while the Save button still looks ready. The view never renders `files.error`. Spec: [`platform.md`](../docs/ref/features/platform.md) "Image upload" + "error on every page".
**Fix:** Wrap the upload in try/catch, reset the file input, surface a visible upload error (render `files.error` or a local `uploadError` beside the field); add a thumbnail preview + "remove image" control (clears `form.imageFileId`); optionally a success toast (AB-10).

### AB-06 · E2E: platform-user lifecycle (create+secret, reset, block, unblock) — `testing` · high · M

**Files:** `e2e/tests/access-and-provisioning.spec.ts` (extend), `AdminPlatformUsersView.vue:79/98/112/245`.
**Why:** The platform-user (operator) registry is the most privileged, most dangerous admin surface — create operator, reset password, block, unblock, one-time-secret reveal — and **no E2E exercises any of it through the UI**. The existing admin E2E only covers workshop provisioning + block; backend `test_platform_api.py` covers the API contract but not the UI wiring (right store action, `lastPlatformUserSecret` render, self-block hidden, error surfacing). Per [`testing-practices`], this user journey belongs at E2E.
**Fix:** Add a journey to `access-and-provisioning.spec.ts` (reuse the seed helper): log in at `/admin`, open platform-users, create an operator → assert the temp-password secret panel renders once; reset that operator's password → assert a new secret renders; block then unblock → assert the status transitions. Ship this **with** the AB-03/AB-04/AB-18 changes (update locators in lockstep).

### AB-07 · E2E + UI guard: last-active-operator / self-block can't lock the platform out — `testing` · high · S

**Files:** `AdminPlatformUsersView.vue:214` (self-block disable), `:106` (generic block-fail), `backend/.../service.py:474/489/766` (`cannot_block_self`, `_ensure_another_active_platform_user`).
**Why:** This is the single most dangerous admin path — locking every operator out of the platform. The backend guards both cases and pytest covers them, but the **UI only reflects self-block** (`AdminPlatformUsersView.vue:214` disables the button for `auth.me.principal_id`); the last-active-operator case has an *enabled* Block button that opens the modal, takes a mandatory reason, submits, and 400s into the generic "Operator amali bajarilmadi." toast — even though the modal copy at `:357` asserts "Oxirgi faol operator bloklanmaydi". No regression test pins the UI behaviour.
**Fix:** (UI part lives in AB-18 — disable Block when `activeOperatorCount <= 1` + map `last_platform_operator`.) Here: add a focused E2E asserting the current-operator Block control is disabled, and ship a UI assertion that a last-operator block attempt renders the dedicated message — **with** the AB-18 guard fix.

## P2 — important

### AB-08 · Extract shared `AdminErrorState` / empty / skeleton (retry + permission-denied) — `tech-debt` · med · M — **Done (B3)**

**Files:** the hand-copied 3-block scaffold across `AdminAuditView.vue:79`, `AdminMaterialsView.vue:245`, `AdminManufacturersView.vue:119`, `AdminPlatformUsersView.vue:147`, `AdminPlatformJobsView.vue:49`, `AdminPlatformErrorsView.vue:95`, `AdminNotificationsView.vue:66`, `AdminWorkshopDetailView.vue:62`, `AdminDashboardView.vue:60`. Reference: `components/ClientErrorState.vue` (the client's solution, CB-22).
**Why:** The loading-skeleton / `admin-error` / `admin-empty` blocks are duplicated verbatim ~9×. Two concrete regressions follow: (a) every error block hardcodes "<X> endpoint javob bermadi", so the copy can't be fixed in one place (AB-11), and (b) unlike `ClientErrorState`, the admin error blocks have **no retry button** — a failed load strands the operator. The client already solved exactly this.
**Fix:** Add `AdminErrorState` (title + traceId + `retry` emit + a `permission_denied` variant) and small `AdminEmpty`/`AdminSkeleton` helpers; replace the inline blocks. This becomes the single home for the AB-01 no-access state and the missing retry.

### AB-09 · Delete dead orphan `AdminCatalogView.vue` + fix the stale comment — `tech-debt` · med · S

**Files:** `web/src/shared/views/AdminCatalogView.vue` (660 lines, ~23.5 KB), `stores/admin.ts:321-322` (the only reference — a comment).
**Why:** `AdminCatalogView.vue` is never imported or routed (`routes.ts` maps `/admin/catalog/{manufacturers,materials}` to `AdminManufacturersView`/`AdminMaterialsView`; `/admin/catalog` redirects to materials). A repo-wide grep finds exactly one reference: a comment at `admin.ts:321` ("so AdminCatalogView's no-access state can trigger"). The dead view *does* contain a real `permission_denied` state (`AdminCatalogView.vue:243`) — but it's unreachable, and the comment misleads readers about where that handling lives (it lives nowhere live — see AB-01).
**Fix:** Delete the file and update the `admin.ts` comment to point at the live `AdminManufacturersView`/`AdminMaterialsView` permission-denied handling (added in AB-01/AB-08). Verify no dynamic-import string references it.

### AB-10 · Adopt `useToast` in admin views — success + failure signals on every mutation — `states-errors` · med · M — **Done (B2)**

**Files:** `components/AppShell.vue:526` (`ToastHost` already mounted), `components/NotificationsMenu.vue:131-139` (already uses `toast.success`/`toast.danger`); admin views push nothing — `AdminWorkshopsView.vue:87-121`, `AdminWorkshopDetailView.vue:24-50`, `AdminPlatformUsersView.vue:54-122`, `AdminPlatformErrorsView.vue:58-69`.
**Why:** `ToastHost` is mounted and the shared notifications menu uses it, but **no `Admin*.vue` page view imports `useToast`** (grep = 0 hits). Provision, block/unblock, reset-password, save-operator, run-job, resolve-error all complete **silently** — the only feedback is inline error banners on *failure*. For destructive/irreversible actions especially, the operator gets no positive confirmation a mutation took effect; they must infer it from a row badge or the secret card appearing. Spec: [`platform.md`](../docs/ref/features/platform.md) "result badges pair colour with text".
**Fix:** Push `toast.success` on each completed mutation and `toast.danger` on failure (mirroring `NotificationsMenu`). Keep a shared helper but admin-scoped so other SPAs are untouched.

### AB-11 · Adopt one operator-copy policy; sweep mixed-language strings — `i18n-copy` · med · M

**Files:** `AdminDashboardView.vue:113/116/176/183/248`, `roleConfig.ts:145/152` (nav) + `:138` (dropdown), `apps/admin/routes.ts:42/60` (meta titles), and the `<X> endpoint javob bermadi` copy in `AdminWorkshopsView.vue:168`, `AdminWorkshopDetailView.vue:65`, `AdminManufacturersView.vue:128`, `AdminMaterialsView.vue:254`, `AdminPlatformJobsView.vue:58`, `AdminPlatformErrorsView.vue:104`, `AdminPlatformUsersView.vue:156`, `AdminAuditView.vue:88`, `AdminNotificationsView.vue:74`.
**Why:** The operator surface has no coherent copy policy. Login (`AdminLoginView`) and Profile are clean Uzbek-latin, but dashboards/nav/empties mix raw English connective words — "Failed ish", "Background ish", "Manufacturerlar" (English root + Uzbek plural), "Registry/Scheduler/Monitor/Inbox/Catalog endpoint javob bermadi" (leaks internal route nicknames), bare "failed"/"monitor". No `docs/` clause forces English on admin, so this is unintentional drift ported from the unfinished prototype. The intended policy (client SPA, admin login, workshop nav in the *same* `roleConfig.ts` which is fully Uzbek): **Uzbek-latin prose; English kept only for genuine domain/status identifiers and `trace_id`.**
**Fix:** Adopt that policy explicitly, then sweep: "Background ish" → "Fon vazifalar", "Failed ish[ yo'q]" → "Muvaffaqiyatsiz vazifa[lar][ yo'q]", "Manufacturerlar" → "Ishlab chiqaruvchilar" (nav + `routes.ts` meta in lockstep), and replace every "<X> endpoint javob bermadi" with one generic Uzbek line (drop the endpoint nicknames) — ideally centralized in `AdminErrorState` (AB-08). Update the prototype admin HTML copy in the same pass so they don't re-diverge. (Status-pill localization is AB-12; login errors AB-13.)

### AB-12 · Localize status pills (Faol/Bloklangan/Faol emas) + dot + `statusLabel` enum maps — `i18n-copy` · med · S

**Files:** `app/adminUi.ts:79` (`statusLabel` returns "no run" + underscore-replace), the raw `{{ status }}` renders at `AdminWorkshopsView.vue:201`, `AdminWorkshopDetailView.vue:82`, `AdminManufacturersView.vue:162`, `AdminMaterialsView.vue:300`, `AdminPlatformUsersView.vue:189`, `AdminDashboardView.vue:163`. Prototype: `workshops.html:111`, `manufacturers.html:120`, `platform-users.html:106`.
**Why:** Every admin status pill renders the raw enum — `active`/`blocked`/`inactive`/`ok`/`failed`/`running`/`skipped`/`open`/`resolved` — and `statusLabel` returns the English free-text "no run" for null. The prototype consistently shows localized labels (Faol / Bloklangan / Faol emas) with a leading status **dot**. This is the most pervasive parity + i18n drift in the SPA. (`materialKindLabel` already maps `panel`→Panel/`edge`→Krom — status deserves the same.)
**Fix:** Add `workshopStatusLabel`/`materialStatusLabel`/`platformUserStatusLabel`/`jobStatusLabel`/`errorStatusLabel` maps in `adminUi.ts`, route the raw renders through them, add the leading dot (the prototype's `.pill .pd`), and change the "no run" fallback to "ishga tushmagan". If the team decides enum values stay English for operators, document that and only fix "no run".

### AB-13 · Translate `useStaffLogin` English error map (decision: shared with workshop) — `i18n-copy` · med · S

**Files:** `composables/useStaffLogin.ts:8-13` (English `STAFF_ERROR_TEXT`), `:34` ("Sign-in failed." fallback), rendered at `AdminLoginView.vue:48`.
**Why:** `useStaffLogin` hardcodes an all-English error map ("Credentials do not match an active account.", "Account is locked. Try again later.", "Account is blocked.", "API is not reachable.") rendered verbatim on the otherwise fully-Uzbek admin login. **Cross-cutting:** the composable is shared by both the admin *and* workshop login views — workshop is a separate owner.
**Fix (decision):** Translate to Uzbek-latin to match the admin login (the workshop login is also Uzbek per `roleConfig.ts`). Because it's shared, confirm with the workshop owner; if workshop must differ, parameterize the message map by `config.role` so admin gets Uzbek without touching workshop copy.

### AB-14 · Dashboard concurrent loaders share one error/loading ref → race → false-"healthy" — `correctness-bug` · med · M

**Files:** `AdminDashboardView.vue:20-23/25-35`, `stores/admin.ts:221-227` (single `loading`/`error`/`traceId` triple), `:245-257/482-519`.
**Why:** `onMounted` fires a 7-way `Promise.all`. `loadOverview`/`loadWorkshops`/`loadWorkshop` all mutate the **same** `error`/`loading`/`traceId`; `loadJobs`/`loadErrors`/`loadPlatformUsers` all mutate the **same** `opsError`/`opsLoading`/`opsTraceId`. Running concurrently makes the flags last-writer-wins: each one's `error=null`/`loading=false` clobbers its siblings'. The view gates `isLoading`/`hasError` on `!overview.value`, so a *successful overview hides any other loader's failure* — if jobs or errors 403/fail, the dashboard renders normally and those sections show their empty states ("Failed ish yo'q", "Xatolik yozilmagan") as if all-clear. That's a **false "healthy" signal on a health dashboard**, and a surfaced `traceId` may belong to a different request than the failure.
**Fix:** Give the concurrently-fetched endpoints independent loading/error slots (per-area triples, or have each loader return a result object aggregated in the view via `Promise.allSettled`); at minimum a non-fatal banner when any tile's loader failed so empty ≠ healthy. (Tech-debt framing of the shared-triple is the same root; fix once.)

### AB-15 · Job run never surfaces `skipped`/"already running"; optimistic patch overwrites `failed`→`skipped` — `correctness-bug` · med · S

**Files:** `AdminPlatformJobsView.vue:18-28`, `stores/admin.ts:496-505`, `backend/.../scheduler.py:42-49`.
**Why:** The backend skip guard is an in-process `asyncio.Lock`: when a job is already running, `run_platform_job` returns a `JobRun` with `status='skipped'` / `brief_log='already running'` **without raising** and **without updating** `JobDefinition.last_run_at/last_result`. The view's `runJob` awaits and never inspects `run.status`, so on a skip the button flashes "Ishlamoqda" then returns to normal with **zero feedback** — the operator believes it ran. Worse, the store unconditionally writes `row.definition.last_result = run.status` (`admin.ts:500-501`): on a skip it writes a `skipped` + a `last_run_at` the server never persisted, and if the job was previously `failed`, this **silently drops it from the Dashboard failed-jobs KPI** (`AdminDashboardView.vue:13` filters `last_result==='failed'`) until the next `loadJobs` reverts it.
**Fix:** Branch on `run.status`: on `skipped` show a distinct "Job allaqachon ishlamoqda — o'tkazib yuborildi" notice and **don't** patch the definition; only patch on terminal `ok`/`failed`. Simplest robust option: stop optimistically mutating the definition and re-`loadJobs()` after `runJob` resolves so list and server stay consistent. (Dead `definition.running` flag is AB-33.)

### AB-16 · Renaming a manufacturer leaves stale `manufacturer_name` on cached materials — `correctness-bug` · med · S

**Files:** `stores/admin.ts:364-372` (`updateManufacturer`→`patchManufacturer`), `:410-412` (`patchManufacturer` only touches the manufacturers array), `AdminMaterialsView.vue:288` (renders denormalized `manufacturer_name`).
**Why:** `Material` carries a denormalized `manufacturer_name` (`admin.ts:69`). `patchManufacturer` only updates the `manufacturers` array — it never refreshes `materials[].manufacturer_name`. After an operator renames a manufacturer, the Materials table and the Materials manufacturer filter keep showing the **old** name (the store is a session-long singleton, so it persists across navigation) until a full materials reload.
**Fix:** In `patchManufacturer`, also map `materials.value` and refresh `manufacturer_name` for rows whose `manufacturer_id === updated.id`; or have `updateManufacturer` trigger `loadMaterials()` when materials are already loaded.

### AB-17 · Audit viewer: spec'd filters + pagination + wire/remove CSV — `spec-conformance` · med · M

**Files:** `AdminAuditView.vue:52-58` (only free-text search + a no-op CSV button), `:37`/`stores/admin.ts:547-549` (`loadAudit` sends no `limit`), `backend/.../routes.py:284-291/304-311` (`limit` default 50, `le=200`). Spec: [`workshop.md`](../docs/ref/features/workshop.md) (owns the cross-workshop audit viewer). Prototype: `audit.html:29-34/117-131`.
**Why:** The cross-workshop superadmin audit viewer offers only a single text box (+ a dead CSV button, AB-09-style stub at `:57`). It's missing the spec'd filter set — most importantly the **workshop filter**, the defining affordance of a cross-workshop viewer — plus module / date-range / action-family (actions tab) and entity / from→to (status tab). The store fetches both feeds **unlimited-but-defaulted-to-50** with no pagination, no "load more", and no truncation hint, so older audit history is permanently unreachable from the UI — an append-only log you can't page through is functionally incomplete. The status tab also shows raw `from → to` instead of the prototype's localized transition + order link.
**Fix:** Add Workshop + Module + date-range filters (and entity/from→to on the status tab); plumb an explicit `limit` (and `before`/offset) through `loadAudit` with a "Load older" control + "showing latest N" hint; map status codes through a shared label helper; either implement the CSV export (client-side serialization of the loaded rows via the existing `downloadBlob`) with feedback, or remove the button.

### AB-18 · Platform-users: last-operator Block guard + error mapping + 'Joriy' marker + operator-model banner — `design-parity` · med · M

**Files:** `AdminPlatformUsersView.vue:127/180/210-219/357`, `:97-110` (`confirmBlock` catch). Prototype: `platform-users.html:29-32/90-118`.
**Why:** Three parity/safety gaps vs the prototype: (1) no info banner explaining the no-permission-model rule + "can't block yourself or the last active operator"; (2) no "Joriy" marker on the signed-in operator's row (only a disabled self-block button); (3) the **last-active-operator Block is not disabled** — the UI guards only self-block and relies entirely on the backend 400, surfacing the generic "Operator amali bajarilmadi." even though the modal copy promises otherwise (see AB-07). The prototype disables it with the reason "Kamida bitta faol operator qolishi shart".
**Fix:** Add the info banner (prototype copy); render a "Joriy" pill where `user.id === auth.me.principal_id`; compute `activeOperatorCount` and disable Block (with an explanatory label/title) when `status==='active'` and only one active operator remains; map `last_platform_operator` to a specific message in `confirmBlock`'s catch. Ship the AB-07 E2E with it; update e2e locators.

### AB-19 · Workshops list: inline Block/Unblock row actions (with confirm) — `design-parity` · med · M

**Files:** `AdminWorkshopsView.vue:205-212` (row only has a "Tafsilotlar" link). Prototype: `workshops.html:112-122`.
**Why:** The prototype gives each workshops-table row a "⋯" menu with "Tafsilotlar" plus a contextual Block/Unblock that fires a `confirmAction` dialog carrying the full cascade-consequence copy. The Vue row only links to the detail view, so the one-click incident action the design provides is lost — block/unblock is reachable only after navigating in.
**Fix:** Add a row action menu (or compact buttons) with Block (active) / Unblock (blocked) opening the same reason-required block modal / unblock confirm already in `AdminWorkshopDetailView`. Reuse `admin.blockWorkshop`/`unblockWorkshop`; route through the AB-04 ConfirmDialog + AB-02 focus-trap.

### AB-20 · Workshop detail: blocked danger banner + block reason on pill + operator-scope banner — `design-parity` · med · S

**Files:** `AdminWorkshopDetailView.vue:74/139`. Prototype: `workshop-detail.html:63/74/86`.
**Why:** When a workshop is blocked the prototype shows (a) the block reason inline in the status pill, (b) a full-width danger banner under the header ("buyurtmalar muzlatilgan, xodimlar kira olmaydi, blokdan chiqarilganda sessiyalar tiklanmaydi"), and (c) a Profile-tab info banner explaining operator scope (only provision/block/unblock, no edit). The Vue detail view renders **none** — just a bare pill with raw English status — so a blocked workshop reads identically to an active one and the operator-scope guidance is lost.
**Fix:** Add a `v-if="status==='blocked'"` danger banner with the prototype copy, surface the block reason near the status pill (needs the reason on the detail response — confirm `PlatformWorkshopDetail` carries it; flag a small backend add if not), and add the read-only operator-scope info banner to the Profile tab.

### AB-21 · Profile sessions: per-row revoke + load-failure state + logout error handling + localize pills — `spec-conformance` · med · S

**Files:** `AdminProfileView.vue:29-37` (`deviceLabel` fallback "Browser"; `loadSessions` no try/catch), `:55-65` (logout handlers no try/catch), `:186-206` (sessions list; pills render "current"/"active"). Store: `auth.ts` `revokeSession(id)` already exists (CB-114). Spec: [`access-management.md`](../docs/ref/features/access-management.md) "Sessions list (current marker, 'revoke' per row, 'log out everywhere')".
**Why:** Three gaps: (1) **no per-row "revoke"** though `auth.revokeSession` exists and the workshop profile uses it — spec requires it; (2) `loadSessions` has no try/catch → a failed load falls through to the empty state "Sessiya topilmadi", falsely telling the operator they have no sessions, and `logoutCurrent`/`logoutEverywhere` set `loggingOut=true` then await with no catch → on rejection the button stays stuck disabled with no error; (3) the session pills render English "current"/"active" and `deviceLabel` falls back to "Browser" (the client fixed exactly this in CB-81 → "joriy"/"faol"/"Brauzer").
**Fix:** Add a per-row "Yopish" revoke (hidden on the current session) calling `auth.revokeSession`; wrap `loadSessions` in try/catch with a distinct error state; wrap logout handlers, reset `loggingOut`, surface failure (or force-clear + navigate); localize the pills + `deviceLabel`.

### AB-22 · Materials table/modal parity: image col, kind/status pills, dimension validation, edge/kind hints — `design-parity` · med · M

**Files:** `AdminMaterialsView.vue:268-281` (no image column), `:289` (kind = plain text), `:300` (raw status), `:401-419` (modal lacks validations). Spec: [`platform.md`](../docs/ref/features/platform.md):39. Prototype: `materials.html:91/95/154/161`.
**Why:** vs spec + prototype: (1) the materials table has **no image column** though `Material.image_file_id` exists and the form uploads one (spec lists image as the first column); (2) `Tur` is plain text, the prototype uses a colored pill ("Panel" / "Krom lentasi"); (3) the status cell shows raw English (AB-12); (4) the create/edit modal omits the prototype's **panel length≥width inline validation**, the **edge-banding info banner**, and the **kind-locked-on-edit hint**. The prototype's branch-usage ("Ustaxonalar") column + "Qaysi filiallarda?" action need a per-material branch count the platform read model may not expose — **data dependency**, defer unless `catalog-inventory.md` justifies the backend surface.
**Fix:** Add a leading image cell (thumbnail via files store / `image_file_id`, placeholder when unset); render kind as a colored pill + status via the AB-12 label pill; add the length≥width validation + edge info banner + kind-locked hint to the modal. Branch-usage column only if/when the backend exposes the count (decision vs `catalog-inventory.md`).

### AB-23 · Catalog activate/deactivate failures swallowed — surface a failure signal — `states-errors` · med · S — **Done (B2)**

**Files:** `AdminManufacturersView.vue:80-87`, `AdminMaterialsView.vue:207-214` (`setStatus` is try/finally, **no catch**).
**Why:** Both `setStatus` handlers can reject (403, conflict) but only `finally`-clear `actionId` — there's no error ref, banner, or toast. The operator clicks "Faollashtirish"/"Faol emas qilish", the row simply doesn't change, and nothing explains why. (The missing *confirm* is AB-04; this is the missing *failure* signal.)
**Fix:** Add a catch that surfaces a visible action error (banner or AB-10 `toast.danger`) for both handlers.

### AB-24 · Admin notifications: surface mark-read failures + per-kind icon + unread bg + drop raw `event_code` + poll — `design-parity` · med · M

**Files:** `AdminNotificationsView.vue:31-38` (`markRead` no catch), `:56-57` (`markAllRead` inline, no result handling), `:82-113` (generic pill, raw `event_code` subtext at `:99`, no kind icon, no unread bg, no poll). Store: `notifications.ts:94/109` (sets `actionError`); `NotificationsMenu.vue:131-139` checks it; `adminUi.ts:132-138` (`adminNotificationTitle` embeds `event_code`). Prototype: `notifications.html:15-23/78-86`.
**Why:** The operator inbox is the *only* v1 channel for job-failure + error-spike alerts ([`notifications.md`](../docs/ref/features/notifications.md)), yet: (1) `markRead`/`markAllRead` failures are **silent** on the full page (the store sets `actionError` and the *menu* toasts it, but the page never reads it); (2) no per-kind icon and **no unread row background** — failed-job vs error-spike alerts are visually indistinguishable, exactly the distinction the inbox exists for; (3) the raw `event_code` is shown as subtext (`:99`) and embedded in the title helper (the client dropped raw codes in CB-126); (4) **no unread polling** (the client polls ~45s, CB-10), so a new alert leaves a stale badge.
**Fix:** After `markRead`/`markAllRead`, check `notifications.actionError` → `toast.danger`/`toast.success` (match `NotificationsMenu`); add a leading kind-icon tile colored by event kind + an unread row treatment; drop the raw `event_code` subtext (use the localized title only); add a visibility-gated unread poll.

### AB-25 · Error-detail modal: affected workshops/users + split context/stack + reopen + in-modal failure state — `design-parity` · med · M

**Files:** `AdminPlatformErrorsView.vue:43/188/219-240` (raw JSON `context`; no affected rows; perpetual skeleton on load failure; resolve is one-way), `:48-56` (`openDetail` sets `actionError` outside the modal). Store: `admin.ts:521-525` (`loadErrorDetail` no try/catch). Spec: [`platform.md`](../docs/ref/features/platform.md):120-122. Prototype: `errors.html:48-52/143-148`.
**Why:** The detail modal dumps `occurrence.context` as raw `JSON.stringify` and never renders the **affected workshops / users** the spec requires (the `ErrorOccurrence` carries `workshop_id`/`user_id`), loses the prototype's "— tegishli emas (tenant-attributable emas)" framing, and has **no in-modal failure state** — if `loadErrorDetail` fails, `selectedDetail` stays null and the body shows a **perpetual skeleton** with the error banner hidden behind the scrim. Resolve is also one-way (no reopen, though backend supports `open`).
**Fix:** Render labeled "Affected workshops"/"Affected user" rows (with the "tegishli emas" fallback) from the occurrences; split context vs stack into two labeled sections; track a `detailError` and render an in-modal error + retry instead of an endless skeleton; add a re-open affordance for resolved records (verify/add a backend reopen use-case — decision). Confirm field availability in `platform/schemas.py` before wiring (data dependency).

### AB-26 · Error monitor: add count-threshold + time-range filters — `spec-conformance` · med · M

**Files:** `AdminPlatformErrorsView.vue:86-93` (only search + status + module). Spec: [`platform.md`](../docs/ref/features/platform.md):121-122 ("Filters: module, code, time range, count threshold"). Prototype: `errors.html:28-32` (threshold select).
**Why:** Spec requires four filters; the view has search, status, and module. The **count-threshold** filter (prototype's "24 soat ≥ 3 / ≥ 10") and a **time-range** filter are both missing — the operator can't isolate spiking codes, the monitor's core job.
**Fix:** Add a count-threshold dropdown filtering on `count_24h` (≥3 / ≥10, matching the prototype) and a time-range control; consider a dedicated code filter for parity (currently folded into the text query).

### AB-27 · Tab strips: real `role=tab/tabpanel`, `aria-selected`, roving focus — `a11y` · med · S

**Files:** `AdminWorkshopDetailView.vue:112`, `AdminProfileView.vue:97`, `AdminAuditView.vue:60`.
**Why:** Each tab strip declares `role="tablist"` on the container but the buttons are plain `<button class="admin-tab">` — no `role="tab"`, no `aria-selected`, no `aria-controls`, and the revealed panels have no `role="tabpanel"`/`aria-labelledby`. A screen reader announces a tablist containing no tabs; the active tab is conveyed by colour only; arrow-key roving is absent.
**Fix:** Add `role="tab"` + `:aria-selected` + `:id`/`:aria-controls` to each tab button and `role="tabpanel"`/`:aria-labelledby` to each panel; implement roving tabindex + arrow-key navigation per the WAI-ARIA tabs pattern. Extract a small `AdminTabs` helper to apply identically across the three views.

### AB-28 · Live regions on load-error + action-failure surfaces; standardize skeleton `aria-live` — `a11y` · med · S — **Done (B3)**

**Files:** the `admin-error` blocks (`AdminWorkshopsView.vue:165`, `AdminPlatformUsersView.vue:153`, `AdminPlatformErrorsView.vue:101`, `AdminPlatformJobsView.vue:55`, `AdminWorkshopDetailView.vue:62`) and the action-failure `<p>` notices (`AdminPlatformUsersView.vue:238`, `AdminPlatformErrorsView.vue:161`, `AdminPlatformJobsView.vue:138`, `AdminWorkshopDetailView.vue:105`); inconsistent skeleton `aria-live` (`Workshops:159`/`Dashboard:52` have it; `PlatformUsers:147`/`PlatformErrors:95`/`PlatformJobs:49`/`Manufacturers:119`/`Materials:245` don't).
**Why:** Error states swap in with no live-region announcement — a screen-reader operator who triggers a block/reset/run and gets a silent failure receives no aural signal. (Success/info already go through `ToastHost`, a correct `aria-live="polite"` region.)
**Fix:** Add `role="alert"` to the action-failure notices and `role="status"`/`aria-live="polite"` to the load-error sections; standardize `aria-live="polite"` on all loading skeletons. Routing failures through the AB-10 toast channel (already a live region) is an acceptable alternative.

### AB-29 · Type the 7 `payload: unknown` store mutators with request DTOs — `tech-debt` · med · M

**Files:** `stores/admin.ts:273` (`provision`), `:354` (`createManufacturer`), `:364` (`updateManufacturer`), `:384` (`createMaterial`), `:390` (`updateMaterial`), `:432` (`createPlatformUser`), `:442` (`updatePlatformUser`).
**Why:** Seven mutating actions accept `payload: unknown`, defeating type-checking exactly on the privileged write paths (provisioning, catalog create/edit, operator create/edit). A renamed/missing field in a view form isn't caught at compile time and becomes a silent 422 at runtime. The store already has rich *response* interfaces but no *request* ones.
**Fix:** Define request DTOs (`ProvisionWorkshopRequest`, `ManufacturerCreate/Update`, `MaterialCreate/Update`, `PlatformUserCreate/Update`) in `admin.ts` and type each `payload`; adjust the view forms to satisfy them.

### AB-30 · E2E: run-job + resolve-error operator journeys — `testing` · med · M

**Files:** new `e2e/tests/platform-ops.spec.ts`; `AdminPlatformJobsView.vue`, `AdminPlatformErrorsView.vue:58`, `stores/admin.ts:496/527`.
**Why:** Two operator journeys have zero UI test: triggering a background job run (non-trivial optimistic merge — AB-15/AB-31) and resolving an error record (mutates both list and `errorDetail`). The backend already-running guard is covered by `test_scheduler.py`, but the UI flow (trigger → new run row → `skipped` handling; resolve → row flips → button disables) is untested. Per [`testing-practices`], these journeys belong at E2E.
**Fix:** Add `platform-ops.spec.ts`: admin opens jobs, triggers a seeded job, asserts the run appears; opens errors (seed an `ErrorRecord`), resolves it, asserts the row flips to resolved and the button disables. Ship with the AB-15 fix so the `skipped` assertion is meaningful.

### AB-31 · Vitest: admin store `runJob` optimistic merge — `testing` · med · S

**Files:** `stores/admin.ts:496-505`; pattern: `stores/__tests__/notifications.spec.ts`.
**Why:** `runJob` is the one store action with genuine pure-transform logic worth a unit (find row by `definition.name`, write `last_result`, prepend to `recent_runs` capped at `slice(0,5)`). Real bug modes exist: a name mismatch silently drops the update (the `if (row)` early-out), and the slice boundary is off-by-one-prone. There's no admin store unit test yet (the `patch*` helpers are trivial map-replace and don't warrant units). Per [`testing-practices`], pure store logic with branches is the right place for a unit.
**Fix:** Add `stores/__tests__/admin.spec.ts` (mock the api client à la `notifications.spec.ts`): seed jobs with a 5-run history, call `runJob`, assert the matching row gets the run prepended + capped at 5, and a run for an unknown name is a no-op. Pair with the AB-15 fix (test the corrected `skipped` behaviour).

## P3 — nice-to-have / polish

### AB-32 · `loadAudit` Promise.all → allSettled (partial failure blanks both tabs) — `correctness-bug` · low · S

**Files:** `stores/admin.ts:547-552`, `AdminAuditView.vue:85-91`.
**Why:** `loadAudit` does `Promise.all` of `/audit/actions` + `/audit/status-changes`. If only one feed fails, the whole view drops to the error state (the good feed is discarded), and on success both lists are replaced — so a later partial failure on "Yangilash" blanks both tabs. No indication which feed failed.
**Fix:** `Promise.allSettled`, assign each list independently, surface an error only for the feed(s) that actually failed (or keep the previously loaded data on partial failure).

### AB-33 · Job `definition.running` disable-guard is dead — wire or drop — `correctness-bug` · low · M

**Files:** `AdminPlatformJobsView.vue:119` (`runningJob === name || job.definition.running`), `backend/.../models.py:23` (`running` exists, default False), `scheduler.py:39-75` (the lock never writes `running`).
**Why:** The Run button's `job.definition.running` half is always false — the scheduler uses an `asyncio.Lock` and never sets `definition.running = True/False`. So the cross-operator/cross-tab guard is dead; only the local `runningJob` ref disables the current operator's own button. A second operator can still fire a run the server records as `skipped` (AB-15).
**Fix:** Either (a) make the backend set `definition.running` around the lock (clear in `finally`) so the existing UI guard becomes meaningful cross-session, or (b) drop the dead `job.definition.running` reference (and the type field) so the UI stops implying a guarantee that doesn't exist. (Backend change = decision.)

### AB-34 · `createPlatformUser` unshift breaks server `(status, name)` sort until reload — `correctness-bug` · low · S

**Files:** `stores/admin.ts:438-440`, `backend/.../service.py:362-368` (server sorts by `(status, full_name)`).
**Why:** `createPlatformUser` prepends the new user, but the list is server-sorted by `(status, full_name)`. The new active user jumps to the top out of alphabetical order and, after a "Yangilash" reload, silently relocates — a visible reorder jump. (`provision`/`createManufacturer`/`createMaterial` prepend to created_at-desc lists and stay consistent; only platform users are mis-ordered.)
**Fix:** After `createPlatformUser`, re-fetch the list, or insert at the position consistent with `(status, full_name)` instead of always unshifting.

### AB-35 · Provision form hardcodes Tashkent lat/lon (dup literal) + no working-hours UI — `completeness-stub` · low · S

**Files:** `AdminWorkshopsView.vue:25-26` (initial form), `:79-80` (resetForm), `:50-60` (`defaultWorkingHours` hardcoded 09:00–18:00).
**Why:** The form seeds `latitude '41.2995' / longitude '69.2401'` (Tashkent center) in two duplicated literals (drift risk), submitted verbatim as the new branch's coordinates if unchanged — silently placing unrelated workshops at one point, with no map/geocode picker. Branch `working_hours` (a spec'd provisioning input, [`access-management.md`](../docs/ref/features/access-management.md):154) is also hardcoded with no UI.
**Fix:** Hoist the coordinates to a single named constant (or leave the fields blank and require entry); de-dupe the literal. Optionally add a light map/geocode picker and surface working-hours inputs (or make lat/lon optional if the backend can default them).

### AB-36 · Provision code field stops re-deriving from name after first auto-fill — `spec-conformance` · low · S

**Files:** `AdminWorkshopsView.vue:123-128` (`if (!form.code) form.code = codeFromName(name)`), `:245-247`. Spec: [`access-management.md`](../docs/ref/features/access-management.md):181-182 ("auto-generates from the workshop name and stays editable").
**Why:** The code auto-fills from the name only while `form.code` is empty; once auto-filled, a later name change leaves a **stale** auto-code (the field is editable, so it's mostly within spec — borderline).
**Fix:** Track a "manually touched" flag; while untouched, keep re-deriving from the name on each change (set the flag only on real user input to the code field).

### AB-37 · Dashboard recent-workshops: owner login (not UUID) + Filial col + localized pill + re-run on failed-job card — `design-parity` · low · S

**Files:** `AdminDashboardView.vue:18/126-171` (owner = `owner_user_id.slice(0,8)`; no branch col; raw status), `:174-204` (failed-job card = plain rows, no re-run). Spec: [`platform.md`](../docs/ref/features/platform.md):102-103. Prototype: `dashboard.html:89/97-105`.
**Why:** "Recent provisioning" renders the owner as an opaque UUID slice (the list summary lacks the owner login), the recent-workshops table drops the prototype's Filial (branch count) column and shows raw English status, and the "Failed ish" panel lists failed jobs as plain rows with no error summary and **no re-run** — losing the incident-landing shortcut the design provides.
**Fix:** Surface the owner login (needs it on the list summary — small backend add, or read from detail), add a Filial count column, localize the status pill (AB-12), and add a "Qaytadan ishga tushirish" button on the failed-job card calling `admin.runJob` (gated like AB-04).

### AB-38 · Profile password tab: add 'Tasdiqlash' confirm field + strength meter — `design-parity` · low · S

**Files:** `AdminProfileView.vue:143-167` (only current + new). Spec: [`access-management.md`](../docs/ref/features/access-management.md):78 ("Change password (strength meter)"). Prototype: `profile.html:52-54` (three fields).
**Why:** The password form has only current + new — no confirm field (a mistyped new password is submitted with no client-side match check) and no strength meter the spec calls for.
**Fix:** Add a "Tasdiqlash" confirm input (block submit + inline message on mismatch) and a strength meter, matching the prototype's three-field layout + the spec.

### AB-39 · Workshop-detail error state is a dead end — add back-link + retry — `ux-flow` · low · S

**Files:** `AdminWorkshopDetailView.vue:62-68` (error card), `:71` (the `← Ustaxonalar` back-link lives only in the success branch).
**Why:** When `loadWorkshop` fails, the detail view renders only an error card with no back-link and no retry — the operator must edit the URL or hit browser-back. The list view's refresh is always reachable; the detail's isn't.
**Fix:** Add a back-to-list link + a retry button to the error state (folds into `AdminErrorState`'s retry emit, AB-08).

### AB-40 · Materials empty-state: add CTA + distinguish no-data vs filtered-to-zero — `ux-flow` · low · S

**Files:** `AdminMaterialsView.vue:261-264`.
**Why:** The empty card ("Material yo'q — Manufacturer qo'shing, keyin … material yarating") has no button and no link to the manufacturers screen, and conflates the truly-empty case with filtered-to-zero — a first-time operator reading it may not connect it to the page-head create button.
**Fix:** Distinguish "no materials at all" (show a "Yangi material" CTA + link to manufacturers) from "filtered to zero" (offer "clear filters"), mirroring the prototype's filter-aware empty copy.

### AB-41 · Workshop block: second confirm + destructive styling + "unblock won't restore sessions" note — `security-rbac` · low · S

**Files:** `AdminWorkshopDetailView.vue:250-292` (`canBlock` only requires a non-empty reason; confirm button is `mp-button-primary`, not destructive), and apply to `AdminPlatformUsersView.vue:353-379`. Spec: [`access-patterns.md`](../docs/access-patterns.md) (block cascade), [`access-management.md`](../docs/ref/features/access-management.md) ("Unblocking does NOT restore sessions").
**Why:** `block_workshop` is a hard cascade (revoke all owner/staff sessions + freeze open orders), yet the only friction is a mandatory reason and one primary-styled submit — a mis-click on the wrong workshop is one stroke from cutting off a tenant. The dialog also never states that unblocking won't restore sessions (a spec consequence operators should know), and the in-dialog confirm isn't destructive-styled.
**Fix:** Style the confirm as destructive; add the "unblock won't restore sessions" line; consider a type-to-confirm of the workshop code for the cascade. Apply the same destructive styling to the operator block dialog. Keep the mandatory reason.

### AB-42 · Manufacturers: add the spec'd Country filter — `spec-conformance` · low · S

**Files:** `AdminManufacturersView.vue:104-117` (search + status only). Spec: [`platform.md`](../docs/ref/features/platform.md):37 ("Filters: status dropdown, country dropdown"). Prototype: `manufacturers.html:32-34`.
**Why:** The spec and prototype both call for a Country filter on the manufacturers list; the Vue filter bar has only search + status.
**Fix:** Add a Country `ProjectDropdown` built from the distinct `manufacturer.country` values, folded into the `filtered` computed.

### AB-43 · Error-detail renders context/stack verbatim — add render-time defense-in-depth — `security-rbac` · low · S

**Files:** `AdminPlatformErrorsView.vue:43/230-239` (raw `JSON.stringify(context)` + raw stack), `backend/.../errors.py:26-58` + `support/audit.py:14-52` (write-time scrub via a fixed key/keyword/regex list).
**Why:** Masking is **only** done at write time via a fixed list, so a secret carried under a non-listed key name or as free text with a non-matching delimiter passes straight to the operator's screen with no defense-in-depth at render time. This is the documented design (not a current leak), but the detail view has zero redaction layer of its own.
**Fix:** Keep write-time scrubbing as source of truth but add a thin render-time guard — collapse raw context/stack behind an explicit "reveal raw" affordance and run a last-line redact over obvious token/JWT/bearer patterns. (Backend scrub-list review is a separate decision.)

### AB-44 · `list_error_records` has no server-side limit — add a defensive cap — `performance` · low · S

**Files:** `backend/.../service.py:613-629` (no limit), `AdminPlatformErrorsView.vue:129-156` (plain `v-for`, no virtualization).
**Why:** Risk is bounded because `ErrorRecord` rows are *grouped* by code+module (cardinality tracks distinct signatures, usually small), but there's no server ceiling — a pathological spread of distinct codes renders an arbitrarily long table.
**Fix:** Add a defensive server-side limit (e.g. 200) ordered by spike count + a "top N shown" note. No virtualization needed at expected cardinality. (Backend change = decision.)

### AB-45 · Catalog views fetch full list + filter client-side; `CatalogFilters` server plumbing unused — `performance` · low · M

**Files:** `stores/admin.ts:200/308-352` (`CatalogFilters` + server query built), call sites `AdminMaterialsView.vue:217`/`AdminManufacturersView.vue:90/113` (called with **no args**), `:88-108`/`:27-37` (client-side `filtered`).
**Why:** The store plumbs `search/status/kind/manufacturer_id` into the backend query, and the endpoints support `search`+`status` server-side — but every call site invokes the loaders with no filters and filters the full in-memory list locally. The whole catalog ships to the browser on every mount; the server-filter path is dead code that misleads readers.
**Fix:** Either (a) wire the filter refs into a debounced watcher calling `loadMaterials({...})` so filtering is server-paged (safer as the master catalog grows), or (b) delete the unused filter params to match the client-side reality. Pick one.

### AB-46 · Every view refetches on mount (no staleness guard); dashboard pre-pulls full catalog for a count — `performance` · low · M

**Files:** `AdminDashboardView.vue:25-35` (7-way fan-out incl. full `loadManufacturers`+`loadMaterials`+`loadPlatformUsers` just for `.length`), `AdminMaterialsView.vue:217`/`AdminManufacturersView.vue:90`/`AdminPlatformErrorsView.vue:71`/`AdminPlatformUsersView.vue:124` (unconditional reload on mount).
**Why:** The dashboard pre-pulls two full catalog lists + the operator list to render them as single counts (`AdminDashboardView.vue:248-257`) — and `overview` already carries `platform_users_active`. Then every destination view re-fetches the same data unconditionally, so dashboard → materials → manufacturers re-downloads manufacturers+materials three times in seconds. No request is shared or memoized.
**Fix:** Add a lightweight per-resource staleness guard in the store (`loadedAt` + `maxAge` ~30s, skip if fresh) or load only when the array is empty / explicitly refreshed; drop the dashboard's `loadManufacturers`/`loadMaterials` (it only needs their counts — use `overview` where possible).

### AB-47 · Empty action-column `<th></th>` needs an sr-only label — `a11y` · low · S

**Files:** `AdminWorkshopsView.vue:188`, `AdminPlatformUsersView.vue:176`, `AdminManufacturersView.vue:150`, `AdminMaterialsView.vue:279`, `AdminPlatformJobsView.vue:78`, `AdminPlatformErrorsView.vue:126`.
**Why:** The data tables end with an empty `<th></th>` over the action buttons; a screen reader gets no column name when navigating action cells.
**Fix:** Put a visually-hidden label in the header, e.g. `<th><span class="sr-only">Amallar</span></th>` (the `.sr-only` utility is already used in these views).

### AB-48 · Provision modal stays 3-up between 620–920px — add a 2-up tablet step — `responsive` · low · S

**Files:** `AdminWorkshopsView.vue:240` (`.admin-form-grid.three`), `main.css:3977-3981` (only collapses to 1-up at `max-width:620px`), `:3624` (modal width `min(100% − 32px, 640px)`).
**Why:** The 14-field provision form stays 3 columns between ~620–920px (where the ~640px modal lives), giving ~190px-wide inputs under labels like "Filial telefoni" — tight and awkward to fill on a tablet. Not broken (`minmax(0,1fr)` prevents overflow), just cramped.
**Fix:** Add a `max-width:760px` breakpoint dropping `.admin-form-grid.three` to 2 columns before the existing 620px single-column rule. CSS-only, admin-scoped.

### AB-49 · Admin filter-bar input is fixed 220px — make it fluid — `responsive` · low · S

**Files:** `main.css:3423` (`.admin-filter-input input { width: 220px }`), `AdminWorkshopsView.vue:149`, `AdminMaterialsView.vue:232`.
**Why:** The search input is hard-coded to 220px at every width; in drawer mode at ~320–360px it nearly fills the row and can't shrink to match narrower controls, giving a ragged filter bar. Cosmetic, not a break.
**Fix:** `width: 100%; max-width: 220px` on the input (or `flex: 1 1 180px; min-width: 0` on `.admin-filter-input`) so it grows/shrinks gracefully. Admin-scoped class.

### AB-50 · Button-dense tables hit the 680px floor → tall wrapped action rows — `responsive` · low · S

**Files:** `main.css:3340` (`.admin-table { min-width: 680px }`), `AdminPlatformUsersView.vue:194` (3–4 wrapping action buttons), Materials + Audit similar.
**Why:** The shared 680px min-width is tuned for the narrow tables; on the button-dense ones (platform-users, materials, audit) the action column is squeezed at the floor and its buttons wrap onto several lines, ballooning row height while neighbours have slack.
**Fix:** Give the button-dense tables a higher min-width (e.g. `.admin-table.wide { min-width: 900px }`) so action buttons stay on one row and the operator scrolls horizontally as intended. CSS + one class, admin-scoped.

### AB-51 · E2E/unit for the cross-workshop audit viewer (filter predicate) — `testing` · low · M

**Files:** `AdminAuditView.vue:11-30` (filter computeds), `stores/admin.ts:542` (`loadAudit`).
**Why:** The audit viewer loads both feeds and has client-side filter computeds (substring-match across several fields) with no test. Lower priority — read-only (no destructive path), and the backend audit surface is covered by `test_platform_api.py`.
**Fix:** Prefer (a) extracting the filter predicate into `adminUi.ts` + a Vitest unit (matches by action/entity_id/trace_id; empty query returns all); or (b) an audit-tab assertion in the AB-30 platform-ops E2E (after provision+block, open `/admin/audit`, assert the actions appear + the search filters them).

### AB-52 · Extend provisioning E2E with workshop unblock — `testing` · low · S

**Files:** `e2e/tests/access-and-provisioning.spec.ts:~138` (ends at asserting "blocked"), `AdminWorkshopDetailView.vue` (unblock control), `stores/admin.ts` (`unblockWorkshop`).
**Why:** The admin E2E asserts a workshop is "blocked" but never unblocks it — a one-sided lifecycle assertion. The unblock path is wired but never exercised through the UI (backend covers it at the API).
**Fix:** Extend the test: after "blocked", click the unblock control and assert status returns to "active" — completing the lifecycle round-trip.

### AB-53 · Bind a permission-denied regression test to the AB-01 fix — `testing` · low · S — **Done (B3)**

**Files:** `stores/admin.ts` loaders; an E2E for the no-access render.
**Why:** No test pins the 403-handling behaviour either way (only catalog preserves `permission_denied`, and the only view rendering it is dead). A regression guard should ship **with** AB-01, not standalone.
**Fix:** With AB-01, add a Vitest unit asserting a 403 yields `permission_denied` for each ops/error loader, plus one E2E where a blocked operator's session renders the no-access state rather than a generic failure.

## Won't

### AB-54 · Backend privilege-gate audit — verified solid, nothing to fix — `security-rbac` · Won't

**Files:** `backend/app/modules/platform/service.py:351` (`require_platform_operator`), `:114-321` (use-cases), `platform/routes.py:75/105`, `catalog/service.py:62/78/107/125/153/188/213/265/283/352`.
**Why (Won't):** The audit's highest-priority question — does any `/platform/*` use-case lack the operator gate (a privilege leak)? — was checked exhaustively and the answer is **no**. Every platform use-case calls `require_platform_operator(principal)` inline (18 occurrences: overview, provision, block/unblock workshop, list/create/update/reset/block/unblock platform user, list/run jobs, list/get/resolve errors, audit actions + status-changes) except `list_workshops`/`get_workshop_detail`, which gate at the **route** level (`routes.py:75/105`). The catalog mutators `update_manufacturer`/`set_manufacturer_status`/`update_material`/`set_material_status` gate **transitively** — their first line calls `get_manufacturer`/`get_material`, both of which call `require_platform_operator`. The `cannot_block_self` and `last_platform_operator` guards exist server-side (`service.py:474/489/766`). There is no missing-gate finding to action. Recorded here (rather than dropped) so the verification is on the record and isn't re-litigated. The *frontend* consequences of these guards not being surfaced in the UI are tracked as **AB-07 / AB-18** (last-operator) and **AB-41** (block cascade friction) — those are real and Open.
