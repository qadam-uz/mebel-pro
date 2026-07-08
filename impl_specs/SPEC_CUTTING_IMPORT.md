# Cutting import from XLSX/CSV — Implementation Spec

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-05
Repo: `mebel-pro` (backend + web + docs together).

## 0. Read first, and process rules

- This is a **complex-flow** task per `AGENTS.md` — read `.workflows/playbooks/complex.md`
  and follow it. Docs edits under `docs/` follow the **docs-management** skill; UX work
  follows **ui-ux-mastery** / **frontend-design**; test placement follows
  **testing-practices**.
- Read `backend/AGENTS.md` and `web/AGENTS.md` before touching those trees.
- **Prerequisite:** the per-part `follow_grain` work (`SPEC_FOLLOW_GRAIN.md`) is merged.
  This spec assumes `CuttingPart.follow_grain: bool = True` exists on both backend and
  frontend.
- **Deliberate spec correction:** `docs/ref/features/cutting.md` currently says the parts
  editor has an upload mode *"(`.bas` / `.xlsx`; disabled in v1 with a 'Coming soon'
  pill)"*. `.bas` is not a real Базис-Мебельщик export format (research 2026-07-05: real
  ones are `.b3d`/`.oblx`/`.cutwork` [proprietary] and xlsx/csv/PDF/DXF [open]). This spec
  **implements** the upload mode as XLSX/CSV and §6 updates the doc. Not a conflict to
  re-raise.
- No DB migration anywhere in this task. The parse endpoint is stateless: no file storage
  (no MinIO), no draft creation, no DB writes, no `action_log` row (nothing mutates).

## 1. Scope — what we import, and the three fixed principles

**Accepted:** `.xlsx` (Excel OOXML) and `.csv` (delimited text). That covers both real
Bazis sources: **БАЗИС-Мебельщик**'s built-in «Спецификация в CSV» (the Мебель toolbar /
Формирование проекта dialog — no Раскрой module needed; columns are user-configurable
and renamable, so there is no fixed header set; official doc: Drawings.pdf ch. 7) and
**БАЗИС-Раскрой**'s Файл → Сохранить как → xlsx/csv — plus any other CAD or hand-made
spreadsheet. Мебельщик CSV realities the parser must survive: an optional **blank line
between models** (covered by the silent empty-row skip), the **«По материалам» split
mode** where each file is one material and carries **no material column** (covered by the
`__all__` single-group path — the material name lives in the file name, which the wizard
shows), and dimensions possibly inflated by the optional «припуск» allowance (imported
as-is; not our concern).

**Rejected with a clear error, never parsed:** `.xls` (legacy BIFF — error message tells
the user to re-save as `.xlsx`), `.b3d`, `.obl`, `.oblx`, `.cutwork`, `.txt`, XML, JSON,
PDF, everything else.

Three principles every decision below follows:

1. **No guessing.** Materials are never auto-matched; the user picks every material from
   the platform catalog on every import. Column-role guesses and encoding/delimiter
   sniffing are allowed *only* where the user confirms the result in the wizard before it
   takes effect (column mapping) or where the result is deterministically verifiable
   (encoding).
2. **Nothing silent.** Every skipped row, defaulted value, and rounded number is listed in
   the import report before the user confirms loading. Fully-empty rows are the single
   exception (skipped without mention).
3. **Parse decides representability; the editor decides validity.** The parser excludes a
   row only when it literally cannot represent it (non-numeric required cell). Domain
   violations (part < 50 mm, > usable panel area, > 100 pieces total with existing rows)
   import fine and are flagged by the editor's existing validation — they are recoverable
   typos, not data to discard.

## 2. Flow overview

```
Editor "Fayldan yuklash" mode
  → step 1: pick file (client-side size pre-check)
  → POST /import/parse (no mapping)      → { status: "needs_mapping", grid, guesses }
  → step 2: column mapping (user confirms; sheet selector; skip-rows counter)
  → POST /import/parse (with mapping)    → { status: "parsed", IR }
  → step 3: material picking (client-side only — no API call)
  → step 4: report + load (append/replace) → parts land in the editor state
```

