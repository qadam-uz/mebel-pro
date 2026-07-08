# Per-part `follow_grain` — Implementation Spec

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-05
Repo: `mebel-pro` (this repo — backend + web + docs together).

## 0. Read first, and process rules

- This is a **complex-flow** task per `AGENTS.md` — read `.workflows/playbooks/complex.md`
  and follow it. Docs edits under `docs/` must follow the **docs-management** skill.
- Read `backend/AGENTS.md` and `web/AGENTS.md` before touching those trees.
- **Deliberate spec reversal**: `docs/ref/features/cutting.md` currently states
  *"Grain — a property of the panel material, not the part. … The user is never asked to
  set grain on a part."* The product owner has explicitly reversed this decision — parts
  now carry a follow-the-grain instruction. Updating that doc is part of this task (§5),
  not a conflict to re-raise.
- No DB migration is needed anywhere in this task: draft/result parts are stored as JSON
  (`parts_snapshot`), and the new key is additive with a default.

## 1. The rule

Grain (texture) remains a **material** property (`materials.grain_direction`, already
exists). Each part gains an **instruction**, not a property:

```
follow_grain: bool = true    # "align this part with the material's grain"
```

| Material `grain_direction` | Part `follow_grain` | Effective behavior                            |
| -------------------------- | ------------------- | --------------------------------------------- |
| true (grained)             | true (default)      | rotation forbidden (today's behavior)         |
| true (grained)             | false               | rotation allowed — optimizer may rotate 90°   |
| false / null               | any                 | field ignored; rotation allowed (unchanged)   |

Derivation used everywhere: `locked = material.grain_direction AND part.follow_grain`.

Naming is deliberate: the part does not *have* texture; it *follows* the material's grain.
Do not name the field `texture` or `can_rotate`. UI label keeps the existing Uzbek term
**«Tola»** (see §4).

Compatibility invariant: any stored part dict **without** the key reads as
`follow_grain = true` — old drafts, quotes, and confirmed results keep today's semantics
bit-for-bit.

## 2. Backend — `backend/app/modules/cutting/`

### 2.1 `schemas.py`

`CuttingPart` (currently: `part_ref`, `material_id`, `material_source`, `length_mm`,
`width_mm`, `quantity`, `edge_top/bottom/left/right`) gains:

```python
follow_grain: bool = True
```

Pydantic default handles old snapshots on re-validation. `model_dump` in the service will
start writing the key into new snapshots — that is intended.

### 2.2 `optimizer.py` (the cutting-engine adapter)

- `PartInput` dataclass gains `follow_grain: bool = True`.
- In `_optimize_material` (engine `Part` construction — currently
  `can_rotate=not material.grain_direction` / `grain=VERTICAL if material.grain_direction
  else NONE`), switch to per-part:

  ```python
  locked = material.grain_direction and part.follow_grain
  can_rotate=not locked,
  grain=GrainDirection.VERTICAL if locked else GrainDirection.NONE,
  ```

- `_ensure_part_can_fit`: the `impossible_grain` branch currently triggers on
  `material.grain_direction and not fits_normal`. It must trigger on
  `locked and not fits_normal`; the `part_too_large` branch (rotation considered) applies
  whenever `not locked`.
- No cutting-engine package change is needed — engine `Part.can_rotate` / `Part.grain`
  are already per-part inputs (pinned version supports this).

### 2.3 `service.py`

- The pre-optimize fit validation (the block that emits `impossible_grain` /
  `part_too_large` row errors, currently keyed on `panel.grain_direction`) must use the
  same `locked = panel.grain_direction and part.follow_grain` derivation. Keep error codes
  and shapes unchanged — only the trigger condition narrows.
- `PartInput(...)` construction: pass `follow_grain=part.follow_grain`.
- `_material_snapshot` already records the material's `grain_direction`; no change.

### 2.4 Backend tests (`backend/tests/`)

- `test_cutting_optimizer.py`: a 4-row matrix test of the table in §1 — assert the engine
  `Part.can_rotate`/`grain` mapping per case (grained+true → locked; grained+false → free;
  non-grained ± → free). Plus: `impossible_grain` raised only for the locked case.
- `test_cutting_api.py`:
  - optimize with a part that fits **only rotated** on a grained material:
    `follow_grain=true` → row error `impossible_grain`; `follow_grain=false` → succeeds
    and the stored result marks the placement rotated.
  - old-snapshot compatibility: PATCH/optimize a draft whose `parts_snapshot` dicts lack
    the key (build the dict by hand, not via `CuttingPart`) → treated as `true`, response
    echoes `follow_grain: true`.

## 3. Frontend — `web/src/shared/`

### 3.1 `stores/cutting.ts`

- `CuttingPart` interface gains `follow_grain: boolean`.
- `partFitError(...)` gains a `followGrain: boolean` parameter and uses the same `locked`
  derivation (`panel.grain_direction && followGrain`) to pick between `impossible_grain`
  and `part_too_large` — mirror of §2.3. Update all call sites.

### 3.2 New-part factory

`ClientCuttingEditorView.vue` creates new part rows (the object literal with
`quantity: 1, edge_top: null, …`): add `follow_grain: true`. Any other place constructing
a `CuttingPart` literal (search the tree) gets the same.

### 3.3 `components/CuttingPartRow.vue` — badge becomes a toggle

Today the row shows a **static** chip when the material is grained (`grain` computed):
`↕ Tola` with title "Tola yo'nalishi bor — bu qism burilmaydi" (desktop + mobile variants).
Replace both variants with a **toggle button**, visible only when the material is grained
(`v-if="grain"` stays):

- Pressed / active (= `follow_grain: true`, default): current look (`bg-info-soft
  text-info`), label `↕ Tola`, title `Tola yo'nalishi bo'yicha — burilmaydi`.
- Unpressed (= `follow_grain: false`): muted style (follow the file's existing muted chip
  classes), same `↕ Tola` label with strike-through or reduced opacity per the file's
  conventions, title `Tola hisobga olinmaydi — burilishi mumkin`.
- Proper `aria-pressed`, keyboard-operable (it is a `<button>`), and an
  `emit('update:follow-grain', !part.follow_grain)` following the row's existing
  `update:source`/`update:quantity` emit pattern; the editor view handles it by patching
  the part (autosave flow picks it up like any other part edit).
- When the material is **not** grained the control is absent entirely (not disabled) —
  the stored value is simply ignored, matching §1.

### 3.4 Frontend tests

- `partFitError` unit spec: the §1 matrix (4 cases).
- `CuttingPartRow` spec: toggle renders only for grained material; click emits
  `update:follow-grain` with the inverted value; `aria-pressed` reflects state.

### 3.5 E2E (optional, keep small)

If `e2e/tests/cutting-drafts.spec.ts` already walks the editor: one assertion pair —
toggle visible on a grained-material row, absent on a non-grained row. Do not build a new
journey for this.

## 4. Copy (Uzbek, inline strings as the codebase does)

- Active title: `Tola yo'nalishi bo'yicha — burilmaydi`
- Inactive title: `Tola hisobga olinmaydi — burilishi mumkin`
- Label stays `Tola` (existing term; do not introduce "tekstura" in UI copy).

## 5. Docs (source of truth — mandatory, via docs-management)

- `docs/ref/features/cutting.md` — rewrite the *"Grain — a property of the panel
  material, not the part."* bullet: grain stays a material property; each part carries a
  `follow_grain` instruction (default true) honored **only on grained materials**; the §1
  table; `impossible_grain` now fires only for locked parts; delete the sentence "The
  user is never asked to set grain on a part" and describe the row toggle instead. Update
  any enumeration of part fields in this doc to include `follow_grain`.
- `docs/ref/entities/cutting.md` — add `follow_grain` wherever draft/result
  `parts_snapshot` part fields are enumerated.
- Keep both docs' frontmatter `updated:` current per docs conventions.

## 6. Acceptance gates

1. Backend: `cd backend && uv run ruff check . && uv run ruff format --check . &&
   uv run mypy app && uv run pytest` — green.
2. Web: `cd web && pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test &&
   pnpm build` — green.
3. The §2.4 old-snapshot test proves no behavior change for existing drafts/results.
4. Docs updated per §5 (this is a gate, not a nice-to-have — the repo treats docs as
   canon).

## 7. Non-goals

- No bulk-action for the toggle in the editor's multi-select bar.
- No cutting-engine changes, no dependency bump.
- No workshop/admin UI surface for the flag (order detail read views unchanged in v1).
- No display of grain arrows on the cutting map SVG/PDF (future).
- No DB schema migration (JSON snapshots only).
