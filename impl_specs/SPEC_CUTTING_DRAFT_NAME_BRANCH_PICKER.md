# Draft naming + branch picker redesign — named drafts, grouped searchable branch selection

Status: approved for implementation · Owner: Abrorjon Berdiyorov · Written: 2026-07-16
Repo: `mebel-pro`. Agreed on interactive mockups with the owner in conversation; this
document is the single source for implementation. Owner decisions locked in:
**branch-first stays mandatory** (the parts UI remains gated on a branch), the gate's
*presentation* is what changes; **the editor's picker opens in an `AppModal` dialog**
(owner decision 2026-07-16, matching the DESIGN.md rule that pick/edit flows are modal,
never inline cards) while the order wizard keeps the picker as in-page step content;
drafts get an optional user-facing **name** and the raw UUID prefix disappears from
every client surface.

Relationship to other specs:
- `SPEC_CUTTING_EDITOR_REDESIGN.md` — implemented; its part-level `name` normalization
  rules (§1.1) are reused verbatim for the draft-level name. This spec touches the same
  editor view but different regions (header strip / branch gate), no conflicts.
- No overlap with `SPEC_CUTTING_RESULTS_POLISH.md` / `SPEC_CUTTING_PDF_DETAILED.md`.

## 0. Process rules

- Read `backend/AGENTS.md` and `web/AGENTS.md` first; docs edits via the
  **docs-management** skill; visual language comes from `web/DESIGN.md` tokens — this spec
  defines structure/behavior, not new colors or type styles.
- Implement in stage order §1→§5; every stage ends with its project's full check gate
  green. Stage A (backend) and B–E (web) may land as separate commits on one branch —
  one spec = one PR.
- All user-facing copy is Uzbek; exact strings in §6. No new English leaks.

## 1. Stage A — backend (small, additive)

### 1.1 Draft `name`

`CuttingDraft` (`backend/app/modules/cutting/models.py`) gains
`name: Mapped[str | None]` (nullable text) — one Alembic migration. Schemas
(`modules/cutting/schemas.py`): `name: str | None = None` on draft create/update/response,
with the **same normalization as the part name** (max length 64, strip whitespace,
empty → `None`) — extract or mirror the existing `normalize_name` validator. The name:

- round-trips through draft PATCH (autosave path) and appears in the draft list response;
- does **not** flow into results, orders, or pricing — it dies with the draft on order
  placement (deliberate; the order has its own number);
- old rows read as `None`.

### 1.2 Branch options carry the address

`ClientBranchOption` (`modules/client_portal/schemas.py` + `service.branch_options`)
gains `address: str` (from `Branch.address`, already non-null). The `search` filter
extends to `Branch.address.ilike(pattern)` alongside the existing workshop/branch name
match. Response ordering stays `Workshop.name, Branch.name` — grouping is a web-side
view transform.

### 1.3 First order seeds the profile's preferred branch

In the sales place-order path: when a **client-placed** (self-serve) order is created and
the client's profile `preferred_branch_id` is `NULL`, set it to the order's `branch_id`
in the same transaction (via the `access` module's public `api.py` — no cross-module
private imports). Staff walk-in placement never touches the profile. Effect: the editor's
branch gate is a **first-draft-only** event for a returning client; it never overwrites
an existing preference.

Tests: name normalization + PATCH round-trip + list response; old drafts return
`name: null`; branch-options search matches address; preferred-branch seeding fires only
on self-serve placement and only from `NULL`.

## 2. Stage B — draft name in the web client

### 2.1 Display fallback (shared helper)

One helper in `web/src/shared/app/clientUi.ts` (or a cutting-scoped module):
`draftDisplayName(draft)` → `draft.name` when set, else the existing material-derived
label (distinct material short-names, first 2 + `+N`), else `«Nomsiz chizma»`. **The UUID
prefix is removed everywhere** — no client surface renders `draft.id` fragments.

### 2.2 Editor header — click-to-edit title (`CuttingEditorView.vue`)

- The editor gets a title line above the branch strip: the draft name rendered with a
  dashed underline + pencil icon (visual affordance from the agreed mockup). Click (or
  Enter/Space when focused) swaps in a text input (max 64) pre-filled with the raw
  `name` (empty when `null` — the fallback is a placeholder, never committed as a value).
- Commit on Enter or blur; Esc cancels. Commit PATCHes `{ name }` through the existing
  draft-update/autosave path (one mutation, existing debounce/save-state indicator
  applies). Unsaved new drafts hold the name locally (same pattern as `localBranchId`)
  and send it with the first draft-creating save.
