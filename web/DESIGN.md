---
version: alpha
name: Mebel Pro
description: >-
  Design system for the three Vue SPAs (client, workshop, superadmin) — a dense,
  utilitarian back-office language on a warm paper canvas with an ultramarine
  accent. Realized as @theme tokens in src/assets/main.css and shared primitives
  under src/shared/components/.
colors:
  bg: "#f5f4ef"
  elevated: "#ffffff"
  sunk: "#edebe2"
  deep: "#211f19"
  ink: "#23221c"
  ink-strong: "#3b382e"
  ink-soft: "#57544a"
  ink-muted: "#68645a"
  hairline: "#e7e4da"
  hairline-strong: "#d5d1c3"
  accent: "#4341c6"
  accent-hover: "#4f4dd3"
  accent-soft: "#edecfa"
  accent-tint: "#d9d8f5"
  accent-deep: "#322f96"
  success: "#217a3c"
  success-soft: "#eaf5eb"
  success-border: "#cfe7d2"
  warning: "#96490a"
  warning-soft: "#faf1de"
  warning-border: "#eedfba"
  danger: "#b5372a"
  danger-soft: "#fbedea"
  danger-border: "#f2d3cb"
  info: "#0b6e8d"
  info-soft: "#e6f2f7"
  info-border: "#c9e2eb"
typography:
  headline-lg:
    fontFamily: "'Source Serif 4', 'Charter', 'Iowan Old Style', Georgia, serif"
    fontSize: 32px
    fontWeight: 600
  brand:
    fontFamily: "'Source Serif 4', 'Charter', 'Iowan Old Style', Georgia, serif"
    fontSize: 19px
    fontWeight: 600
  body-md:
    fontFamily: "'Hanken Grotesk', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 14px
    lineHeight: 1.5
  label-md:
    fontFamily: "'Hanken Grotesk', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 13px
  label-sm:
    fontFamily: "'Hanken Grotesk', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 11px
  numeric-md:
    fontFamily: "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"
    fontSize: 13px
rounded:
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  full: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
components:
  button:
    minHeight: 40px
    radius: "{rounded.sm}"
    fontWeight: 700
    padding: 10px 16px
    background: "{colors.accent}"
  input:
    height: 40px
    valueWeight: 600
    labelPosition: outside-persistent
  popover:
    surface: "{colors.elevated}"
    zIndex: 50
  modal:
    surface: "{colors.elevated}"
    zIndex: 80
  status-pill:
    radius: "{rounded.full}"
---

# Mebel Pro — design system

This file is the **design system** for the three Vue SPAs and nothing else — tokens, surfaces,
type, components, and the words the product uses. How to build against it, and the bar a screen
has to clear before it ships, are working instructions and live in
[`AGENTS.md`](./AGENTS.md).

The frontmatter tokens are the machine-readable source; they mirror `@theme` in
`src/assets/main.css` one-to-one (`colors.accent` → `--color-accent`). Change a value there and
here together. Shared primitives live under `src/shared/components/`. The static landing
(`web/landing/`) styles itself and is out of scope.

## Overview

A working tool for furniture workshops in Uzbekistan — operators, workshop staff, and clients
who cut panels, move stock, and track money all day. The language is **dense, calm, and
utilitarian**: data-first tables, compact 40px controls, one clear action per screen. Serif
display type gives the brand a human voice; everything operational is a plain sans. Uzbek is
the only shipped locale — copy is concise and specific, never vague. Nothing decorates:
every color, weight, and elevation step encodes state or hierarchy.

## Colors

One light theme; there is no dark mode. Never hardcode hex in components — always the
semantic `--color-*` tokens.

- **Canvas & surfaces** — `bg` is the warm limestone-paper page canvas; `elevated` (white)
  is cards, popovers, modals; `sunk` is inset wells (table headers, disabled fields); `deep`
  is the dark brand surface (shell chrome). The whole neutral ramp is warm-cast — it sits
  with the wood-tone material content instead of fighting it.
- **Text** — `ink` (warm graphite) for body, `ink-strong` for emphasis, `ink-soft`/
  `ink-muted` for secondary and captions. `::selection` inverts to accent/white.
- **Borders** — `hairline` for resting dividers, `hairline-strong` where separation must
  survive on `sunk` surfaces.
