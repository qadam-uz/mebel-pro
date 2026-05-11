# Visual Design — type, color, hierarchy, density, icons, dark mode, data display

## When this matters

Building (or auditing) the visual system: the type scale, the color tokens, how hierarchy is established, how dense or airy the interface is, the icon set, light/dark, and how data is displayed (tables, charts). This is step 5 of the workflow on purpose — it's where the work reads as deliberate, but applying it to a screen with the wrong structure just makes a wrong screen prettier. The aim isn't "decoration"; it's making the right things obvious and the interface feel like one coherent system rather than a pile of parts.

## Principles

### 1. Build one type scale and one set of named text styles

Pick a small set of sizes related by a consistent ratio — e.g. **12, 14, 16, 18, 20, 24, 30, 36, 48** — and a small set of weights, then define *named text styles* on top (`body`, `body-sm`, `heading-1…3`, `label`, `caption`, …) that each pair size + weight + line-height + letter-spacing. Use the named styles, not raw values, so type stays consistent and changes in one place. Two or three sizes do most of the work on most screens; resist a bespoke size per element. And the floors that matter: **body text ≥ 16px** (smaller is a strain, and on mobile a focused input below 16px triggers an annoying browser zoom), **line-height ~1.5** for body (tighter — ~1.1–1.3 — for large headings), **line length ~50–75 characters** (cap the container; see `layout-and-responsive.md`). One or two typefaces; if two, give them clearly different jobs (e.g. a display face for headings, a workhorse for everything else) rather than two that quietly fight.

### 2. Hierarchy: make the eye land in the right order

