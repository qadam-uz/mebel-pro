# DESIGN SYSTEM

The selected visual direction is still represented by `web/prototypes/prototype-full/`.
Until the Vue design system is extracted, that prototype is the executable reference for
tokens, primitives, density, and interaction behavior.

## Primitives

- **Dropdowns** use the project dropdown primitive (`mp-select` in the HTML prototype,
  later a shared Vue component). Do not use browser-native `<select>` as visible UI in
  filters, forms, modals, tables, or settings. The primitive must match the app surface:
  crisp radius, elevated popover, visible focus ring, selected check mark, hover/active
  states, and keyboard operation (`Enter` / `Space`, arrows, `Esc`, `Tab` close).
- Native controls remain acceptable for text inputs, textareas, checkboxes, radios, and
  file inputs until a project primitive exists for a specific case.
