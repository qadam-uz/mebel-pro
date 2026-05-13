---
name: ui-ux-mastery
description: >-
  Discipline and layered reference library for designing usable, accessible, considered user interfaces — covering UX foundations (users, jobs-to-be-done, information architecture, user flows, content), accessibility, interaction and touch, responsive layout, forms and system states (empty/loading/error/success), visual design and design tokens, and motion. Framework-agnostic; produces UX specifications, prioritized UX reviews, or implementation-ready interaction/component specs. Use this whenever you are designing or evaluating anything a person looks at and operates: defining a product's screens, navigation, or flows; writing the UX/design section of a spec, brief, PRD, or design doc; building or refactoring a page or component; choosing layout grids, spacing scales, type scales, or color tokens; reviewing an interface for usability, accessibility, or consistency; or whenever someone gives vague "this feels off / looks unpolished / is confusing / hard to use" feedback about an interface and the cause isn't named. Reach for it even when the request never says "UX" or "design" — if the output has a user who has to figure out how to use it, this applies.
---

# UI / UX Mastery

A practitioner's discipline for designing interfaces that are usable, accessible, and considered. Framework-agnostic — principles, structure, and concrete heuristics, not any one UI toolkit (it does assume the web platform: CSS, HTML semantics, ARIA). Decoration isn't the *starting point* — structure comes first and the visual finish sits on top of it (Step 5 below; reach for the `frontend-design` skill for surface-level craft) — but the finish is real work, not an afterthought. The goal: an interface where the right things are obvious, everyone can operate it, it's *comfortable* to use, and the whole reads as one coherent system rather than a pile of assembled parts.

## Step 0 — declare the deliverable, then honor the gate

Three things this skill produces. Decide which the request wants, **say so in your first response**, then follow the procedure below. Don't hand back a vague critique when a spec was wanted, or a 6-section spec when someone asked you to fix one button — these are scaffolds, not straitjackets: drop sections that don't apply, add ones that do.

| Deliverable | When | Template |
|---|---|---|
| **A — UX specification** | briefs, PRDs, design docs, ideation, "design the X" | §A below |
| **B — UX review** | "look at this UI", "why does this feel off", reacting to quality feedback | §B below |
| **C — Interaction/component spec** | build-time, "spec out this component" | §C below |

**The gate — for A and C, and for any build task.** Before you write a line of UI markup/CSS or call a spec done, you must have produced and shown: **(1)** the user + job in one sentence, **(2)** the screen/route inventory, **(3)** for each screen, *every state it can be in* — not just the populated happy one, **(4)** the key flows as steps including the unhappy branches, **(5)** the keyboard/focus behavior of anything interactive. If you can't yet state those, you are not ready to choose colors or components — that's Step 5, and reaching for it first is the single most common way interfaces end up confidently wrong. When a request jumps straight to "build me a settings page," your first move is to fill that gate, briefly, out loud — not to start emitting `<div>`s.

## The procedure

Work top-down. Each step names the reference file with the depth behind it — read the one(s) for the step you're on.

