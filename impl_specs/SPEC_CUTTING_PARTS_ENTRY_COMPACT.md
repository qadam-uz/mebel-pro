# Compact parts entry — material-first groups, dense rows, one-glyph edge banding

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-16
Repo: `mebel-pro`. Agreed on an interactive mockup with the owner; this document is the
single source for implementation. Owner decisions locked in: **material-first entry**
(material is picked in a dialog before parts are typed; parts live in per-material
groups), **no per-row material select** (material changes at the group level; a single
part moves via an explicit action), **checkbox/selection bar removed** (bulk needs are
covered by registry chips + a group-level edge action), **edge banding renders as one
rectangle glyph** with per-side colored borders, and the row style is a **dense-table
hybrid** — not a full Excel/spreadsheet (explicitly rejected: no cell ranges, no
cell-level copy/paste).

Relationship to other specs:
- `SPEC_CUTTING_EDITOR_REDESIGN.md` — implemented; this spec **amends its §2 (row
  layout, keyboard) and §3.2 (krom cells / cell popover)**. Its §2.1 grouping, §3.1
  registry derivation, §2.4 undo-toast deletion, and everything else stand unchanged.
- `SPEC_CUTTING_DRAFT_NAME_BRANCH_PICKER.md` — independent; both touch
  `CuttingEditorView.vue` but different regions (header/gate vs parts card). Land in
  either order.

**Web-only. No backend change**: `parts_snapshot` shape, validation, optimization, and
pricing are untouched — every change here is a view/interaction transform over the same
data.

## 0. Process rules

- Read `web/AGENTS.md` first; docs edits via the **docs-management** skill; visual
  language comes from `web/DESIGN.md` tokens — this spec defines structure/behavior, not
  new colors or type styles.
- Implement in stage order §1→§4; every stage ends with the full web gate green.
- All user-facing copy is Uzbek; exact strings in §5. No new English leaks.
- **No abstract "group" term in the UI.** The group *is* the material: headers show the
  material, buttons name the action by material («+ Detal», «+ Boshqa material»).
  "Group" appears only in code/docs.

## 1. Stage A — material-first entry flow

### 1.1 Adding the first material / a new material

- An empty draft (branch already chosen — the gate spec owns that) shows a parts-card
  empty state: explainer + primary **«+ Material tanlash»** button → opens the existing
  material picker dialog (branch-scoped catalog, search — unchanged).
- Picking a material creates its group with **one blank row**, focus on Bo'y.
- Below the last group a **«+ Boshqa material»** button repeats the flow. Picking a
  material that already has a group does not duplicate the group — it appends a blank
  row to the existing group and scrolls to it.
- The old "new row starts with no material" state disappears: **every row belongs to a
  material group from birth**. The «Material tanlanmagan» fallback group remains only as
  a render path for legacy drafts that still contain material-less rows.

### 1.2 Group header

Left → right: material swatch · **material name with a dashed underline** (click, or
Enter/Space when focused, opens the material picker dialog; the pick re-materials
**every row in the group** — one store mutation, one autosave) · summary
`{n} detal · {x} m²` · «+ Detal» button · overflow `⋯` menu · collapse chevron.

- «+ Detal» appends a blank row to the group (same inheritance as §2.3) and focuses
  Bo'y.
- Group `⋯` menu: **«Guruhga krom qo'llash»** (opens the §3 popover in group mode) and
  **«Guruhni o'chirish»** (ConfirmDialog naming the material and part count; deletion is
  not undo-toasted — it is confirm-gated like the existing clear-all).
