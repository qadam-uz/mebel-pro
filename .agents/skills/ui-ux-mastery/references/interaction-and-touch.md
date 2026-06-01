# Interaction & Touch

## When this matters

Whenever you're specifying or reviewing anything a user touches, clicks, drags, or hovers — buttons, links, toggles, menus, cards, list rows, draggable handles, sliders. This is "interaction integrity": does the thing *look* interactive, is it actually hittable, does it *respond*, does it tell the user what happened? When this layer is broken, no amount of visual polish or clever flow design rescues the screen — it just feels broken, and "feels broken" is fatal.

## Principles

### 1. Affordance: interactive things look interactive; static things don't

Users decide what's clickable in a fraction of a second, from visual cues — a button looks filled or outlined or raised; a link is set apart (an underline, or a clear color difference *plus* something non-color); a draggable thing has a grip. The corollary matters just as much: don't style non-interactive things to look clickable (a static card wearing a button's drop shadow), and don't make the clickable thing look like plain text. Consistency is part of this — once "filled rounded rectangle in the accent color" means "primary button" in your interface, a filled rounded rectangle that *isn't* a button is a lie the user has to learn to distrust.

### 2. Hit targets are bigger than they look

A target must offer **≥ 44×44 CSS px** of *hittable area* — which can extend invisibly past the visual bounds via padding or a pseudo-element; the glyph can be 16px as long as the *target* is 44. Push toward **48px** when targets crowd together, and keep **≥ 8px of gap** between adjacent ones, because fingers are imprecise and a mis-tap that fires the *wrong* action erodes trust fast. Targets near screen edges, corners, or system gesture strips need extra inset — that's exactly where accidental activations happen. The tiny 16px "✕" close button is the classic offender: pad its target, don't enlarge its glyph.

### 3. Every interactive element has a full set of states

Depending on what it is: **rest**, **hover** (pointer only — see #5), **focus** (keyboard — see `accessibility.md`), **active/pressed**, **disabled**, **loading/busy**, **selected/checked**, **error**. Each needs a distinct, intentional visual. Two constraints on those visuals:

- Pressed and hover states must **not change the element's size in a way that reflows its neighbors** — animate color, shadow, or a `transform: scale()` that doesn't affect layout, not `width`/`padding`/`margin`. A row that jumps as the pointer crosses it is jarring.
- A **disabled** element looks clearly disabled (reduced emphasis) *and* is genuinely non-interactive — and ideally communicates *why* it's disabled (a tooltip, helper text, an inline note), because a dead button with no explanation reads as a bug, not a state.

### 4. Feedback is immediate — within ~100ms

When a user acts, *something* visible must change within roughly 100ms, or the interface feels unresponsive and they'll act again — and now you've got a double-submit or a double-navigation. The feedback scales to the wait:

- Instant action → a pressed/active flash is enough.
- < ~1s → a subtle inline spinner or a brief busy state.
- ~1–10s → a determinate progress indicator or a skeleton, *and disable the trigger*.
- > ~10s → progress, the ability to keep working elsewhere, and ideally a cancel.

A button that kicks off async work shows a busy state *and disables itself* so it physically can't be fired twice; server-side idempotency is the backstop, not the first line.

### 5. Don't depend on hover

Hover doesn't exist on touch devices and isn't reachable by keyboard, so anything available *only* on hover is, for a large share of users, simply absent. Hover is fine for *enhancements* — a tooltip with extra detail, a subtle row highlight — but the menu, the row actions, the "edit" affordance must be reachable without it: visible by default, or revealed by focus/tap as well. Also: don't make hover targets so fiddly that the revealed menu vanishes the instant the pointer crosses a 2px gap to reach it.

### 6. Gestures: discoverable, forgiving, never the only way

Swipe-to-delete, pull-to-refresh, drag-to-reorder, pinch-zoom — fine as *accelerators*, but a hidden gesture is a feature most users never find, so anything important also has a visible control. Gestures must not fight the platform's own (an edge-swipe drawer that collides with the OS "back" gesture is a constant misfire). Destructive gestures need a confirmation or — better — an undo. And give visual feedback *during* the gesture — the row sliding under the finger, the list compressing as you drag — so it feels direct rather than like a guess that either works or doesn't.

### 7. Make destructive and irreversible actions resist reflexes

Delete, discard, send, pay, overwrite, reset — these get extra friction proportional to how bad the mistake is: visual separation from routine actions, a danger color, and a label that *names the consequence* ("Delete 3 files", not "OK"). Then either a confirmation step *or* — better wherever feasible — an **undo**: let the user act fast and recover, rather than nagging them with a dialog every single time. Never put a destructive action where muscle memory expects something safe (a "Delete" sitting where "Save" usually is; a swipe that deletes with no undo).

## Numbers & heuristics

- Touch/click target: **≥ 44×44 CSS px** hittable area; **≥ 48** in dense clusters; **≥ 8px** between adjacent targets; extra inset near edges and gesture zones.
- Feedback latency budget: visible response **< 100ms**; show a loading indicator if the wait exceeds **~1s**; determinate progress + disabled trigger if it's longer; cancellable past **~10s**.
- Press feedback fires in ~**80–150ms** and is visible (highlight/ripple/scale) — but doesn't reflow neighbors.
- Tooltips appear on hover **and** on focus; never put essential information *only* in a tooltip.
- Write the **state inventory** per control: which of rest / hover / focus / active / disabled / loading / selected / error apply, and what each looks and behaves like.

## Common mistakes

- **16px icon, 16px target** — small glyph *and* small hit area; pad the target to 44 without enlarging the glyph.
- **Hover-only menus and row actions** — invisible on touch, unreachable by keyboard; reveal them on focus/tap too, or keep them visible.
- **No busy state on async buttons** — user clicks again → double-submit; disable + spin on click.
- **Pressed/hover state that resizes the element** — the row jumps as the pointer moves; animate color/shadow/scale, not layout.
- **Disabled control with no explanation** — looks like a bug; say *why* it's disabled, or don't show it disabled.
- **Hidden-gesture-only features** — "you can swipe to archive" that 90% of users never discover; pair every gesture with a visible control.
- **Destructive action one reflex-tap away** — "Delete" where "Save" usually sits; a swipe that deletes with no undo.
- **Things that look clickable but aren't** (and vice versa) — borrowed button styling on static cards; links that look like body text.
- **Fiddly hover bridges** — the menu disappears when the pointer crosses the gap to reach it.
