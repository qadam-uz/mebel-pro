# Catalog material identity — generated name · edge width · picker width guidance — Implementation Spec

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-12
Repo: `mebel-pro`. **Delta spec** against the implemented catalog module: backend
`app/modules/catalog/` (models, service, schemas), web `AdminMaterialsView.vue` +
`adminMaterials.ts` + `stores/admin.ts`, cutting editor edge picking
(`cuttingEdgeDisplay.ts`, `CuttingEdgePickerModal.vue`, `CuttingEdgeTapeRegistry.vue`),
seed `deploy/seed-demo.sh`, docs `docs/ref/entities/catalog.md` +
`docs/ref/features/catalog-inventory.md` + `docs/ref/features/cutting.md`.

## 0. Read first, and process rules

- Cross-module change (API surface + schema) — plan/track natively; docs via
  **docs-management**; test placement via **testing-practices**. Read
  `backend/AGENTS.md` / `web/AGENTS.md` before touching each side.
- Three agreed decisions, one spec (they interlock — the generated name embeds the new
  width field):
  1. **`Material.name` stops being an input.** The column stays `NOT NULL`; a single
     server-side composer generates it from structured fields (including the
     manufacturer's name) on every create/update.
  2. **`edge_width_mm`** — new required dimension for `edge` materials (tape width).
     One decor in two widths = two catalog rows, same philosophy as one spec in two
     panel sizes.
  3. **Edge picker guides by width, never blocks.** Soft warning when tape is
     narrower than the panel edge; width-fit joins the existing decor/colour ranking
     (CB-130). Rationale (owner decision, 2026-07-12): a hard width filter would block
     the legitimate *thickened-edge* flow — a 42 mm tape picked on an 18 mm part whose
     edge is doubled to 36 mm by a glued strip. The system cannot see the physical
     edge, so it must not veto.
- **Docs conflict, resolved deliberately:** `docs/ref/entities/catalog.md` currently
  rules "manufacturer rendered separately, **not embedded in the name**". That rule
  guarded hand-written names against drift; with a generated name drift is impossible,
  and embedding the manufacturer keeps the name self-contained where it travels alone
  — order-line snapshots copy only `material.name`
  ([sales/service.py:1814](../backend/app/modules/sales/service.py)), action-log
  summaries, PDFs. **The docs rule flips** (owner decision, 2026-07-12); §8 updates it.
- **Thickened edges themselves need no feature.** The flat parts model already handles
  them by decomposition (strip = its own part, `follow_grain=true`, no tape on mating
  sides, wide tape on the visible side). This spec only unlocks the wide-tape half
  (width on the material + non-blocking picker). No helper UI in v1.
- API surface changes are **breaking for `name`** (create/patch no longer accept it) —
  acceptable pre-launch; the only callers are the admin SPA and `seed-demo.sh`, both
  updated here.

## 1. Name composition (the contract)

One function owns it: `compose_material_name(...)` in
`backend/app/modules/catalog/service.py` (private helper; takes the manufacturer's
display name as an argument). Called on create and on every patch that touches a
source field or the manufacturer. Nothing else writes `Material.name`.

```
panel:  "{TYPE} {manufacturer} {decor_code}? · {color} · {length}×{width}×{thickness} mm"
edge:   "Kromka {manufacturer} {decor_code}? · {color} · {thickness}×{edge_width} mm"
```

- `TYPE` label map (module-level dict): `dsp → "LDSP"`, `mdf → "MDF"`,
  `plywood → "Fanera"`, `natural_wood → "Yog'och"`, `other → "Panel"`.
- `manufacturer` is the `Manufacturer.name` as stored (e.g. `Kronospan`).
- The `decor_code` segment is omitted when empty; it sits inside the first segment
  (`"LDSP Kronospan K003"`).
- Dimension segments follow **trade notation**, one per kind (owner decision,
  2026-07-12): panels are the price-list triple `L×W×T mm` (`2750×1830×18 mm` — how
  boards are written on invoices and in Bazis bases), edges are the tape notation
  **thickness×width** (`2×19 mm`). Thickness-only scanning is covered by the existing
  thickness filters in pickers, not by the name.
- `thickness` / `edge_width`: Decimal rendered without trailing zeros (`18`, `0.4`,
  `2`).
- Renaming a manufacturer does **not** retroactively rewrite material names (names
  regenerate on the material's own next update). Acceptable: manufacturer renames are
  rare and cosmetic; do not build a cascade.
- Examples:
  - `LDSP Egger H1334 ST9 · Sonoma eman · 2750×1830×18 mm`
  - `Kromka Egger H1145 · Sonoma eman · 2×19 mm`

## 2. Backend — `app/modules/catalog/`

### 2.1 Model (`models.py`)

- `Material` gains `edge_width_mm: Mapped[int | None]` — integer mm; tape roll width.
- `ck_materials_kind_shape` extended: panel branch adds `edge_width_mm IS NULL`; edge
  branch adds `edge_width_mm IS NOT NULL`.
- New `CheckConstraint("edge_width_mm IS NULL OR edge_width_mm > 0",
  name="ck_materials_edge_width_positive")`.
- **No uniqueness constraint** (owner decision, 2026-07-12 — deferred; see §9).

### 2.2 Migration (one Alembic revision, autogenerate then hand-finish)

Ordered steps inside the revision:

1. Add the `edge_width_mm` column (nullable).
2. Backfill `edge_width_mm = 19` for all `kind='edge'` rows. **19 mm is the standard
   width for 16–18 mm boards and matches every current seed/demo tape; real prod data
   is demo-seeded only. Documented assumption — operators adjust via admin after
   deploy if a real tape differs.**
3. Regenerate `name` for **all** rows using a **frozen copy** of the composer embedded
   in the migration (plain SQLAlchemy core over reflected/lightweight tables with a
   join to `manufacturers` for the name — do not import the app service into the
   migration).
4. Drop + recreate `ck_materials_kind_shape` with the extended shape; add
   `ck_materials_edge_width_positive`.

Autogenerate misses the constraint rewrite and the data steps — review per
`backend/AGENTS.md`.

### 2.3 Service (`service.py`)

- `compose_material_name(...)` + `_TYPE_LABELS` + a `_fmt_mm(Decimal) -> str`
  trailing-zero trimmer.
- `create_material`: drop `payload.name` handling ([service.py:243](../backend/app/modules/catalog/service.py)); after validation set
  `row.name = compose_material_name(...)` (manufacturer is already loaded).
  `_validate_material_shape` gains `edge_width_mm`: required + positive for `edge`,
  must be `None` for `panel` (same `invalid_*` error family as the panel-field
  checks).
- `update_material`: drop the `name` patch branch ([service.py:305](../backend/app/modules/catalog/service.py)); accept
  `edge_width_mm` (edge only — reject on panel via the existing
  `invalid_edge_material`-style guard, code `invalid_panel_material`);
  **recompose `row.name` at the end of every patch** (cheap, unconditional; also
  covers `manufacturer_id` changes since the target manufacturer is loaded there).

### 2.4 Schemas (`schemas.py`)

- `MaterialCreateRequest`: **remove `name`**; add `edge_width_mm: int | None = None`.
- `MaterialPatchRequest`: **remove `name`**; add `edge_width_mm: int | None = None`.
- `MaterialResponse`: keep `name`; add `edge_width_mm: int | None`.
- Ripple: `BranchMaterialResponse` / `BranchCatalogMaterialOption` embed
  `MaterialResponse` — nothing to do beyond the base change. Sales snapshots copy
  `material.name` text — no change (and they now carry the manufacturer for free).

## 3. Web — admin form + TS mirror

### 3.1 `stores/admin.ts`

`MaterialWriteRequest` / material response type: drop `name` from the write shapes,
add `edge_width_mm` (number on the edge write shape; `number | null` on responses).

### 3.2 `adminMaterials.ts` + `AdminMaterialsView.vue`

- `AdminMaterialFormState`: remove `name`; add `edgeWidthMm: string`.
- `buildAdminMaterialWriteRequest`: stop sending `name`; edge branch sends
  `edge_width_mm: Number(form.edgeWidthMm)`.
- Form UI: remove the name input. Add **"Eni (mm)"** (edge kind only, required,
  integer) next to the thickness input.
- **Live name preview**: a TS mirror `composeMaterialName(...)` (new, colocated in
  `adminMaterials.ts`; takes the selected manufacturer's name) renders the would-be
  name under the form as the operator types. Preview-only — the server value is
  authoritative. A parity unit test pins the same examples as the backend tests (§6).
- Edit flow: populate the width field from the response; the name shows as read-only
  derived text, never an input.

### 3.3 Cutting editor — width guidance (`cuttingEdgeDisplay.ts` + the two components)

- `ClientCatalogMaterialOption` (in `stores/cutting.ts`) gains `edge_width_mm` per
  the response change.
- New helper in `cuttingEdgeDisplay.ts`:
  `widthPenalty(panelThickness: number, edge): number` —
  `w < t ? 10_000 + (t - w) : (w - t)` (narrow tapes sink to the bottom with the worst
  fit last; among covering tapes, closest width first).
- `rankedEdges` sort becomes: `rank` (decor/colour, unchanged) → `widthPenalty` →
  `thickness_mm` → manufacturer+name. Panel `null` → widthPenalty 0 for all (no-op).
- New helper `edgeTooNarrow(panelThickness, edge): boolean` (`w < t`).
- `CuttingEdgePickerModal.vue`: options where `edgeTooNarrow` show a warning badge
  (copy §5); selection stays allowed — **no disabling, no filtering**.
- `CuttingEdgeTapeRegistry.vue`: a selected tape that is too narrow for its panel
  carries the same badge, so the warning survives past the modal.
- Tape display strings: the generated name now carries `2×19 mm` and the
  manufacturer — audit `cuttingDisplay.ts` / registry labels for redundant hand-built
  thickness or manufacturer suffixes and drop any duplication.

## 4. Seed — `deploy/seed-demo.sh`

- Material create calls stop sending `name`; panels/edges rows carry their structured
  fields only. Edge rows gain a width column: 19 for the standard tapes, plus retag
  two tapes for picker-guidance coverage — one **22 mm** and one **42 mm** (the 42 mm
  one documents the thickened-edge flow in demo data).
- Comment header (counts/credentials block) stays accurate.
- `--reset` run must come up green; the demo names will be the generated ones.

## 5. Copy (Uzbek, inline)

- Admin form: `Eni (mm)` · name preview label `Nomi (avtomatik)`.
- Picker/registry narrow-tape badge: `Qirradan tor` · tooltip
  `Lenta eni ({w} mm) panel qalinligidan ({t} mm) tor — qirrani to'liq yopmaydi.`

## 6. Tests

Backend (`tests/test_phase3_catalog_inventory_api.py`, or a colocated new
`test_catalog_material_identity.py` if the phase file is unwieldy):

- Composer unit cases: panel with/without decor_code; edge with/without decor;
  `0.4` and `2` and `18` formatting; manufacturer embedded; exact expected strings
  from §1.
- Create: edge without `edge_width_mm` → 4xx; panel with `edge_width_mm` → 4xx;
  `name` in the payload is ignored (extra field), response `name` is generated.
- Patch: changing `color`/`thickness_mm`/`edge_width_mm`/`manufacturer_id`
  regenerates `name`; patching `edge_width_mm` on a panel → 4xx.
- Migration-shape safety net: model metadata create_all + a panel/edge insert
  violating the new constraints fails (sqlite-level check as in existing model tests).

Web (Vitest):

- `adminMaterials.spec.ts`: write-request shape (no `name`, width on edge) +
  `composeMaterialName` parity with the §1 examples.
- `cuttingEdgeDisplay.spec.ts`: widthPenalty ordering (covering-closest first, narrow
  last), `edgeTooNarrow`, rank still dominating width, thickened-edge case pinned:
  42 mm tape on an 18 mm panel ranks as a normal covering tape and carries **no**
  warning.
- `AdminMaterialsView` spec: no name input rendered; width input appears only for
  edge kind; preview text updates.

E2E: run the existing suite (`cd e2e && pnpm typecheck && pnpm test`); no spec asserts
seed material names today — if a selector breaks on the regenerated names, fix the
selector, don't reintroduce hand names.

## 7. Acceptance gates

1. `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
   && uv run pytest` — green, incl. §6.
2. `cd web && pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test &&
   pnpm build` — green.
3. `cd e2e && pnpm typecheck && pnpm test` — green.
4. Manual pass (verify skill): `bash deploy/seed-demo.sh --reset`; in the admin SPA
   create a panel and an edge (watch the live name preview); in the client cutting
   editor open the edge picker on an 18 mm panel — 19 mm tapes rank above 42 mm, a
   narrow tape shows the badge but stays selectable.
5. Docs (§8) updated.

## 8. Docs (source of truth — via docs-management)

- `docs/ref/entities/catalog.md` — Material table: `name` becomes *generated* (state
  the composition rule + "never an input"), **flip the "manufacturer not embedded in
  the name" rule** to its opposite with the snapshot rationale, add `edge_width_mm`
  (edge-only, required there); invariants gain "identity includes tape width — one
  decor in two widths is two rows"; update the `ck` shape description.
- `docs/ref/features/catalog-inventory.md` — material create/edit operation: field
  list (no name input, width for edges).
- `docs/ref/features/cutting.md` — editor edge-picking: width-fit ranking + the
  non-blocking narrow-tape warning, with the thickened-edge decomposition note (strip
  as its own part; wide tape on the visible side) as the reason blocking is wrong.
- Keep frontmatter `updated:` current.

## 9. Non-goals (do not partially build)

- **No uniqueness constraint/index on materials** (owner decision, 2026-07-12 —
  deferred; operator discipline for now). Revisit when duplicates actually appear.
- **No `variant` field** (owner decision, 2026-07-12). Bazis-parity: such qualifiers
  have no dedicated field there either; a rare variant like "namlikka chidamli" goes
  into `color` (e.g. `Kashmir (namlikka chidamli)`) until a real need is shown.
- **No manufacturer-rename cascade** into material names — names refresh on the
  material's own next update.
- **No thickened-edge helper UI** (auto-generating strip parts) — decomposition is
  manual in v1; revisit with demand numbers.
- **No hard width/thickness filter anywhere** — guidance only, everywhere.
- **No surface-finish field** — finish stays inside `decor_code` (`H1334 ST9`).
- **No name localisation** — one stored name, Uzbek-latin labels; not per-locale.
- **No renaming of `color`** — it stays the human decor name field.
- **No auto-matching changes in the Bazis import** — imports still pick materials
  manually; `decor_code`-assisted suggestions remain a future, separate spec.
