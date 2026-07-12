# Cutting editor — stable edge-tape identity & group-aware recommendations — Implementation Spec

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-12
Repo: `mebel-pro`. **Delta spec** against the implemented cutting editor: web
`cuttingEditorDerived.ts`, `cuttingEdgeDisplay.ts`, `CuttingEdgePickerModal.vue`,
`CuttingEdgeTapeRegistry.vue`, `CuttingPartRow.vue`, `CuttingEditorView.vue`, colocated
specs. No backend change.

## 0. Diagnosis (why colours are broken today)

The editor has **two disconnected numbering systems** plus two stability defects:

1. **Modal vs document mismatch.** The document registry
   (`deriveEdgeRegistry`, [cuttingEditorDerived.ts:79](../web/src/shared/app/cuttingEditorDerived.ts))
   numbers tapes by part-list first-use order. The picker modal builds its **own**
   local numbering (`tapeEntries`,
   [CuttingEdgePickerModal.vue:179](../web/src/shared/components/CuttingEdgePickerModal.vue))
   by modal-encounter order (sides → last-picked → active → recommended → group ids).
   The same tape can be ② orange in the grid and ① teal inside the modal, and the
   modal's numbers shift live as the user interacts.
2. **Unstable under edits.** Reordering or deleting parts renumbers and recolours
   every later tape — ① becomes ② mid-session.
3. **Colours repeat.** `index % 6` reuses the palette from the 7th tape on — two
   different tapes can wear the same colour, violating "unique per tape".
4. **Recommendations are group-blind beyond the group.** The modal only receives
   same-group tape ids (`materialEdgeIds`,
   [CuttingEditorView.vue:726](../web/src/shared/views/CuttingEditorView.vue)); tapes
   used in *other* groups of the drawing are never offered, and a brand-new tape has
   no identity preview.

## 1. Identity model (the contract)

- **Key** = `material_id:source` (unchanged shape).
- **One assignment per draft session**: on first use a key gets `(number, colour)`;
  the pair never changes and is never reassigned while the draft is open — reordering,
  editing, even removing the tape from every part does not free its number (re-adding
  it returns the same badge). The registry bar shows only *currently used* entries,
  sorted by number, so gaps may appear after a removal — gaps are honest and rare;
  stability wins (owner requirement: "chizma bo'yicha bir xil va takrorlanmas").