- The **first parse call always returns `needs_mapping`**, even when every guess is
  confident — the user always confirms the mapping. This removes any "when do we skip the
  step" ambiguity.
- Material picking is pure client-side substitution (`material_key → material_id`); the
  file is not re-sent after step 2 unless the user goes back and changes
  sheet/mapping/skip-rows (each change re-calls parse).
- Loading writes into the editor's parts state exactly like manual row adds. **No draft is
  created** — the existing lifecycle holds: first Optimise mints the draft. Import is
  available in the unsaved editor and in a mutable `draft` (autosave picks the change up);
  the mode switch is absent in the `confirmed` read-only view.

## 3. Backend — `backend/app/modules/cutting/`

### 3.1 Layout and dependencies

```
app/modules/cutting/
  imports/
    __init__.py       # re-exports parse_import_file
    base.py           # IR pydantic models, ImportParseError, error codes
    detect.py         # content sniffing, encoding/delimiter detection
    spreadsheet.py    # xlsx + csv readers → uniform grid; header guesser;
                      # row classification; value parsing; grouping
  import_schemas.py   # request/response API schemas (extend APIModel)
  api.py              # + parse_import_file(...) public export
  routes.py           # + one route
```

- `uv add openpyxl` (pinned via lockfile). `python-multipart` already ships with
  `fastapi[standard]`. No other new dependency.
- mypy: add a `[[tool.mypy.overrides]]` block for `openpyxl.*` with
  `ignore_missing_imports = true` (same precedent as `reportlab.*`).
- Parsing is synchronous CPU work → the route runs it via `anyio.to_thread.run_sync`
  (backend convention: no blocking work inline in a handler).

### 3.2 Endpoint contract

`POST /api/v1/client/cutting/import/parse` — same client auth dependency as the other
client cutting routes (`AccountReadyPrincipal`). Multipart form:

| Field | Type | Notes |
|---|---|---|
| `file` | file | required |
| `options` | string (JSON) | optional; `{"sheet": str?, "skip_rows": int?, "mapping": {role: col_index}?}` |

`mapping` absent → **detection call** → `needs_mapping` response.
`mapping` present → **full parse** → `parsed` response.

**`needs_mapping` response:**

```json
{
  "status": "needs_mapping",
  "source_format": "xlsx" | "csv",
  "sheet_names": ["Лист1", "..."],        // csv → ["CSV"]
  "sheet": "Лист1",                        // the sheet that was scanned
  "grid": [["Позиция", "Длина", null, ...], ...],  // ≤ 15 rows × ≤ 20 cols, stringified cells
  "guessed_mapping": {"length_mm": 2, "width_mm": 3},  // may be partial or {}
  "guessed_skip_rows": 1
}
```

**`parsed` response (the IR):**

```json
{
  "status": "parsed",
  "source_format": "xlsx",
  "parts": [
    {
      "row": 4,                       // 1-based sheet row, for report references
      "length_mm": 720, "width_mm": 450, "quantity": 2,
      "material_key": "m1",
      "follow_grain": true,
      "edges": {"top": "e1", "bottom": "e1", "left": null, "right": null}
    }
  ],
  "panel_materials": [
    {"key": "m1", "label": "ЛДСП EGGER H1334 16мм", "part_count": 14}
  ],
  "edge_materials": [
    {"key": "e1", "label": "0.4 H1334", "side_count": 22}
  ],
  "skipped_rows": [
    {"row": 21, "reason": "non_numeric_length", "preview": "Итого:"}
  ],
  "warnings": [
    {"code": "dimension_rounded", "rows": [7, 9]},
    {"code": "quantity_defaulted", "rows": [12]}
  ],
  "total_parts": 46,
  "total_pieces": 61
}
```