- Read-only drafts (confirmed/order-bound view) render the name as plain text, no edit
  affordance. Workshop (walk-in) scope gets the same field — staff can name a walk-in
  draft.

### 2.3 Drafts list (`DraftsView.vue`)

- Row title becomes `draftDisplayName(draft)`; named drafts render in the primary ink,
  unnamed fall back to the material label in secondary ink with a muted `(nomsiz)`
  suffix — the metadata line (N qism · N panel · date) already disambiguates.
- `draftTitle()`'s UUID prefix logic is deleted. The delete-confirm dialog message leads
  with the display name: `«{nomi}» — N qismli chizma butunlay o'chiriladi…`.
- Client home's «continue» list and any other surface that labels a draft reuse the same
  helper.

## 3. Stage C — shared branch picker (`CuttingBranchPicker.vue` rework)

One component serves both the editor gate and the order wizard. Structure (from the
agreed mockup):

### 3.1 Anatomy

- **Search field always visible** (drop the `options.length > 6` condition). Client-side
  filter over the loaded options, matching workshop name + branch name + **address**
  (new field from §1.2). Placeholder teaches the address case:
  `Ustaxona, filial yoki manzil — masalan: Chilonzor`.
- **Pinned recommendation**: when a `recommendedBranchId` prop is set and that branch is
  present (and, in quote mode, quotable), it renders as a standalone card *above* the
  groups with the accent treatment (2px accent border) and the
  `Tavsiya — afzal filial` pill. It is excluded from its group below (no duplicate row).
- **Workshop groups**: remaining branches group by `workshop_id`, ordered by workshop
  name. Group header: initials avatar (first letters of workshop name) + workshop name +
  `N filial` count. Branches render as rows inside **one bordered container** per group
  (dense rows, not per-branch cards).
- **Row anatomy**: branch name · status pill (`faol` success-tint / `vaqtincha yopiq`
  warning-tint) · second line `address · Bugun: {hours}` (+ `closed_reason` when
  temporarily closed). One tap selects (`aria-pressed`); `temporarily_closed` stays
  selectable as today (durable preference).
- Empty search result keeps the existing dashed «Mos filial topilmadi» row.

### 3.2 Quote mode (order wizard)

Props extend with an optional per-branch quote map. When present:

- each row gains a right-aligned price column — mono total + `so'm · N panel` sub-line;
- branches whose quote failed render disabled (reduced opacity, not focusable for
  selection) with the reason line in danger ink (reuse the existing per-branch error
  labels: not-carried / closed / pricing-gap) and `—` in the price column; they sort to
  the **bottom of their group**;
- group order: the group containing the cheapest quotable branch first, then by that
  group's cheapest price ascending; groups with no quotable branch last (alphabetical
  among themselves). Within a group, quotable branches sort by price ascending;
- the **selected** row expands in place to show the 3-line breakdown (Kesish xizmati ·
  Materiallar · Krom yopishtirish) that today lives on every card — unselected rows show
  only the total. Selecting another row moves the expansion.

Without the quote map (editor mode) the component behaves as §3.1 only.

## 4. Stage D — editor branch gate presentation (`CuttingEditorView.vue`)

Branch-first stays mandatory; the picker moves into an **`AppModal` dialog** (per
DESIGN.md: pick/edit flows are modal, never inline on-page cards — the current inline
`client-card` picker section is removed):

- **Modal shell**: `AppModal` (z-80 layer, body scroll lock, Esc/overlay/× close, focus
  trap — all existing behavior). Title `Filialni tanlang`; body = the §3 picker in
  editor mode (search field on top, grouped list scrolls inside the modal body). One tap
  on a row applies the branch immediately (PATCH / local pre-filter as today) **and
  closes the modal** — the «Bekor qilish / Qo'llash» button pair is removed; selection
  *is* the action, and a mid-draft change is non-destructive by design (existing
  recovery affordances stay).
- **No branch yet** (first draft / no profile preference): the editor renders a gate
  empty-state card in place of the parts grid — icon + explainer
  `Materiallar va narxlar filialga qarab farq qiladi — avval filialni tanlang.` + primary
  «Filial tanlash» button — and the modal **opens automatically** on entry. The modal
  stays dismissable (never a trap): closing it returns to the empty-state card with the
  parts UI still gated; the button reopens it.
- **Branch chosen**: the summary strip stays (branch · workshop + `O'zgartirish`), and
  `O'zgartirish` opens the same modal.
- Because §1.3 seeds the profile preference on the first order and draft-create already
  seeds from the profile, a returning client normally lands **straight in the parts
  grid** (no modal, no empty state) — verify this path stays intact.
