# DESIGN SYSTEM

This file is the deterministic design system contract — tokens, primitives, density, and
interaction behavior — for the three Vue SPAs. Realize it in shared code: `@theme` tokens in
`src/assets/main.css`, primitives and composed components under `src/shared/`.

## Primitives

- **Dropdowns** use the project dropdown primitive (a shared Vue component). Do not use
  browser-native `<select>` as visible UI in
  filters, forms, modals, tables, or settings. The primitive must match the app surface:
  crisp radius, elevated popover, visible focus ring, selected check mark, hover/active
  states, and keyboard operation (`Enter` / `Space`, arrows, `Esc`, `Tab` close).
- Native controls remain acceptable for text inputs, textareas, checkboxes, radios, and
  file inputs until a project primitive exists for a specific case.
- Image uploads use the shared preview primitive: a framed preview, native file input triggered
  by labelled buttons, upload/error state in the field, and a remove action when an image is set.
  Data tables show images in fixed-size framed thumbnails with a non-empty fallback.
- Forms mark required fields with a compact `*` beside the persistent label, backed by
  `required` / `aria-required` semantics and inline errors; unmarked fields are optional.
- Filter rows use shared `mp-*` filter classes with persistent labels outside the input value,
  and controls in one filter row align to the same height. Workshop filter controls are
  compact: 40px tall, sized to their content (not stretched across the row), and filter
  selects show the plain value only — no secondary description text. Colored dot prefixes
  are reserved for status filters, mapped from the matching status-pill palette. Date
  ranges use the shared date-range picker primitive: one trigger opening a popover with
  preset shortcuts and a calendar; selections auto-apply (no apply button). Role-prefixed
  classes such as `admin-*` stay inside that role's app (the admin app keeps its older
  48px stretched filter look).
- Create/edit forms open in `AppModal` dialogs, never as inline on-page cards; reason-gated
  confirmations (void, revert, cancel) use `ConfirmDialog`. Inside modals use the
  inline-listbox selects (`FormSelect`, `SearchCombobox`, `MultiSelectFilter`) —
  `ProjectDropdown` teleports its panel at z-50 and would render behind the modal layer
  (z-80).
- Object-creation buttons use a visible `+` prefix in the label (all apps). In the
  workshop app every list-add create button sits at the **right end of the filter row**
  (`.mp-filters > .mp-button`, baseline-aligned with the 40px controls); a page or tab
  without filters renders the button as a lone right-aligned `.mp-filters` row directly
  above the table. Page heads are title-only. The one exception is a pair of primary
  operations (Ombor's Kirim + Tuzatish), which spans the full row as a two-column grid.
- Form input **values** render semibold (600) with placeholders pinned to regular — a
  filled field must read as data, a hint must not. This spans all three apps
  (`input.mp-input` for workshop/client, `.admin-field input` was already 600) and the
  composed controls (PhoneInput, FormSelect and SearchCombobox selected values);
  `textarea.mp-input` reason fields stay regular.
- Numeric fields sanitize **as you type** (the PhoneInput pattern — an invalid character
  never sticks, paste included) via `src/shared/app/inputSanitizers.ts`: money fields
  keep digits/grouping/one decimal mark, quantities keep digits + one separator, and the
  inventory adjustment takes a **signed quantity with a required leading + or −**
  ("-2" decreases, "+5" increases; inputmode stays text so mobile keyboards carry the
  signs) — structural validation stays with the submit-path parsers.
- Table cells: numeric columns (money, quantities) right-align in mono with the unit on a
  small muted second line so digits align for comparison. Event timestamps render as
  `DD.MM.YYYY HH:mm`; ledger rows show the business date with a muted "Kiritildi:"
  entry-timestamp line beneath. In-place status toggles are `role="switch"` buttons —
  track + thumb plus the current state's word as a visible text label (never color
  alone), disabled while the row saves.
- Pointer cursor and row hover belong only on clickable controls or clickable rows. Static table
  rows stay visually still and use the default cursor.
