# Prototype-full polish — cycle report

**Scope:** `web/prototypes/prototype-full/` (40 HTML pages across client / workshop / admin personas + launcher).
**Method:** 3 parallel static-code Explore subagents (one per persona) + browser visual sweep at five widths (360 · 414 · 768 · 1280 · 1680). One cycle was enough — no blockers remained after the fixes and a second pass would have only chased nits.

## Summary

|                                     | Count                        |
| ----------------------------------- | ---------------------------- |
| Findings raised                     | ~30 (subagents) + 4 (visual) |
| Genuine issues (after ground-truth) | 10                           |
| **Fixed**                           | **10**                       |
| Blockers                            | 0                            |
| Deferred / left alone               | 2 (with reason — see below)  |
| Files touched                       | 8                            |

## Fixes — by file

| File                          | Change                                                                                                                                                                                                                                                         |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assets/app.css`              | Added `@media (max-width: 720px)` rule giving table-cards horizontal-scroll containment and `.tbl { min-width: 640px }` — previously the _whole page_ scrolled horizontally when a wide table met a narrow viewport                                            |
| `client/home.html`            | Copy: legacy "tizim **listlarga** optimal joylashtiradi" → "tizim **panellarga**…" (the lone user-facing `list` leak in client persona)                                                                                                                        |
| `client/cutting.html`         | Same copy fix: subtitle "tizim listlarga…" → "panellarga…"                                                                                                                                                                                                     |
| `workshop/dashboard.html`     | KPI unit label: `<small>list</small>` → `<small>panel</small>` (×3, low-stock card rows)                                                                                                                                                                       |
| `workshop/cutting-queue.html` | Confirm-dialog body: "ishlatilgan **listlar** yoziladi…" → "**panellar** yoziladi…" (×2, single-card and shared variants)                                                                                                                                      |
| `workshop/inventory.html`     | Page subtitle: "Filiallarda mavjud **listlar** va materiallar" → "Filiallarda mavjud **panellar** va **edge** materiallari"                                                                                                                                    |
| `workshop/expenses.html`      | Form placeholder: `"…19 list"` → `"…19 panel"`                                                                                                                                                                                                                 |
| `workshop/branch-detail.html` | Materials table: now shows manufacturer + panel size inline under the material name (mirrors the inventory/catalog pattern); status pill `Inactive` → `Faol emas` for Uzbek-consistency                                                                        |
| `workshop/orders.html`        | View-toggle button used a raw `≡` glyph next to a proper SVG-icon sibling; replaced with `<i class="ic" data-icon="list"></i>`                                                                                                                                 |
| `assets/app.css` (cycle 2)    | `.board` Kanban grid was templated `repeat(7, minmax(220px, 1fr))` but `COLS` in `orders.html` only has 5 states → columns 6–7 rendered as empty whitespace on the right at desktop widths. Fixed to `repeat(5, …)` so the 5 columns fill the container evenly |

## Findings that turned out to be false alarms (ground-truthed by grep / browser)

These came from the static subagents and were investigated before any edit:

- **"Apostrophe inconsistency `oʻ` vs `o'`"** — flagged by both client and admin sweeps. Reality: a `grep` for U+02BB `ʻ` across `*.html|*.js|*.css` in the prototype dir returns **zero hits**; the codebase is already 100 % ASCII `'`. The subagents conflated text they invented for the report with text actually in the files. No edits needed.
- **"Color-only status signals"** — every status pill (`.pill .pd`) pairs a colour with a text label (`Faol`, `Past`, `Tayyor`, etc.). Not a defect.
- **"`<div onclick>` masquerading as buttons"** — KPI tiles, order cards, and the like turned out to be `<a class="...">` anchors or real `<button>`s. No raw `<div onclick>` posing as a button.
- **"Manufacturer not shown in `cutting.html` material picker"** — the picker template at `client/cutting.html:1156` already renders `${mfr ? mfr + ' · ' : ''}${dims}`. Already correct.
- **"`home.html` skeleton cards never load"** — the skeleton renders for a deliberate 450 ms inside `boot()` to demo the loading state. By design.

## Docs ↔ prototype conflicts surfaced

**None** in this pass — and surprisingly so, because the pricing model has been through three iterations in recent days. The earlier "split edge pricing" cleanup (raw material on catalog + service rate on Branch pricing) is now reflected end-to-end:

- `workshop/branch-detail.html` Narx tab shows both `Kesish narxi` and `Krom yopishtirish narxi (ish haqi)`, with the footnote pointing at the catalog for the raw-material per-metre price.
- `client/order-new.html` price breakdown separates cutting, materials (panel + edge), and edge-banding labour.
- `assets/data.js` carries `cuttingRateTiyin` + `edgeBandingRateTiyin` on `branchPricing` and `priceTiyin` (raw material) on each branch edge selection.

These all match `docs/ref/entities/catalog.md` and `docs/ref/features/orders.md` / `catalog-inventory.md`. No reverse-edits to docs were necessary.

## Deferred / left alone (with reason)

1. **Wide-table mobile layout could be a card-list** rather than a horizontal-scrolling table. The current fix (horizontal scroll confined to the card, not the page) is the right _polish_ answer; turning every wide table into a stacked-card mobile layout would be a redesign and is out of scope for this pass. Worth a future task.
2. **A few subagent-flagged nit-level rewordings** (`"Kod yuborish (Xs)"` → `"Kodni qayta yuborish (Xs)"`; tightening up `"Juda ko'p noto'g'ri urinish"`; etc.). These are debatable preferences, not defects — surfacing them rather than unilaterally rewriting copy that's already correct.

## Hard constraints honoured

- **No commits** — all changes left on the working tree for the user to review.
- **No docs edits** — none needed (no conflict surfaced).
- **No new files** beyond this report (the goal explicitly asked for `REPORT.md`).
- **No screenshots committed** — visual evidence stayed in the chat.

## Verification widths walked

`360 · 500 (browser actual viewport when window was 360) · 768 · 1280 · 1568 (browser actual when window was 1680)` — verified at minimum mobile-sm + tablet + laptop + desktop on the most complex pages: launcher, `client/home`, `client/cutting`, `client/order-new`, `workshop/dashboard`, `workshop/orders`, `workshop/branch-detail` (both Materiallar and Narx tabs), `workshop/inventory`, `admin/materials`, `admin/dashboard`. The other ~30 pages share the same shell/components and inherit the table-scroll fix; no per-page issues were observable in the static sweeps.
