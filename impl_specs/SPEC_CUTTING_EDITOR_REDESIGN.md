# Cutting editor redesign — parts grid, edge-tape registry, results, import UI, variant tabs

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-10
Repo: `mebel-pro`. The structure below was agreed on interactive mockups with the owner;
this document is the single source for implementation — it fully describes what the
mockups showed, plus one post-mockup owner decision: **variants are viewed one at a time
via tabs, never side-by-side.**

Relationship to other specs:
- `impl_specs/SPEC_CUTTING_IMPORT_MAP.md` — its backend part (§2) stands unchanged; its
  web part (§3) is **superseded** by §6–§7 of this spec.
- `SPEC_FOLLOW_GRAIN.md` — implemented; the Tola toggle referenced here already exists.

## 0. Process rules

- Complex-flow task per `AGENTS.md`; read `backend/AGENTS.md` and `web/AGENTS.md`; docs
  edits via the docs-management skill; visual language comes from `web/DESIGN.md` tokens —
  this spec defines structure/behavior, not new colors or type styles.
- Implement in the stage order §1→§7; every stage ends with the full web gate green.
  Stages A (backend) and B–G (web) may land as separate commits.
- All user-facing copy is Uzbek; exact strings are given in §8. No new English leaks.

## 1. Stage A — backend additions (small, additive, no behavior change)

### 1.1 Part `name`

`CuttingPart` (`backend/app/modules/cutting/schemas.py`) gains
`name: str | None = None` (max length 64, strip whitespace, empty → `None`). Stored in
`parts_snapshot` JSON — no migration. It does not affect validation, optimization, or
pricing. Old snapshots read as `None`. Frontend display fallback is `D{row_number}` —
computed in the web layer, never stored.

### 1.2 Persisted offcuts for display

`CuttingPanel` (`models.py`) gains `offcuts: list[dict] | None` (JSON, nullable) — one
Alembic migration. Each entry: `{x_mm, y_mm, length_mm, width_mm, usable: bool}`.

- Optimizer path: the engine already returns per-sheet offcut rectangles with a `usable`
  flag; the adapter (`optimizer.py` → service persistence) currently drops them — map them
  through to the panel rows.
- Imported-map path (amends `SPEC_CUTTING_IMPORT_MAP.md` §8): persist the file's
  waste/remainder rectangles as offcuts with `usable = is_remainder`. Display-only data;
  nothing prices from it.
- Panel API schema (`schemas.py` panel layout response) exposes the list (empty for old
  rows). Update `docs/ref/entities/cutting.md` accordingly.

Tests: adapter maps engine offcuts; old panels return `[]`; imported panels carry
remainder rects; `name` round-trips through draft PATCH and result snapshots.

## 2. Stage B — parts grid restructure (`web/src/shared/views/ClientCuttingEditorView.vue`, `CuttingPartRow.vue`)

### 2.1 Material grouping

Rows are visually grouped by `material_id` (order: first appearance). Each group renders a
header row: material swatch + name + summary `«N detal · X m²»` (m² = Σ length×width×qty,
1 decimal). Header click collapses/expands the group (local UI state, not persisted).
Rows keep their own `material_id` — grouping is a pure view transform; the row-level
material select moves into the row's overflow menu (`⋯`) as «Materialni almashtirish»
(opens the existing material picker). A part whose material changes moves groups.
Ungrouped fallback: rows with empty `material_id` (new rows before material pick) sit in a
leading «Material tanlanmagan» group.

### 2.2 Row layout (desktop grid)

