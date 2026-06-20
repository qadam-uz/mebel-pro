# Admin SPA — Codex Residual Backlog

A living, engineering-owned backlog for the **admin SPA** (the platform-operator
surface). This is implementation/tracking, not product canon, so it lives under
`web/`. `docs/` stays the source of truth for product behavior.

> Seeded 2026-06-20 from the Codex multi-lens admin audit, then reconciled on
> 2026-06-20 against current `main` and the completed Claude harness admin audit.
> Items already fixed by the Claude harness or refuted against current code were
> removed from this file. The remaining entries are the actual non-fixed Codex
> findings, with current file references.

## Conventions

- **Priority** — `P1` do-first, `P2` important, `P3` nice-to-have.
- **Severity** — user-facing or operational impact. **Effort** — `S` <= 1/2 day ·
  `M` ~1-2 days · `L` larger.
- **Category** — `ux-flow` · `responsive` · `i18n-copy` · `design-parity` · `a11y` ·
  `correctness-bug` · `performance` · `states-errors` · `completeness-stub` ·
  `security-rbac` · `spec-conformance` · `tech-debt` · `testing`.
- **Status** — `Open` · `WIP` · `Done` · `Won't`.
- Scope guard: admin SPA only. Backend changes are listed only where admin correctness
  genuinely requires them.

## Counts

| | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| Open | 0 | 9 | 3 | **12** |
| Done | 6 | 5 | 0 | **11** |
| Won't | — | — | — | **0** |

> Category totals (Open): i18n-copy 2 · a11y 4 · completeness-stub 2 · spec-conformance 2 · ux-flow 1 ·
> performance 1.

> Reconciliation note: Codex AB-001, AB-002, AB-008…AB-012, AB-014…AB-016,
> AB-019…AB-023, AB-027, AB-029, AB-033…AB-036, AB-038, AB-040…AB-042,
> AB-045…AB-047, AB-049…AB-052, AB-055…AB-059 were removed because current code
> already contains the corresponding Claude fixes or the finding is stale/refuted.
>
> Progress (2026-06-20, B1 Codex residual fixes): **AB-003, AB-004, AB-005,
> AB-006, AB-007, AB-017, AB-018, AB-030, AB-031, AB-032, AB-053 Done**.
> Gates: `backend/` `uv run ruff check . && uv run ruff format --check . &&
> uv run mypy app && uv run pytest` passed (124 passed, 2 skipped);
> `web/` `pnpm lint:check && pnpm format:check && pnpm typecheck &&
> pnpm test && pnpm build` passed (197 tests passed, build passed);
> `e2e/` `pnpm typecheck && pnpm test` passed (25 passed).

## Index

| ID | Priority | Category | Severity | Effort | Status | Title |
|---|---|---|---|---|---|---|
| AB-003 | P1 | security-rbac | high | M | Done | Last active platform-operator guard is race-prone |
| AB-004 | P1 | correctness-bug | high | M | Done | Job `running` state is never persisted as server truth |
| AB-005 | P1 | correctness-bug | high | M | Done | Error 24 h / 7 d counters are lifetime increments |
| AB-006 | P1 | correctness-bug | high | S | Done | Edge material edit sends panel-only null fields and fails |
| AB-007 | P1 | correctness-bug | high | M | Done | Workshop provisioning ships hardcoded coordinates and lacks coordinate validation |
| AB-017 | P1 | correctness-bug | high | S | Done | Material image upload can race against Save |
| AB-013 | P2 | i18n-copy | high | M | Open | Native browser validation leaks non-Uzbek form errors |
| AB-018 | P2 | responsive | high | S | Done | Admin notification dropdown can render off-screen at small widths |
| AB-024 | P2 | a11y | med | M | Open | Route changes do not move focus to page content |
| AB-025 | P2 | a11y | med | S | Open | Admin shell has no skip link |
| AB-030 | P2 | a11y | med | S | Done | Mobile admin drawer dialog has no accessible name |
| AB-031 | P2 | responsive | med | S | Done | Mobile admin drawer stays open after route navigation |
| AB-032 | P2 | responsive | low | S | Done | Docs/API links disappear from mobile navigation |
| AB-037 | P2 | completeness-stub | med | M | Open | Workshop first-branch working hours are hidden defaults |
| AB-039 | P2 | spec-conformance | med | M | Open | Materials filters are incomplete |
| AB-043 | P2 | ux-flow | med | M | Open | Error/job notifications lose incident context on navigation |
| AB-044 | P2 | spec-conformance | med | M | Open | Notifications page is fixed-size and does not mark rows read on open |
| AB-048 | P2 | performance | med | S | Open | Latest audit-log reads lack time-oriented indexes |
| AB-053 | P2 | i18n-copy | med | S | Done | Admin notification dropdown action stays English |
| AB-054 | P2 | i18n-copy | med | M | Open | Catalog/material forms retain English operator-facing terms |
| AB-026 | P3 | a11y | med | S | Open | Filters rely on placeholder-only visible labels |
| AB-028 | P3 | a11y | med | M | Open | Repeated row action names lack row context |
| AB-060 | P3 | completeness-stub | low | S | Open | Admin topbar global search is inert |

