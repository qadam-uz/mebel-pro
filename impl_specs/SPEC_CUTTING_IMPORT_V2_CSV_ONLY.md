# Cutting import V2 — CSV-only, tuned for БАЗИС-Мебельщик — Implementation Spec

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-05
Repo: `mebel-pro`. This is a **delta spec** against the implemented V1
(`SPEC_CUTTING_IMPORT.md`): backend `app/modules/cutting/imports/` +
`import_schemas.py` + the `/client/cutting/import/parse` route, frontend
`CuttingImportWizard.vue` + `stores/cuttingImport.ts`, tests
`backend/tests/test_cutting_import.py` and `web/.../cuttingImport.spec.ts`.

## 0. Read first, and process rules

- Complex-flow task per `AGENTS.md` — follow `.workflows/playbooks/complex.md`; docs via
  **docs-management**; UI via **ui-ux-mastery**/**frontend-design**;
  test placement via **testing-practices**. Read `backend/AGENTS.md` / `web/AGENTS.md`.
- Owner decisions this spec encodes (2026-07-05):
  1. **XLSX support is removed. Only `.csv` is accepted.** Rationale: the primary real
     source is БАЗИС-Мебельщик's built-in «Спецификация в CSV» (Мебель toolbar /
     Формирование проекта — official doc: Drawings.pdf ch. 7); Мебельщик has no direct
     XLSX export. Excel users convert with «Сохранить как → CSV».
  2. The CSV parser is **tuned to Мебельщик's export realities** (§3).
- The internal API may change shape with a coordinated deploy (bundled SPAs are the only
  consumers — `docs/architecture.md`), so response fields are removed outright, no
  compatibility shims.
- V1 principles stay in force: no auto-matching, nothing silent (one documented
  exception in §3.3), parse = representability / editor = validity.

## 1. Backend — file-by-file

### 1.1 `imports/detect.py`

- `detect_source_format(...)` → replace with `ensure_csv(content, filename) -> None`:
  - starts with `PK\x03\x04` (xlsx/zip) → `ImportParseError("unsupported_format", ...)`
  - starts with `\xd0\xcf\x11\xe0` (OLE2 = legacy .xls) → same error
  - extension not in `{"", ".csv"}` → same error
  - otherwise return; the caller proceeds on the CSV path unconditionally.
- `unsupported_format_message()` → new copy (§5). One message for every rejected shape —
  it names both conversion paths (Мебельщик CSV button, Excel save-as-CSV).
- `decode_csv_text` / `sniff_csv_delimiter` — unchanged.

### 1.2 `imports/base.py`

- Delete `ImportSourceFormat`; delete `source_format` from both response models.
- Delete `sheet` from `ImportParseOptions` (pydantic ignores stray extras — no shim);
  delete `sheet_names` + `sheet` from `ImportNeedsMappingResponse`.
- Error codes `invalid_file` and `sheet_not_found` are gone; the remaining set is exactly:
  `unsupported_format`, `file_too_large`, `empty_file`, `invalid_mapping`,
  `too_many_parts`.
- `ImportRole` gains `"thickness_mm"` (and `IMPORT_ROLES` likewise).
- `ImportPanelMaterialGroup` gains `thickness_hint: str | None = None` (§3.3).
  `ImportEdgeMaterialGroup` is unchanged (tape thickness lives in its label).

### 1.3 `imports/spreadsheet.py` → rename to `imports/parser.py`

- Rename the module (update `imports/__init__.py` re-export and test imports); the
  public `parse_import_file(filename, content, options)` signature is unchanged.
- Delete `_read_xlsx`, `_sheet_grid`, the openpyxl import, and the xlsx branch of
  `_read_workbook`; `_WorkbookGrid` collapses to just `grid` (drop
  `source_format`/`sheet_names`/`sheet` — a bare `Grid` return is fine).
- `parse_import_file` starts with `_ensure_file_size` → `ensure_csv` → `_read_csv`.
- Header-guesser token table changes (matching rules unchanged — casefold, equality or
  startswith, single-char tokens equality-only):
  - `thickness_mm` (new): `толщина`, `thickness`, `qalinlik`
  - `material` adds: `наименование материала`
  - `edge_top` adds: `облицовка д1`, `кромка l1`
  - `edge_bottom` adds: `облицовка д2`, `кромка l2`
  - `edge_left` adds: `облицовка ш1`, `кромка w1`
  - `edge_right` adds: `облицовка ш2`, `кромка w2`

### 1.4 Dependencies and config

- `cd backend && uv remove openpyxl` (lockfile updates); delete the `openpyxl.*` mypy
  override block from `pyproject.toml`.
- `routes.py` needs no change (the `ImportParseResponse` union narrows via
  `import_schemas.py`, which re-exports from `base.py`).

## 2. What stays untouched (asserted, not re-decided)

File gates (1 MiB / empty), encoding chain (UTF-16-BOM → utf-8-sig → cp1251), delimiter
sniff + `;` tie rule, decimal commas, the §3.6/3.7 V1 row-classification and value tables,
skip reasons, warnings, `__all__`/`__unspecified__` grouping, 100-piece cap, two-call
protocol (first call always `needs_mapping`), thread offload in the route, manual material
picking on every import.

## 3. Мебельщик-format tuning

### 3.1 Blank lines between models («Добавлять пустую строку между моделями»)

Already covered: a fully-empty row is the one silent skip. Add an explicit fixture + test
(§4) so the behavior is pinned.

### 3.2 Repeated header rows (project export, «Одним файлом» mode)

A header row repeated mid-file parses as a skipped row (`non_numeric_length`, preview =
first cell, e.g. `Позиция`). This is **accepted and documented** — it shows up honestly
in the step-4 report; no silent header detection inside data. Test pins it.

### 3.3 `thickness_mm` role — a display hint, never a matcher

Мебельщик spec CSV typically carries «Толщина». Captured only to help the user pick the
right catalog material in step 3:

- Per row: value through the existing `_parse_number`; result kept when `> 0`, else the
  row simply contributes no hint — **this is the one exception to "nothing silent"**,
  allowed because the hint is advisory display, not part data.
- Per panel group: collect distinct values (format: integral → `"16"`, else trimmed
  decimal `"16.5"`); `thickness_hint` = values sorted numerically, joined `" / "`
  (e.g. `"16"` or `"16 / 18"`); `None` when no row contributed.
- Never used for matching or stored on parts. Not collected for edge groups.

### 3.4 «По материалам» mode (one file per material, no material column)

Covered by `__all__`. The material name lives in the **file name**, so step 3 must show
the uploaded file name (§5 frontend). Multiple files are imported one at a time with
**Qo'shish** (append) — batch upload stays a non-goal.

### 3.5 «Припуск» allowances

Dimensions arrive as the designer exported them (possibly inflated by заготовка
allowance). Imported as-is; no detection, no warning. The help block does not mention it
(v1 keeps instructions minimal).

## 4. Fixtures and tests

Fixtures (`backend/tests/fixtures/cutting_import/`):

- **Delete** `bazis_raskroy.xlsx`.
- **Keep** `bazis_cp1251.csv` (Раскрой-style save: cp1251, `;`, decimal commas, Итого
  footer) and `bazis_mebelshik_spec.csv` (no material column, blank row between models,
  renamed headers).
- **Add** `bazis_mebelshik_project.csv` — «Одним файлом» project export: `Материал` +
  `Толщина` columns, two models separated by a blank line **and a repeated header row**,
  cp1251, `;`. Exercises §3.1–3.3 in one file (two panel groups with thickness hints
  `"16"` and `"18"`, repeated header in skipped_rows, invisible blank line). The
  mixed-thickness hint (`"16 / 18"` within one group) is pinned by a unit test with
  inline rows, not by this fixture.

Test changes (`test_cutting_import.py`):

- Delete `_xlsx_bytes` and every xlsx-parse test. Rejection table becomes:
  `PK\x03\x04...` bytes, OLE2 bytes, `foo.txt` extension, binary junk — **all** →
  `unsupported_format` (the `invalid_file` case is gone).
- Update imports to `imports.parser`; drop `sheet`/`source_format` assertions.
- New tests: thickness hint aggregation (`"16"`, `"16 / 18"`, absent), guesser matches
  `Толщина`/`Облицовка Д1`/`Наименование материала`, blank-line skip, repeated-header
  skipped row, full parse over `bazis_mebelshik_project.csv` asserting exact IR.

Web tests (`cuttingImport.spec.ts` + wizard spec): drop sheet-selector and
`sheet_not_found` cases; add file-name display and thickness-chip rendering; update the
client-side extension check to `.csv` only.

## 5. Frontend — `CuttingImportWizard.vue` + `stores/cuttingImport.ts`

- Types: remove `source_format`, `sheet_names`, `sheet`, `options.sheet`; remove
  `sheetName` state, the sheet selector block, and `detectFile`'s sheet parameter;
  payload never includes `sheet`. Remove the `sheet_not_found` error mapping.
- File input: `accept=".csv"`; client-side extension check `.csv` only.
- Step 1 file-type hint text: `CSV (*.csv)`.
- Step 3: show `Fayl: {file.name}` above the group list (covers «По материалам» — the
  material name is usually the file name); panel group rows render a muted chip
  `{thickness_hint} mm` when `thickness_hint` is non-null.
- Copy changes:
  - Help block body: `БАЗИС-Мебельщик'da: Мебель panelidagi «Спецификация в CSV»
    tugmasini bosing (butun loyiha uchun — «Формирование проекта» oynasidagi shu tugma).
    Excel'da tayyorlangan ro'yxat bo'lsa: Файл → Сохранить как → CSV. Hosil bo'lgan
    faylni shu yerga yuklang.`
  - `unsupported_format` (backend and the client-side pre-check use the same text):
    `Bu fayl turi qo'llab-quvvatlanmaydi — faqat CSV. БАЗИС-Мебельщик'da «Спецификация
    в CSV» orqali, Excel'da «Сохранить как → CSV» qilib saqlang.`

## 6. Docs (mandatory, via docs-management)

- `docs/ref/features/cutting.md`: upload mode is `.csv` only — update the mode-switch
  sentence, the wizard subsection (no sheet step; thickness hint in the material-picking
  description; file name shown), and the limits table row (`Import file ≤ 1 MiB · csv
  only`). Name Мебельщик's «Спецификация в CSV» as the expected source.
- Frontmatter `updated:` current.

## 7. Acceptance gates

1. `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
   && uv run pytest` — green; `grep -r openpyxl backend/app backend/pyproject.toml` →
   no hits; `uv.lock` no longer contains openpyxl.
2. `cd web && pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test &&
   pnpm build` — green; `grep -rn "xlsx" web/src/shared/components/CuttingImportWizard.vue
   web/src/shared/stores/cuttingImport.ts` → no hits.
3. Manual walk with `bazis_mebelshik_project.csv`: repeated header appears in the report,
   two material groups with thickness chips, blank line invisible, load succeeds.
4. Docs updated per §6.

## 8. Non-goals (decided)

- **No XLSX** (this spec removes it; the IR design keeps re-adding it possible later as
  its own task). No `.txt`/XML/JSON/GibLab — unchanged from V1.
- **No material-as-section-header grouping** (`Материал <name>` rows spanning following
  rows). Such rows surface as skipped rows. Revisit only against a real workshop file
  that actually uses sections — then it becomes a small deterministic rule, its own task.
- No multi-file batch upload (append flow covers «По материалам»).
- No thickness-based auto-matching or filtering of the catalog picker.
- Наименование/Позиция still not captured (V1 decision stands).