Columns, left → right: select-checkbox · row number · **Nomi** (text input, placeholder
`D{n}`) · Bo'y · En · Soni · **Tola** (existing toggle, hidden for non-grained material) ·
**Krom** (4 numbered cells, §3) · duplicate (`⧉`) · overflow (`⋯` menu: materialni
almashtirish, o'chirish). Adjust the existing CSS grid template; mobile keeps the card
layout with the same additions (Nomi input on top of the card).

### 2.3 Keyboard-first entry

- `Enter` in any cell moves focus to the next cell in row order; `Enter` on the last cell
  of the **last row** appends a new row and focuses its Bo'y field.
- A new row inherits the previous row's `material_id`, edge picks, and `follow_grain`;
  `name` and dims start empty, `quantity` 1. (First-ever row still starts with no
  material — existing deliberate behavior.)
- Duplicate (`⧉`) inserts a copy below (name copied, focus on Bo'y).

### 2.4 Errors and deletion

- Error rows: existing per-row validation stays; add a header chip «N xato» (danger tint)
  visible when N>0; clicking toggles a filter that hides valid rows. Chip and filter reset
  automatically when errors clear.
- Row delete: no confirm dialog; the row is removed and an **undo toast** appears
  («‹Nomi› o'chirildi — Qaytarish», 6 s, restores the row at its old index). The
  clear-all-rows action keeps its ConfirmDialog. Use the existing toast primitive.

### 2.5 Header summary strip

Above the groups: `«N detal · M material · ~X m²»` + the error chip + the import button
(`Fayldan import`) — import entry stays prominent here.

## 3. Stage C — edge-tape registry

### 3.1 Registry model (derived, not stored)

The registry is a **pure derivation** from the current parts: the ordered set of distinct
`(edge material_id, source)` pairs appearing in any side pick, numbered ①② … in order of
first appearance, each assigned a color from a fixed 6-color cycle (DESIGN.md accent-safe
tints). No new persisted state; no schema change.

### 3.2 UI

- A chips row above the grid (inside the parts card header): one chip per registry entry —
  colored numbered dot + tape name; a trailing «+ Tasma» chip.
- Chip click → tape replace flow: pick another catalog edge material → **all** side picks
  using that entry switch to it (single store mutation, one autosave).
- «+ Tasma» → catalog edge picker; the picked tape joins the registry unused (available in
  cell popovers).
- Row krom cells (U·P·CH·O' = top/bottom/left/right) render the entry **number** with its
  color when banded, a muted `·` when not.
- Cell click (desktop) → popover anchored to the cell: list of registry tapes (radio),
  «Kromsiz», «Boshqa tasma…» (catalog picker), a «Manba: o'zimning tasmam» checkbox
  (maps to `source: own`), and a «To'rt tomonga qo'llash» button. Mobile: cell tap opens
  the existing `CuttingEdgePickerModal` (keep it; restyle labels to match §8 copy).
- Existing bulk edge apply (selection bar) stays and now writes registry entries.

New components: `CuttingEdgeTapeRegistry.vue`, `CuttingEdgeCellPopover.vue` (extract the
per-side pick logic shared with the modal into a composable).

## 4. Stage D — results section restructure (`CuttingResultsSection.vue`)

Order, top → bottom:

1. **Metric cards** (2×2 grid on mobile, 4-up desktop): Taxminiy narx · Listlar (with
   per-material breakdown line) · Chiqit % · Krom metr. Price comes from the existing
   quote call when a branch is chosen; without a branch the card shows «Filial tanlang».
2. **Sheet thumbnails strip**: one small SVG per panel (all materials, sequential), click
   selects; selected thumb gets the accent border. Caption under each: material short name
   + index.
3. **Single large sheet view** (existing `CuttingPanelSvg`, enhanced):
   - part labels: `name ?? D{n}` + dims, existing banded-side ticks stay;
   - rotated placements get a `↻` suffix in the label;
   - offcut rects from §1.2 render as dashed outlines — usable ones in the success tint
     with label «Qoldiq L×W — sizda qoladi», non-usable in muted/danger tint labelled
     «chiqit» (small);
   - caption above: `List {i} · {material} · {sheet dims} · KIM {x}%`.
4. **Sticky footer bar** (in-page, bottom of the results card): chosen summary
   `«N list · X% chiqit · price»` + primary CTA «Buyurtma berish» (existing order flow).

New component: `CuttingSheetThumbnails.vue`; metric cards inline in the section.

## 5. Stage E — variant tabs (owner decision: tabs, not side-by-side)

Applies whenever a draft has >1 result (imported + optimizer — and any future multi-result
case). Structure:

- A tab bar above the §4 block: one tab per result. Labels: «Fayldagi joylashuv» (imported;
  with a small «Fayldan» chip) and «Optimizer varianti». The **chosen** result's tab label
  carries a leading ✓. Exactly one tab's content is rendered at a time (§4 renders inside
  the active tab); switching tabs does NOT change the chosen result.
- Inside each tab, next to the metric cards, a select action: «Shu variantni tanlash»
  (sets `chosen_result_id` via the existing endpoint) — on the chosen one it renders as a
  static «Tanlangan ✓» state.
- **Savings banner** above the tab bar when both variants exist and their sheet counts or
  prices differ: success tint, e.g. «Optimizer 1 list kam ishlatadi — taxminan X so'm
  tejaysiz» (computed from the two results' recomputed metrics + quote prices; hidden when
  equal). Direction can favor either variant — phrase from the cheaper one's perspective.
- The §4 sticky footer always reflects the **chosen** result regardless of the active tab;
  if the user views the non-chosen tab, the footer gains a muted hint
  «Boshqa variant tanlangan».
- Single-result drafts render §4 without the tab bar (no visual change from today's flow).

New component: `CuttingVariantTabs.vue` (a11y: `role="tablist"`, arrow-key switching,
`aria-selected`).

## 6. Stage F — import wizard, `.map` flow (`CuttingImportWizard.vue`, `stores/cuttingImport.ts`)

Wizard for `source_format="map_2dplace"` (backend per `SPEC_CUTTING_IMPORT_MAP.md`):

1. **Stepper**: Fayl → Materiallar → Tekshirish (CSV keeps its existing 4-step flow; the
   stepper component becomes shared).
2. **Fayl step**: existing dropzone; on parse success show the file summary bar — file
   icon, filename, chip «2D-Place xarita», recomputed summary `«N detal · M list ·
   W×H mm»`.
3. **Materiallar step**:
   - accent info banner (always, top): «Fayldagi joylashuv saqlanadi va birinchi variant
     sifatida ko'rsatiladi. Narx va statistika qayta hisoblanadi.»;
   - one mapping row per sheet-dimension group: left — file material hint (from filename
     `OrderType`) + `«fayl nomidan · list W×H · N detal»`; right — catalog panel select.
     Under the select, a live match indicator: match → success «List o'lchami mos —
     joylashuv saqlanadi»; mismatch → warning «List o'lchami mos emas — faqat detallar
     import qilinadi» (parts-only degrade, wizard continues);
   - edge mapping row when any banded sides exist: `«N tomonda krom bor · tasma faylda
     ko'rsatilmagan»` + catalog edge select (becomes registry entry ① after import);
   - import notices (warnings list from parse) as warning banners — e.g. unnamed parts
     auto-named.
4. **Tekshirish step**: read-only parts preview (grouped as §2.1) + per-sheet mini stats +
   primary «Import qilish» → calls the commit endpoint → `router.push` to the editor for
   the returned draft; the editor opens with the imported variant chosen (tabs appear
   after the user optimises).
5. Editor guard (from the map spec): before the first parts-mutating edit on a draft whose
   imported result exists, show the existing ConfirmDialog with the §8 warning copy.

## 7. Stage G — imported-part names

`.map` part names (§2.3 of the map spec parses them) flow into the new `name` field;
unnamed → `null` (display fallback `D{n}`), with the wizard notice. Update the map spec's
aggregation key mention: grouping key already includes name — unchanged.

## 8. Copy (Uzbek, exact strings)

| Where | String |
| --- | --- |
| Name column header / placeholder | `Nomi` / `D{n}` |
| Error chip | `{n} xato` |
| Undo toast | `«{nomi}» o'chirildi` · action `Qaytarish` |
| Group summary | `{n} detal · {x} m²` |
| Registry add chip | `Tasma` (with plus icon) |
| Popover source checkbox | `Manba: o'zimning tasmam` |
| Popover apply-all | `To'rt tomonga qo'llash` |
| Popover no-edge | `Kromsiz` |
| Metric card labels | `Taxminiy narx` · `Listlar` · `Chiqit` · `Krom` |
| Offcut labels | `Qoldiq {L}×{W} — sizda qoladi` · `chiqit` |
| Sheet caption | `List {i} · {material} · {W}×{H} · KIM {x}%` |
| Tab labels | `Fayldagi joylashuv` · `Optimizer varianti` |
| Variant chip / select / selected | `Fayldan` · `Shu variantni tanlash` · `Tanlangan ✓` |
| Savings banner | `{variant} {n} list kam ishlatadi — taxminan {summa} so'm tejaysiz` |
| Footer hint (non-chosen tab open) | `Boshqa variant tanlangan` |
| Import banner | `Fayldagi joylashuv saqlanadi va birinchi variant sifatida ko'rsatiladi. Narx va statistika qayta hisoblanadi.` |
| Size match / mismatch | `List o'lchami mos — joylashuv saqlanadi` · `List o'lchami mos emas — faqat detallar import qilinadi` |
| Parts-edit guard (title/body) | `Import qilingan joylashuv bekor bo'ladi` / `Detallar o'zgartirilsa, fayldan olingan joylashuv o'chiriladi. Yangi joylashuv olish uchun qayta optimallashtiring.` |

## 9. Tests

Backend: §1.1/§1.2 items listed there.

Web unit (Vitest, colocated `__tests__`):
- grouping selector: order by first appearance, ungrouped bucket, group summaries;
- registry derivation: numbering by first appearance, color stability, replace-tape
  mutation rewrites all matching side picks in one commit;
- popover: per-side set / clear / apply-all / own-source emit shapes;
- keyboard: Enter progression, last-cell append + inheritance, duplicate-row;
- undo toast: restore at original index, timeout removal;
- error chip filter show/hide;
- thumbnails: selection state, caption text;
- sheet SVG: rotated `↻` label, offcut rendering (usable vs not), name fallback `D{n}`;
- variant tabs: render only with >1 result, ✓ on chosen, switching does not mutate
  chosen, select action calls the store, savings banner math + hidden-when-equal;
- wizard `.map` flow: step progression, match/mismatch indicator branches, commit call +
  navigation.

E2E (extend `cutting-drafts.spec.ts`, keep small): enter two parts via keyboard flow →
optimise → thumbnails visible → place order. If the map-import backend is present in the
same build: import fixture map → tabs visible → switch → choose optimizer → order.

## 10. Acceptance gates

1. Backend gate green (`ruff check`, `ruff format --check`, `mypy app`, `pytest`).
2. Web gate green (`lint:check`, `format:check`, `typecheck`, `test`, `build`).
3. Docs updated: `docs/ref/features/cutting.md` (editor UX: grouping, name, registry,
   variant tabs — replaces the current editor description; result view structure) and
   `docs/ref/entities/cutting.md` (part `name`, panel `offcuts`).
4. Existing flows unbroken: single-result drafts show no tab bar; drafts created before
   this change render (missing `name`/`offcuts` tolerated).

## 11. Non-goals

- Excel-paste into the grid, sample-data button, per-part comment field — separate later
  passes.
- No side-by-side variant view (explicit owner decision — tabs only).
- No workshop-side surfaces; client editor only.
- No changes to optimization, pricing, or the map-import backend contract.
