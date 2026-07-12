# Cutting PDF — Bazis-grade detailed document — Implementation Spec

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-12
Repo: `mebel-pro`. **Delta spec** against the implemented one-page-per-sheet print
(`backend/app/modules/cutting/rendering.py`, public `render_cutting_pdf` re-exported
via `api.py`, served by `routes.py:177` / `:293`), tests
`backend/tests/test_cutting_rendering.py`, docs `docs/ref/features/cutting.md`.
Reference model: БАЗИС-Раскрой print form, studied from the official user manual
(«Модуль БАЗИС Раскрой — Руководство пользователя», cdn.bazissoft.ru, 2026 edition;
statistics block fig. 10.4, panel/cut-list settings §10.5–10.6, report set fig. 17.1).

## 0. Read first, and process rules

- **What we adopt from Bazis** (the parts that serve a cutting workshop and derive
  from data we already have): the title block, the per-sheet parts table, the
  two-KIM statistics, a summary (general-report) page with per-material stats +
  edge-tape specification + usable-offcut inventory, and identical-sheet grouping
  («Количество плит = N»).
- **What we deliberately do differently**: material-level statistics live in the
  summary page's table, not cramped above the first map (modern layout, same data);
  banded sides are marked with **edge-registry numbers** (①②…) instead of Bazis's
  underline convention — richer and consistent with the web editor.
- **Explicit non-goals** (§8): cut list (список резов) — needs the guillotine cut
  sequence from the engine; labels/бирки, barcodes, накладные, Word/Excel exports,
  machine postprocessors.
- **Print-parity rule updated:** the PDF stops being a bare mirror of the
  visualiser and becomes a superset document. The parity contract **narrows to the
  map panel**: the sheet drawing inside the PDF (placements, offcut overlays +
  label ladder, banding ticks, label fitting) keeps mirroring `CuttingPanelSvg.vue`
  one-for-one; page composition around it is PDF-own. Update the rendering.py
  docstring and the docs statement accordingly (this also amends the §0 parity
  wording of `SPEC_CUTTING_RESULTS_POLISH.md` — same scope, narrower object).
- Uzbek copy throughout (§4); Cyrillic-capable DejaVu fonts already vendored.
- Backend-only spec. No schema, endpoint-URL, or web change (the download button
  stays as is). Runs under the existing thread-offload path.

## 1. Document structure (the contract)

All pages are **A4 portrait**, fixed. Order: one summary page, then sheet pages.

### 1.1 Page 1 — Xulosa (general report)

1. **Title block** (top, boxed): `Mebel Pro — kesish xujjati` wordmark line;
   left column `Buyurtma: {order_number | chizma {draft-short-id}}` ·
   `Mijoz: {client_name?}` · `Filial: {branch_name?}`; right column
   `Sana: {generated_at:%d.%m.%Y}` · `Listlar: {total}` · `Detallar: {pieces} dona`.
   Unknown context fields render as `—` (§3.2).
2. **Materiallar table** — one row per panel material:
   `Material (full generated name) · List o'lchami · Listlar soni · Detallar (dona)
   · Detal maydoni m² · Qoldiq m² (usable) · Chiqit m² · KIM % · KIM (qoldiq bilan) %`.
   Totals row underneath.
3. **Kromka spetsifikatsiyasi** — one row per tape in registry order:
   `① · tape full name · {metres} m` (shop+own summed; when `own > 0` add
   ` (shu jumladan o'zingizniki {m})`). Empty → `Krom ishlatilmagan.`
4. **Sizda qoladigan qoldiqlar** — usable offcuts inventory grouped by
   `(material, L×W)`: `{material short} · {L}×{W} mm · {n} dona`, largest area
   first. Empty → omit the section.

### 1.2 Sheet pages — one per **distinct** layout

1. **Title block** (compact, boxed, Bazis-shtamp analog):
   `Material: {full name} · {sheet L}×{W} mm` / `List {i}[–{j}] · jami {total}` /
   `{n} dona list` (grouping §2.3; n=1 renders `1 dona`) / `Buyurtma · Sana`
   (short repeats).
2. **Stat line** (single line under the block):
   `To'ldirish {x}% · Detallar {a} m² · Qoldiq {q} m² · Chiqit {w} m²`.