- **Colour is a pure function of the number** — `registryColorStyle(number)`:
  extend `EDGE_REGISTRY_COLOR_STYLES` from 6 to **10** hand-tuned entries (first 6
  stay byte-identical to today's), then a deterministic golden-angle fallback for
  11+: `bg = hsl(((n-1)·137.508) mod 360, 45%, 42%)`, `fg = #fff`,
  `soft = hsl(same-hue, 55%, 92%)`. Distinct hues forever; no modulo reuse.
  (`EDGE_REGISTRY_COLORS` — the parallel Tailwind-class array — becomes unused by the
  new path; delete it if nothing else references it.)
- **Reload semantics**: assignments are session state; on draft load they are seeded
  from the parts snapshot in first-use order (deterministic). A reload after
  deletions therefore compacts gaps — acceptable; within any live editing session
  numbers never move. No backend/schema change.
- **Every surface reads the same assignment**: registry bar, group-header chips,
  part-row band badges, modal side buttons, modal chip list. No surface may derive
  its own numbering (this deletes the modal's `tapeNumberLabel`/`tapeColor`).

## 2. State & derivation — `cuttingEditorDerived.ts` + `CuttingEditorView.vue`

Parts live in the view (`const parts = ref<CuttingPart[]>`,
[CuttingEditorView.vue:82](../web/src/shared/views/CuttingEditorView.vue)), so the
assignment state lives beside them; the derived module stays pure.

### 2.1 Pure helpers (`cuttingEditorDerived.ts`)

- `registryColorStyle(number: number): EdgeRegistryColorStyle` — §1 palette+fallback.
- `syncEdgeAssignments(assignments: Map<string, number>, parts: CuttingPart[]): void`
  — walk parts in order, assign `max(assigned)+1` to any used-but-unassigned key.
  Never deletes entries.
- `previewEdgeAssignments(assignments: ReadonlyMap<string, number>, keys: string[]):
  Map<string, number>` — existing keys → their number; unknown keys → next free
  numbers in the given order, **without mutating** (the modal's tentative badges).
- `deriveEdgeRegistry(parts, assignments)` — reshape of the existing function:
  entries = currently-used keys, `number` from `assignments`,
  `colorStyle = registryColorStyle(number)`, sorted by number. (`colorClass` drops
  out with `EDGE_REGISTRY_COLORS`.)

### 2.2 View wiring (`CuttingEditorView.vue`)

- `const edgeAssignments = ref(new Map<string, number>())`; a `watch(parts, …,
  {deep: true, immediate: true})` calls `syncEdgeAssignments` — one choke point
  covers manual banding, bulk apply, import, and draft load (seeding = the immediate
  first run). Reset the map when a different draft is loaded.
- `edgeRegistry` computed becomes `deriveEdgeRegistry(parts.value,
  edgeAssignments.value)`. `groupEdgeRegistryEntries`, `registryEntryForBand`,
  `CuttingPartRow`, `CuttingEdgeTapeRegistry` are consumers of the entries and need
  **no API change** — they just become stable.
- New computed for the modal: `otherGroupEdgeIds(part)` — distinct tape ids used by
  parts of **other** material groups (complement of `materialEdgeIds`, same
  first-use ordering, same dedup); rename `materialEdgeIds` → `groupEdgeIds` for
  symmetry.
- Modal props: pass `edge-registry="edgeRegistry"`, `group-edge-ids`,
  `other-group-edge-ids`.

## 3. Modal — one recommendation stack, real badges, previews

`CuttingEdgePickerModal.vue`:

- **Delete** the local numbering (`tapeNumberLabel`, `tapeColor`, index-based
  `tapeEntries` identity). New props: `edgeRegistry: EdgeRegistryEntry[]`,
  `groupEdgeIds: string[]`, `otherGroupEdgeIds: string[]`.
- `tapeEntries` becomes the **recommendation stack**, in this order (dedup by id,
  keep existing "must include sides' tapes" rule):
  1. tapes on this part's sides (working state) — always shown;
  2. `groupEdgeIds` — tapes already used in this material group;
  3. `otherGroupEdgeIds` — tapes used elsewhere in the drawing;
  4. the top catalog recommendation (`recommendedEdgeForPart`) if not already listed.
  Cap the stack at **6 chips** (sides' tapes never dropped); the full catalog stays
  behind "+ Yana tasma qo'shish".
- **Identity per chip**: resolve through `previewEdgeAssignments(assignmentsOf(edgeRegistry),
  orderedChipKeys)`. A key present in `edgeRegistry` renders its real badge (solid,
  exact colour/number from the document). A key not yet used anywhere renders the
  **tentative badge**: next-free number + its colour, `border-dashed` ring + the
  word `Yangi` in the meta line — visually "not in the drawing yet". The tentative
  number materializes on apply via the §2.2 watcher; if several new tapes were
  previewed and only some applied, the committed numbers compact (previews are
  tentative by design — the dashed ring is the promise-softener).
- **Origin meta line** per chip (replaces the bare "N tomonga" when relevant, joined
  with ` · `): `Shu qismda N tomonga` / `Shu guruhda ishlatilgan` /
  `Chizmaning boshqa guruhida` / `Tavsiya — dekor mos` / `Yangi`.
- Side buttons (`sideStyle`/badges) resolve through the same preview map — a side
  painted with a not-yet-applied tape shows the tentative badge, switching to solid
  after apply.
- Narrow-width warning, patterns, focus trap, branch note — unchanged.

## 4. Default recommendation ladder (`cuttingEdgeDisplay.ts`)

`recommendedEdge(...)` gains usage context and picks the modal's initial active tape
(and the pattern-chip tape) by this ladder — first non-empty wins:

1. the tape already on the clicked side / most-used on this part (existing);
2. the part's remembered tape (existing `preferredEdgeId`);
3. **most-used tape of this material group** — group consistency beats a marginally
   better decor match (a group half-banded with tape ② must not switch mid-group);
4. **decor/colour-matched tape among the drawing's other groups** (`edgeRank` 0 or 1
   against the panel) — the owner's "agar boshqa guruhda ishlatilgan bo'lsa o'sha
   nomer va rang bilan" case;
5. top of the catalog ranking (`rankedEdges`: decor → width-fit → thickness) — a new
   tape, presented with the tentative badge.

Signature: `recommendedEdge(panel, edges, currentId, rememberedId, groupUsage:
string[], documentUsage: string[])` where the arrays are ordered most-used-first
(view computes counts). Steps 3–4 resolve against `edges` membership as today (a
tape the branch stopped carrying keeps working via the existing flagged-selection
rule).

## 5. Copy (Uzbek, inline)

- Chip meta: `Shu qismda {n} tomonga` · `Shu guruhda ishlatilgan` ·
  `Chizmaning boshqa guruhida` · `Tavsiya — dekor mos` · `Yangi`.
- Tentative badge tooltip: `Bu tasma chizmada hali ishlatilmagan — qo'llangach shu
  raqam va rangni oladi.`
- Registry bar and everything else: existing copy unchanged.

## 6. Tests

`cuttingEditorDerived` / new `cuttingEdgeRegistry` cases (Vitest, colocated):

- `syncEdgeAssignments`: first-use order; sticky across part reorder and deletion;
  re-added tape gets its old number back; gaps preserved in-session.
- `registryColorStyle`: numbers 1–14 give 14 distinct `bg` values; 1–6 byte-match
  the old palette entries.
- `previewEdgeAssignments`: known keys keep numbers; unknown keys get consecutive
  free numbers; no mutation of the input map.
- `deriveEdgeRegistry`: only used keys, sorted by number, colour follows number.

`cuttingEdgeDisplay.spec.ts`: the §4 ladder — one case per rung, plus "group tape
beats a decor-matched other-group tape" and "decor-matched other-group tape beats
catalog top".

`CuttingEdgePickerModal` spec: stack order (sides → group → other-group → catalog);
badges match a provided registry exactly (no local renumbering); unknown tape renders
the dashed `Yangi` badge with the next free number; cap at 6 chips keeps sides'
tapes.

`CuttingPartRow.spec.ts` / registry-bar specs: update fixtures to the new entry shape
(no `colorClass`); assert numbers survive a parts reorder (regression for defect #2).

E2E: existing cutting journey only if it asserts badge text — adjust selectors, do
not add a new journey.

## 7. Acceptance gates

1. `cd web && pnpm lint:check && pnpm format:check && pnpm typecheck && pnpm test &&
   pnpm build` — green.
2. `cd e2e && pnpm typecheck && pnpm test` — green.
3. Manual pass (verify skill, seeded stack): band parts in two material groups with
   a shared tape and a group-local tape → the shared tape wears one number/colour in
   the bar, both group headers, part rows, and the modal; delete/reorder parts → no
   badge shifts; open the picker on a part of a fresh group → decor-matched
   other-group tape offered with its real badge, a never-used tape offered dashed
   `Yangi`; apply → dashed becomes solid with the same number.

## 8. Docs (source of truth — via docs-management)

- `docs/ref/features/cutting.md` — editor section: the tape-registry identity rules
  (one number+colour per tape per draft, stable within the session, unique colours),
  the recommendation stack (part → group → drawing → catalog) and the default-tape
  ladder, the tentative-badge behaviour. Keep frontmatter `updated:` current.

## 9. Non-goals (do not partially build)

- **No numbered/coloured banding in the panel visualiser or PDF** — both render
  plain banding ticks today ([rendering.py:282](../backend/app/modules/cutting/rendering.py));
  carrying registry numbers into results/print is a separate spec (it must then
  match the editor's assignment — note the dependency, don't half-do it here).
- **No persistence of assignments in the draft snapshot** — reload re-derives
  deterministically; no backend/schema change in this spec.
- **No cross-draft tape memory** (a client's favourite tapes) — separate concern.
- **No changes to `source` semantics** (`shop`/`own`) or to the width-guidance
  warning shipped by SPEC_CATALOG_MATERIAL_IDENTITY.
