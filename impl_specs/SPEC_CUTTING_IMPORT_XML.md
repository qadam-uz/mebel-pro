# Cutting import — add БАЗИС-Мебельщик «Спецификация в XML» — Implementation Spec

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-09
Repo: `mebel-pro`. **Delta spec** against the implemented CSV importer
(`SPEC_CUTTING_IMPORT.md` / `..._V2_CSV_ONLY.md`): backend
`app/modules/cutting/imports/` + `import_schemas.py` + `/client/cutting/import/parse`,
frontend `CuttingImportWizard.vue` + `stores/cuttingImport.ts`, tests
`backend/tests/test_cutting_import.py` + `web/.../cuttingImport.spec.ts`.

## 0. Read first, and process rules

- Complex-flow task per `AGENTS.md` — follow `.workflows/playbooks/complex.md`; docs via
  **docs-management**; UI via **ui-ux-mastery**/**frontend-design**; test placement via
  **testing-practices**. Read `backend/AGENTS.md` / `web/AGENTS.md`.
- **Prerequisite:** the CSV importer (V2) and per-part `follow_grain` are merged. This
  spec adds XML as a **second source format that produces the same IR** — it does not
  change the CSV path, the material-picking step, the report step, or the load step.
- **Grounded in the official schema.** The mapping in §2 is taken from БАЗИС-Центр's
  «Структура файла спецификации в формате XML» (`XML_structure.pdf`, 2023-12-04). Element
  names are Russian/Cyrillic and are matched **case-sensitively as documented**. Where a
  side-index or dimension-field choice can't be 100% confirmed without a real export, the
  decision is stated **and** flagged "verify against the committed fixture" — pin it when
  building the fixture (§5), do not invent beyond the schema.
- Target the **built-in «Спецификация в XML»** (Формирование проекта → *Спецификация в
  XML*), whose root is `<Проект>`. The script-based `Экспорт XML.js` (ObjTree) emits a
  different, flatter shape — **out of scope**; detection (§3.3) only accepts the `<Проект>`
  schema and rejects anything else as `unsupported_format`.
- No DB migration. Parse stays stateless (no storage, no draft, no `action_log`).

## 1. Why XML is simpler than CSV here

The XML is self-describing, so **there is no column-mapping step**. Everything the CSV
path needed a human to map is an explicitly named element:

| CSV needed… | XML gives directly |
| --- | --- |
| user maps which column is length/width | `Длина` / `Ширина` on each `Объект` |
| user maps the material column | `ОсновнойМатериал` on each `Объект` |
| guess grain from a "Текстура" column | `ОриентацияТекстуры` enum |
| guess 4 edge columns | `СписокКромок1..4` |
| footers/blank rows to skip | typed objects — filter by `ТипОбъекта` |
| can't tell rectangular vs shaped | `Прямоугольная` enum (Y/N) |

Consequence: **for an XML file the parse endpoint returns `status:"parsed"` on the first
call** (no `needs_mapping`), and the wizard skips step 2 (§4). The material-picking,
report, and load steps are byte-for-byte the CSV flow.

## 2. Element → IR mapping (the whole contract)

Root `<Проект …>` → one or more `<Изделие>` → `<СписокЭлементов>` → many `<Объект>`.
We flatten **all** products' objects into one parts list.

### 2.1 Which objects become parts

Read `Объект/ТипОбъекта`. Import **only `Панель`**. Every other type (`Фурнитура`,
`Сборка`, `Полуфабрикат`, `Профиль`, `Отверстие`, `Блок`, …) is **not a part**:

- Not reported as a "skipped row" (a screw is not a failed part — that would be noise).
- Counted once: `ignored_object_count` (new IR field, §3.4) → the report shows
  "N ta panel bo'lmagan obyekt e'tiborsiz qoldirildi (furnitura, yig'malar)."

### 2.2 One `Объект` (ТипОбъекта=Панель) → one `ImportedPart`

| IR field | XML source | Rule |
| --- | --- | --- |
| `length_mm` | `Длина_детали_без_облицовки` → else `Длина` | saw-cut size preferred over the finished (with-tape) size, because our edge model adds tape separately; parse via the CSV number rule (comma decimal, spaces stripped), round half-up to int mm (warning `dimension_rounded`). Missing/≤0/>10000 → skipped row `non_numeric_length` / `dimension_not_positive` / `dimension_too_large`. **verify field choice against the fixture.** |
| `width_mm` | `Ширина_детали_без_облицовки` → else `Ширина` | same rule (`non_numeric_width`) |
| `quantity` | `Объект/Количество` × parent `Изделие/Количество` | each defaults to 1 when absent/non-integer; the **product multiplier applies** (a product placed 3× multiplies its parts). Non-integer/≤0 on either → skipped row `quantity_not_integer` / `quantity_not_positive`. |
| `follow_grain` | `Объект/ОриентацияТекстуры` | `Горизонтальная` or `Вертикальная` → `true` (oriented → don't rotate); `Не задана` or absent → `false`. **Known lossy point:** our model always aligns length-to-grain, so `Горизонтальная` (grain across width) still imports as `follow_grain=true`; we do not model cross-grain. Acceptable (most panels are `Вертикальная`); note it, don't block. |
| `material_key` | `Объект/ОсновнойМатериал` → `Наименование` (+ ` ` + `Код` when present) | distinct-key = casefolded collapsed text (same rule as CSV); label = first-seen original. Absent `ОсновнойМатериал` → `__unspecified__` group. |
| `edges.top/bottom/left/right` | `СписокКромок1/2/3/4` → first child `Кромка` | side 1→top, 2→bottom, 3→left, 4→right (matches the CSV Д1/Д2/Ш1/Ш2 convention: length-sides first, width-sides next). **verify side order against the fixture.** A `СписокКромокN` with no `Кромка` child, or absent → that side `null`. Edge group key/label from `Кромка/Наименование` (+ `Код`); grouped like panels for manual catalog picking. `СписокКромокСМЧертеж` (edges marked "see drawing") → ignored for banding, contributes to the ops warning (§2.3). |

`row` (IR): synthetic 1-based index in panel-encounter order — used only for report
references (XML has no line numbers).

### 2.3 Operations we cut through but flag (nothing silent)

A panel imports as its `Длина×Ширина` rectangle regardless; when the object carries
geometry we don't reproduce, add a per-row warning (does **not** skip the part):

| Condition | Warning code |
| --- | --- |
| `Объект/Прямоугольная` = `N` | `non_rectangular` (we import the bounding rectangle) |
| `Объект/Отверстия` has ≥1 `Отверстие` | `ignored_holes` |
| `Объект/СписокПазов` has ≥1 `Паз` | `ignored_grooves` |
| `Объект/СписокКромокСМЧертеж` non-empty | `edge_see_drawing` (a banded side we can't resolve to a tape) |

These four join the existing warning set (`dimension_rounded`, `quantity_defaulted`,
`grain_token_unknown`) — same `{code, rows[]}` shape, shown in the report.

### 2.4 Explicitly ignored (read nothing into the IR)

`ОблицовкаПласти1/2` (face lamination — not edge tape), `ПорядокОблицовкиПласти`,
`СписокОпераций`/`Сдельная операция`, `СопутствующиеМатериалы`,
`ДополнительныеМатериалы`, `ДобавленоВручную`, `Раскрой` (Bazis's own cut stats),
`Цена`/`Стоимость`/`Масса`, project/product-level `ОсновнойМатериал`. Cutting needs only
geometry + panel material + per-side tape.

## 3. Backend — `backend/app/modules/cutting/imports/`

### 3.1 Files & deps

- New `imports/bazis_xml.py` — `parse_bazis_xml(content: bytes) -> ImportParsedResponse`.
- `imports/detect.py` — add `sniff_format(content, filename) -> Literal["csv","bazis_xml"]`
  (§3.3); the existing `ensure_csv` becomes one branch.
- `imports/__init__.py` / `parser.py` — `parse_import_file(...)` becomes a **dispatcher**:
  detect → XML: return `parse_bazis_xml(content)` (ignore `options`); CSV: today's flow.
- `uv add defusedxml` (pinned). Parse with
  `defusedxml.ElementTree.fromstring(content)` — XML-bomb/entity-safe. Pass **bytes**
  (not a pre-decoded str) so the `<?xml encoding=…?>` declaration is honored (Bazis emits
  windows-1251 or utf-8). mypy: add `[[tool.mypy.overrides]]` for `defusedxml.*`
  (`ignore_missing_imports = true`), mirroring `openpyxl.*`.
- Reuse from `parser.py`: `_parse_number`, `_distinct_key`, `_cell_text`, the
  `_GroupRegistry`, `_add_warning` — factor them into `imports/common.py` if importing
  across modules is awkward; do not duplicate.

### 3.2 Endpoint contract change (`routes.py`, unchanged URL)

`POST /api/v1/client/cutting/import/parse` — after reading ≤1 MiB+1:

1. `sniff_format(content, filename)`.
2. `bazis_xml` → `parse_bazis_xml(content)` → **`ImportParsedResponse`** directly
   (`options` ignored; there is no mapping/skip-rows for XML).
3. `csv` → existing behavior (`needs_mapping` then `parsed`).

Both wrapped in the existing `ImportParseError → APIError(422)` handling. Runs under
`anyio.to_thread.run_sync` like today.

### 3.3 Detection order (`detect.py`)

Terminal, content wins over extension:

1. Size gate (unchanged): >1 MiB → `file_too_large`; 0 bytes → `empty_file`.
2. Leading bytes are a ZIP (`PK\x03\x04`) or OLE2 (`\xd0\xcf\x11\xe0`) → `unsupported_format`
   (xlsx/legacy-xls; re-save as CSV/XML message).
3. Sniff XML: strip a leading BOM/whitespace; if it starts with `<?xml` **or** `<Проект`
   → **XML path**. If it is XML but the root element is not `Проект` (after parsing) →
   `unsupported_format` with a message naming «Спецификация в XML» (rejects the ObjTree
   script export and unrelated XML). Decode for the sniff only enough to test the prefix;
   the real parse uses the byte content + declared encoding.
4. Otherwise → CSV path (existing `decode_csv_text` cp1251/utf-8 chain, delimiter sniff).

### 3.4 IR / schema additions (`imports/base.py`, `import_schemas.py`)

- `SourceFormat` gains `"bazis_xml"` (alongside `"csv"`); surface it in
  `import_schemas.py` and the TS mirror.
- New `WarningCode`s: `non_rectangular`, `ignored_holes`, `ignored_grooves`,
  `edge_see_drawing`.
- `ImportParsedResponse` gains `ignored_object_count: int = 0` (additive; CSV always 0).
- `ImportedPart`, groups, `ImportSkippedRow`, `total_parts`, `total_pieces`,
  `MAX_IMPORT_PIECES` (100) — unchanged and reused. The >100 cap fires the same
  `too_many_parts` (422) after flattening products × parts.

### 3.5 Parser rules (`bazis_xml.py`)

- Iterate `.//Изделие`; per product read `Количество` (product multiplier, default 1);
  iterate its `СписокЭлементов/Объект`.
- Per `Объект`: if `ТипОбъекта != "Панель"` → `ignored_object_count += 1`, continue.
- Else map per §2.2/§2.3, appending an `ImportedPart` (quantity = part × product) and any
  warnings; register panel and edge groups.
- Missing required geometry → a skipped row (same reasons/preview shape as CSV; `preview`
  = the object's `Наименование` truncated to 40).
- Element text read helper: trimmed text of a child element or `""`; numbers via the
  shared `_parse_number`.
- Whitespace-only / empty products contribute nothing (no error).

## 4. Frontend — `web/src/shared/`

### 4.1 Wizard skips the mapping step for XML (`CuttingImportWizard.vue`)

- Step 1 (file) is unchanged except copy: the help block now names **both** exports
  (§5 copy). `accept=".csv,.xml"`; the client-side extension pre-check allows both.
- After the parse call:
  - `status === "needs_mapping"` (CSV) → step 2 (column mapping) as today.
  - `status === "parsed"` (XML) → **jump straight to step 3 (materials)**; the stepper
    renders 3 steps (`Fayl · Materiallar · Xulosa`) instead of 4 when
    `source_format === "bazis_xml"`.
- Steps 3 (material picking) and 4 (report + append/replace load) are **unchanged** —
  they already consume the IR. The report additionally renders the new warnings and, when
  `ignored_object_count > 0`, the "N ta panel bo'lmagan obyekt…" line.

### 4.2 `stores/cuttingImport.ts`

- Add `"bazis_xml"` to the `SourceFormat` union and `"non_rectangular" | "ignored_holes"
  | "ignored_grooves" | "edge_see_drawing"` to `ImportWarningCode`; add
  `ignored_object_count` to `ImportParsedResponse`.
- `parseCuttingImport` is unchanged (same endpoint/FormData); for XML the caller simply
  won't send `options`.
- `buildImportedParts` / `applyImportedParts` — **unchanged** (IR is identical).

### 4.3 Frontend tests

- Store spec: an XML `parsed` response with `ignored_object_count` + new warnings maps to
  `CuttingPart[]` correctly (grain, per-side edges, product-multiplier quantity).
- Wizard spec: `source_format === "bazis_xml"` renders the 3-step flow and never shows the
  column-mapping step; the new warnings + ignored-object line render in the report.

## 5. Copy (Uzbek, inline)

- Help block (both formats): `БАЗИС-Мебельщик'da: Формирование проекта → «Спецификация в
  CSV» yoki «Спецификация в XML». Hosil bo'lgan faylni shu yerga yuklang.`
- Stepper (XML): `Fayl · Materiallar · Xulosa`
- New warnings: `non_rectangular` → `To'rtburchak emas — chegara o'lchami olindi`,
  `ignored_holes` → `Teshiklar e'tiborsiz qoldirildi (biz faqat kesamiz)`,
  `ignored_grooves` → `Pazlar e'tiborsiz qoldirildi`, `edge_see_drawing` → `«См. чертеж»
  kromkasi aniqlanmadi — qo'lda tekshiring`.
- Ignored objects: `{n} ta panel bo'lmagan obyekt e'tiborsiz qoldirildi (furnitura,
  yig'malar)`.
- `unsupported_format` (XML branch): `Bu XML «Спецификация в XML» formati emas. БАЗИС-
  Мебельщик'dan Формирование проекта → «Спецификация в XML» orqali saqlang.`

## 6. Fixtures & backend tests

`backend/tests/fixtures/cutting_import/` add **`bazis_mebelshik_spec.xml`** — a hand-built
file that mirrors `XML_structure.pdf`, declaring `encoding="windows-1251"` and covering:

1. `<Проект Версия="…">` with **two** `<Изделие>`, one having `Количество="2"` (proves the
   product multiplier).
2. Panels (`ТипОбъекта=Панель`) across **two** distinct `ОсновнойМатериал` values.
3. One panel per texture case: `ОриентацияТекстуры` = `Вертикальная`, `Горизонтальная`,
   `Не задана`.
4. Per-side edges: a panel with all four `СписокКромок1..4`, one with only 1&2, one with
   none; two distinct `Кромка` names.
5. A non-panel object (`ТипОбъекта=Фурнитура`) → exercises `ignored_object_count`.
6. A `Прямоугольная=N` panel, a panel with `Отверстия`, a panel with `СписокПазов` →
   exercise each ops warning.
7. One panel missing `Ширина` → a skipped row.
8. (Build the fixture from a real export if the workshop can provide one; otherwise pin
   the side-order and dimension-field choices here and note them in the test.)

Tests in `test_cutting_import.py` (new cases; keep the CSV cases green):

- `sniff_format`: `<?xml…>` and bare `<Проект>` → `bazis_xml`; non-`Проект` XML →
  `unsupported_format`; CSV/xlsx/ole2 branches unchanged.
- First parse call on the XML fixture returns `status="parsed"` (never `needs_mapping`).
- Exact IR: `total_parts` / `total_pieces` (with the ×2 product applied), the two panel
  groups, edge groups, per-part `follow_grain` for the three texture cases, per-side edge
  mapping (1→top…4→right), each ops warning on the right synthetic row, the missing-width
  skipped row, `ignored_object_count == 1`.
- Encoding: the windows-1251 fixture decodes via the `<?xml?>` declaration (no manual
  decode); a utf-8-declared variant also parses.
- `too_many_parts`: a product `Количество` large enough to push pieces >100 → 422.
- An XML-bomb / billion-laughs payload → rejected by defusedxml (asserts we don't expand
  entities), surfaced as `unsupported_format` / `invalid_file` (pick one code and assert
  it).

## 7. Acceptance gates

1. Backend: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run
   mypy app && uv run pytest` — green, incl. §6.
2. Web: `cd web && pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test &&
   pnpm build` — green.
3. E2E already covers the CSV import journey; **add one** XML assertion only if the
   journey exists — upload the XML fixture, confirm the wizard shows 3 steps (no mapping)
   and lands parts in the editor. Don't build a new journey.
4. Docs (§8) updated.

## 8. Docs (source of truth — via docs-management)

- `docs/ref/features/cutting.md` — the import subsection: the upload mode now accepts
  `.csv` **and** `.xml` (БАЗИС «Спецификация в XML»); XML skips column mapping (named
  elements); same manual material picking, same report/append-replace. Add the edge
  cases: non-`Проект` XML rejected, non-panel objects counted-not-imported, non-rectangular
  / holes / grooves flagged-not-dropped, product×part quantity multiplier.
- Limits table: `Import file ≤ 1 MiB · csv / bazis-xml`.
- Keep frontmatter `updated:` current.

## 9. Non-goals (do not partially build)

- **The ObjTree script export (`Экспорт XML.js`)** and any non-`Проект` XML — rejected,
  not parsed.
- **No holes/grooves/CNC geometry** into the model — flagged only (guillotine-only stays).
- **No cross-grain modelling** — `Горизонтальная` imports as `follow_grain=true`; we don't
  add a per-part grain-direction field.
- **No dimension-variant picker** in the UI — the `без_облицовки`→`Длина` fallback is
  fixed in the parser (revisit only if a real file proves it wrong).
- No pulling price/mass/operations/hardware from the XML — geometry + panel + edges only.
- No auto material matching (unchanged owner decision): every distinct `ОсновнойМатериал`
  / `Кромка` is picked manually from the catalog on every import.
