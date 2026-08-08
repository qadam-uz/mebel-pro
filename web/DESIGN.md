---
version: alpha
name: Mebel Pro
description: >-
  Design system for the three Vue SPAs (client, workshop, superadmin) — a dense,
  utilitarian back-office language on a cool neutral canvas: graphite carries every
  action, one orange signal marks what needs attention. Realized as @theme tokens in
  src/assets/main.css and shared primitives under src/shared/components/.
colors:
  bg: "#f1f2f4"
  elevated: "#ffffff"
  sunk: "#f6f7f9"
  track: "#e6e8ec"
  deep: "#22252a"
  ink: "#0f1115"
  ink-strong: "#0f1115"
  ink-nav: "#4a5058"
  ink-soft: "#565c66"
  ink-muted: "#666d79"
  divider: "#f0f1f4"
  hairline-soft: "#e9ebef"
  hairline: "#e4e6ea"
  hairline-strong: "#c3c8d0"
  accent: "#22252a"
  accent-hover: "#34383f"
  on-accent: "#f4f2ee"
  signal: "#ff5a1f"
  accent-soft: "#ffe9e0"
  accent-tint: "#ffd8c9"
  accent-deep: "#c53d0c"
  accent-strong: "#a83408"
  success: "#067a4b"
  success-soft: "#e7f5ee"
  success-border: "#cbe8da"
  warning: "#a15c00"
  warning-soft: "#fcf2e2"
  warning-border: "#f2e2bf"
  danger: "#c9302a"
  danger-soft: "#fdecea"
  danger-border: "#f7d3cf"
  info: "#0b6e8d"
  info-soft: "#e8f2f7"
  info-border: "#c9e2eb"
  neutral-soft: "#eef0f3"
  taupe: "#6b5647"
  taupe-soft: "#f3f0ec"
typography:
  page-title:
    fontFamily: "{fonts.display}"
    fontSize: 34px
    lineHeight: 1.1
    fontWeight: 700
    letterSpacing: -0.028em
  panel-title:
    fontFamily: "{fonts.display}"
    fontSize: 19px
    fontWeight: 700
    letterSpacing: -0.02em
  figure-lg:
    fontFamily: "{fonts.display}"
    fontSize: clamp(24px, 2.3vw, 32px)
    lineHeight: 1
    fontWeight: 700
    letterSpacing: -0.03em
  brand:
    fontFamily: "{fonts.display}"
    fontSize: 17px
    fontWeight: 700
    letterSpacing: -0.015em
  row-title:
    fontFamily: "{fonts.sans}"
    fontSize: 15px
    fontWeight: 600
  body-md:
    fontFamily: "{fonts.sans}"
    fontSize: 14px
    lineHeight: 1.5
  label-md:
    fontFamily: "{fonts.sans}"
    fontSize: 13.5px
  label-sm:
    fontFamily: "{fonts.sans}"
    fontSize: 12.5px
    fontWeight: 500
fonts:
  sans: "'Wix Madefor Text', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
  display: "'Wix Madefor Display', 'Wix Madefor Text', system-ui, sans-serif"
rounded:
  xs: 6px
  sm: 8px
  md: 10px
  lg: 11px
  xl: 14px
  2xl: 18px
  full: 999px
shadow:
  panel: "0 1px 2px {ink}/4%, 0 10px 28px -22px {ink}/50%"
  card: "0 1px 2px {ink}/5%, 0 8px 22px -18px {ink}/50%"
  lifted: "0 1px 2px {ink}/6%, 0 14px 32px -20px {ink}/60%"
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
    radius: "{rounded.lg}"
    fontWeight: 600
    padding: 10px 16px
    background: "{colors.accent}"
    color: "{colors.on-accent}"
  input:
    minHeight: 44px
    radius: "{rounded.lg}"
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
here together. Shared primitives live under `src/shared/components/`.

## Overview

A working tool for furniture workshops in Uzbekistan — operators, workshop staff, and clients
who cut panels, move stock, and track money all day. The language is **dense, calm, and
utilitarian**: data-first tables, compact controls (a 40px button, a 44px form field), one clear
action per screen.