Every screen has a most-important thing — the eye should find it first, then the second, then the rest, without effort. You establish that with **size, weight, color/contrast, and space** (a heading isn't just bigger — it has air around it; a CTA isn't just colored — it's isolated). Most screens need only ~3 levels of emphasis; if everything is bold and big and colored, nothing leads. The fastest test: **squint at the screen** — does the most important thing still stand out, or does it disappear into a wall of equal-weight stuff? If it competes with five other things, the hierarchy is flat and needs fixing before anything else visual matters.

### 3. Color as a system of roles, not a box of crayons

Define colors by **role**, not appearance, and reference them as **semantic tokens** everywhere: `color-text`, `color-text-muted`, `color-bg`, `surface`, `surface-raised`, `border`, `color-primary` (the brand/action color), and the **status colors** `color-success` / `color-warning` / `color-danger` / `color-info`. Raw hex sprinkled per component makes consistency impossible and dark mode a nightmare. Keep the *accent surface small* — the primary color belongs on the one primary action and a few highlights, not everywhere; an interface that's saturated in brand color has no emphasis left to give. Status colors carry consistent meaning across the product and *always* travel with a non-color signal — an icon, a label (see `accessibility.md`). And every text/background pairing in the system must pass contrast *before* it ships, not as a later cleanup.

### 4. One primary action per screen; everything else recedes

Buttons come in a small hierarchy:

- **Primary** — filled, the accent color: the *one* action you most want taken. One per screen (or per distinct section).
- **Secondary** — outlined or tonal: genuine alternatives.
- **Tertiary / ghost** — text-like: minor or cancel-ish actions.
- **Destructive** — danger color, visually set apart (see `interaction-and-touch.md`).

If a screen shows two filled accent buttons side by side, the user has no idea which is "the" action — pick one. This is as much an information-architecture call as a visual one: deciding the primary action *is* deciding what the screen is for.

### 5. Spacing and density are deliberate, consistent choices

How tight or airy the interface is should be intentional and uniform. A data-dense admin tool legitimately runs tighter than a marketing page — but *within* a product, the density holds steady; you don't get a roomy settings screen next to a cramped dashboard with no reason. Use the **4-based spacing scale** (`layout-and-responsive.md`) for everything, and let **proximity do the grouping**: related items close together, groups separated by more space than the items within them, generous space around the things you want noticed. White space isn't wasted space — it's how the layout says "these belong together" and "look here".

### 6. Iconography: one set, vector, consistent, labeled

Use **one icon library** — Lucide, Heroicons, Material Symbols, Phosphor; pick one and commit — so every icon shares a visual language. Icons are **vector / SVG**, never emoji-as-UI-icons (emoji render differently on every OS, can't take your color/size/stroke, and look unprofessional at any size that matters). Keep **stroke width consistent** within a context (all 1.5px, or all 2px — not mixed), pick **filled *or* outline** as a deliberate system choice (a common pattern: outline for inactive, filled for active/selected), size icons from a small token set (**16 / 20 / 24**), and make sure any icon that *carries meaning* meets **3:1 contrast**. An icon whose meaning isn't self-evident gets a text label — and an icon-only button *always* needs an accessible name (see `accessibility.md`).

### 7. Dark mode is a designed theme, not an inversion

A real dark theme:

- **Surfaces** are dark grey, not pure black (around `#121212`–`#1e1e1e`) — pure black makes edges harsh and OLED smearing worse, and leaves no room to show elevation.
- **Elevation via lighter surfaces** — drop shadows barely read on dark, so a "raised" card is a *lighter* grey, not a shadow.
- **Accent and status colors are desaturated and slightly lightened** — fully saturated colors vibrate unpleasantly on dark backgrounds.
- **Text is off-white, not `#fff`** — full white on dark is harsh; ease it down a notch. Secondary text drops further but still clears its contrast ratio.
- **Modal scrims** around 40–60% black.
- Built through the **same semantic tokens, remapped** — and contrast checked in *both* themes (a pairing that passes in light can fail in dark, and vice versa).

Never invert the light palette — you get muddy, garish, low-contrast results. Dark mode is its own pass.

### 8. Data display: match the form to the question

Tables, lists, and charts each answer different questions; pick the one that fits:

- **Trend over time → line** (or area). **Comparison between categories → bar / column.** **Part of a whole → stacked bar, or — sparingly — a pie/donut with ≤ ~5 slices** (beyond that the slices are indistinguishable; use a bar). **Relationship between two variables → scatter.** **Precise lookup of individual values → a table**, not a chart — charts are for the *shape* of data, tables for the *numbers*.
- Always: **label axes and units**; label series **directly** where you can (beats the eye ping-ponging to a legend) or put the **legend right next to the chart**; give **tooltips on hover/tap** with exact values; distinguish series by **more than hue** (pattern, shape, direct label — and don't make red/green the *only* contrast); start bar-chart value axes at **zero** (truncating exaggerates differences and misleads). Don't over-decorate — no 3D, no gratuitous gridlines, no chartjunk; the data is the point.
- Charts **reflow** on small screens — or degrade to a simpler view or a table — rather than overflowing the viewport.
- Big tables: sticky header, sortable where it helps, **right-align numbers**, and if a table must be wide give it **its own horizontal scroll container** (don't let one wide table drag the whole page sideways — `layout-and-responsive.md`); and it gets a real empty state (`forms-and-feedback.md`).

## Numbers & heuristics

- Type scale: ~**12 / 14 / 16 / 18 / 20 / 24 / 30 / 36 / 48**; named text styles on top; body **≥ 16px**, line-height **~1.5**, line length **~50–75 chars**.
- Emphasis levels: ~**3** (primary / secondary / rest); apply the **squint test** — does the #1 thing still pop?
- Spacing: the **4-based scale** for everything; proximity = grouping.
- Buttons: **one primary per screen**; secondary/tertiary recede; destructive set apart in danger color.
- Color: **semantic tokens** only; accent used sparingly; status colors consistent across the product and *always* with a non-color cue; every pairing passes contrast in **both** themes.
- Icons: **one library**; **SVG only**, never emoji-as-UI; consistent stroke; filled-or-outline as a system; **16 / 20 / 24** sizes; **3:1** contrast when meaningful.
- Dark mode: dark-grey (not black) surfaces; elevation via lighter surfaces; desaturated/lightened accents; off-white text; scrim 40–60%.
- Charts: form fits the question; axes and units labeled; direct labels or a nearby legend; non-hue series differentiation; bar axes from zero; reflows on small screens; a table for precise values.

## Common mistakes

- **A unique font size per element** — twelve sizes that are all "kind of medium"; collapse to a scale and a few named styles.
- **Body text below 16px** — strains the eyes and triggers zoom-on-focus on mobile.
- **Flat hierarchy** — everything bold/big/colored, so nothing leads; fails the squint test.
- **Raw hex everywhere** — no token layer, so consistency drifts and dark mode is unbuildable.
- **Brand color slathered everywhere** — no emphasis left for the action that actually matters.
- **Two co-equal primary buttons** — the user can't tell which one is *the* action.
- **Mixed icon sets / mixed stroke widths / emoji icons** — visual incoherence; reads as "assembled, not designed".
- **Dark mode by inverting light** — muddy, garish, fails contrast; do a real dark pass.
- **Pie chart with 11 slices / 3D bars / a truncated value axis** — chartjunk that obscures, or actively misleads.
- **A chart where a table was wanted** — the user needed the exact numbers; a pretty line graph doesn't give them.
- **A wide table that drags the whole page sideways** — give it its own scroll container.