---

## AB-003 — Last active platform-operator guard is race-prone

- **Category:** security-rbac
- **Priority:** P1
- **Severity:** high
- **Effort:** M
- **Status:** Done
- **Affected files:** `backend/app/modules/platform/service.py:852`,
  `backend/app/modules/platform/service.py:866`
- **Spec/prototype:** `docs/ref/features/platform.md` — platform must prevent blocking the
  last active `PLATFORM_USER`.

**Notes:** `_ensure_another_active_platform_user()` performs a count query before blocking a
platform operator. Concurrent requests can each see another active operator and both proceed.
Use row locking / transactional selection of active operators before changing status, and keep
the existing audit log behavior.

**Resolution (B1, 2026-06-20):** Replaced the count-only guard with a locked active-operator
selection before block status changes. Verified by backend full gate.

## AB-004 — Job `running` state is never persisted as server truth

- **Category:** correctness-bug
- **Priority:** P1
- **Severity:** high
- **Effort:** M
- **Status:** Done
- **Affected files:** `backend/app/modules/platform/scheduler.py:39`,
  `backend/app/modules/platform/scheduler.py:55`,
  `backend/app/modules/platform/scheduler.py:64`,
  `backend/app/modules/platform/scheduler.py:79`
- **Spec/prototype:** `docs/ref/features/platform.md` — jobs expose `running` state and manual
  run controls must reflect already-running jobs.

**Notes:** `JobDefinition.running` is returned by the platform API, but the scheduler only
creates `RUNNING` `JobRun` rows. The definition row never flips true/false, so the admin UI
cannot rely on server truth after reload or across clients.

**Resolution (B1, 2026-06-20):** `JobDefinition.running` now commits true before the handler runs
so other operator sessions can see it, then returns false on terminal completion; skipped runs
attach to the definition without overwriting terminal `last_result`. Covered by
`backend/tests/test_scheduler.py`.

## AB-005 — Error 24 h / 7 d counters are lifetime increments

- **Category:** correctness-bug
- **Priority:** P1
- **Severity:** high
- **Effort:** M
- **Status:** Done
- **Affected files:** `backend/app/modules/platform/errors.py:65`,
  `backend/app/modules/platform/errors.py:69`,
  `backend/app/modules/platform/service.py:690`,
  `backend/app/modules/platform/service.py:703`
- **Spec/prototype:** `docs/ref/features/platform.md` — error monitor shows rolling 24-hour
  and 7-day counts.

**Notes:** `record_application_error()` increments `count_24h` and `count_7d` forever. Counts
must be recomputed from `ErrorOccurrence.occurred_at` windows on record and read paths so stale
records age out correctly.

**Resolution (B1, 2026-06-20):** Added rolling counter refresh from `ErrorOccurrence` windows on
record and platform read paths. Covered by `backend/tests/test_audit_errors_files.py`.

## AB-006 — Edge material edit sends panel-only null fields and fails

- **Category:** correctness-bug
- **Priority:** P1
- **Severity:** high
- **Effort:** S
- **Status:** Done
- **Affected files:** `web/src/shared/app/adminMaterials.ts:17`,
  `web/src/shared/views/AdminMaterialsView.vue:216`
- **Spec/prototype:** `docs/ref/features/catalog-inventory.md` — edge materials do not carry
  panel dimensions/type fields.

