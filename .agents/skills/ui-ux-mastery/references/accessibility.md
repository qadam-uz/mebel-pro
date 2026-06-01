# Accessibility

## When this matters

Always — accessibility isn't a feature you bolt on, it's a property the interface either has or doesn't, and retrofitting it is far costlier than building it in. Pay special attention when specifying interaction, choosing colors, building forms, or reviewing anything. The bar to keep in mind is **WCAG 2.1 / 2.2 level AA** — the common legal and professional baseline. And accessible design is *better* design generally: captions help people in noisy rooms, high contrast helps in sunlight, keyboard support helps power users, clear errors and clear structure help everyone.

## Principles

### 1. Everything works from the keyboard

A meaningful fraction of users can't or don't use a pointer — motor impairments, screen-reader users, power users, anyone whose trackpad just died. So every interactive element is reachable by Tab, operable by Enter/Space (and Arrows where it's a composite widget like a menu, tablist, or radio group), in an order that matches the visual layout, with no traps (you can always Tab back out of anything). If you build a custom control, you've signed up to implement its keyboard behavior — match the equivalent native control's. The corollary: prefer native elements (`<button>`, `<input>`, `<a href>`, `<select>`) precisely because they bring all of this for free.

### 2. Focus is always visible

A keyboard user needs to see where they are. Every focusable element shows a clear focus indicator — a ring or outline ~2–3px thick, with its own ≥3:1 contrast against whatever's behind it, not clipped by `overflow: hidden` on an ancestor. Never `outline: none` unless you're replacing it with something at least as visible — this is the single most common accessibility regression. Use `:focus-visible` to show the indicator for keyboard interaction without the "ugly ring when I click with the mouse" complaint that tempts people to remove it entirely.

### 3. Contrast is measured, not eyeballed

- **Text vs. its background:** ≥ **4.5:1** for normal text; ≥ **3:1** for large text (≥ 24px, or ≥ 19px bold).
- **Meaningful non-text:** ≥ **3:1** against adjacent colors — icons that carry information, input borders, focus rings, the boundary of a button, chart elements, toggle states.

Eyeballing fails, *especially* for designers and developers with good vision — "looks fine to me" is not the test. Use a contrast checker. Disabled elements are exempt from the ratio, but should still read clearly as "disabled", not "invisible".

### 4. Never encode meaning in color alone

Roughly 1 in 12 men has some color vision deficiency, and everyone loses color fidelity in bright light or on a cheap screen. So a red border alone doesn't say "error" — add an icon and text. A green dot alone doesn't say "online" — add a label. Chart series distinguished only by hue are unreadable for many people — add patterns, direct labels, or shape. Treat color as an *enhancement* to a signal that already exists without it.

### 5. Everything has an accessible name, role, and state

Screen readers announce an element's **role** (button, link, checkbox, heading, …), its **name** (its label), and its **state** (pressed, expanded, checked, disabled, current). Native HTML gives you this for free — another reason to reach for `<button>` over `<div onclick>`. Specifics:

- **Icon-only buttons** need a text label — visually hidden text, or `aria-label`.
- **Form inputs** need a programmatically associated `<label>` (not just visually adjacent text).
- **Images that convey meaning** need `alt` text describing the meaning; purely decorative images need empty `alt=""` so screen readers skip them.
- **Headings** (`<h1>`–`<h6>`) form the document outline screen-reader users navigate by — use them in order, for real headings, not for "this text should be big".
- **ARIA** is the patch for when native semantics genuinely don't cover a pattern. The first rule of ARIA: don't use ARIA if a native element would do — wrong or redundant ARIA is *worse* than none.

### 6. Respect the user's stated preferences

The OS exposes preferences; honor them.

- **`prefers-reduced-motion: reduce`** → cut or drastically tone down non-essential animation (no parallax, no big slides, no scale-ins, nothing that travels distance or zooms); a quick, small opacity fade is usually fine. The interface must still convey every state change without the motion.
- **Larger text / zoom** → the layout holds at **200%** with no loss of content or function and no horizontal scrolling. (Use relative units; don't pin everything in px and lock the user out.)
- **Dark mode preference** → an actual dark design (see `visual-design.md`), not a literal inversion.

These aren't fringe users; they're users who told the system what they need.

### 7. Manage focus across state changes

When the UI changes out from under the user, move focus deliberately:

- Open a **modal/dialog** → focus moves *into* it and is trapped there until it closes; on close, focus returns to the element that opened it.
- **Submit a form with errors** → focus the first invalid field (and scroll it into view).
- **Navigate to a new view** in a single-page app → move focus to the new view's heading; the browser won't do it for you, so the screen-reader user is left adrift otherwise.
- **Delete the item you were focused on** (a row, a card) → move focus to the next sensible thing, not to nowhere.

"Focus went nowhere" means a keyboard or screen-reader user is now lost in the page.

## Heuristics & checklist

- Unplug the mouse. Can you do everything? Can you always see where you are? Can you get back out of everything?
- Run a contrast checker on text (4.5:1 / 3:1) *and* on meaningful icons, borders, and focus rings (3:1).
- For every status, validation, and chart encoding: is there a non-color signal too?
- Every icon-only button: text label? Every input: associated `<label>`? Every meaningful image: `alt`? Every decorative one: `alt=""`?
- Custom widget? Does its keyboard behavior match the native equivalent, and does it announce role/name/state?
- Does it survive 200% zoom? Does it calm down under `prefers-reduced-motion` while still showing every state change?
- Modals: focus moves in, is trapped, returns on close?
- Form submit with errors: does focus land on the first bad field?
- Headings used in order, for real headings, forming a sensible outline?

## Common mistakes

- **`outline: none` with nothing in its place** — the most common accessibility bug; it blinds keyboard users.
- **`<div>` / `<span>` as buttons and links** — no role, no keyboard, no focus, nothing announced; use `<button>` and `<a>`.
- **Placeholder as the only label** — fails screen readers and vanishes on input (see `forms-and-feedback.md`).
- **Contrast judged by eye** — a "looks fine" from someone with 20/20 vision proves nothing.
- **Color-only status and color-only chart series** — invisible to a large minority of users.
- **ARIA sprinkled to "make it accessible"** — wrong/redundant ARIA breaks things; reach for native elements first.
- **Modal that doesn't trap or restore focus** — keyboard users fall out the back of it into the page behind.
- **SPA route change with no focus move** — screen-reader users don't know the page changed.
- **Animation with no `prefers-reduced-motion` path** — at best unpleasant; for some users, genuinely nauseating or vestibular-triggering.
- **Headings used for styling** — `<h3>` because "I wanted it that size"; wrecks the outline screen-reader users navigate by.
