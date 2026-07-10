# Cutting import — 2D-Place `.map` source with kept layout

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-09
Repo: `mebel-pro`. Builds on the implemented import pipeline
(`impl_specs/SPEC_CUTTING_IMPORT.md`, `SPEC_CUTTING_IMPORT_V2_CSV_ONLY.md`) and the XML spec
(`SPEC_CUTTING_IMPORT_XML.md`). Format knowledge source:
`../maps-print/MAP_PARSING.md` (reverse-engineered `.map` parser doc — READ IT FULLY; this
spec does not repeat its byte-level tables).

## 0. Process rules

- Complex-flow task per `AGENTS.md`: backend + web + docs + a DB migration. Read
  `backend/AGENTS.md`, `web/AGENTS.md`; docs edits follow the docs-management skill.
- The map file's own statistics are **never trusted**: every number we store or price from
  is recomputed server-side from parsed placements. This is a hard security rule (a client
  file must not be able to claim fewer sheets than its layout shows).
- No automatic material matching (standing owner decision) — the user manually picks
  catalog materials in the wizard, every import.
- Parse stays **stateless** (file bytes are never stored); persistence happens in a new
  commit endpoint.

## 1. Product behavior

1. Client uploads a 2D-Place `.map` file in the existing import wizard.
2. Wizard steps for this source: **upload → materials → preview/commit** (no column
   mapping — the format is fixed). Materials step: one **panel material** pick per distinct
   sheet size found in the file (usually exactly one), plus one **edge material** pick if
   any part has banded sides (applied to all banded sides, `source=shop`; refinable later
   in the editor).
3. Commit creates a **draft** (parts list) **plus a persisted "imported layout" cutting
   result** reproducing the file's placements, and returns the draft id. The editor opens
   on that draft with the imported layout rendered **by default** (it is
   `chosen_result_id`). The existing results section already supports multiple result
   variants — no new viewer.
4. Client may press the existing Optimise action: our optimizer's result appears as a
   second variant next to the imported one; the client picks either (existing chosen-result
   flow). Ordering from the imported layout is fully supported.
5. If the file's sheet size matches no catalog panel material exactly, the wizard offers
   **parts-only import** (fills the editor like CSV/XML; no kept layout) with a clear
   notice — never a silent fallback.

## 2. Backend

### 2.1 Parser — `backend/app/modules/cutting/imports/map_parser.py`

Pure-function port of the C# parser documented in `../maps-print/MAP_PARSING.md`. Follow
that doc exactly: `KV_MAP` magic validation, Windows-1251 decoding, `Лист` sheet markers,
`Arial` record markers, record-length filtering (120..200), first-record vs normal-record
offsets (140/127, waste markers 157/144), remainder (`01 FF 00 00`) vs legacy waste
(`+73 == 03` and `01 00 00 00`), companion-record edge attribution (edge bytes at
+41/45/49/53 belong to the **previous** non-waste part), length-prefixed cp1251 name
heuristics, `Лист 1-3` duplicate-sheet expansion, and the +5 mm bounds tolerance.

Output dataclasses (module-local): `MapFile(description, customer_name, order_type,
sheets)`, `MapSheet(name, width_mm, height_mm, records)`, `MapRecord(x, y, width, height,
name, edges: (top, bottom, left, right), is_waste, is_remainder)`.

Hardening: input capped by the existing `MAX_IMPORT_FILE_BYTES`; every offset read
bounds-checked (no exceptions from slicing past EOF); no recursion; reject files with 0
sheets or 0 non-waste records with a typed parse error.

### 2.2 Source registration