**Notes:** The material save payload always includes `type`, `panel_length_mm`,
`panel_width_mm`, and `grain_direction`, setting them to `null` for edges. Backend validators
reject panel-only fields when present for edge writes.

**Resolution (B1, 2026-06-20):** Introduced a typed material write helper that omits panel-only
keys for edge payloads. Covered by `web/src/shared/app/__tests__/adminMaterials.spec.ts`.

## AB-007 — Workshop provisioning ships hardcoded coordinates and lacks coordinate validation

- **Category:** correctness-bug
- **Priority:** P1
- **Severity:** high
- **Effort:** M
- **Status:** Done
- **Affected files:** `web/src/shared/views/AdminWorkshopsView.vue:97`,
  `backend/app/modules/platform/schemas.py:49`,
  `backend/app/modules/platform/schemas.py:56`
- **Spec/prototype:** `docs/ref/features/access-management.md` — first branch payload includes
  real branch coordinates and working hours.

**Notes:** The admin form defaults every new workshop to `41.2995 / 69.2401`, and the backend
schema accepts any decimal coordinate. Remove unsafe geographic defaults from the form path and
validate latitude/longitude ranges in the platform API.

**Resolution (B1, 2026-06-20):** Removed hardcoded form coordinates and added backend
latitude/longitude range validation. Covered by `backend/tests/test_platform_api.py`.

## AB-017 — Material image upload can race against Save

- **Category:** correctness-bug
- **Priority:** P1
- **Severity:** high
- **Effort:** S
- **Status:** Done
- **Affected files:** `web/src/shared/views/AdminMaterialsView.vue:569`
- **Spec/prototype:** `docs/ref/features/catalog-inventory.md` — catalog image selection is part
  of the material record and must save deterministically.

**Notes:** While `files.uploading` is true, the Save button remains enabled. An operator can save
before `image_file_id` is set, producing a record without the selected image.

**Resolution (B1, 2026-06-20):** Disabled Save while image upload is in progress and changed the
button copy to the upload-in-progress state. Verified by web full gate.

## AB-013 — Native browser validation leaks non-Uzbek form errors

- **Category:** i18n-copy
- **Priority:** P2
- **Severity:** high
- **Effort:** M
- **Status:** Open
- **Affected files:** `web/src/shared/views/AdminLoginView.vue:44`,
  `web/src/shared/views/AdminWorkshopsView.vue:345`,
  `web/src/shared/views/AdminMaterialsView.vue:493`,
  `web/src/shared/views/AdminPlatformUsersView.vue:375`
- **Spec/prototype:** `docs/ref/features/access-management.md` — operator-facing admin copy is
  coherent and localized.

**Notes:** Admin forms still rely on native `required`/`minlength` validation. Browser-generated
messages can appear in the browser language instead of the admin copy policy.

## AB-018 — Admin notification dropdown can render off-screen at small widths

- **Category:** responsive
- **Priority:** P2
- **Severity:** high
- **Effort:** S
- **Status:** Done
- **Affected files:** `web/src/shared/components/NotificationsMenu.vue:39`,
  `web/src/shared/components/NotificationsMenu.vue:248`
- **Spec/prototype:** `web/prototypes/prototype-full` — admin shell notifications remain usable
  at narrow widths.

**Notes:** The dropdown is absolutely positioned with `right-0` relative to the bell. In narrow
admin layouts, the menu can overflow the viewport instead of anchoring to the viewport.

**Resolution (B1, 2026-06-20):** Admin dropdown now uses viewport-fixed positioning on narrow
screens and reverts to anchored positioning at `sm` and above. Verified by web/e2e gates.

## AB-024 — Route changes do not move focus to page content

- **Category:** a11y
- **Priority:** P2
- **Severity:** med
- **Effort:** M
- **Status:** Open
- **Affected files:** `web/src/shared/app/createRoleApp.ts:147`,
  `web/src/shared/components/AppShell.vue:896`
- **Spec/prototype:** `docs/ref/features/access-management.md` — modal and navigation flows must
  preserve keyboard accessibility.

**Notes:** Router `afterEach` only updates the document title. Keyboard and screen-reader users
remain focused on the previous navigation control after page navigation.

## AB-025 — Admin shell has no skip link