- **Accent** — ultramarine `accent` is the single brand/action color: primary buttons, focus
  rings, active nav, links. `accent-hover` on hover, `accent-soft`/`accent-tint` for
  selected and tinted fills, `accent-deep` for gradient depth and text on `accent-tint`.
  Use it sparingly — one primary action per screen.
- **Status** — `success` / `warning` / `danger` / `info`, each with a `-soft` fill for pills
  and banners and a `-border` tint for their outlines. Status color is never the only
  signal: pair it with the state's word or an icon. Colored dot prefixes are reserved for
  status filters, mapped from the status-pill palette.
- **Derived values** — shadows/scrims tint from `ink`, glows and focus rings from `accent`,
  via `color-mix(... , transparent)`. Never bake a palette hex into a shadow or ring — a
  retheme must stay a token-file change.

## Typography

- **Sans (Hanken Grotesk)** is the workhorse. Base body is **14px / 1.5** — this is a dense
  back-office, not a marketing site. Table and control text runs 12–13.5px; micro-captions
  bottom out at 10.5–11px, never smaller.
- **Serif (Source Serif 4)** is reserved for identity: the brand wordmark (19px/600) and
  page-head display (`headline-lg`, 32px/600 in the client app). Don't use serif for
  controls, tables, or labels.
- **Mono (JetBrains Mono)** for numeric table columns — money and quantities right-aligned
  so digits line up for comparison, with the unit on a small muted second line.
- **Weight carries meaning**: form input *values* render semibold (600) with placeholders
  pinned to regular — a filled field must read as data, a hint must not. This spans all
  three apps and the composed controls (PhoneInput, FormSelect, SearchCombobox selected
  values); `textarea.mp-input` reason fields stay regular. Buttons are 700.

## Layout

- **Spacing is a 4px scale** (4 / 8 / 12 / 16 / 24 / 32). Arbitrary values are the visible
  symptom of an absent system.
- **Filter rows** are the standard list-page header: shared `mp-*` filter classes,
  persistent labels outside the input value, all controls in one row aligned to the same
  **40px** height, compact and sized to their content (not stretched). Filter selects show
  the plain value only — no secondary description text. Role-prefixed classes such as
  `admin-*` stay inside that role's app (the admin app keeps its older 48px stretched
  filter look).