**Error responses** — HTTP 422, the module's existing error envelope (same shape the
optimize route uses), with exactly these codes:

| Code | When |
|---|---|
| `unsupported_format` | content is neither xlsx-zip nor decodable text; or a `.xls` BIFF file (message names the fix: re-save as .xlsx) |
| `file_too_large` | > 1 MiB (checked by reading at most 1 MiB + 1 byte) |
| `empty_file` | zero bytes; or no non-empty cell in the scan window of any sheet |
| `invalid_file` | xlsx that openpyxl cannot open (corrupt, password-protected) |
| `sheet_not_found` | `options.sheet` names no sheet in the workbook |
| `invalid_mapping` | required role missing, unknown role, column index ≥ 30, or two roles on one column |
| `too_many_parts` | sum of parsed quantities > 100 (message includes the count and says to split the file) |

### 3.3 Format detection and file gates (`detect.py`)

Order of checks — content wins over extension, every branch terminal:

1. Size gate: read up to 1 MiB + 1 byte; over → `file_too_large`. Zero bytes →
   `empty_file`.
2. Bytes start `PK\x03\x04` → **xlsx path** (openpyxl; failure to open →
   `invalid_file`).
3. Bytes start `\xd0\xcf\x11\xe0` (OLE2 = legacy `.xls`) → `unsupported_format` with the
   re-save message.
4. Otherwise **text path**: decode with the first succeeding of — UTF-16 (only if a
   UTF-16 BOM is present) → `utf-8-sig` (strict) → `cp1251` (always succeeds). Result
   feeds the CSV reader. If the decoded text contains `\x00` (binary junk that survived) →
   `unsupported_format`.

CSV delimiter: run `csv.Sniffer` on the first 4096 chars restricted to `;`, `\t`, `,`;
if it raises, count each candidate's occurrences in the first non-empty line and take the
max; tie → `;` (RU-locale default, since `,` is the decimal separator). Quote char `"`,
`csv` stdlib dialect otherwise.

### 3.4 Grid rules (both formats)

Both readers produce the same in-memory grid; every rule below applies to both.

- **Scan window:** first **2000 rows × 30 columns**. Cells outside are ignored (never an
  error — the 100-piece cap fires long before 2000 rows on any real file).
- **XLSX:** `openpyxl.load_workbook(read_only=True, data_only=True)`. Formula cells yield
  their cached value; no cached value → empty cell. Merged cells: value lives on the
  anchor cell only, the rest read as empty (read-only behavior; no un-merging).
  `datetime`/`bool` cells in numeric roles → non-numeric (row error). Sheet selection:
  `options.sheet` by name; default = first sheet (workbook order) containing ≥ 1
  non-empty cell in the scan window; none → `empty_file`.
- **CSV:** one pseudo-sheet named `CSV`; `options.sheet` is ignored.
- **Grid preview** (needs_mapping): first 15 rows × 20 columns, each cell `str(value)`
  trimmed, empty → `null`.

### 3.5 Column roles and the header guesser

Exactly these roles exist — no others (Наименование/Позиция are deliberately **not**
captured; see §8):

| Role | Required | Empty-cell behavior |
|---|---|---|
| `length_mm` | **yes** | row error `non_numeric_length` |
| `width_mm` | **yes** | row error `non_numeric_width` |
| `quantity` | no (unmapped → every part qty 1) | qty 1 + warning `quantity_defaulted` |
| `material` | no (unmapped → single group `__all__`) | group `__unspecified__` |
| `follow_grain` | no (unmapped → all `true`) | `true` |
| `edge_top` `edge_bottom` `edge_left` `edge_right` | no | that side `null` |

Guesser: a pure function over the first `min(5, rows)` rows; the first row where ≥ 2
header tokens match becomes the header row; `guessed_skip_rows` = its 1-based index.
Token dictionary (case-insensitive, trimmed, matched on equality or startswith), kept as
data in `spreadsheet.py` so tests pin it:

- `length_mm`: `длина`, `length`, `l`, `uzunlik`, `bo'y`, `boy`
- `width_mm`: `ширина`, `width`, `w`, `eni`, `kenglik`
- `quantity`: `количество`, `кол-во`, `кол.`, `шт`, `qty`, `soni`, `dona`, `miqdor`
- `material`: `материал`, `material`, `плита`, `лдсп`
- `follow_grain`: `текстура`, `ориентация`, `tola`, `grain`, `направление`
- `edge_top`/`edge_bottom`: `д1`/`д2`, `l1`/`l2`, `кромка д1`/`кромка д2`
- `edge_left`/`edge_right`: `ш1`/`ш2`, `w1`/`w2`, `кромка ш1`/`кромка ш2`

(Bazis convention: Д1/Д2 are the two length-side edges → top/bottom; Ш1/Ш2 the
width-side edges → left/right. Fixed assignment, in that order.)

No matches → `guessed_mapping: {}`, `guessed_skip_rows: 0`; the user maps manually.
Guesses are suggestions only — the parse call uses exclusively the mapping the client
sends back.

### 3.6 Row classification (full parse)

Data rows = grid rows strictly after `skip_rows` (default: the value the client sends,
which the wizard seeded from `guessed_skip_rows`).

For each data row, look only at mapped cells:

| Case | Outcome |
|---|---|
| All mapped cells empty | skipped **silently** (the one silent case) |
| ≥ 1 mapped cell non-empty, length+width parse as valid numbers, qty valid | **part** |
| ≥ 1 mapped cell non-empty, a required numeric fails | **skipped row** in the report: `{row, reason, preview}` where `preview` = first non-empty cell string (≤ 40 chars) — this is how `Итого`-style footers surface honestly |

Skip reasons (exact set): `non_numeric_length`, `non_numeric_width`,
`non_numeric_quantity`, `quantity_not_integer`, `quantity_not_positive`,
`dimension_not_positive`, `dimension_too_large`.

### 3.7 Value parsing — decision table

