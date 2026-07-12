# Cutting results — polish batch & interactive details panel — Implementation Spec

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-12
Repo: `mebel-pro`. **Delta spec** against the implemented results surface:
`CuttingResultsSection.vue`, `CuttingPanelSvg.vue`, `CuttingSheetThumbnails.vue`,
`CuttingVariantTabs.vue`, backend `app/modules/cutting/rendering.py` (print parity),
docs `docs/ref/features/cutting.md`. Findings verified in a live browser pass
(27-part / 2-material / 4-sheet draft) on 2026-07-12.

## 0. Read first, and process rules

- Two independent stages: **A — polish batch** (small, safe, releasable alone) and
  **B — interactive details panel** (one interaction model, ships as a unit).
  **Stage B depends on `SPEC_CUTTING_EDGE_REGISTRY_IDENTITY.md` being implemented**
  (it reuses the registry derivation and colour function); Stage A has no
  dependencies.
- **Print-parity rule (hard):** `rendering.py` mirrors `CuttingPanelSvg.vue`
  one-for-one (its own docstring). Any change to what the sheet SVG *renders* —
  labels, fitting rules, copy — must land in `rendering.py` in the same stage.
  Interactive-only states (hover, selection) have no print counterpart and are
  exempt.
- UI per `web/DESIGN.md`; docs via **docs-management**; test placement via
  **testing-practices**.

## 1. Stage A — polish batch

### A1. Waste KPI severity tint (`CuttingResultsSection.vue:355`)

`Chiqit` is hard-coded `text-success` — 38% waste renders as good news. New pure
helper `wasteToneClass(pct: number | string | null): string` (module-level, exported
for tests): `≤ 15 → 'text-success'`, `> 30 → 'text-warning'`, else `'text-ink'`;
null/NaN → `'text-ink'`. Applies to the KPI tile only — the sticky-footer summary
stays neutral mono (it is a receipt line, not a signal).

### A2. Offcut labels stop clipping (`CuttingPanelSvg.vue` + `rendering.py`)

Verified: a tall-narrow offcut (322×1820) renders its horizontal label off the SVG
edge, clipped mid-word ("…— sizda" cut). Replace the single horizontal-fit check
with one shared rule, `offcutLabelMode(offcut, normScale)`:

1. full label `Qoldiq L×W — sizda qoladi` fits horizontally → horizontal, full;
2. else short label `Qoldiq L×W` fits horizontally → horizontal, short;
3. else full/short fits **vertically** (swap the fit dims) → render rotated 90°
   (`transform="rotate(-90 cx cy)"`), preferring full then short;
4. else dims only `L×W` in whichever orientation fits;
5. else no label (unchanged).

Non-usable offcuts keep the single word `chiqit` through the same mode ladder.
**Mirror the ladder in `rendering.py`** (`_label_fits` → `_offcut_label_mode`;
ReportLab `saveState/translate/rotate` for the vertical case) — one shared table of
expected modes drives both test suites (§4).

### A3. Selection contrast (`CuttingPanelSvg.vue`)

The `accent-soft → accent-tint` fill change on the active placement is
imperceptible (verified by clicking — no visible response). Active placement gets
`stroke-width: 3` (vs 1.5) and its label `font-weight: 700`. Full selection model
(dimming, list sync) is Stage B — this is only the minimum honest feedback, and it
is interactive-only (no PDF impact).

### A4. Savings line — implement the stub (`CuttingResultsSection.vue:130`)

`savingsBanner = computed(() => null)` is dead code from the redesign spec. Implement
the **sheets-only** version: when the draft has >1 result and their total sheet
counts differ, from the fewer-sheets result's perspective:
`«{algorithm label}» varianti {d} list kam ishlatadi`. Algorithm label: reuse the
variant-tab naming (imported → `Fayldagi joylashuv`, optimizer → `Optimizer`).
Equal counts → null (no banner). **No price delta** — the backend quotes only the
chosen result (no per-variant preview quote); pulling prices in is a non-goal (§7).

### A5. Copy fixes (web + PDF parity)

- `CuttingPanelSvg.vue` `aria-label`: `Panel N layout` (English) →
  `List {n} joylashuvi`.
- `KIM {x}%` → `To'ldirish {x}%` in the sheet caption (`panelCaption`) **and** the
  PDF header line (`rendering.py:88`) — same string, same pass.

### A6. KPI tile sublines (`CuttingResultsSection.vue`)

- **Listlar** tile: breakdown currently truncates. Drop the dims from the breakdown
  (short names only, e.g. `TD-W18: 2 · H1334 ST9: 2`) and replace `truncate` with
  `line-clamp-2`. Dims stay available in the sheet caption and thumbnails.
- **Krom** tile: add the subline `{n} xil tasma` (count of `edgeByMaterial`).

### A7. Thumbnail fill badge (`CuttingSheetThumbnails.vue`)

Each thumb gets a tiny fill-percent badge (bottom-right overlay on the mini-SVG,
`To'ldirish`-consistent number only, e.g. `78%`) — which sheet is dense and which is
loose becomes scannable. Extract the existing `panelFillPercent` from
`CuttingResultsSection.vue` into the shared helper module so both use one function.

### A8. One short-name rule (`cuttingDisplay.ts`)

Three surfaces name the same material three ways (thumbnail `TD-W18`, parts grid
full generated name, Krom aside truncated full name). New helper
`snapshotShortLabel(snapshot): string` = `decor_code ?? color ?? name-prefix`,
used by: sheet caption, thumbnails (`materialShortName` dies), the Listlar
breakdown (A6), and the Krom aside rows (full generated name moves to `title`
tooltips). One rule, stated in docs (§6).

