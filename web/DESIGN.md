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
- Admin forms mark required fields with text, not color alone; unmarked fields are optional.
- Admin filters use persistent labels outside the input value, and controls in one filter row
  align to the same height. Object-creation buttons in the admin app use a visible `+` prefix
  in the label.