The surface is a **cool neutral** — near-white panels floating on a light grey canvas, separated
by whitespace and a soft shadow rather than by ruled lines. Everything a person can *do* is
**graphite**; a single **orange signal** marks the one thing that wants attention. Nothing
decorates: every colour, weight, and elevation step encodes state or hierarchy.

## Colors

One light theme; there is no dark mode. Never hardcode hex in components — always the
semantic `--color-*` tokens.

- **Canvas & surfaces** — `bg` is the cool grey page canvas; `elevated` (white) is panels,
  cards, popovers, modals; `sunk` is the secondary block *inside* a panel (an inset row, a
  station tile, a well); `track` is the trough a segmented control sits in; `deep` is the
  graphite brand surface.
- **Text** — `ink` for body and headings, `ink-soft` for descriptions and labels, `ink-muted`
  for third-level captions, `ink-nav` for a resting sidebar item. `ink-strong` is a legacy alias
  of `ink`; new code writes `ink`.
- **Lines** — three weights, and they are not interchangeable: `divider` for a row separator
  inside a card, `hairline-soft` for a panel edge (the sidebar's right edge), `hairline` for
  input and button borders. `hairline-strong` is the line that must survive on `sunk`, and it
  doubles as the chart's period-max bar.
- **Action — graphite.** `accent` is the single action colour: primary buttons, the focus ring,
  icon tiles, a selected state, `::selection`. `accent-hover` on hover. Text on it is
  `on-accent` — **bone, not white**; pure white on graphite reads as a screen glare.
- **Signal — orange.** `signal` (`#ff5a1f`) is an **accent, not a fill**: the notification dot,
  today's column in a chart, the banding ticks on a job sheet, the cut mark in the logo, a 2px
  rule, a spotlight ring. It gives only **3.1:1 under white text**, so it is never a button
  background and never sits under text. When orange has to carry words it steps down — to
  `accent-deep` on a neutral surface (a text link, a text button), and to `accent-strong` on
  either orange tint. Its tints are the app's *selected* fills: `accent-soft` for an active nav
  item or a chip, `accent-tint` one step stronger.
- **Status** — `success` / `warning` / `danger` / `info`, each with a `-soft` fill for pills and
  banners and a `-border` tint for their outlines. Status colour is never the only signal: pair
  it with the state's word or an icon.
- **Order stages** warm as the work advances — `Yangi` (`neutral-soft` / `ink-nav`) →
  `Tasdiqlangan` (`taupe-soft` / `taupe`) → `Kesilmoqda` (`accent-soft` / `accent-strong`) →
  `Kromkada` (`accent-tint` / `accent-strong`) → `Tayyor` (`success-soft` / `success`), with
  `Tugatilgan` (`neutral-soft` / `ink-soft`) and `Bekor qilingan` (`danger-soft` / `danger`) off
  to the side. The chip always carries the stage's word.
- **Derived values** — shadows/scrims tint from `ink`, focus rings from `accent`, via
  `color-mix(... , transparent)`. Never bake a palette hex into a shadow or ring — a retheme must
  stay a token-file change.

**Three values sit a shade off the handoff, and deliberately.** `AGENTS.md` sets a hard 4.5:1
floor for text, and the handoff's own numbers miss it in three places: `ink-muted` is `#666d79`
rather than `#6b7280` (which gives 4.32:1 on the canvas), `danger` is `#c9302a` rather than
`#d0342c` (4.36:1 on `danger-soft`), and text on **either** orange tint is `accent-strong`
rather than `accent-deep` (4.44:1 on `accent-soft`). All three are visually indistinguishable
from the specified value; none of them changes the design.

## Typography

**Two families, and that is the whole system.** `Wix Madefor Display` for headings and figures,
`Wix Madefor Text` for everything else. There is **no serif and no mono**.

- **Text** is the workhorse. Base body is **14px / 1.5** — a dense back-office, not a marketing
  site. Secondary text 13.5px, captions 12.5px, and 12.5px is the floor.
- **Display** carries identity and magnitude, nothing else: the page title (34px/700/−0.028em),
  a panel title (19px/700/−0.02em), the brand wordmark (17px/700/−0.015em), and a headline
  figure (`clamp(24px, 2.3vw, 32px)`/700/−0.03em). Display is negatively tracked at every size —
  that tightening *is* the voice. Never use it for controls, tables, or labels.
- **Numbers are the Text face's tabular figures.** `font-variant-numeric: tabular-nums` is set
  on `body`, so every digit in the app lines up by default and no column needs a second family.
  No call site writes `font-mono` any more, but `--font-mono` is **not** an alias of the text
  face — it stays a real monospace stack, because Tailwind's Preflight resolves
  `code, kbd, samp, pre` through it and the superadmin's stack traces and JSON dumps have to keep
  their columns. **Money stays compactly scaled** (`formatTiyinParts` / `formatTiyinRow`): a KPI row
  reads on one ruler — `4,12 mln so'm`, not `4 120 000` beside `540 855` — and the exact figure
  lives on the element's `title`.
- **Weight carries meaning**: form input *values* render semibold (600) with placeholders pinned
  to regular — a filled field must read as data, a hint must not. This spans all three apps and
  the composed controls (PhoneInput, FormSelect, SearchCombobox selected values);
  `textarea.mp-input` reason fields stay regular. Buttons are 600.
- **Labels are sentence case in grey**, at normal-to-semibold weight. The old uppercase,
  wide-tracked label is gone from the system — small caps at 11px with 0.08em tracking read as a
  systems console, not as a calm tool.
- **All three locales use the same two families.** Wix Madefor ships a real `cyrillic` subset in
  both, so `ru` and `uz-Cyrl` need no font swap — there is no per-locale `--font-sans` override
  any more, and no risk of a browser mixing two faces inside one word.

## Layout

- **Spacing is a 4px scale** (4 / 8 / 12 / 16 / 24 / 32). Arbitrary values are the visible
  symptom of an absent system.
- **The workshop shell** is a two-column frame that does not scroll as a page: a 264px sidebar
  and the content column, each scrolling on its own inside `var(--app-vh)` — never `100vh`,
  which does not participate in the root zoom. The sidebar holds, top to bottom: the wordmark,
  the branch picker, the one primary create action, the grouped nav, and the account button. The
  68px header above the content holds global search and the two utilities (locale,
  notifications) — nothing else. There is no desktop sidebar-collapse: the 264px column is the
  layout, and below 921px the sidebar becomes the drawer, which carries **the sidebar's whole
  content** (branch card, create action, nav, account) because those controls exist nowhere else.
- **The fixed frame is desktop-only.** Below 921px the page reverts to document scrolling with a
  sticky header, so iOS URL-bar collapse, `scrollLock` and pull-to-refresh keep working; and
  `@media print` resets the frame to `height: auto; overflow: visible` or a printed document
  clips to one screen.
- **Panels sit in a grid with a 16–20px gutter**, `align-items: start`, and never touch. A
  dashboard's two-column split is `minmax(0, 1.65fr) minmax(0, 1fr)`, collapsing to one column
  below 1100px with the **work list first**. A KPI row is `repeat(4, minmax(0, 1fr))` above
  900px and `repeat(2, …)` below it.
- **Filter rows** are the standard list-page header: shared `mp-*` filter classes, persistent
  labels outside the input value, all controls in one row aligned to the same **40px** height,
  compact and sized to their content (not stretched). Filter selects show the plain value only —
  no secondary description text. Role-prefixed classes such as `admin-*` stay inside that role's
  app (the admin app keeps its older 48px stretched filter look).
- **Create buttons**: every add button uses a visible `+` prefix in the label (all apps). The
  workshop's **one** headline create action — `+ Yangi buyurtma` — lives in the sidebar above
  the nav, because it is the app's most-run task and it belongs to the workshop rather than to
  any one list; it carries the same gate the route does (`manage_orders` on an active branch)
  and renders disabled with a reason otherwise. Because it is always on screen, the Buyurtmalar
  list does **not** repeat it. Every *other* list-add button sits at the **right end of the
  filter row** (`.mp-filters > .mp-button`, baseline-aligned with the 40px controls); a page or
  tab without filters renders it as a lone right-aligned `.mp-filters` row directly above the
  table. Page heads are title-only. The one exception is a pair of primary operations (Ombor's
  Kirim + Tuzatish), which spans the full row as a two-column grid.
- **Tables** are the primary data surface: header row on the panel's own background with no fill,
  rows tall and airy, numeric columns right-aligned with tabular figures; event timestamps as
  `DD.MM.YYYY HH:mm`; ledger rows show the business date with a muted "Kiritildi:"
  entry-timestamp line beneath; images in fixed-size framed thumbnails with a non-empty fallback.

## Elevation & Depth

Depth comes from **a panel floating on the canvas**: white on `bg`, lifted by a soft, wide,
low-opacity shadow, and carrying **no border**. Three steps —

```
panel:   0 1px 2px {ink}/4%,  0 10px 28px -22px {ink}/50%
card:    0 1px 2px {ink}/5%,  0  8px 22px -18px {ink}/50%
lifted:  0 1px 2px {ink}/6%,  0 14px 32px -20px {ink}/60%   ← hover on a clickable card
```

— reachable as the `shadow-panel` / `shadow-card` / `shadow-lifted` utilities. Inside a panel the
second level is a **`sunk` fill**, not another shadow, and a row separator is a `divider` line. A
border on a panel is a bug: it fights the shadow and doubles the edge.

Interactive lift is subtle — buttons raise 1px on hover (`translateY(-1px)`), settle on press,
and lose all elevation when disabled. A clickable card deepens its shadow instead of gaining a
border. Coloured glows are gone: nothing separates with a tinted halo any more.

Two overlay layers, and the order matters: dropdown/popover panels teleport at **z-50**; the
modal layer sits at **z-80**. `body.modal-open` locks scroll (position-fixed pin so iOS Safari
can't scroll behind) **and** pins the desktop frame's inner scroller, which the body pin alone
cannot reach.

Desktop paints at `zoom: 90%` on the root (≥769px) — the density the back-office is designed
for. Full-bleed surfaces size from the **`--app-vh` / `--app-vw`** tokens rather than raw
viewport units, which do not participate in the zoom. The `lg` / `xl` / `2xl` breakpoints are
pre-divided by that ratio (922 / 1152 / 1382), so a hand-written `@media (min-width: 1024px)`
fires 11% later than the `lg:` utility — use the utility. Measuring and positioning under the
zoom is an implementation concern: see [`AGENTS.md`](./AGENTS.md).

## Shapes

Radius scale: **8px** for an icon tile, **10px** for a small control (nav item, compact button),
**11px** for buttons and inputs, **14px** for a card or an inset block, **18px** for a panel,
**999px** for pills and status badges. `6px` (`rounded-xs`) survives for the smallest chips, and
2–4px stays for a swatch the scale would round into a circle. Legacy off-scale radii
(5/7/9/12/16px) exist in older CSS — converge on the scale when touching them; don't add new
off-scale values.

## Components

- **Buttons** (`.mp-button`) — 40px min-height, 600 weight, `{rounded.lg}`, 10×16px padding.
  Primary = graphite fill with `on-accent` text; secondary = `sunk` fill with `ink`; tertiary =
  white with a `hairline` border; disabled = 50% opacity, no elevation, `not-allowed` cursor.
  A **text button** is `accent-deep` on nothing — that is the only place orange carries words.
  Submit buttons disable + show progress during async work and end in explicit success or a
  re-enabled error state — never a silent reset.
- **Dropdowns** — use the project dropdown primitive (`ProjectDropdown`); never browser-native
  `<select>` as visible UI in filters, forms, modals, tables, or settings. The primitive matches
  the app surface: crisp radius, elevated popover, visible focus ring, selected check mark,
  hover/active states, keyboard operation (`Enter`/`Space`, arrows, `Esc`, `Tab` close). It takes
  a `#trigger` slot, so a host that needs a different shape — the sidebar's two-line branch
  card — wears its own skin without forking the listbox. Native controls remain acceptable for
  text inputs, textareas, checkboxes, radios, and file inputs until a project primitive exists —
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
- **Segmented control** (`SegmentedControl`) — a **closed set of two or three** choices, all
  visible at once on a `track` trough with 3px padding; the selected segment is a **white
  chip** with a 1px lift shadow and `ink` text, the resting ones are `ink-soft` on the track.
  A dropdown for two options is a click that reveals nothing; past three or four segments the
  row stops fitting and it goes back to `FormSelect`. Keyboard contract is the radiogroup one:
  `role="radiogroup"` + `role="radio"`/`aria-checked`, one tab stop with a roving tabindex,
  arrows wrap, `Home`/`End` jump, focus follows the selection.
- **Status toggles** — in-place toggles are `role="switch"` buttons: track + thumb plus the
  current state's word as a visible text label (never colour alone), disabled while the row
  saves.
- **Icons** — one line set on a 24×24 grid, round caps and joins. `AppIcon` draws it at
  `stroke-width: 2`; the shells inline the same paths at 18px and thin them to `1.8` per host in
  CSS (nav item, chrome button, station tile). Icon-only buttons always carry an accessible name
  that says the action *and* the row it acts on (`Beton bo'yoq — tahrirlash`). An icon tile has two
  treatments and they mean different things: a **graphite** tile with a bone glyph belongs to
  the chrome and the brand, an **`accent-soft`** tile with an `accent-strong` glyph marks a
  production station. An empty state gets neither — it is a `sunk` tile with an `ink-muted`
  glyph, so it cannot be mistaken for a control. One glyph per concept: expand/collapse is
  `chevron-down` rotated 180°, and voiding a row is `ban` — a circle with a diagonal, never
  `trash`, because nothing here is ever deleted.
- **Cursor honesty** — pointer cursor and row hover belong only on clickable controls or
  clickable rows; static table rows stay visually still with the default cursor. A row hover is
  a `sunk` fill, never a tint of the accent — a coloured flash on every row is not an
  affordance, it is a strobe.
- **Clickable rows** — where a table row has one obvious primary action, the row runs it and
  the action column goes away. The control stays a real `RouterLink` or `<button>` in the
  row's identifying cell and is stretched across the row by a pseudo-element (`.row-clickable`
  + `.row-open`), so the row keeps a tab stop, `Enter`, and ⌘-/middle-click on a navigating
  row. `<tr @click>` has none of those and is not the pattern. A second action moves into the
  row's `⋯` menu and keeps its word — a destructive action is never a bare glyph. Anything
  that stays independently clickable inside the row (a status switch, the `⋯` trigger) sits
  above the stretched layer with `.row-above`, never on the cell holding `.row-open`.
- **Headline figures** — two treatments, and the page picks by weight. `.kpi` cards are for a
  dashboard, where the numbers *are* the page: an 18px-radius white panel, a sentence-case
  `ink-soft` label, the figure in Display below it, and one caption line under that — a green
  or red pill when the figure has a delta to report. `.figs` is the lighter row for a page whose
  numbers are context above a table: no border, radius, shadow or background tint — hairlines
  above, below and between, sentence-case labels at normal weight, and the value in Display with
  tabular figures. **Colour lands on the figure only**; the label stays `ink-soft`, and a figure
  whose colour carries meaning also states it in words.
- **Work lists** — a dashboard panel whose rows are *jobs*, not data: each row is a title, a
  detail line, and one action button on the right, separated by `divider` lines. Exactly **one**
  row in the panel carries the graphite primary button — the first row that has an action, which
  is also the most urgent — and every other action is the neutral **`bg`** button, so the eye
  lands on the one thing to do first. `bg` and not `sunk`: one step darker is what gives the
  button an edge against the white panel it sits on. A row appears whenever its condition holds
  and the reader can see the data behind it; the **button** is what follows the grant that can
  *run* the action — it retargets to the narrowest page that reader can open, and drops away
  entirely when there is none, because an instruction the reader cannot carry out is worse than a
  row that only reports. A panel with nothing in it says so.
- **Charts** are read as text first. A bar chart's colour ramp is three steps — `signal` for
  today, `hairline-strong` for the period maximum, `hairline` for the rest — which is a
  deliberately quiet hierarchy, so the numbers themselves must be reachable without it: an
  `sr-only` sentence summarising total / today / peak, and a `<title>` on every bar.
- **Skeletons** fill with `hairline`, not `sunk`: on a white panel `sunk` sits at 1.07:1 and the
  placeholder is invisible. The shimmer sweeps `hairline-strong`, not white.
- **Documents that leave the building** (the akt sverka today) are laid out on screen the way
  they print — title, both parties, period, totals — so print is a restyle of the same DOM,
  not a second implementation. A print stylesheet cannot number pages (no browser implements
  `@page` margin boxes); when page numbers matter, the file comes from the server renderer.
  The cutting-map PDF mirrors four tokens in Python (`backend/app/modules/cutting/rendering.py`)
  — success, danger, ink-muted, ink-soft. That is a sync contract: change them together.

## Copy

Three locales ship: **`uz`** (Latin) is the one copy is *written* in, **`ru`** is its
translation, and **`uz-Cyrl`** is transliterated from `uz` automatically. Every string lives in
`src/shared/i18n/locales/<locale>/<namespace>.json` and reaches the screen through `$t()` — a
literal in a template is a bug in two languages. Copy is part of the design contract, not a
finishing touch: one failure explained two different ways is the same defect as two different
button radii. The rules below are the standard; the glossary under them is the whole vocabulary.

Rules 1–7 are language-independent and bind every locale. Rule 8 is Uzbek orthography and binds
the two Uzbek scripts only.

**1. Say what happened, then what to do.** One sentence where it fits.
`Summa buyurtma qoldig'idan oshib ketdi.` beats `Amal bajarilmadi.` A message the operator
cannot act on is a log line, not copy.

**2. No generic fallback where a specific message is possible.** Every `APIError` code a
user can realistically trigger is enumerated for its role. The two translated apps keep a
**set of codes**, not a bag of copy — `WORKSHOP_ERROR_CODES` (`app/workshopUi.ts`) and
`CLIENT_ERROR_CODES` (`app/clientUi.ts`) resolve through `workshopAdmin.error.<code>` /
`client.error.<code>`, so the sentence follows the active locale instead of freezing at
module-evaluation time. The superadmin app is Uzbek-only and keeps a literal map,
`ADMIN_ERROR_MESSAGES` (`app/adminUi.ts`), with field-level rejections in `apiValidationMessage`
(`app/adminValidation.ts`); the cutting import carries its own, `cuttingImportErrorLabel`
(`stores/cuttingImport.ts`). The generic string is reserved for genuinely unexpected failures —
unhandled 500s, transport errors. A code that reaches the fallback is a missing entry, not a
shrug. When a call site catches an error, it passes `apiErrorCode(error)` through the role's
resolver and keeps its own action-specific sentence as the fallback; a bare `catch {}` that
throws the code away is the bug QAD-123 found and QAD-163 swept.

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

**8. Uzbek Latin orthography** (the `uz` catalog; `uz-Cyrl` is derived from it, so this is
where its quality comes from). The tutuq belgisi is the **ASCII apostrophe `'`** (U+0027)
throughout — `bo'ladi`, `yo'q`, `to'lov`, `ta'minotchi`. Never a backtick (`` ` ``), never
a curly `'`/`'`, never the modifier letters `ʻ`/`ʼ`; they render as visibly different
glyphs and there is no reason for a screen to show four of them. In Uzbek, no Russian
transliteration (`chegirma`, not `skidka`) and no developer shorthand in anything a user can
see — the ban is on borrowing *into Uzbek*, and inverts in the `ru` catalog, where `скидка` is
simply the right word.

**Punctuation is shared by all three locales.** Ellipsis is the single character `…` and belongs
only to progress labels (`Saqlanmoqda…` / `Сохранение…`). Separators are `—` (em dash) between
clauses and `·` between fields, never a hyphen.

**Russian agrees its nouns with numbers.** A counted noun carries three forms in the catalog,
`one | few | many` — `{n} деталь | {n} детали | {n} деталей` — resolved by `Intl.PluralRules`.
Uzbek keeps its single form. A Russian message that concatenates a number and a noun is wrong
even when it reads fine at n=1.

### Glossary

One term per concept, across client, workshop and admin — and one Russian term per Uzbek one,
so the `ru` catalog does not drift into synonyms screen by screen. The **Not** column is the
Uzbek ban list; several of those words (`skidka`, `rasxod`, `nadbavka`) are the *correct*
Russian and appear in the Russian column on purpose.

| Concept                                | Term                | Russian              | Not (in Uzbek)                    |
| -------------------------------------- | ------------------- | -------------------- | --------------------------------- |
| A client's cutting order               | `buyurtma`          | `заказ`              | `zakaz`                           |
| A cut piece on a drawing               | `detal`             | `деталь`             | `qism`, `part`                    |
| A distinct part size on a drawing      | `xil`               | `типоразмер`         | `qator`, `tur`                    |
| A saved cutting drawing                | `chizma`            | `раскрой`            | `eskiz`, `draft`                  |
| A panel sheet                          | `list`              | `лист`               | `plita`, `panel`                  |
| One buyable size of a dekor            | `o'lcham`           | `размер`             | `format`                          |
| A sheet's length × width               | `list o'lchami`     | `размер листа`       | bare `o'lcham`                    |
| A tape's width                         | `lenta eni`         | `ширина ленты`       | bare `o'lcham`, `eni`             |
| Edge tape (the material)               | `kromka`            | `кромка`             | `krom`                            |
| The edge-banding station / stage       | `Krom` / `Kromka`   | `Кромка`             | — _owner's ruling pending_        |
| The cutting station / stage            | `Kesish`            | `Распил`             | —                                 |
| A workshop location                    | `filial`            | `филиал`             | `bo'lim` (= a UI section)         |
| The workshop shell's nav column        | `yon menyu`         | `боковое меню`       | `sidebar`, `panel`                |
| A permission a staff member holds      | `ruxsat`            | `право доступа`      | `grant`                           |
| Everything, across branches            | `Barcha filiallar`  | `Все филиалы`        | `ustaxona-keng`                   |
| A supplier                             | `ta'minotchi`       | `поставщик`          | `yetkazib beruvchi`, `postavshik` |
| Goods arriving into stock (a faktura)  | `kirim` (`K-…`)     | `приход`             | `tushum`                          |
| Money coming in (the finance ledger)   | `tushum`            | `поступление`        | `kirim`                           |
| Money going out                        | `xarajat`           | `расход`             | `rasxod`                          |
| A price reduction                      | `chegirma`          | `скидка`             | `skidka`                          |
| A price addition                       | `ustama`            | `наценка`            | `nadbavka`                        |
| A background job                       | `fon vazifa`        | `фоновая задача`     | `ish`, `scheduler`                |
| A signed statement of account          | `akt sverka`        | `акт сверки`         | —                                 |
| A printed/served document              | `hujjat`            | `документ`           | `xujjat`                          |
| A part fitted onto a sheet             | `joylashtirildi`    | `размещено`          | — _orders never use it_           |
| An order the client just submitted     | `Yuborildi`         | `Отправлен`          | `Joylashtirildi`                  |
| The currency unit                      | `so'm`              | `сум` (`сўм` in Cyrillic Uzbek) | —                      |

`kirim` and `tushum` are **not** synonyms and must never be unified: `Kirim` is a stock
arrival carrying a `K-…` invoice number and lives in Ombor; `Tushum` is a finance-ledger
income row and lives beside `Xarajat`. Likewise `filial` (a place) and `bo'lim` (a section
of the interface) are different words for different things.

`yon menyu` names the 264px column itself, and it is the one word copy uses to send someone
there — below 921px the same content becomes the drawer, so "yon menyuda" stays true on a phone
and no string has to name two places.

`o'lcham` is the whole a branch carries and prices — a dekor at one thickness in one size
(`2750×1830×18`, or `2 mm × 19` for kromka); the API calls it a `format` and always will, but no
screen does. It **contains** a `list o'lchami` (`2750×1830`) or a `lenta eni` (`19`), so those
two stay qualified wherever they are named: a bare `O'lcham` on a size chip group, a column, or
an "add" dialog reads as the whole and hides the part. `format` never reaches a screen in any
locale.

`joylashtirish` belongs to the cutting result and nothing else — a part fitted onto a sheet
(`Joylashtirildi 12/14`, `Fayldan joylashuv`). The `new` order status used to borrow the same
word, so a client read `Joylashtirildi 12/14` on the result screen and then saw their order
sitting in a stage called `Joylashtirildi` — one meaning a placed part, the other a submitted
order. Submitting is `Yuborildi`.

## Brand

There is no pictorial logo. The name **is** the mark, with a single cut running through it.

- **Wordmark** — `MEBEL | PRO` in Display 800, uppercase, `−0.02em`. The cut sits between the
  words: width 7% of the cap height, 15% taller than the caps, in `signal` orange. Minimum size
  13px on screen / 6mm in print — below that the cut disappears and the icon takes over. This is
  the standard for print and partner material; no app screen renders it today.
- **Icon** — the name abbreviated: `M`, the cut, `P`, bone on a graphite tile. Proportions come
  from the tile's edge, so they hold at every size: radius 22%, letters at 44% of the edge in
  Display 800, the cut 6% wide and 53% tall, gaps of 4.7%. **Below 16px the `P` is dropped** and
  only `M` and the cut survive — two letters at that size smear into one shape. The 16px frame of
  the `.ico` is the only place that reduction ships.
- **The icon exists twice, and both have to say the same thing.** *In the app* it is markup —
  `BrandMark.vue` renders the letters as type, so every shell and every login screen draws one
  component and none of them reaches for the icon file. *As an asset*
  (`web/public/favicon.svg`, the 180 / 192 / 512 rasters, the maskable variant, the three-size
  `.ico`) the letters are **Wix Madefor Display 800 outlines**, because an SVG used as an icon
  renders in a restricted mode with no webfont and a `<text>` element would fall back to whatever
  the OS has. Regenerate the assets from the font, never by tracing.
- **One-colour** — for a stamp, a fax or an engraving the cut goes graphite with the letters.
- **Clear space** — one cap height on every side, and nothing inside it.
- **Orange is never the mark's background** and never fills a button: the cut would vanish and
  text on it would fail contrast.

## Do's and Don'ts

**Do**

- Use semantic tokens for every colour, radius, and spacing value.
- Keep one primary (graphite) action per screen, visually dominant — the shell's own
  `+ Yangi buyurtma` is the workshop's single exception, and a screen that has it does not add
  a second copy.
- Pair every status colour with a word or icon.
- Reach for `signal` orange only in small areas — a dot, a rule, one bar, a ring, a tick.
- Open create/edit in `AppModal`; seed inline-listbox selects inside it.
- Right-align money/quantities with tabular figures and the unit beneath.
- Focus ring on everything interactive: 3px graphite outline, 2px offset, and keep the 5px
  light halo — it is the only thing that makes the ring visible on a graphite fill.

**Don't**

- Don't hardcode hex — no raw colours outside `@theme`.
- Don't fill a button, a badge background, or any surface under text with `signal` orange
  (3.1:1 under white); step down to `accent-deep`/`accent-strong` when orange carries words.
- Don't put a border on a panel or a KPI card — the shadow is the edge — and don't add a
  coloured glow to anything.
- Don't use uppercase, wide-tracked labels, or a serif or monospace face anywhere.
- Don't use native `<select>` as visible UI, or `ProjectDropdown` inside a modal.
- Don't use placeholders as labels, or clear a form on a validation error.
- Don't swallow an error code in a bare `catch {}`, or ship a string with a backtick
  apostrophe, an English fallback, or a term that isn't in the glossary.
- Don't write user-facing text as a literal in a template or component — it goes in the
  catalog, in `uz` and `ru`, or it ships in one language.
- Don't split a sentence around an interpolation into two keys, and don't build a Russian
  count by concatenating a number and a noun.
- Don't put hover/pointer affordances on non-clickable rows.
- Don't add font sizes below 12.5px, or a touch target under 44px of hittable area — the
  desktop chrome runs at 38px and grows under `@media (pointer: coarse)`.
- Don't invent off-scale radii or spacing; don't add a dark theme ad hoc — it doesn't exist.