| Input | Rule |
|---|---|
| Numeric string | strip regular/NBSP/thin spaces (thousands seps), `,` → `.`, then Python `float()`; NaN/±inf → non-numeric |
| `length_mm` / `width_mm` | must be > 0 and ≤ 10 000 after parse (else `dimension_not_positive` / `dimension_too_large`); fractional → round half-up to int mm + warning `dimension_rounded` for that row. Values < 50 mm **import** (editor's existing min-bound validation flags them) |
| `quantity` | must parse to an exact integer (2.0 ok, 2.5 → `quantity_not_integer`); ≥ 1 (0/negative → `quantity_not_positive`); empty cell with mapped column → 1 + `quantity_defaulted` |
| `follow_grain` | truthy set `{да, есть, +, 1, true, ha, v, ✓, x, х}` → `true`; falsy set `{нет, -, 0, false, yo'q, yoq}` → `false`; empty → `true`; any other token → `true` + warning `grain_token_unknown` for that row. Matching is case-insensitive, trimmed |
| `material` cell | trimmed, inner whitespace collapsed; **distinct-key** = casefolded form; **label** = first-seen original form (display truncates at 160 chars in UI only) |
| `edge_*` cell | falsy set `{empty, -, 0, нет, yo'q, yoq}` → side `null`; anything else → edge-material reference, same distinct-key/label rule as material (a bare thickness like `0.4` is a legitimate group the user maps to a catalog tape) |

Grouping: `panel_materials` = distinct material keys in part order, plus `__all__`
("whole file", when the material role is unmapped) or `__unspecified__` (mapped column,
empty cells) when applicable — both behave as ordinary groups the user must assign.
`edge_materials` = distinct edge keys across all four side columns.

Caps, applied after parsing all rows: `total_pieces = Σ quantity` > 100 →
`too_many_parts` (422; nothing partial is returned).

### 3.8 Backend tests (`tests/test_cutting_import.py` + `tests/fixtures/cutting_import/`)

Fixtures (committed binaries/text, small):

1. `bazis_raskroy.xlsx` — mimics the БАЗИС-Раскрой save-as shape: header row, Позиция /
   Наименование / Длина / Ширина / Количество / Материал / Текстура / Д1 / Д2 / Ш1 / Ш2,
   an `Итого` footer row, one merged title cell above the header.
2. `bazis_cp1251.csv` — cp1251, `;`-delimited, decimal commas, Текстура `+`/`-`.
3. `minimal.csv` — three columns L/W/Qty, no header, no material column.
4. `multisheet.xlsx` — empty first sheet, data on the second.
5. `encrypted.xlsx`, `legacy.xls` (or a crafted OLE2 header), `binary.bin`, `empty.csv`.
6. `too_many.csv` — quantities summing to 101.
7. `bazis_mebelshik_spec.csv` — Мебельщик «Спецификация в CSV» in «По материалам» mode:
   cp1251, `;`, **no material column**, a blank row between two models, user-renamed
   headers (`Кол-во`, `Кромка Д1`…) — exercises `__all__` grouping + silent empty-row
   skip + guesser partial matches.

(Fixtures 1, 2 and 7 already exist in `tests/fixtures/cutting_import/` — they are
spec-faithful replicas built from the official manuals, not genuine Bazis output; validate
against one real workshop file before shipping and adjust if the real layout differs,
e.g. material-as-section-header rows instead of a material column.)

Unit coverage (pure functions): content sniffing branches (§3.3 order), encoding
fallback chain incl. UTF-16-BOM and cp1251, delimiter sniff + tie rule, header-guesser
dictionary (each role, and the ≥2-tokens header-row rule), every row in the §3.7 table,
every skip reason in §3.6, distinct-key normalization (case/whitespace variants
collapse), Д1→top/Д2→bottom/Ш1→left/Ш2→right assignment.

Endpoint coverage: first call always `needs_mapping`; full parse over fixture 1 asserts
exact IR (counts, groups, skipped `Итого` row with reason + preview, `dimension_rounded`
rows); every 422 code in §3.2 has one test; auth required (401 without principal);
`invalid_mapping` on duplicate column and on missing `length_mm`.

## 4. Frontend — `web/src/shared/`

### 4.1 Entry point

`ClientCuttingEditorView.vue` gets the mode switch the feature doc foresees: **«Qo'lda
kiritish»** (default) · **«Fayldan yuklash»**. Selecting the second opens the import
wizard (a modal dialog on desktop, full-screen sheet on mobile — follow the edge picker's
existing responsive pattern). The switch is hidden entirely in the `confirmed` read-only
view. Closing/cancelling the wizard at any step discards all wizard state and leaves the
editor untouched; the mode flips back to manual.

### 4.2 Wizard — four steps, exact behavior

**Step 1 — file.** `<input type="file" accept=".xlsx,.csv">`; client-side pre-checks
(size ≤ 1 MiB, extension in the accept list) show the same error copy as the backend
codes. A collapsed **«Bazis'dan qanday eksport qilinadi?»** help block (copy in §5).
Picking a file immediately fires the detection call; on `needs_mapping` → step 2.

**Step 2 — column mapping.** Renders the grid preview (first 15 rows); above each column
a role dropdown seeded from `guessed_mapping` (blank = ignored column); a **skip-rows**
stepper seeded from `guessed_skip_rows` (skipped rows render dimmed in the grid); a sheet
dropdown, shown only when `sheet_names.length > 1` (changing it re-fires the detection
call for that sheet). **Davom etish** is disabled until `length_mm` and `width_mm` are
each assigned to exactly one column; assigning a role already used elsewhere clears it
from the other column (the UI therefore cannot produce `invalid_mapping`). Confirming
fires the full parse; 422 errors render inline in this step.

**Step 3 — materials.** One list, panel groups first, then edge groups. Each group row:
the source `label` verbatim (this is the user's only clue — never abbreviate it), the
part/side count, and a catalog picker — the **same picker components the parts editor
uses** (`panel`-kind picker for panel groups, edge-material picker for edge groups),
including the `preferred_branch_id` pre-filter + "Show all catalog" behavior. `__all__`
renders as «Butun fayl uchun material», `__unspecified__` as «Material ko'rsatilmagan
qatorlar». **Davom etish** is disabled until every group has a selection — there is no
"skip this material" path (conservative principle; the user can delete rows in the editor
afterwards instead).

**Step 4 — report + load.** Shows: `total_parts` / `total_pieces`; the skipped-rows list
(row number, reason in Uzbek, preview text); warnings grouped by code with row numbers;
and — when current editor pieces + imported pieces > 100 — a non-blocking notice that
Optimise will refuse until rows are removed. Buttons: empty editor → single **«Yuklash»**;
non-empty editor → **«Qo'shish»** (append below existing rows) and **«Almashtirish»**
(replace; styled as the existing danger actions and guarded by the same confirm pattern as
"Clear parts list"). Never a silent replace.

### 4.3 Applying the IR (pure client-side)

For each IR part, build a `CuttingPart` exactly as manual add does:

- `part_ref`: new uuid (same generator as manual rows).
- `material_id`: the group's picked id; `material_source: 'shop'` (files carry no
  own/shop concept; flip afterwards in the editor if needed).
- `length_mm/width_mm/quantity/follow_grain`: from IR verbatim.
- `edge_<side>`: IR side key `null` → `null`; else
  `{ material_id: <picked id for that edge group>, source: 'shop' }`.

Append = concat after existing rows; replace = swap the array. Both mark results stale
exactly like manual edits (existing mechanism); in a saved draft, autosave persists the
new snapshot; in the unsaved editor the rows live locally until first Optimise.

### 4.4 Code placement and tests

- Wizard state + API call live in a new `stores/cuttingImport.ts` (or composable —
  follow whichever pattern `useDraftAutosave.ts` set); the parse call goes through
  `shared/api/client.ts`. Components under `shared/components/` next to the other
  cutting pieces (`CuttingImportWizard.vue` + small step components as needed).
- Unit tests: IR+picks → `CuttingPart[]` mapping (follow_grain passthrough, edge side
  mapping, source defaults); step gating (step 2 requires L/W roles; step 3 requires all
  groups assigned); append vs replace semantics; cancel discards state.
- E2E: only if `e2e` already walks the editor — one happy path with `minimal.csv`
  (upload → map 3 columns → pick one material → load → rows appear). Do not build a new
  journey beyond that.

## 5. Copy (Uzbek, inline strings as the codebase does)

- Mode switch: `Qo'lda kiritish` / `Fayldan yuklash`
- Wizard title: `Fayldan import` · steps: `Fayl` · `Ustunlar` · `Materiallar` · `Xulosa`
- Help block title: `Bazis'dan qanday eksport qilinadi?` · body: `БАЗИС-Мебельщик'da:
  Мебель panelidagi «Спецификация в CSV» tugmasini bosing (butun loyiha uchun —
  «Формирование проекта» oynasidagi shu tugma). БАЗИС-Раскрой bo'lsa: Файл → Сохранить
  как → Excel (*.xlsx) yoki CSV. Hosil bo'lgan faylni shu yerga yuklang.`
- Step 2: `Qaysi ustun nimani bildiradi?` · skip stepper: `Yuqoridan o'tkazib yuborish:
  {n} qator` · roles: `Uzunlik (mm)`, `Kenglik (mm)`, `Soni`, `Material`, `Tola`,
  `Kromka: yuqori/past/chap/o'ng` · ignored option: `—`
- Step 3: `Katalogdan mos materialni tanlang` · `__all__`: `Butun fayl uchun material` ·
  `__unspecified__`: `Material ko'rsatilmagan qatorlar` · counts: `{n} ta detal` /
  `{n} ta tomon`
- Step 4: `{parts} ta detal ({pieces} dona) tayyor` · skipped:
  `O'tkazib yuborilgan qatorlar` · buttons: `Yuklash` / `Qo'shish` / `Almashtirish` ·
  over-cap notice: `Jami {n} dona — 100 dan oshadi, Optimise uchun qatorlarni kamaytiring`
- Skip reasons: non_numeric_* → `raqam emas`, quantity_not_integer → `soni butun son
  emas`, quantity_not_positive → `soni 1 dan kichik`, dimension_not_positive → `o'lcham
  noto'g'ri`, dimension_too_large → `o'lcham 10 m dan katta`
- Warnings: dimension_rounded → `O'lcham mm gacha yaxlitlandi`, quantity_defaulted →
  `Soni ko'rsatilmagan — 1 deb olindi`, grain_token_unknown → `Tola belgisi
  tushunarsiz — "bo'ylab" deb olindi`
- Errors: unsupported_format → `Bu fayl turi qo'llab-quvvatlanmaydi. Excel (*.xlsx) yoki
  CSV yuklang; eski *.xls faylni Excel'da *.xlsx qilib qayta saqlang`, file_too_large →
  `Fayl 1 MB dan katta`, empty_file → `Fayl bo'sh`, invalid_file → `Fayl ochilmadi —
  buzilgan yoki parol bilan himoyalangan`, too_many_parts → `Faylda {n} dona detal — bir
  optimallashtirishga eng ko'pi 100 dona. Faylni bo'lib yuklang`

## 6. Docs (source of truth — mandatory, via docs-management)

- `docs/ref/features/cutting.md` — rewrite the parts-editor mode-switch sentence: the
  upload mode is **implemented**, accepts `.xlsx` / `.csv`, and opens the import wizard.
  Add a subsection describing the wizard (four steps, always-confirmed column mapping,
  manual material picking on every import — no auto-matching by design, report before
  load, append/replace). Add the edge cases: unsupported/oversized/empty file, `Итого`
  footers surfacing as skipped rows, imported sub-50 mm parts flagged by editor
  validation, over-100 pieces rejected at parse. Remove `.bas` everywhere.
- `docs/ref/features/cutting.md` limits table: add `Import file ≤ 1 MiB · xlsx/csv only`.
- No entity doc changes (`parts_snapshot` shape is untouched — import produces ordinary
  parts).
- Keep frontmatter `updated:` current.

## 7. Acceptance gates

1. Backend: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run
   mypy app && uv run pytest` — green, incl. every §3.8 case.
2. Web: `cd web && pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test &&
   pnpm build` — green.
3. Manual walk: fixture 1 (`bazis_raskroy.xlsx`) end-to-end — Итого row appears in the
   report, Д1/Д2/Ш1/Ш2 land on the right sides, Текстура `-` rows import with
   `follow_grain: false`, loaded rows optimise successfully.
4. Docs updated per §6 (a gate, not a nice-to-have).

## 8. Non-goals (decided, do not partially implement)

- **No GibLab XML, no Bazis export script, no `.xls`/`.txt`/JSON input.** The IR design
  admits new parsers later without wizard changes; adding them is a separate task.
- **No automatic material matching, no mapping-memory table, no column-mapping presets
  persistence, no thickness/size hint extraction from material strings.** Owner decision
  2026-07-05: the user picks manually on every import.
- **Наименование/Позиция columns are not captured.** `CuttingPart` has no name/label
  field, and cutting-map placements are deliberately labelled by dimensions (existing
  product decision). Adding a label field would be new surface across rendering/PDF —
  out of scope; revisit only as its own task.
- No import on the workshop/admin apps; client editor only.
- No file persistence, no import history, no audit row (nothing mutates).
- No new i18n infrastructure — inline Uzbek strings like the rest of the editor.
