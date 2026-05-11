# Motion

## When this matters

Adding or reviewing any animation or transition — things appearing or disappearing, state changes, page/view transitions, drag feedback, loading indicators, micro-interactions on buttons and toggles. Motion is the last layer of the workflow because it's the smallest fraction of the value and the easiest to overdo: good motion is almost invisible (it just makes things feel right); bad motion is the thing everyone notices and nobody likes.

## Principles

### 1. Motion must mean something — cause → effect

Every animation should express a relationship: *this* came from *there*; *this* turned into *that*; *that* happened because *you did this*. A panel slides in from the edge it lives on, so you know where it went and how to dismiss it. A deleted row collapses in place, so you see *which* item left. A new item fades or scales in, so you don't wonder where it came from. A validation message slides down so you connect it to the field above. Motion that doesn't carry meaning — decorative drifting, bouncing "for personality", things animating just because the library makes it one line — is noise that costs performance and patience. Before animating, answer: *what does this motion tell the user?* No answer → no animation.

### 2. Fast — measured in milliseconds, not seconds

UI animation is functional, not cinematic.

- **Micro-interactions** (hover, press, toggle, small reveals): **~150–200ms**.
- **Larger transitions** (a modal, a side panel, a meaningful layout change): **~200–300ms**, up to ~**400ms** for genuinely large movements.
- Past ~400ms it stops feeling responsive and starts feeling like *waiting*.
- **Exit faster than enter** — roughly **60–70%** of the enter duration — because the user has decided to move on, and dawdling on the way out feels sluggish.

When in doubt, make it faster. Almost no UI animation is too quick; plenty are too slow.

### 3. Easing that mimics the physical world

Linear motion — constant speed, abrupt stop — looks robotic; real things accelerate and decelerate.

- **Entering / moving into view → `ease-out`** (starts quick, settles gently; feels responsive).
- **Exiting / moving out of view → `ease-in`** (eases away).
- **Moving between two on-screen positions → `ease-in-out`**.
- **Spring / physics-based curves** often feel even more natural for *interactive* motion (a dragged sheet that settles into place) — but keep them snappy, not bouncy-for-the-sake-of-bounce. Match the curve to the action: a quick toggle wants a tight ease-out, not a long springy overshoot.

### 4. Animate only the cheap properties

Animate **`transform`** (translate / scale / rotate) and **`opacity`** — the compositor handles those on the GPU without re-laying-out or repainting the page, so they hold 60fps. Animating `width`, `height`, `top`/`left`, `margin`, `padding`, etc. forces layout on every frame → jank, especially on mid-range phones. Need to animate size or position? Use a `transform: scale()` / `translate()`, or a technique like FLIP, rather than the layout properties directly. (Animating `height: auto` for an accordion is the canonical trap — measure and use transforms, or accept a clip-based approach.)

### 5. Interruptible — the user is always in charge

If a user can trigger an animation, they can trigger it again mid-flight — toggle, toggle-back; open, immediately close. The animation must handle that gracefully: reverse or redirect smoothly *from wherever it currently is*, never queue up a backlog, freeze, or snap. And animation never *blocks* interaction — the user can click through it; it never holds them hostage waiting for it to finish. A spinner is the rare loop-until-done case, and even then the surrounding UI stays responsive.

### 6. Respect `prefers-reduced-motion`

A real population finds motion uncomfortable or vestibular-triggering, and they've told the OS so. When `prefers-reduced-motion: reduce` is set: drop the big stuff entirely — slides, parallax, scale-ins, anything that travels distance or zooms — and either remove the transition or replace it with a quick, small opacity fade (a gentle cross-fade is generally fine; it doesn't *move*). Crucially, the interface must convey every state change *without* relying on the motion — don't let "the only way you know the panel opened is the slide" happen. Build the reduced-motion path in from the start, not as a bolt-on.

### 7. Loading & progress motion: honest and proportional

Indeterminate spinner for short, unknowable waits; **determinate** progress (a real bar that fills toward a real end) when you can estimate — because a progress bar that lies, or stalls forever at 99%, is worse than no bar at all. Skeletons (with a subtle shimmer) for content that's coming — and the shimmer should be slow and gentle, not a strobe. Match the indicator to the wait: a flicker of a spinner for a 200ms fetch is pure visual noise; show a loading indicator only once the wait exceeds **~1s** (see `interaction-and-touch.md`).

## Numbers & heuristics

- Micro-interactions **~150–200ms**; larger transitions **~200–300ms**; hard ceiling around **400ms**.
- **Exit ≈ 60–70% of enter** duration.
- Easing: **`ease-out` entering**, **`ease-in` exiting**, **`ease-in-out` moving between points**; springs OK for interactive motion, kept snappy.
- Animate **`transform` and `opacity` only**; never the layout properties.
- Every animation **interruptible** and **non-blocking**.
- `prefers-reduced-motion: reduce` → kill travel/zoom animations; at most a quick small fade; state changes still legible without the motion.
- Show a loading indicator only past **~1s** of wait; determinate when you can estimate; gentle (not strobing) shimmer on skeletons.

## Common mistakes

- **Decorative motion** — things drifting, bouncing, or sliding for "delight" with no cause → effect meaning; it's just noise.
- **Too slow** — 500ms+ transitions; the interface feels laggy and the user out-runs it.
- **Linear easing** — robotic, abrupt; real motion accelerates and decelerates.
- **Exit as slow as enter** (or slower) — feels sluggish; the user has already moved on mentally.
- **Animating `width`/`height`/`top`/`left`/`margin`** — layout thrash and dropped frames on real devices.
- **`height: auto` accordion transition** — the canonical jank trap; transform/measure instead.
- **Non-interruptible animation** — toggle it twice quickly and it queues, freezes, or snaps.
- **Animation that blocks interaction** — the user waits for the pretty transition to finish before they can act.
- **No `prefers-reduced-motion` path** — at best unpleasant; for some users, makes them physically ill.
- **Spinner for a 150ms fetch** — a flicker of loading UI that's pure noise; threshold it at ~1s.
- **Fake or stalling progress bars** — a bar stuck at 99% is more infuriating than an honest spinner.