- Fixed-branch (workshop walk-in) mode is untouched: locked label, no picker.
- The **order wizard is explicitly not a modal**: there the branch choice is the step's
  primary page content (§5) — an overlay over an empty step would invert the hierarchy.

## 5. Stage E — order wizard branch step (`ClientOrderNewView.vue`)

Replace the flat per-branch card list with the shared picker in quote mode:

- quotes load as today (all active branches, per-branch errors kept); the quote map +
  error labels feed §3.2; skeletons stay for the loading state;
- `recommendedBranchId` = the draft's `preferred_branch_id` when it can fulfil
  (pre-selection behavior unchanged);
- selection drives the existing `selectedBranchId` → «Davom etish» flow; the
  carry-recovery, no-active-branch, and quotes-error empty states are unchanged;
- the step header may show the draft's display name in the sub-line
  (`«{nomi}» uchun ustaxona tanlang`) — small, optional polish.

## 6. Copy (Uzbek, exact strings)

| Where | String |
| --- | --- |
| Unnamed draft fallback | `Nomsiz chizma` · list suffix `(nomsiz)` |
| Editor title placeholder | `Chizmaga nom bering` |
| Gate explainer | `Materiallar va narxlar filialga qarab farq qiladi — avval filialni tanlang.` |
| Gate button / modal title | `Filial tanlash` / `Filialni tanlang` |
| Picker search placeholder | `Ustaxona, filial yoki manzil — masalan: Chilonzor` |
| Recommendation pill | `Tavsiya — afzal filial` |
| Group branch count | `{n} filial` |
| Status pills | `faol` · `vaqtincha yopiq` |
| Row hours | `Bugun: {open}–{close}` (existing `formatTodayHours`) |
| Price sub-line | `so'm · {n} panel` |
| Cannot-fulfil reason | existing quote error labels (unchanged) |
| Empty search | `Mos filial topilmadi.` |
| Change / close picker | `O'zgartirish` · aria `Yopish` |
| Delete dialog lead | `«{nomi}» — {n} qismli chizma butunlay o'chiriladi. Bu amal qaytarilmaydi.` |
| Wizard sub-line (optional) | `«{nomi}» uchun ustaxona tanlang` |

## 7. Tests

Backend: §1 items listed there.

Web unit (Vitest, colocated `__tests__`):
- `draftDisplayName`: named / material-fallback / empty cases; no UUID anywhere;
- editor title: click-to-edit swap, Enter/blur commit → PATCH payload, Esc cancel,
  placeholder-not-committed, read-only render;
- picker grouping: group by workshop, ordering (quote mode: cheapest-group first,
  in-group price ascending, failed rows last), recommendation extraction (no duplicate);
- picker filter: matches name/workshop/address, empty-state row;
- quote mode: price cell render, disabled failed rows with reason, selected-row
  breakdown expansion moves with selection;
- gate: no-branch auto-opens the modal + renders the empty-state card behind it;
  dismiss returns to the gated empty state (parts UI still hidden); button and
  `O'zgartirish` reopen; tap applies branch + closes the modal.

E2E (extend the existing cutting/order specs, keep small): new client → editor shows
branch gate open → pick branch → enter parts → optimise → name the draft → drafts list
shows the name → place order → (backend) profile preferred branch now set; second draft
opens with no gate.

## 8. Acceptance gates

1. Backend gate green (`ruff check`, `ruff format --check`, `mypy app`, `pytest`).
2. Web gate green (`lint:check`, `format:check`, `typecheck`, `test`, `build`).
3. Docs updated: `docs/ref/entities/cutting.md` (draft `name` field + invariant),
   `docs/ref/features/cutting.md` (gate presentation, picker UX),
   `docs/ref/features/orders.md` (branch-step UI description),
   `docs/domain-model.md` / client entity page (preferred branch now also seeded by the
   first self-serve order).
4. Manual browser pass per the **verify** skill: first-draft gate, returning-client
   no-gate path, walk-in fixed-branch path, wizard with a failing branch, draft rename +
   list display, dark/light and mobile layouts.
5. Existing flows unbroken: pre-change drafts render (`name` null tolerated), staff
   walk-in flow untouched, wizard pre-selection and recovery states behave as before.

## 9. Non-goals

- No geolocation, maps, or distance sorting (outside the operating envelope).
- No draft-name carryover onto orders or results.
- No server-side pagination of branch options (low hundreds of branches load fine; the
  server `search` param stays for future use).
- No change to the branch-first rule itself, walk-in fixed-branch behavior, quoting
  logic, or the order state machine.