- **Create buttons**: every list-add button uses a visible `+` prefix in the label (all
  apps). In the workshop app it sits at the **right end of the filter row**
  (`.mp-filters > .mp-button`, baseline-aligned with the 40px controls); a page or tab
  without filters renders it as a lone right-aligned `.mp-filters` row directly above the
  table. Page heads are title-only. The one exception is a pair of primary operations
  (Ombor's Kirim + Tuzatish), which spans the full row as a two-column grid.
- **Tables** are the primary data surface: numeric columns right-aligned in mono; event
  timestamps as `DD.MM.YYYY HH:mm`; ledger rows show the business date with a muted
  "Kiritildi:" entry-timestamp line beneath; images in fixed-size framed thumbnails with a
  non-empty fallback.

## Elevation & Depth

Depth comes from **surface steps, not heavy shadows**: `sunk` → `bg` → `elevated`, separated
by hairlines. Shadows are reserved for true overlays (dropdown popovers, modals, toasts).
Interactive lift is subtle — buttons raise 1px on hover (`translateY(-1px)`), settle on
press, and lose all elevation when disabled.

Two overlay layers, and the order matters: dropdown/popover panels teleport at **z-50**;
the modal layer sits at **z-80**. `body.modal-open` locks scroll (position-fixed pin so iOS
Safari can't scroll behind).

Desktop paints at `zoom: 90%` on the root (≥769px) — the density the back-office is designed
for. Full-bleed surfaces size from the **`--app-vh` / `--app-vw`** tokens rather than raw
viewport units, which do not participate in the zoom. Measuring and positioning under it is an
implementation concern: see [`AGENTS.md`](./AGENTS.md).

## Shapes

Radius scale: **6px** for buttons and inputs, **8px** for cards and popover items, **12px**
for modals and larger cards, **16px** for hero surfaces, **999px** for pills and status
badges. Legacy one-off radii (5/7/9/10px) exist in older CSS — converge on the scale when
touching them; don't add new off-scale values.

## Components

- **Buttons** (`.mp-button`) — 40px min-height, 700 weight, `{rounded.sm}`, 10×16px padding.
  Primary = accent fill; disabled = 50% opacity, no elevation, `not-allowed` cursor. Submit
  buttons disable + show progress during async work and end in explicit success or a
  re-enabled error state — never a silent reset.
- **Dropdowns** — use the project dropdown primitive (`ProjectDropdown`); never
  browser-native `<select>` as visible UI in filters, forms, modals, tables, or settings.
  The primitive matches the app surface: crisp radius, elevated popover, visible focus
  ring, selected check mark, hover/active states, keyboard operation (`Enter`/`Space`,
  arrows, `Esc`, `Tab` close). Native controls remain acceptable for text inputs,
  textareas, checkboxes, radios, and file inputs until a project primitive exists —
  but **never `<input type="date">`**, which renders in the browser's OS locale
  (`07/19/2026` on en-US) and so can't hold the app's date convention.
- **Server-backed pickers** — when the candidate set is too large or too live to preload, the
  combobox queries the server instead of filtering a page it already holds (`SearchCombobox`
  with `serverFiltered` + `loading` + `searchDebounceMs`). Non-negotiable: the query is
  **debounced** (never a request per keystroke), the panel shows a loading row and a
  no-results row, an explicit clear skips the debounce, and a standing footer hint names what
  the list contains and what it searches. Rich rows go through the `#option` slot — the plain
  label still drives the input's text.
- **Modals** — create/edit forms open in `AppModal` dialogs, never as inline on-page cards;
  reason-gated confirmations (void, revert, cancel) use `ConfirmDialog`. Inside modals use
  the inline-listbox selects (`FormSelect`, `SearchCombobox`, `MultiSelectFilter`) —
  `ProjectDropdown` teleports its panel at z-50 and would render behind the modal layer
  (z-80).
- **Forms** — required fields get a compact `*` beside the persistent label, backed by
  `required`/`aria-required` semantics and inline errors; unmarked fields are optional.
- **Numeric input** sanitizes **as you type** (the PhoneInput pattern — an invalid character
  never sticks, paste included) via `src/shared/app/inputSanitizers.ts`: money keeps
  digits/grouping/one decimal mark; quantities keep digits + one separator; the inventory
  adjustment takes a **signed quantity with a required leading + or −** ("-2" decreases,
  "+5" increases; inputmode stays text so mobile keyboards carry the signs). Structural
  validation stays with the submit-path parsers.
- **Image upload** — the shared preview primitive: framed preview, native file input
  triggered by labelled buttons, upload/error state in the field, a remove action when an
  image is set.
- **Dates** — one calendar serves the whole app (`CalendarMonths`: Monday-first grid, arrow
  keys, `PageUp`/`PageDown` by month, `Esc` closes and returns focus). Two hosts wrap it:
  `DateRangePicker` for filters — one trigger opening a popover with preset shortcuts and the
  calendar, selections auto-apply (no apply button) — and `DateField` for a single date on a
  form, which types and displays **dd.mm.yyyy** in every locale while speaking the API's
  `yyyy-mm-dd`, honours `min`/`max` (out-of-range days are unclickable, a typed one blocks
  submit), and drops into the usual `<label class="field">` wrapper.
- **Filter bars** (`.mp-filters`) — filters **auto-apply** (debounced for text) with no apply
  button, and because auto-apply is invisible by itself, the bar must prove it worked: while
  any filter is active, a `role="status"` line under the bar shows the live result count
  ("Filtr bo'yicha N ta buyurtma topildi", "Yangilanmoqda…" while refreshing) — a silent list
  swap reads as "nothing happened". Every filter **clears itself** — dropdowns via their
  default option, text filters via an inline ✕ shown only when non-empty — so a control that
  clears one field is always inside that field. A bar-level **reset-all** ("Hammasini
  tozalash") is a convenience for the multi-filter case only: it appears from the **second**
  active filter on, because with one filter active it would duplicate that filter's own clear
  sitting right beside it. **No two visible controls may do the same thing.** Filtered-empty
  keeps the no-results empty state, never first-run copy.
- **Segmented control** (`SegmentedControl`) — a **closed set of two or three** form choices,
  all visible at once on a `sunk` track, selected segment filled `accent-soft` with
  `accent-deep` text. A dropdown for two options is a click that reveals nothing; past three
  or four segments the row stops fitting and it goes back to `FormSelect`. Keyboard contract
  is the radiogroup one: `role="radiogroup"` + `role="radio"`/`aria-checked`, one tab stop
  with a roving tabindex, arrows wrap, `Home`/`End` jump, focus follows the selection.
- **Status toggles** — in-place toggles are `role="switch"` buttons: track + thumb plus the
  current state's word as a visible text label (never color alone), disabled while the row
  saves.
- **Icons** — `AppIcon` (one SVG set, 24×24 stroke grid); icon-only buttons always carry an
  accessible name that says the action *and* the row it acts on
  (`Beton bo'yoq — tahrirlash`). One glyph per concept: expand/collapse is `chevron-down`
  rotated 180°, and voiding a row is `ban` — a circle with a diagonal, never `trash`, because
  nothing here is ever deleted.
- **Cursor honesty** — pointer cursor and row hover belong only on clickable controls or
  clickable rows; static table rows stay visually still with the default cursor.
- **Clickable rows** — where a table row has one obvious primary action, the row runs it and
  the action column goes away. The control stays a real `RouterLink` or `<button>` in the
  row's identifying cell and is stretched across the row by a pseudo-element (`.row-clickable`
  + `.row-open`), so the row keeps a tab stop, `Enter`, and ⌘-/middle-click on a navigating
  row. `<tr @click>` has none of those and is not the pattern. A second action moves into the
  row's `⋯` menu and keeps its word — a destructive action is never a bare glyph. Anything
  that stays independently clickable inside the row (a status switch, the `⋯` trigger) sits
  above the stretched layer with `.row-above`, never on the cell holding `.row-open`.
- **Headline figures** — two treatments, and the page picks by weight. `.kpi` cards are for a
  dashboard, where the numbers *are* the page. `.figs` is the lighter row for a page whose
  numbers are context above a table: no border, radius, shadow or background tint — hairlines
  above, below and between, sentence-case labels at normal weight, and the value in mono
  ~22px with tabular numerals. **Colour lands on the figure only**; the label stays
  `ink-muted`, and a figure whose colour carries meaning also states it in words.
- **Documents that leave the building** (the akt sverka today) are laid out on screen the way
  they print — title, both parties, period, totals — so print is a restyle of the same DOM,
  not a second implementation. A print stylesheet cannot number pages (no browser implements
  `@page` margin boxes); when page numbers matter, the file comes from the server renderer.

## Copy

Uzbek (Latin) is the only shipped locale. Copy is part of the design contract, not a
finishing touch: one failure explained two different ways is the same defect as two
different button radii. The rules below are the standard; the glossary under them is the
whole vocabulary.

**1. Say what happened, then what to do.** One sentence where it fits.
`Summa buyurtma qoldig'idan oshib ketdi.` beats `Amal bajarilmadi.` A message the operator
cannot act on is a log line, not copy.

**2. No generic fallback where a specific message is possible.** Every `APIError` code a
user can realistically trigger gets its own entry in the role's error map —
`workshopErrorMessages` (`app/workshopUi.ts`), `CLIENT_ERROR_LABELS` (`app/clientUi.ts`),
`ADMIN_ERROR_MESSAGES` (`app/adminUi.ts`), plus the field-level `apiValidationMessage`
(`app/adminValidation.ts`) and `cuttingImportErrorLabel` (`stores/cuttingImport.ts`). The
generic string is reserved for genuinely unexpected failures — unhandled 500s, transport
errors. A code that reaches the fallback is a missing entry, not a shrug. When a call site
catches an error, it passes `apiErrorCode(error)` through the map and keeps its own
action-specific sentence as the fallback; a bare `catch {}` that throws the code away is
the bug QAD-123 found and QAD-163 swept.

**3. No blame, no apology, no filler.** No `Iltimos`, no exclamation marks, no
`muvaffaqiyatli` — a success toast *is* the success, so it states the outcome
(`Kirim K-0007 yozildi.`), never the fact that something worked.

**4. Verb-first, sentence case.** Buttons are actions: `Buyurtma yaratish`, never
`Yaratish uchun bosing`. Sentence case everywhere — never ALL CAPS, never Title Case; only
the first word and proper nouns are capitalised. A destructive confirm names its
consequence rather than saying `OK`.

**5. Empty states invite, not apologise.** Name the space, then offer the action:
`Bu chizmada detal yo'q` + `Material tanlang`. `Hech narsa topilmadi` alone is not an empty
state, and a body that restates its own title is not a body. **First-run and
filtered-empty are different copy** — "change the filter" is useless advice when nothing
exists yet, so a list that can be filtered branches on whether a filter is active.

**6. Placeholders show a real example**, not a repeat of the label: `+998 90 123 45 67`,
not `Telefon raqamini kiriting`. Search inputs are the one exception — their placeholder
names what the search covers (`Ism yoki login`) and carries **no trailing ellipsis**.

**7. One term per concept.** The glossary below is the list. When a new concept needs a
word, it goes in the glossary in the same commit that introduces it.

**8. Uzbek Latin orthography.** The tutuq belgisi is the **ASCII apostrophe `'`** (U+0027)
throughout — `bo'ladi`, `yo'q`, `to'lov`, `ta'minotchi`. Never a backtick (`` ` ``), never
a curly `'`/`'`, never the modifier letters `ʻ`/`ʼ`; they render as visibly different
glyphs and there is no reason for a screen to show four of them. Ellipsis is the single
character `…` and belongs only to progress labels (`Saqlanmoqda…`). Separators are `—` (em
dash) between clauses and `·` between fields, never a hyphen. No Russian transliteration
(`chegirma`, not `skidka`) and no developer shorthand in anything a user can see.

### Glossary

One term per concept, across client, workshop and admin.

| Concept                                | Term                | Not                       |
| -------------------------------------- | ------------------- | ------------------------- |
| A client's cutting order               | `buyurtma`          | `zakaz`                   |
| A cut piece on a drawing               | `detal`             | `qism`, `part`            |
| A saved cutting drawing                | `chizma`            | `eskiz`, `draft`          |
| A panel sheet                          | `list`              | `plita`                   |
| Edge tape (the material)               | `kromka`            | `krom`                    |
| The edge-banding station / stage       | `Krom` / `Kromka`   | — _owner's ruling pending_ |
| A workshop location                    | `filial`            | `bo'lim` (= a UI section) |
| A permission a staff member holds      | `ruxsat`            | `grant`                   |
| Everything, across branches            | `Barcha filiallar`  | `ustaxona-keng`           |
| A supplier                             | `ta'minotchi`       | `yetkazib beruvchi`, `postavshik` |
| Goods arriving into stock (a faktura)  | `kirim` (`K-…`)     | `tushum`                  |
| Money coming in (the finance ledger)   | `tushum`            | `kirim`                   |
| Money going out                        | `xarajat`           | `rasxod`                  |
| A price reduction                      | `chegirma`          | `skidka`                  |
| A price addition                       | `ustama`            | `nadbavka`                |
| A background job                       | `fon vazifa`        | `ish`, `scheduler`        |
| A signed statement of account          | `akt sverka`        | —                         |
| A printed/served document              | `hujjat`            | `xujjat`                  |

`kirim` and `tushum` are **not** synonyms and must never be unified: `Kirim` is a stock
arrival carrying a `K-…` invoice number and lives in Ombor; `Tushum` is a finance-ledger
income row and lives beside `Xarajat`. Likewise `filial` (a place) and `bo'lim` (a section
of the interface) are different words for different things.

## Do's and Don'ts

**Do**

- Use semantic tokens for every color, radius, and spacing value.
- Keep one primary (accent) action per screen, visually dominant.
- Pair every status color with a word or icon.
- Open create/edit in `AppModal`; seed inline-listbox selects inside it.
- Right-align money/quantities in mono with the unit beneath.
- Focus ring on everything interactive: 3px accent outline, 2px offset (`:focus-visible`).

**Don't**

- Don't hardcode hex — no raw colors outside `@theme`.
- Don't use native `<select>` as visible UI, or `ProjectDropdown` inside a modal.
- Don't use placeholders as labels, or clear a form on a validation error.
- Don't swallow an error code in a bare `catch {}`, or ship a string with a backtick
  apostrophe, an English fallback, or a term that isn't in the glossary.
- Don't put hover/pointer affordances on non-clickable rows.
- Don't use serif for operational UI, or add font sizes below 10.5px.
- Don't invent off-scale radii or spacing; don't add a dark theme ad hoc — it doesn't exist.
