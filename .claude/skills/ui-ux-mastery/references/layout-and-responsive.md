# Layout & Responsive

## When this matters

Laying out any screen, choosing breakpoints and grids, deciding how something reflows from phone to desktop, handling safe areas and fixed bars, or chasing down a "the page jumps around when it loads" complaint. The goal: every piece of content is reachable and readable at every viewport, nothing is trapped, and the page doesn't shove itself around as it loads.

## Principles

### 1. Mobile-first, because it forces priority

Design the smallest viewport first, then add room — not the reverse. The small screen has no space for "we'll just put it on the side", so it forces you to decide what *actually matters*; scaling that up is easy, while cramming a desktop design down is how you end up with 9pt text and a horizontal scrollbar on a phone. Start with one column, the essential content in priority order, and progressively *enhance* — more columns, more visible at once, more secondary content surfaced — as space allows.

### 2. Breakpoints follow the content, not device names

Add a breakpoint where the *layout needs one* — where a line of text gets too long to read comfortably, where there's room for a second column, where the nav should switch from a drawer to a bar — not at a fixed list of "phone / tablet / laptop" widths. The device landscape keeps changing and your content's needs don't map to it cleanly. Pick a small set (often ~3–4 — e.g. ~640 / ~768 / ~1024 / ~1280 as a common starting point) and use them *consistently*; a breakpoint set that varies per component is chaos with extra steps. Between breakpoints, use fluid units (`%`, `fr`, `clamp()`, `min()`/`max()`) so the layout adapts smoothly rather than in lurches.

### 3. One spacing scale, everywhere

Pick a scale built on a base unit — 4px is the common choice: **4, 8, 12, 16, 24, 32, 48, 64, 96** — and draw *every* margin, padding, and gap from it. Consistent spacing is most of what "looks designed" actually is; ad-hoc values (a 13px here, a 27px there) read as sloppiness even to people who can't articulate why. And spacing is structural, not just air: related things sit closer together than unrelated things — **proximity = grouping**. Generous space around something is how you say "look here".

### 4. Use a grid, and respect the container

A consistent column grid (commonly 12 columns on wide screens, fewer as it narrows) keeps things aligned across screens and over time. On wide viewports, **cap the content's max-width** — text that runs the full span of a 27" monitor is unreadable (target ~50–75 characters per line; see `visual-design.md`) — and decide what to do with the leftover width: center the column, or use it for a sidebar, or allow a deliberately wider canvas for a specific surface. Either way, *decide*; don't let the layout sprawl edge to edge by default. Margins and gutters can grow with the viewport; the reading column needn't.

### 5. Account for fixed elements and safe areas

Fixed headers, bottom bars, floating action buttons, and the on-screen keyboard all *occupy* space — content must not hide behind them. Pad the scroll container by their height; on mobile, add bottom padding so the last list item clears a bottom bar and isn't covered when the keyboard opens. Modern devices also have **safe-area insets** — rounded corners, notches/camera cutouts, the OS gesture strip — so keep interactive controls and important text out of those regions (use the platform's safe-area values, like `env(safe-area-inset-*)`, rather than guessing magic numbers).

### 6. No horizontal scrolling — ever (unless it's the point)

A horizontal scrollbar on the *page* is almost always a bug: something is wider than the viewport — an unconstrained image, a table with a `min-width`, a row that won't wrap, a long unbroken string. Hunt it down (`overflow-x` audits, `max-width: 100%` on media, `min-width: 0` on flex children, `overflow-wrap`/`word-break` on text). The legitimate exceptions are *intentional* horizontal scrollers — a carousel, a wide data table inside its own scroll container — and those need an obvious affordance signalling that more content exists sideways. This must also hold at 200% zoom (see `accessibility.md`).

### 7. Reserve space for everything that loads later

The page jumping as images decode, ads slot in, web fonts swap, or async content arrives is one of the most-hated experiences — and it actively causes mis-taps when a button shifts under a finger mid-tap. Prevent it:

- Give images and media **explicit `width`/`height`** (or wrap them in an `aspect-ratio` box) so their space is held before they load.
- Size **skeleton placeholders** like the real content they're standing in for.
- **Reserve room for things that *might* appear** — a validation-message slot under a field, a banner area — rather than letting them push the layout when they show up.

This is the layout side of *perceived performance*: a page that loads in pieces but doesn't *move* feels fast and stable; a fast page that lurches feels broken.

## Numbers & heuristics

- Spacing scale: 4-based — **4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96**; everything snaps to it.
- Breakpoints: a small, consistent set (~**640 / 768 / 1024 / 1280** is a fine starting point); add one only where content demands it; fluid units between them.
- Content/reading column max-width on wide screens so text stays **~50–75 chars/line**; margins may grow, the column needn't.
- Grid: ~**12 columns** wide, collapsing to fewer (or one) as it narrows.
- Layout shift: target near-zero — explicit media dimensions, `aspect-ratio` boxes, correctly-sized skeletons, reserved slots for conditional content.
- Test at minimum: a small phone (~360px wide), a large phone, a tablet (portrait *and* landscape), a wide desktop — and at 200% zoom.

## Common mistakes

- **Desktop-first, then squished** — the phone layout becomes an afterthought with tiny text and a sideways scrollbar.
- **Breakpoints named after devices** — `@media (tablet)` instead of "where the second column fits"; brittle and arbitrary.
- **Spacing by vibes** — values picked ad hoc per component; the inconsistency reads as carelessness.
- **Content sprawling edge-to-edge on a huge monitor** — 200-character lines nobody can read; cap the column.
- **Content hidden behind a fixed bar or the keyboard** — the last list item, or the submit button, unreachable; pad the scroll area.
- **Ignoring safe-area insets** — a button tucked under the notch or in the gesture strip, half-tappable.
- **A stray horizontal scrollbar** — one unconstrained element drags the whole page sideways.
- **No space reserved for async content** — the page lurches as images and late content land, and buttons move under fingers mid-tap.