1. **Frame the problem.** Who is the user? What job are they hiring this interface to do — write the JTBD sentence: *"When I `<situation>`, I want to `<motivation>`, so I can `<outcome>`."* In what context (rushed, anxious, small screen, first time vs. hundredth, bad connection, high stakes)? What's in scope for *this* version, and what's explicitly **out** ("not now" is a complete answer)? Write it down — it's the rubric you'll judge everything else against. → `references/ux-foundations.md`
2. **Structure it.** Information architecture: how content/features group, and what each group is called *in the user's words, not internal jargon or table names*. The navigation model. A screen/route inventory. Then the **key flows drawn as steps** — trigger → … → done — *before* you design any screen, because a screen that's flawless in isolation can still sit at a broken point in a flow (too many steps, a dead end, a place the user loses their work). Every flow has unhappy branches (validation fails, network drops, the item's gone) — map where each lands and how the user recovers. → `references/ux-foundations.md`
3. **Lay out each screen.** Content priority (what must be seen first → last). Layout structure and how it reflows small → large. Then **enumerate every state**: empty (first-run) / empty (no results) / loading / partial / error / success / the ideal full state. A screen spec that only describes the full happy state is half-done — the states people forget are where the product pain lives. → `references/layout-and-responsive.md`, `references/forms-and-feedback.md`
4. **Specify interaction.** For each interactive element: its states (rest / hover / focus / active-pressed / disabled / loading / selected — whichever apply), the feedback it gives and how fast, its hit target, and the keyboard path to and through it. Custom widgets get the keyboard behavior + role/name/state of the native control they imitate — which is the main reason to prefer real `<button>`/`<input>`/`<a href>`. → `references/interaction-and-touch.md`, `references/accessibility.md`
5. **Apply the visual system.** *One* type scale, *one* spacing scale (4px-based), semantic color tokens mapped per theme (not raw hex per component), a consistent icon set, light and dark designed together. Define the system once; every screen draws from it. This is where the work reads as deliberate rather than assembled. → `references/visual-design.md`
6. **Add motion — last, and only where it earns its place.** Motion that ties an effect to its cause (where something came from / went). Not decoration. Fast, interruptible, gone under `prefers-reduced-motion`. → `references/motion.md`
7. **Adversarial self-review — required, not optional.** Re-read your deliverable against **The bar** below as if you were trying to reject it. List every item it fails or leaves vague. Fix those. *Then* deliver, noting any item you're consciously not addressing and why. A self-review that finds nothing wrong wasn't a review — find at least the weakest two things and decide about them.

**When constraints conflict — and they will — resolve in this order:** foundations (is this the right screen at all?) → accessibility → interaction integrity → layout & responsive → forms & states → visual → motion. Earlier items are load-bearing; later items are how "considered" shows. **Never polish a screen whose structure is wrong.** A beautiful screen that answers the wrong question, or that a keyboard user can't operate, has a defect no visual refinement fixes.

## Above the bar — comfort, and not looking generic

"The bar" below is the *floor*: clear it and the interface isn't broken. These are how it gets *good* — and they're the easiest things to skip, because nothing visibly breaks when you don't.

**Comfort is designed, not hoped for.** "The bar" is mostly *don't frustrate the user*; this is the offensive half — *make it feel effortless*:
- **Smart defaults** — the common case should take near-zero input. Pre-fill what you know, pre-select the obvious option, remember the last choice. Every field the user doesn't have to touch is a small gift; a form that arrives 80% filled feels like the product was paying attention.
- **Optimistic UI where the action almost always succeeds** — apply the change in the UI immediately, reconcile in the background, roll back + explain on the rare failure. The interface feels instant because it *acts* instant. (Don't do this for actions that often fail or are costly to undo — payments, destructive ops.)
- **Progressive disclosure** — show the 80% case plainly; tuck the advanced 20% behind "More", an expander, an "advanced" section. A screen that shows everything at once shows nothing clearly.
- **Momentum** — inside a flow, don't make the user stop and think: carry context forward so nothing's re-entered, keep the next step in view, autofocus the next field, let Enter submit. Friction mid-task is where people abandon.
- **Never lose the user's work** — preserve input across validation errors, accidental navigation, and reloads; confirm before discarding a draft; autosave where you can. Losing what someone typed is the fastest way to lose the person.
- **Perceived speed beats raw speed** — skeletons shaped like the real content, instant feedback on every tap, stream partial results as they arrive. Show progress; never a frozen screen, even for a second.

**Distinctive comes from fit, not from novelty.** The cure for generic, AI-looking output is **Step 1 done for real**: an interface shaped to *this* user's *specific* job and context looks different from a template because the job is different. The disease is skipping the framing and reaching for "a dashboard with cards." It is emphatically *not* reinventing the dropdown — novel interaction *mechanics* fail, because users can only operate what they've seen before; convention is a feature ("match the real world", "consistency and standards" are Nielsen heuristics for a reason). So: be **unique in fit, conventional in mechanics**. For *visual* distinctiveness — typography with a point of view, a real color system, layout with personality instead of the default centered-hero / three-cards / `rounded-2xl shadow-lg` look — that's the **`frontend-design`** skill's job; reach for it alongside this one. Division of labor: this skill makes the UX *right*; that one makes the surface not read as "an AI generated it."

## The bar — what every deliverable must clear

These are the highest-leverage concrete rules, the ones interfaces most often get wrong. They apply even if you open no reference file. In Step 7 you check your work against them; in a **spec**, they *are* the acceptance criteria — write them in, made concrete for the feature ("the no-results state of the orders table shows …", not "design the empty states").

**Accessibility & interaction**
- Every interactive element has a **visible focus indicator** — a ~2–3px ring/outline with its own ≥3:1 contrast against the background. Never `outline: none` with nothing in its place. Use `:focus-visible` so it shows for keyboard users without the "ugly ring on click" complaint.
- **The keyboard reaches and operates everything** a mouse can, in an order matching the visual layout; no traps. Modals: focus moves in, is trapped, returns to the trigger on close.
- **Text contrast ≥ 4.5:1** (≥ 3:1 for large text and for meaningful non-text marks — icons, input borders, focus rings, chart elements).
- **Color is never the only signal** — pair it with text, an icon, a shape, or position (status, validation, chart series).
- **Touch/click targets ≥ 44×44 CSS px** of hittable area; toward 48 when targets sit close; **≥ 8px between adjacent targets**; extra inset near screen edges and gesture zones.
- **Every action gives visible feedback within ~100ms** — pressed state, spinner, disabled-and-busy button. An action that does nothing visible reads as broken, so the user repeats it — now you have a double-submit.
- **Don't rely on hover** to reveal anything essential — touch has no hover; hover-only menus are invisible to keyboards.
- Respect **reduced-motion** and **larger-text** preferences; usable at 200% text/zoom with no horizontal scrolling.

**Layout**
- **Mobile-first**: design the small viewport first, then add room — it forces the priority calls you'd otherwise dodge.
- **No horizontal page scroll** on any viewport (intentional carousels and self-contained scrollable tables excepted — and those need an obvious "more sideways" affordance). No nested/competing scroll regions.
- **Reserve space for async content** (images with dimensions or an aspect-ratio box; skeletons sized like the real thing) so nothing jumps when it loads — a control that shifts under a finger causes mis-taps.
- **One spacing scale** — a 4px step set (4, 8, 12, 16, 24, 32, 48, 64, 96). Arbitrary values are the visible symptom of an absent system.
- Nothing important **trapped behind a fixed header/footer/keyboard**; respect safe-area insets (notches, rounded corners, gesture strips).

**Forms & system states**
- **Every input has a visible, persistent label.** Placeholder text is not a label — it vanishes on focus, fails screen readers, erases itself the moment someone types, leaves nothing to check an answer against. Placeholders are for example/format hints *in addition to* a label. Set the right input `type` and `autocomplete`.
- **Errors appear next to the field they're about**, name the cause *and* the fix in plain language ("Password needs at least one number", not "Invalid input"), are announced to screen readers, pull focus to the first invalid field on a failed submit, and **never clear the form**.
- **Validate at a humane moment** — on blur or submit, not on every keystroke while someone is still typing.
- **Design the empty (first-run), empty (no-results), loading, partial, and error states** of every list, table, and data region — not just the populated one. Every load that can hang gets a timeout → error path; no infinite spinners.
- **Destructive actions** are visually distinct (danger color *plus* a label naming the consequence — "Delete 3 files", not "OK"), kept out of reflex range; prefer **undo** over a confirmation nag where feasible.
- **Submit buttons** disable + show progress during async work (so they can't fire twice) and end in an explicit success or a re-enabled error state — never a silent reset.

**Visual**
- **One primary action per screen**, visually dominant; everything else secondary/tertiary. Deciding the primary action *is* deciding what the screen is for.
- **Body text ≥ 16px**, line-height ~1.5, line length ~50–75 characters (cap the container).
- **Icons are vector (SVG) from one set** — never emoji as structural UI icons (they render per-platform, can't take your color/size/stroke, don't scale crisply). Icon-only buttons always need an accessible name.
- **Semantic color tokens** (`color-text`, `color-danger`, `surface-raised`, …) mapped per theme — not raw hex per component. Accent/brand color used sparingly.
- **Dark mode is designed, not inverted** — desaturated, slightly-lightened colors on not-quite-black surfaces, off-white (not pure-white) text, elevation shown by lighter surfaces. Check contrast in both themes. The most important thing on each screen survives the squint test.

**Motion**
- Every animation expresses a cause → effect relationship, not decoration. Fast (~150–300ms for micro-interactions), interruptible, non-blocking, gone under `prefers-reduced-motion`. Animate `transform`/`opacity` only — never `width`/`height`/`top`/`left` (layout thrash, dropped frames).

## Deliverable templates

### A — UX specification

```
## <Feature / Product> — UX specification

### Job & users
- Primary user: <who> — Job to be done: "When I <situation>, I want to <motivation>, so I can <outcome>"
- Context of use: <where, when, mental state, first-time vs. repeat, device, connection, stakes>
- In scope (this version): <bullets>   ·   Out of scope (for now): <bullets>

### Information architecture
- How content/features group, named in the user's words
- Navigation model
- Screen/route inventory (tree or list)

### Key flows
For each critical flow:
- **<Flow>** — trigger → step → … → success
  - Unhappy branches: what can go wrong at each step, and where each lands

### Screens
For each screen:
- **<Screen>** — purpose in one line
  - Content priority: what's seen first → last
  - Layout & responsive: structure; how it reflows small → large
  - States: empty (first-run) / empty (no results) / loading / partial / error / success / full — what each shows
  - Interactions: key elements, their states, their feedback
  - Accessibility notes: focus order, labels, anything non-obvious

### Acceptance criteria
- The bar (above), made concrete for this feature
```

### B — UX review

```
## UX review — <what was reviewed>

### Summary
<2–3 sentences: the overall read, and the one or two things that matter most>

### Findings (priority order — accessibility & interaction-integrity defects outrank visual nitpicks, however loud the visual ones are)
1. **[Critical] <issue>** — where: <screen/element>. Why it matters: <impact on the user>. Fix: <concrete change>.
2. **[High] …**   3. **[Medium] …**   4. **[Low / polish] …**

### What's working
<Name what shouldn't be touched — a review that only lists problems is half a review>
```

### C — Interaction / component spec

```
## <Component> — interaction spec

- Purpose & where used:
- Anatomy: the parts it's made of
- Variants / props: the meaningful axes of variation
- States: rest / hover / focus / active-pressed / disabled / loading / selected / error — visual + behavior for each that applies
- Keyboard: which keys do what; focus behavior on open/close/change
- Feedback: what confirms each interaction, and how fast
- Accessibility: role / name / state semantics; focus management; what's announced
- Tokens used: type, color, spacing, radius, elevation — by name
```

## Worked sketch (so the templates aren't abstract)

Request: *"Build the saved-addresses screen for the client app."* — a build task, so honor the gate first:

> **User & job:** a returning customer placing an order — *"When I'm checking out, I want to pick a delivery address I've used before, so I don't retype it."*
> **Screens:** `Addresses` (list) · `Address form` (add/edit, can be a sheet).
> **States of `Addresses`:** *first-run empty* → "No saved addresses yet" + a primary **Add address**; *loading* → 2–3 skeleton rows sized like real ones; *error* → "Couldn't load your addresses" + **Retry**; *full* → list of cards, each with the address, an "edit" and a "remove" action (remove → optimistic removal + an **Undo** toast, not a confirm dialog), one card marked **Default**.
> **Flow — add an address:** tap Add → form (label, recipient, phone, address lines, "set as default") → Save → button shows a spinner, disables → on success the sheet closes and the new card appears, briefly highlighted → on validation error: first bad field focused, message beside it ("Phone should look like +998 90 123 45 67"), form intact.
> **Keyboard/focus:** opening the form moves focus to the first field; Esc closes it and returns focus to the Add button; the remove action is a real `<button>` with an accessible name like "Remove home address".

Only *then* lay out columns, pick the card styling, and reach for tokens. Notice the spec named four states and the unhappy branch before anything visual — that's the gate doing its job.

## Reference files

Each follows the same shape: **when it matters → priority-ranked principles with the reasoning → concrete numbers & heuristics → common mistakes.**

| File | Read it when you're… |
|---|---|
| `references/ux-foundations.md` | Framing the problem, scoping, doing IA, mapping flows, writing UI copy |
| `references/accessibility.md` | Anytime — especially specifying interaction, reviewing, or unsure whether something passes |
| `references/interaction-and-touch.md` | Specifying interactive elements: targets, states, feedback, gestures, hover-vs-tap, loading/disabled |
| `references/layout-and-responsive.md` | Laying out screens; breakpoints/grids/spacing; safe areas; preventing layout shift |
| `references/forms-and-feedback.md` | Designing forms, validation, errors, or the empty/loading/error/success states of any data surface |
| `references/visual-design.md` | Building the type scale, color token system, hierarchy, density, iconography, dark mode, data display |
| `references/motion.md` | Adding or reviewing animation and transitions |

## Anti-patterns — each is a symptom that an earlier step got skipped

Starting from a visual style or component kit (structure first, skin last) · placeholder text as the label · color as the only status signal · emoji as structural icons · hover-only affordances (menus, "edit" controls) · mystery-meat navigation (unlabeled icons, ambiguous destinations) · only the happy path designed ("we'll add error states later" = shipping the broken ones now) · infinite spinner with no exit · nested/competing scroll regions · spacing by vibes · `outline: none` with no replacement · two co-equal primary buttons · dark mode by inversion · `<div onclick>` as a button · animating `width`/`height`/`top`/`left`.