- Group headers are **sticky** within the parts card while their group scrolls
  (`position: sticky` under the card's summary strip).
- Collapse/expand behavior stays from the redesign spec (local UI state).

### 1.3 Moving one part to another material

Row `⋯` menu gains **«Boshqa materialga ko'chirish»** → material picker dialog → the row
moves to that material's group (creating the group if absent). This is the **only** way
a single row changes material — there is no row-level material select anywhere.

## 2. Stage B — dense row layout (`CuttingPartRow.vue`)

### 2.1 Desktop grid

Replace the current 11-column template with 8 columns:

`28px (№) · minmax(120px, 1fr) (Nomi) · 64px (Bo'y) · 64px (En) · 48px (Soni) ·
36px (Tola) · 44px (Krom glyph) · 32px (⋯)` — gap 6px, row height 36–40px. Fixed
minimum ≈ 600px; lower the table-mode container breakpoint from `@min-[920px]` to
`@min-[680px]`. Removed outright: the select checkbox (and the whole selection bar /
bulk-apply UI it fed), the row-level duplicate button (moves into `⋯`), the 4-cell krom
block (replaced by the glyph), and the row-level material item in `⋯` (replaced by
§1.3's move action).

Row `⋯` menu: «Nusxalash» (duplicate below, name copied, focus Bo'y — unchanged
behavior) · «Boshqa materialga ko'chirish» (§1.3) · «O'chirish» (undo-toast flow
unchanged).

### 2.2 Dense-table input styling

- Inputs render **borderless and transparent** at rest (`border-color: transparent`,
  no fill); hover shows the hairline border, focus shows the standard focus ring. This
  is the "sheet feel" without spreadsheet machinery.
- Numeric fields (Bo'y, En, Soni) are right-aligned, `font-mono`; Nomi stays
  left-aligned with the `D{n}` placeholder.
- Tola becomes an **icon toggle** (grain-direction icon, accent when locked, muted at
  40% when off; hidden for non-grained materials — rule unchanged). `aria-pressed` +
  existing labels.
- Per-row validation states are unchanged; an invalid field keeps its danger border
  even at rest (visibility of errors must not regress with borderless styling). The
  header error chip + filter from the redesign spec stay.

### 2.3 Keyboard chain

- Focus chain per row: **Nomi → Bo'y → En → Soni**; both `Enter` and `Tab` advance.
  From **Soni**, Enter/Tab moves to the **next row's Nomi**; on the **last row of a
  group** it appends a new row to that group (inheriting the group material + previous
  row's edge picks and `follow_grain`; name/dims empty, quantity 1) and focuses its
  Bo'y. `Shift+Tab` walks backwards.
- **Tola and the Krom glyph are outside the Enter/Tab chain** (reachable by click, and
  by arrow-key/manual focus — they keep `tabindex` only via a roving pattern within the
  row so keyboard users can still reach them; they are simply not in the rapid-entry
  path).
- Mobile card layout keeps its structure minus the checkbox; the krom 4-cell block is
  replaced by the same glyph (§3), tap opens the existing `CuttingEdgePickerModal`.

## 3. Stage C — edge banding: one glyph + side popover

### 3.1 The glyph

One ~26×18px rounded rectangle per row. Each side's border encodes that side's pick:

- banded side → **2.5px solid** in the side's registry color (same color derivation as
  the registry chips — no new color logic);
- unbanded side → **1px dashed** muted hairline;
- all-unbanded → the whole rectangle dashed muted (empty affordance).

The glyph is a button (`aria-label` per §5, `aria-haspopup="dialog"`). Hover tooltip
lists per-side picks (`U: ① PVX 2mm · P: — …`).

### 3.2 The popover (desktop) — replaces the per-cell popover of the redesign spec

Anchored to the glyph. Contents:

- a **large interactive rectangle** (~120×84px): clicking a side toggles the currently
  selected tape on/off for that side; sides render with the same color/dash language as
  the glyph, plus the side initials U / P / CH / O' just inside each edge;
- a **tape list** (radio): registry entries (numbered colored dot + name) + «Boshqa
  tasma…» (catalog edge picker; the pick joins the registry) — selecting a tape does
  not change sides by itself, it arms what side-clicks apply;
- «Manba: o'zimning tasmam» checkbox (maps to `source: own` for subsequently applied
  sides — existing semantics);
- action row: «To'rt tomonga qo'llash» (armed tape to all four sides) · «Kromsiz»
  (clears all four) · «Tayyor» (closes; every change is already live — the popover
  edits the row directly through the existing per-side composable, one autosave per
  mutation batch).
- Esc / outside click closes. Focus is trapped while open; returns to the glyph on
  close.

**Group mode** (from the header `⋯`): the same popover, but side-clicks and actions
write to **every row in the group** (one store mutation, one autosave); the rectangle
shows a side as banded only when *all* rows agree (mixed state renders the side in a
half-opacity solid with a `≈` tooltip note).

Mobile keeps `CuttingEdgePickerModal` as the tap target for the glyph; restyle its side
selector to the same rectangle language, reusing the shared composable.

### 3.3 Registry strip

The chips row above the grid (redesign spec §3.2) stays exactly as is — chip click
still runs the tape-replace flow; «+ Tasma» still pre-registers a tape. Together with
§3.2's group mode these replace every use the removed selection bar had.

## 4. Stage D — long-list ergonomics

- Sticky group headers (§1.2) + the existing collapse give orientation in long drafts;
  the summary strip (`N detal · M material · ~X m²`) stays pinned at the card top.
- **No virtualization, no pagination** — the 100-part draft cap makes worst-case ~4000px
  of 40px rows, which grouping and collapse handle. Re-evaluate only if the cap moves.
- Import flow (`CuttingImportWizard`) is untouched; imported parts land in groups as
  today.

## 5. Copy (Uzbek, exact strings)

| Where | String |
| --- | --- |
| Empty parts card CTA | `+ Material tanlash` |
| New group button | `+ Boshqa material` |
| Group add-part button | `+ Detal` |
| Group menu | `Guruhga krom qo'llash` · `Guruhni o'chirish` |
| Group delete confirm | `«{material}» — {n} detal o'chiriladi. Bu amal qaytarilmaydi.` |
| Row menu | `Nusxalash` · `Boshqa materialga ko'chirish` · `O'chirish` |
| Glyph aria-label | `Krom tomonlari` |
| Glyph tooltip line | `U: {tasma yoki —} · P: … · CH: … · O': …` |
| Popover side initials | `U` · `P` · `CH` · `O'` |
| Popover actions | `To'rt tomonga qo'llash` · `Kromsiz` · `Tayyor` |
| Popover source checkbox | `Manba: o'zimning tasmam` (unchanged) |
| Popover other-tape | `Boshqa tasma…` |
| Mixed group side tooltip | `Guruhda har xil — qo'llasangiz hammasiga yoziladi` |
| Tola toggle aria | `Tola yo'nalishi bo'yicha qulflash` (existing label kept) |

## 6. Tests

Web unit (Vitest, colocated `__tests__`):
- material-first: empty-state CTA → picker → group with one focused row; picking an
  existing material appends to its group instead of duplicating;
- group header: material-name click re-materials all rows in one mutation; group delete
  confirm; group krom action writes every row; sticky/collapse render states;
- move action: row moves groups, creates the target group when absent;
- keyboard: Nomi→Bo'y→En→Soni chain for Enter and Tab, Soni→next-row Nomi,
  last-row append + inheritance, Shift+Tab reverse, Tola/Krom excluded from the chain;
- glyph: border style per side (solid+color / dashed), all-empty state, tooltip content;
- popover: arm-tape + side-click toggle emits per-side shapes, apply-all, clear-all,
  own-source flag, group mode fan-out + mixed-state render;
- dense styling: invalid field keeps danger border at rest;
- removed surfaces stay removed: no checkbox column, no selection bar, no row-level
  material select.

E2E (extend the existing cutting editor spec, keep small): pick material → keyboard-only
entry of three parts (Enter chain) → set krom via glyph popover → optimise → order. Verify
a legacy draft with a material-less row still renders (fallback group).

## 7. Acceptance gates

1. Web gate green (`lint:check`, `format:check`, `typecheck`, `test`, `build`).
2. Docs updated: `docs/ref/features/cutting.md` editor UX section (material-first entry,
   dense rows, glyph + popover, group actions — replaces the checkbox/4-cell/keyboard
   description).
3. Manual browser pass per the **verify** skill: keyboard-only entry speed path, glyph
   colors against both themes, sticky headers on a 50+ part draft, mobile card layout,
   legacy material-less draft, group krom apply on mixed rows.
4. Existing flows unbroken: import wizard, registry chip replace, undo-toast delete,
   error chip filter, optimise/order path.

## 8. Non-goals

- No Excel/spreadsheet semantics: no cell-range selection, no cell copy/paste, no
  formula bar. (Excel *paste* remains a separate later pass, as before.)
- No virtualization or pagination of the parts list (100-part cap).
- No drag-and-drop row reorder or drag-between-groups (the move action covers it).
- No `parts_snapshot` schema or backend change of any kind.
- No changes to the material picker dialog itself, the import wizard, or the results
  section.