3. **Map panel** (upper ~55% of the content area): the existing sheet drawing
   (outline, placements, offcut overlays with the label ladder, banding ticks),
   scaled to fit the fixed frame; **part labels gain the position number**:
   `#{pos} {name} {L}×{W}{ ↻}`.
4. **Detallar table** (below the map) — rows for parts on THIS layout:
   `# · Nomi · O'lcham (mm) · Dona · Д1 · Д2 · Ш1 · Ш2 · Tekstura`.
   - `#` = 1-based index of the part in `parts_snapshot` (the web grid's row
     number); same number as on the map label.
   - `Dona` = placements of that part on this layout (per single sheet).
   - `Д1/Д2/Ш1/Ш2` = length/length/width/width sides (top/bottom/left/right,
     the web grid convention): registry number when banded, `·` when not.
   - `Tekstura` = `→` when `follow_grain` else `·`.
   - Overflow: if rows don't fit, continue the table on a follow-on page with the
     same title block + `(davomi)`; never shrink below 8 pt.

## 2. Data derivations

### 2.1 Two KIM figures (per material and total)

- `sheet_area = Σ sheets × L×W`; `parts_area = Σ placement L×W`;
  `usable_offcut_area = Σ usable offcuts`; `waste = sheet_area − parts_area −
  usable_offcut_area`.
- `KIM = parts_area / sheet_area` · `KIM (qoldiq bilan) = (parts_area +
  usable_offcut_area) / sheet_area`. Render `52.9% / 97.3%` style, one decimal.
- Existing `waste_percentage` stays untouched (API unchanged); the PDF computes
  its own figures from placements/offcuts so the document is self-consistent.

### 2.2 Edge registry (Python mirror)

`_derive_edge_registry(parts_snapshot) -> list[(key, number)]` — first-use order
over parts in snapshot order, sides in `top, bottom, left, right` order, key
`material_id:source` — **byte-for-byte the web rule** (`deriveEdgeRegistry` /
`syncEdgeAssignments` in `cuttingEditorDerived.ts`). One shared fixture table
(parts → expected numbers) is asserted on both sides (§5). Numbers render as
`①`-style circled digits 1–20 (DejaVu covers U+2460..2473), plain `(21)` beyond.

### 2.3 Identical-sheet grouping

Group **consecutive** panels of the same material whose placement multisets match
on `(x_mm, y_mm, length_mm, width_mm, part_ref)` (quantity indexes ignored) and
whose offcut sets match. A group renders one sheet page titled `List {i}–{j}` +
`{n} dona list`; the summary counts all n. Non-consecutive identical layouts stay
separate (keep it simple; the optimizer emits repeats consecutively).

## 3. Backend changes

### 3.1 File layout