- **Category:** a11y
- **Priority:** P2
- **Severity:** med
- **Effort:** S
- **Status:** Open
- **Affected files:** `web/src/shared/components/AppShell.vue:896`
- **Spec/prototype:** `web/prototypes/prototype-full` admin shell accessibility baseline.

**Notes:** Admin users must tab through sidebar/topbar controls before reaching page content.
Add a visible-on-focus skip link to the admin main landmark.

## AB-030 — Mobile admin drawer dialog has no accessible name

- **Category:** a11y
- **Priority:** P2
- **Severity:** med
- **Effort:** S
- **Status:** Done
- **Affected files:** `web/src/shared/components/AppShell.vue:846`
- **Spec/prototype:** `docs/ref/features/access-management.md` — dialogs need accessible names
  and focus semantics.

**Notes:** The mobile admin drawer has `role="dialog"` and `aria-modal="true"`, but no
`aria-label` or `aria-labelledby`.

**Resolution (B1, 2026-06-20):** Added `aria-labelledby` tied to the drawer title. Verified by
web/e2e gates.

## AB-031 — Mobile admin drawer stays open after route navigation

- **Category:** responsive
- **Priority:** P2
- **Severity:** med
- **Effort:** S
- **Status:** Done
- **Affected files:** `web/src/shared/components/AppShell.vue:880`,
  `web/src/shared/components/AppShell.vue:888`
- **Spec/prototype:** `web/prototypes/prototype-full` admin mobile navigation behavior.

**Notes:** Mobile drawer `RouterLink` entries do not close the drawer on click, leaving the
previous overlay visible after navigation.

**Resolution (B1, 2026-06-20):** Mobile admin nav links now close the drawer on activation.
Verified by web/e2e gates.

## AB-032 — Docs/API links disappear from mobile navigation

- **Category:** responsive
- **Priority:** P2
- **Severity:** low
- **Effort:** S
- **Status:** Done
- **Affected files:** `web/src/shared/components/AppShell.vue:790`,
  `web/src/shared/components/AppShell.vue:896`
- **Spec/prototype:** `docs/architecture.md` — docs are served live and linked from the product
  shell.

**Notes:** The desktop admin sidebar has Docs/API links, but the mobile drawer renders only the
main grouped admin nav.

**Resolution (B1, 2026-06-20):** Added Docs/API links to the mobile admin drawer. Verified by
web/e2e gates.

## AB-037 — Workshop first-branch working hours are hidden defaults

- **Category:** completeness-stub
- **Priority:** P2
- **Severity:** med
- **Effort:** M
- **Status:** Open
- **Affected files:** `web/src/shared/views/AdminWorkshopsView.vue:180`
- **Spec/prototype:** `docs/ref/features/access-management.md` — first branch includes
  `working_hours`.

**Notes:** Provisioning silently sends `defaultWorkingHours()` with no operator review/edit path.
Expose working-hours controls or defer provisioning until the first branch settings are explicit.

## AB-039 — Materials filters are incomplete

- **Category:** spec-conformance
- **Priority:** P2
- **Severity:** med
- **Effort:** M
- **Status:** Open
- **Affected files:** `web/src/shared/views/AdminMaterialsView.vue:51`,
  `web/src/shared/views/AdminMaterialsView.vue:296`
- **Spec/prototype:** `docs/ref/features/platform.md` — material catalog filters include kind,
  type, manufacturer, thickness, status, and free text.

**Notes:** Current filters cover kind, manufacturer, status, and text. Type and thickness
filters are missing, and the UX does not match the prototype filter density.

## AB-043 — Error/job notifications lose incident context on navigation

- **Category:** ux-flow
- **Priority:** P2
- **Severity:** med
- **Effort:** M
- **Status:** Open
- **Affected files:** `web/src/shared/app/adminUi.ts:186`,
  `web/src/shared/views/AdminNotificationsView.vue:107`
- **Spec/prototype:** `docs/ref/features/platform.md` — platform notifications should take
  operators to actionable incident context.

**Notes:** Error-record notifications route only to `/admin/platform/errors`, not to the selected
record or filter context. Job notifications route only to the jobs page, losing the relevant job
or run context.

## AB-044 — Notifications page is fixed-size and does not mark rows read on open