## 2. Stage B — interactive details panel (replaces «Joylashuvlar»)

**Problem (verified):** the aside lists every placement as `2000×600 mm #1` — 9+
identical white rows for one sheet: no part names, no grouping, no visible link to
the SVG, dominant vertical cost. It serves no one.

### B1. Data shape (`cuttingEditorDerived.ts` or a results-scoped module)

- `deriveSnapshotEdgeRegistry(parts: CuttingPart[]): EdgeRegistryEntry[]` — build a
  fresh assignment map via `syncEdgeAssignments` + `deriveEdgeRegistry` from a
  **result's** `parts_snapshot` (self-contained; deterministic). Editor-coincidence
  note: results are invalidated when parts change, so live-editor numbers and
  result numbers only coexist while the snapshots match.
- `groupPanelPlacements(result, panel): PanelPartGroup[]` — placements of the
  active sheet grouped by `part_ref`: `{ partRef, name (partDisplayName), length_mm,
  width_mm, count, rotatedCount, tapeNumbers: number[] }`, ordered by first
  placement on the sheet.

### B2. Panel UI (`CuttingResultsSection.vue` aside)

- Header: `Detallar — List {n}`.
- One row per part group: `{name} · {L}×{W}` + `× {count}` chip + `↻ {n}` when
  `rotatedCount > 0` + the part's tape badges (registry number in registry colour,
  from B1). Selected row: `bg-accent-soft` + `border-accent`.
- **Krom block** rows become: registry badge + `snapshotShortLabel` +
  `{thickness}×{width} mm` + metres, sorted by registry number; full name in
  `title`. (Uses the same B1 registry — numbers match the part rows.)

### B3. Selection model (two-way, unmistakable)

State: `activePartRef: string | null` + `activePlacementId: string | null`.

- Row click → select the part: **all** its placements on the sheet highlight
  (active fill + `stroke-width 3`), every other placement dims to 55% opacity.
  Second click on the selected row clears.
- SVG rect click → selects its part (as above) **and** emphasises the clicked
  instance (label bold); the matching row scrolls into view
  (`scrollIntoView({block:'nearest'})`). Clicking the sheet background clears.
- Selection is interactive-only — zero print impact.

## 3. Copy (Uzbek, inline)

- Savings line: `«{variant}» varianti {d} list kam ishlatadi`
- Caption/PDF: `To'ldirish {x}%` · aria: `List {n} joylashuvi`
- Details panel: `Detallar — List {n}` · count chip `× {n}` · rotated `↻ {n}`
- Krom tile subline: `{n} xil tasma`

## 4. Tests

Web (Vitest, colocated):

- `wasteToneClass`: 14.9/15/15.1/30/30.1/null boundary cases.
- `offcutLabelMode`: the §A2 mode table — wide-flat (full), medium (short),
  tall-narrow 322×1820 (rotated), tiny (none); table exported/copied to the backend
  test for parity.
- Savings line: imported 5 vs optimizer 4 → text names optimizer; equal → null;
  single result → null.
- `snapshotShortLabel`: decor → colour → fallback ladder.
- `groupPanelPlacements`: grouping, counts, rotatedCount, tape numbers, ordering.
- `deriveSnapshotEdgeRegistry`: numbers match first-use order of the snapshot.
- Section/component specs: KPI tint class binding; thumbnails badge renders;
  details rows render badges; selection emits + dimming class logic.

Backend (`tests/test_cutting_rendering.py`): extend with the §A2 parity table —
each mode case asserts the PDF draws the expected string (and rotation state) for
that offcut geometry; `To'ldirish` appears in the header line (KIM gone).

E2E: existing cutting journey — update any selector/text that asserted `KIM` or the
placements list; no new journey.

## 5. Acceptance gates

1. `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
   && uv run pytest` — green (A2/A5 parity).
2. `cd web && pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test &&
   pnpm build` — green.
3. `cd e2e && pnpm typecheck && pnpm test` — green.
4. Manual pass (verify skill, the 27-part/2-material draft recipe): waste 38% reads
   warning-tinted; the 322×1820 offcut label renders rotated and unclipped (screen
   **and** downloaded PDF); clicking a details row visibly highlights its parts and
   dims the rest; SVG click scrolls the row into view; Krom rows wear the same
   badge numbers as the editor registry; thumbnails show fill badges; no `KIM`
   anywhere.

## 6. Docs (source of truth — via docs-management)

- `docs/ref/features/cutting.md` — results subsection: waste severity tint rule,
  sheets-only savings line, the details panel (grouped parts, two-way selection),
  registry badges in results (self-contained snapshot derivation), the short-name
  rule (decor → colour; full name in tooltips), offcut label fitting ladder (shared
  with PDF). Keep frontmatter `updated:` current.

## 7. Non-goals (do not partially build)

- **No tape-coloured banding ticks** in the sheet SVG/PDF — would demand full print
  parity work now; a future spec must land web + `rendering.py` together.
- **No per-variant price quotes / price-delta savings** — needs a backend preview
  quote endpoint; sheets-only is the honest client-side version.
- **No SVG zoom/pan** and no thumbnail material-grouping headers (≤6 sheets today).
- **No layout re-architecture** of the results section (tiles/strip/sheet/aside
  order stays; Stage B replaces only the aside's content).