- `imports/base.py`: `SourceFormat` gains `"map_2dplace"`.
- `imports/detect.py`: sniff the `KV_MAP` magic (per the doc's header rule) **before** the
  CSV/XML sniffers.
- `/client/cutting/import/parse` handles the new source: response `status="parsed"` (no
  column mapping), and additionally carries a `map_layout` payload (sheets with dims and
  placement rectangles incl. waste/remainder flags) plus `material_groups` — one group per
  distinct `(sheet_width, sheet_height)` with the file-name `OrderType` string as the
  display hint. Parts rows reuse the existing normalized-IR shape (→ §2.3).

### 2.3 Aggregation into part rows

Non-waste records aggregate into editor part rows by key
`(name, unordered{width,height}, edges)`:

- Row `length_mm`/`width_mm` = orientation of the **first occurrence**; `quantity` =
  instance count; `part_ref` per the existing import convention; `follow_grain=true`;
  `material_source=shop`; per-side edges = the wizard's edge pick on sides flagged `true`.
- Each instance maps to a placement `(part_ref, part_quantity_index 1..n)`; placement
  `rotated = drawn dims are swapped vs the row orientation`.
- Row validation reuses the editor rules (≥ 50 mm sides, ≤ `MAX_IMPORT_PIECES` total
  pieces); violations are import errors listing sheet + record, never silent drops.

### 2.4 Commit endpoint — `POST /client/cutting/import/map/commit`

Request: the parsed parts rows + `map_layout` + material picks (client round-trips the
parse response; the server re-validates everything — trust level equals hand-typed parts).
Steps:

1. Validate materials (panel kind, active, carried rules identical to `_validate_parts`),
   part rows (same function), and the **layout**:
   - every sheet's dims exactly equal the picked material's `panel_length_mm ×
     panel_width_mm` (else `map_layout_material_mismatch` — wizard then offers parts-only);
   - every placement inside its sheet (clamp with the format's +5 mm tolerance, then hard
     bounds check);
   - non-waste placements must not overlap (interior intersection beyond 1 mm on either
     axis → `map_layout_overlap` with sheet/part detail);
   - placements reconcile with rows: every row's instance count equals its quantity
     (`map_layout_part_mismatch` otherwise).
2. Create the draft (`parts_snapshot` = normalized rows; ≤ 50 open drafts cap applies;
   audit `cutting_draft.create` with `details.source="map_2dplace"`).
3. Create the imported result (§2.5), set `draft.chosen_result_id` to it.
4. Return the standard draft response (result included) — the web app navigates to the
   editor.

### 2.5 The imported result

New column on `cutting_results`: `source` — enum `optimizer | imported_map`,
`server_default='optimizer'` (Alembic migration; additive; register enum per repo
migration conventions). Imported result rows:

- `source='imported_map'`, `algorithm_name="imported-2dplace-map"`,
  `algorithm_version="map-1"`, `status=CANDIDATE`, `kerf_mm=0`, `edge_trim_mm=0`
  (unknown for foreign layouts — provenance is the `source` column).
- `CuttingPanel` per sheet (`panel_index` 1..n per material), `waste_area_mm2 =
  sheet_area − Σ placed part areas` (recomputed). `CuttingPlacement` rows per §2.3.
- Recomputed metrics — never from the file: `panels_used_by_material` = sheet counts;
  `waste_percentage = Decimal(total_sheet_area − parts_area) / total_sheet_area`;
  `total_cut_length_mm` = Σ part perimeters (2D-Place display convention);
  edge maps via the existing pure `_edge_metrics` in `modules/cutting/optimizer.py`
  fed with `PartInput`s built from the rows (identical numbers to the optimizer path —
  pricing safety).
- Waste/remainder rectangles from the file are **not persisted** (waste is recomputed);
  they exist only in the parse preview.

### 2.6 Result lifecycle interplay

- `optimize_draft` currently replaces candidate results. Change: it must **preserve**
  `source='imported_map'` candidates (delete only `source='optimizer'`). The imported
  layout is the reference variant; optimiser reruns refresh only optimizer variants.
- Parts edit (`PATCH` draft → `_delete_candidate_results`) **deletes the imported result
  too** — an edited parts list no longer matches the file layout. The web editor must warn
  before the first mutating edit on a draft whose chosen result is imported
  (existing ConfirmDialog; copy in §4).
- Order placement, PDF rendering, quotes: unchanged — they read the chosen result's
  recomputed fields; verify the PDF renders an imported result via the existing
  `rendering.py` path (placements + panels exist; algorithm stamp shows the imported name).

## 3. Web

- `stores/cuttingImport.ts` + `CuttingImportWizard.vue`: third source. Steps for
  `.map`: upload (accept `.map`, detect via parse response) → materials (panel per sheet
  group with the file-name hint shown, plus single edge pick when any banded side exists)
  → preview (parts table + per-sheet mini stats: sheet count, parts count, recomputed fill
  %) → commit → `router.push` to the editor for the returned draft id.
- Editor: no new viewer work — the imported result arrives as a normal chosen result and
  renders through `CuttingResultsSection`/`CuttingPanelSvg` (verify `rotated` placements
  and part labels render; placements use the same schema). Add: (a) a provenance chip on
  the result card when `source='imported_map'` («Fayldan joylashuv»); (b) the §2.6 warning
  dialog before the first parts edit.
- Optimise CTA unchanged; after optimising, both variants are listed by the existing
  multi-variant UI and the client can switch chosen result (existing flow).

## 4. Copy (Uzbek)

- Provenance chip: `Fayldan joylashuv`
- Optimizer variant label stays as today.
- Parts-edit warning: title `Import qilingan joylashuv bekor bo'ladi`, body
  `Detallar o'zgartirilsa, fayldan olingan joylashuv o'chiriladi. Yangi joylashuv olish
  uchun qayta optimallashtiring.`
- Material-mismatch notice (wizard): `Fayldagi list o'lchami katalogdagi materialga mos
  kelmadi — faqat detallar ro'yxati import qilinadi.`

## 5. Docs (mandatory, via docs-management)

- `docs/ref/features/cutting.md`: import section gains the `.map` source and the kept-
  layout behavior (default variant, invalidation on parts edit, optimizer as second
  variant, recomputed-metrics rule); result provenance (`source`) documented.
- `docs/ref/entities/cutting.md`: `cutting_results.source` column, the imported
  `algorithm_name`, `kerf_mm=0` semantics for imported rows.

## 6. Tests

Backend (`backend/tests/`, fixtures under `tests/fixtures/cutting_import/map/` — copy real
`.map` fixtures from `../maps-print/MapsPrint.Tests/TestData`, at minimum `AFZAL.map`
(known edge truth), one multi-sheet file, one `Лист 1-3` range file, one remainder file):

1. Parser regression: sheet count/dims, part rects, waste vs remainder classification,
   companion-record edge attribution, range expansion, cp1251 names with `/`.
2. Detect: `KV_MAP` → `map_2dplace`; CSV/XML unaffected.
3. Parse endpoint: `parsed` status, `map_layout` + `material_groups` payloads.
4. Commit happy path: draft + imported result created, chosen set, metrics **recomputed**
   (assert a deliberately corrupted in-file stat does not surface anywhere).
5. Commit validation: material size mismatch, overlapping placements, row/placement count
   mismatch, >100 pieces, <50 mm part — each a typed error, nothing persisted.
6. Lifecycle: optimise keeps the imported candidate and adds an optimizer one; parts PATCH
   deletes both; order placement from an imported chosen result confirms it (existing
   sales test pattern).
7. Migration: `source` default backfills existing rows as `optimizer`.

Web: wizard source-flow spec (upload→materials→commit call), provenance chip render,
parts-edit warning emits before PATCH. E2E (optional): one journey — import fixture map →
editor shows layout → optimise → two variants → place order from imported variant.

## 7. Acceptance gates

1. `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
   && uv run pytest` — green.
2. `cd web && pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test &&
   pnpm build` — green.
3. Alembic migration applies forward on a fresh DB and on an existing DB.
4. Docs updated per §5.

## 8. Non-goals

- No automatic material matching, no mapping memory, no kerf inference from the file.
- No persistence of the file itself or its waste rectangles; no import report screen
  beyond the wizard preview.
- No manual editing of the imported layout; no comparison-diff view beyond the existing
  variant list.
- No changes to cutting-engine; no other formats (PDF, `.b3d`) in this task.