- **Category:** spec-conformance
- **Priority:** P2
- **Severity:** med
- **Effort:** M
- **Status:** Open
- **Affected files:** `web/src/shared/views/AdminNotificationsView.vue:59`,
  `web/src/shared/views/AdminNotificationsView.vue:107`
- **Spec/prototype:** `docs/ref/features/platform.md` — admin notifications are an operational
  queue, not only a capped preview.

**Notes:** The page always loads 100 notifications, has no pagination/load-more path, and opening
a row does not mark it read.

## AB-048 — Latest audit-log reads lack time-oriented indexes

- **Category:** performance
- **Priority:** P2
- **Severity:** med
- **Effort:** S
- **Status:** Open
- **Affected files:** `backend/app/modules/support/models.py:65`,
  `backend/app/modules/support/models.py:88`,
  `backend/app/modules/platform/routes.py:304`
- **Spec/prototype:** `docs/ref/features/platform.md` — audit views list latest actions/status
  changes for platform operators.

**Notes:** Audit APIs read latest rows by time, but support models only index entity/workshop
lookups. Add time-oriented indexes for latest-log scans if Postgres query plans confirm this.

## AB-053 — Admin notification dropdown action stays English

- **Category:** i18n-copy
- **Priority:** P2
- **Severity:** med
- **Effort:** S
- **Status:** Done
- **Affected files:** `web/src/shared/components/NotificationsMenu.vue:263`
- **Spec/prototype:** `docs/ref/features/platform.md` — admin operator-facing copy should be
  coherent.

**Notes:** Client/workshop/admin loading and empty states are localized, but the admin dropdown
uses `Mark all read` because the label condition excludes `isAdmin`.

**Resolution (B1, 2026-06-20):** Included admin in the localized mark-all label condition.
Verified by web/e2e gates.

## AB-054 — Catalog/material forms retain English operator-facing terms

- **Category:** i18n-copy
- **Priority:** P2
- **Severity:** med
- **Effort:** M
- **Status:** Open
- **Affected files:** `web/src/shared/views/AdminMaterialsView.vue:75`,
  `web/src/shared/views/AdminMaterialsView.vue:290`,
  `web/src/shared/views/AdminManufacturersView.vue:137`,
  `web/src/shared/app/adminUi.ts:181`
- **Spec/prototype:** `docs/ref/features/platform.md` — choose one coherent admin copy policy.

**Notes:** Domain terms such as `manufacturer`, `record`, `failed job`, and `Error spike` remain
mixed into otherwise Uzbek admin copy. Decide which terms intentionally stay English and localize
the rest consistently.

## AB-026 — Filters rely on placeholder-only visible labels

- **Category:** a11y
- **Priority:** P3
- **Severity:** med
- **Effort:** S
- **Status:** Open
- **Affected files:** `web/src/shared/views/AdminWorkshopsView.vue:227`,
  `web/src/shared/views/AdminMaterialsView.vue:296`,
  `web/src/shared/views/AdminAuditView.vue:154`
- **Spec/prototype:** `web/prototypes/prototype-full` admin forms/filters.

**Notes:** Several filters use a visually hidden label and a placeholder as the only visible
field name. This is technically labeled, but lower quality for cognitive accessibility and
scanability.

## AB-028 — Repeated row action names lack row context

- **Category:** a11y
- **Priority:** P3
- **Severity:** med
- **Effort:** M
- **Status:** Open
- **Affected files:** `web/src/shared/views/AdminPlatformErrorsView.vue:221`,
  `web/src/shared/views/AdminMaterialsView.vue:360`,
  `web/src/shared/views/AdminWorkshopsView.vue:290`
- **Spec/prototype:** `web/prototypes/prototype-full` table action accessibility.

**Notes:** Repeated table actions such as "Ko'rish", "Tahrirlash", and status buttons are hard
to distinguish when announced outside visual row context. Add row-specific accessible labels.

## AB-060 — Admin topbar global search is inert

- **Category:** completeness-stub
- **Priority:** P3
- **Severity:** low
- **Effort:** S
- **Status:** Open
- **Affected files:** `web/src/shared/components/AppShell.vue:820`
- **Spec/prototype:** `web/prototypes/prototype-full` admin topbar search affordance.

**Notes:** The admin topbar shows a global-search field, but no behavior is wired. Either connect
it to supported admin resources or remove/replace the affordance until a global search exists.