- `rendering.py` → keeps the **map-drawing primitives** (sheet transform, offcut
  ladder, band ticks, placement labels) — parity scope per §0 — plus a new
  `draw_sheet_map(pdf, frame, result, panel, parts_by_ref, registry)` entry that
  draws into a given rectangle (extracted from today's page loop).
- New private `pdf_document.py` — owns the document: context dataclass, summary
  page, sheet title blocks/stat lines, tables, pagination, identical-sheet
  grouping, registry derivation; exposes the public
  `render_cutting_pdf(result, context)` .
- `api.py` re-export switches to `pdf_document.render_cutting_pdf`; `routes.py`
  call sites updated. Public name unchanged for external callers.

### 3.2 `PdfContext`

`@dataclass class PdfContext: order_number: str | None = None; client_name: str |
None = None; branch_name: str | None = None; generated_at: datetime | None = None`
(None → now, UTC→local not attempted — render date only).
Routes pass what they have: the draft-scoped endpoints (`routes.py:177` area) pass
`order_number=None` (title falls back to `chizma {result.draft_id.hex[:8]}`); the
order-scoped PDF endpoints (client/workshop order routes) pass the order number and
branch name they already resolve. Keep changes to routes mechanical — no new
queries beyond what the handlers already load; a handler that doesn't have a field
passes None.

### 3.3 Sizing & style

- A4 portrait everywhere (`_page_size_for_panel` dies). Map frame: full content
  width, fixed height; sheet scaled to fit, centered.
- Tables: hairline gray rules, bold header row, DejaVu 8.5–9 pt body, zebra none
  (print friendliness), grayscale except the existing offcut success/danger and
  the accent-gray banding ticks (unchanged from parity scope).

## 4. Copy (Uzbek, inline)

- Summary: `Kesish xujjati` · `Buyurtma` · `Chizma` · `Mijoz` · `Filial` · `Sana` ·
  `Listlar` · `Detallar` · `Materiallar` · `List o'lchami` · `Detal maydoni` ·
  `Qoldiq` · `Chiqit` · `KIM` · `KIM (qoldiq bilan)` · `Jami` ·
  `Kromka spetsifikatsiyasi` · `shu jumladan o'zingizniki` · `Krom ishlatilmagan.` ·
  `Sizda qoladigan qoldiqlar`.
- Sheet: `List {i}–{j} · jami {n}` · `{n} dona list` · `To'ldirish` · `(davomi)` ·
  table header `# · Nomi · O'lcham (mm) · Dona · Д1 · Д2 · Ш1 · Ш2 · Tekstura`.
- Map labels/offcut copy unchanged (parity scope).

## 5. Tests (`test_cutting_rendering.py`, split a `test_cutting_pdf_document.py` if unwieldy)

Assert via extracted text/content streams as the existing tests do:

- Summary page: material full names, sheets counts, both KIM figures (pin a
  fixture where they differ sharply — e.g. parts 40% + usable offcut 50% →
  `40.0%` and `90.0%`), edge rows in registry order with metres, offcut inventory
  line `{L}×{W} mm · {n} dona`, `—` fallbacks with an empty context.
- Registry parity: the shared fixture table (same parts as the web
  `cuttingEditorDerived` spec) → same numbers; circled-digit glyphs present.
- Sheet page: title block `List 1 · jami N`, stat line, table row per part with
  correct `Д1/Д2/Ш1/Ш2` numbers and `·` gaps, `#` matches the map label, `→` for
  `follow_grain`.
- Grouping: two identical consecutive panels → one page `List 1–2` + `2 dona
  list`, summary still counts 2; a differing offcut breaks the group.
- Table overflow: >28 parts on one sheet → `(davomi)` page appears, header
  repeated.
- Page size: every page exactly A4 portrait.
- Existing map-drawing tests (offcut ladder, ticks, label fitting) keep passing —
  they now target `draw_sheet_map` through the document.
- Web: **one** addition — export the shared registry fixture from the
  `cuttingEditorDerived` spec (or duplicate the table verbatim with a comment
  naming the Python twin) so drift is caught on either side.

## 6. Acceptance gates

1. `cd backend && uv run ruff check . && uv run ruff format --check . && uv run
   mypy app && uv run pytest` — green.
2. Web/e2e untouched — run `cd e2e && pnpm typecheck && pnpm test` to confirm the
   download journey still passes.
3. Manual pass (verify skill): regenerate the 27-part/2-material draft's PDF;
   rasterize (`sips`, page-extract via pypdf) and eyeball: summary page reads like
   the Bazis «Общий отчет» analog, sheet pages show map + table with matching `#`
   and registry numbers, Uzbek text renders (DejaVu embedded — `strings x.pdf |
   grep DejaVu`), the two KIM figures are plausible against the web KPIs.
4. Docs (§7) updated.

## 7. Docs (source of truth — via docs-management)

- `docs/ref/features/cutting.md` — PDF subsection rewritten: document composition
  (summary page + grouped sheet pages + parts tables), the two-KIM definitions,
  registry numbers shared with the editor, and the **narrowed parity statement**:
  "the map panel inside the PDF mirrors the web sheet visualiser; the surrounding
  document is PDF-own." Keep frontmatter `updated:` current.

## 8. Non-goals (do not partially build)

- **No cut list (список резов)** — requires the guillotine cut sequence/lengths
  from the cutting engine; a future spec once the engine exposes its cut tree
  (see the engine-optimization phase notes). Do not approximate cuts from
  placements here.
- **No cut count / cut length / rotations / size-setups stats** — same data
  dependency; the stat line carries only area-derived figures.
- **No бирки/labels, no barcodes, no накладные, no Word/Excel/txt exports, no
  machine postprocessors** — out of the operating envelope.
- **No per-variant or per-order pricing on the PDF** — pricing lives in the order
  flow; this is a production document.
- **No landscape/format options or user-configurable report templates** — one
  good default, Convention over Configuration.
