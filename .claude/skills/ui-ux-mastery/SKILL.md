---
name: ui-ux-mastery
description: >-
  Discipline and layered reference library for designing usable, accessible, considered user interfaces — covering UX foundations (users, jobs-to-be-done, information architecture, user flows, content), accessibility, interaction and touch, responsive layout, forms and system states (empty/loading/error/success), visual design and design tokens, and motion. Framework-agnostic; produces UX specifications, prioritized UX reviews, or implementation-ready interaction/component specs. Use this whenever you are designing or evaluating anything a person looks at and operates: defining a product's screens, navigation, or flows; writing the UX/design section of a spec, brief, PRD, or design doc; building or refactoring a page or component; choosing layout grids, spacing scales, type scales, or color tokens; reviewing an interface for usability, accessibility, or consistency; or whenever someone gives vague "this feels off / looks unpolished / is confusing / hard to use" feedback about an interface and the cause isn't named. Reach for it even when the request never says "UX" or "design" — if the output has a user who has to figure out how to use it, this applies.
---

# UI / UX Mastery

A practitioner's discipline for designing interfaces that are usable, accessible, and considered — plus a layered reference library to back it up. Framework-agnostic: it deals in principles, structure, and concrete heuristics, not any one UI toolkit. (It does assume the web platform — CSS, HTML semantics, ARIA — since that's where these surfaces usually live.)

The aim isn't "decoration." It's making the right things obvious, the interface operable by everyone, and the whole thing feel like one coherent system rather than a pile of assembled parts.

Two contexts use the same discipline and differ only in what they hand back:

- **Specifying** an interface (briefs, specs, design docs, ideation, "design the X") → you produce a **UX specification**: the job, the information architecture, the screen inventory, the key flows, and per-screen content / layout / states / interaction / accessibility notes.
- **Building or reviewing** an interface → you produce **components** that honor these principles, or a **UX review** that names what's wrong in priority order with concrete fixes.

Whichever it is, say so up front, then follow the workflow below.

## When to use this

- Designing new screens, flows, or navigation — or deciding what a v1 should even contain
- Writing the UX / design portion of a spec, brief, PRD, or design doc
- Building or refactoring a page or component
- Choosing layout grids, spacing scales, breakpoints, type scales, or color tokens
- Reviewing an interface for usability, accessibility, consistency, or "feels unfinished"
- Acting on vague quality feedback ("this looks off", "it's confusing", "hard to use") where the cause isn't named
- Aligning a set of screens onto one coherent system

Skip it for work with no human-facing surface: pure backend logic, data pipelines, infrastructure, API or schema design with no UI, non-visual automation.

## What you produce

Pick the deliverable that fits the request. Don't hand back a vague critique when a spec was wanted, or a spec when someone asked you to fix one button. These are scaffolds, not straitjackets — drop sections that don't apply, add ones that do. The constant: a deliverable that names the **states**, the **flows**, and the **accessibility behavior**, not just the happy-path appearance.

### A — UX specification (briefs, design docs, ideation, "design the X")

```
## <Feature / Product> — UX specification

### Job & users
- Primary user: <who> — Job to be done: "When I <situation>, I want to <motivation>, so I can <expected outcome>"
- Context of use: <where, when, what state of mind, first-time vs. repeat, device, connection, stakes>
- In scope (this version): <bullets>
- Out of scope (explicitly, for now): <bullets>

### Information architecture
- How content / features are grouped and what each group is called (in the user's words, not internal jargon)
- The navigation model
- Route / screen inventory (a tree or list)

### Key flows
For each critical flow:
- **<Flow name>** — trigger → step → step → … → success
  - Unhappy branches: what can go wrong at each step, and where each lands

### Screens
For each screen:
- **<Screen name>** — purpose in one line
  - Content priority: what must be seen first → last
  - Layout & responsive: structure; how it reflows small → large
  - States: empty (first-run) / empty (no results) / loading / partial / error / success / full — what each shows
  - Interactions: key elements, their states, their feedback
  - Accessibility notes: focus order, labels, anything non-obvious

### Acceptance criteria
- The relevant items from this skill's review checklist, made concrete for this feature
```

### B — UX review ("look at this UI", "why does this feel off", reacting to quality feedback)

```
## UX review — <what was reviewed>

### Summary
<2–3 sentences: the overall read, and the one or two things that matter most>

### Findings (priority order)
1. **[Critical] <issue>** — where: <screen / element>. Why it matters: <impact on the user>. Fix: <concrete change>.
2. **[High] …**
3. **[Medium] …**
4. **[Low / polish] …**

### What's working
<Name what shouldn't be touched — a review that only lists problems is half a review>
```

Order findings by the priority list below: accessibility and interaction-integrity defects outrank visual nitpicks, regardless of how loud the visual ones are.

### C — Interaction / component spec (build-time, "spec out this component")

```
## <Component> — interaction spec

- Purpose & where used:
- Anatomy: the parts it's made of
- Variants / props: the meaningful axes of variation
- States: rest / hover / focus / active-pressed / disabled / loading / selected / error — visual + behavior for each that applies
- Keyboard: which keys do what; focus behavior on open/close/change
- Feedback: what confirms each interaction, and how fast
- Accessibility: role / name / state semantics; focus management; what gets announced
- Tokens used: type, color, spacing, radius, elevation tokens — by name
```

## The order that matters

When constraints conflict — and they will — resolve them in this order. The point: **never polish a screen whose structure is wrong.** A beautiful screen that answers the wrong question, or that a keyboard user can't operate, has a defect no amount of visual refinement fixes. Earlier items are load-bearing; later items are how "considered" shows.

1. **Foundations — is this the right screen at all?** The user, the job, the context of use, what's in scope. → `references/ux-foundations.md`
2. **Accessibility.** Non-negotiable: keyboard operability, sufficient contrast, labels and roles, respect for user motion/text-size preferences. Legal, ethical, and just good design — accessible interfaces are clearer for everyone. → `references/accessibility.md`
3. **Interaction integrity.** Every interactive thing has visible states, a hit target you can actually hit, and feedback that confirms it heard you. Broken affordances make everything downstream moot. → `references/interaction-and-touch.md`
4. **Layout & responsive.** Content is reachable and readable on every viewport; nothing is trapped behind a fixed bar; no horizontal scroll; async content doesn't shove the page around. → `references/layout-and-responsive.md`
5. **Forms & system states.** Most product value flows through inputs, and most product *pain* lives in the states people forget: empty, loading, partial, error, success. Design all of them, not just the happy path. → `references/forms-and-feedback.md`
6. **Visual design.** Hierarchy, type scale, color roles, spacing rhythm, density, iconography, light/dark. This is where the work reads as deliberate rather than assembled. → `references/visual-design.md`
7. **Motion.** The last 5%. Meaningful (expresses cause → effect), fast, interruptible, and gracefully absent when the user asked for less of it. → `references/motion.md`

## Workflow

Work top-down. Resist starting from a visual style or a component library — that's step 5, and reaching for it first is the most common way interfaces end up confidently wrong.

1. **Frame the problem.** Who is the user? What job are they hiring this interface to do? In what context (rushed, anxious, on a small screen, first time vs. hundredth)? What is genuinely in scope for this version, and what is explicitly *not*? Write it down — it's the rubric you'll judge everything else against. → `ux-foundations.md`
2. **Structure it.** Information architecture (how content is grouped and labeled), the navigation model, a screen/route inventory, and the **key user flows drawn as steps** — flows before screens, because a screen that's perfect in isolation can still sit at the wrong point in a broken flow. → `ux-foundations.md`
3. **Lay out each screen.** Decide content priority (what must be seen first), the layout structure and how it reflows across viewports, and enumerate **every state the screen can be in** — empty / loading / partial / error / success / the ideal full state. A screen spec that only describes the full happy state is half-done. → `layout-and-responsive.md`, `forms-and-feedback.md`
4. **Specify interaction.** For each interactive element: its states (rest, hover, focus, active/pressed, disabled, loading, selected — whichever apply), the feedback it gives, its hit target, and the keyboard path to and through it. → `interaction-and-touch.md`, `accessibility.md`
5. **Apply the visual system.** One type scale, one spacing scale, semantic color tokens (not raw hex sprinkled per component), a consistent icon set, light and dark designed together. Define the system once; every screen draws from it. → `visual-design.md`
6. **Add motion — last, and only where it earns its place.** Motion that shows where something came from or went, that ties an effect to its cause. Not motion as decoration. → `motion.md`
7. **Review.** Run the checklist below before calling it done. If you're producing a spec, the checklist items become acceptance criteria.

## Non-negotiables — the list everyone gets wrong

The highest-leverage concrete rules, pulled up front so they apply even without opening a reference file. If you do nothing else, do these.

**Accessibility & interaction**

- Every interactive element has a **visible focus indicator** (a clear ring/outline, ~2–3px, with its own ≥3:1 contrast against the background) — never `outline: none` with nothing in its place. Use `:focus-visible` so it shows for keyboard users without the "ugly ring on click" complaint.
- **The keyboard reaches and operates everything** a mouse can, in an order that matches the visual layout; no traps.
- **Text contrast ≥ 4.5:1** (≥ 3:1 for large text and for meaningful non-text marks — icons, input borders, focus rings, chart elements).
- **Color is never the only signal** — pair it with text, an icon, a shape, or position. (Status, validation, chart series.)
- **Touch/click targets ≥ 44×44 CSS px** of hittable area; bump toward 48 when targets sit close together; keep **≥ 8px between adjacent targets**. Targets near screen edges or system gesture areas get extra inset.
- **Every action gives visible feedback within ~100ms** — a pressed state, a spinner, a disabled-and-busy button. An action that does nothing visible reads as broken, so the user does it again (now you have a double-submit).
- **Don't rely on hover** to reveal anything essential — touch devices have no hover, and hover-only menus are invisible to keyboards.
- Respect **reduced-motion** and **larger text** preferences; the interface stays usable at 200% text size / zoom with no horizontal scrolling.
- Custom widgets get the keyboard behavior and the role/name/state announcements of the native control they imitate — which is the main reason to prefer real `<button>`, `<input>`, `<a href>` in the first place.

**Layout**

- **Mobile-first**: design the small viewport first, then add room — it forces priority decisions you'd otherwise dodge.
- **No horizontal scrolling** of the page on any viewport (intentional carousels and self-contained scrollable tables excepted, and those need an obvious "more sideways" affordance).
- **Reserve space for async content** (images with dimensions or an aspect-ratio box; skeletons sized like the real thing) so nothing jumps when it loads — a button that shifts under a finger causes mis-taps.
- **One consistent spacing scale** — a 4px-based step set (4, 8, 12, 16, 24, 32, 48, 64, 96); arbitrary values are the visible symptom of an absent system.
- Nothing important is **trapped behind a fixed header/footer/keyboard**; account for safe-area insets (notches, rounded corners, gesture strips).

**Forms & states**

- **Every input has a visible, persistent label** — placeholder text is not a label (it vanishes on focus, fails screen readers, erases itself the moment someone types, and leaves nothing to check an answer against). Placeholders are for example/format hints *in addition to* a label.
- **Errors appear next to the field they're about**, state the cause *and* the fix in plain language ("Password needs at least one number", not "Invalid input"), are announced to screen readers, and the first invalid field gets focus on a failed submit. Never clear the form on error.
- **Validate at a humane moment** — generally on blur or submit, not on every keystroke while someone is still typing.
- **Design the empty (first-run), empty (no-results), loading, and error states** of every list, table, and data region — not just the populated one. Every load that can hang needs a timeout → error path; no infinite spinners.
- **Destructive actions** are visually distinct, use a danger color *plus* a label naming the consequence ("Delete 3 files", not "OK"), and aren't placed where someone hits them by reflex; prefer an **undo** over a confirmation nag where feasible.
- **Submit buttons** disable + show progress during async work (so they can't fire twice) and end in an explicit success or a re-enabled error state — never a silent reset.

**Visual**

- **One primary action per screen**, visually dominant; everything else is secondary or tertiary. Deciding the primary action *is* deciding what the screen is for.
- **Body text ≥ 16px**, line-height ~1.5, line length ~50–75 characters (cap the container).
- **Icons are vector (SVG) from one consistent set** — never emoji as structural UI icons (they render differently per platform, can't take your color/size/stroke, and don't scale crisply). Icon-only buttons always need an accessible name.
- **Semantic color tokens** (`color-text`, `color-danger`, `surface-raised`, …) mapped per theme — not raw hex per component, which makes theming and dark mode impossible to do well. Use the accent/brand color sparingly.
- **Dark mode is designed, not inverted** — desaturated, slightly lightened colors on dark, not-quite-black surfaces, off-white (not pure-white) text, elevation shown by lighter surfaces; never a literal color inversion. Check contrast in both themes.

## Reference files

Read the one(s) relevant to the step you're on. Each follows the same shape: **when it matters → priority-ranked principles with the reasoning → concrete numbers and heuristics → common mistakes.**

| File | Read it when you're… |
|---|---|
| `references/ux-foundations.md` | Framing the problem, defining scope, doing information architecture, mapping user flows, writing UI copy |
| `references/accessibility.md` | Anytime — especially specifying interaction, reviewing, or unsure whether something passes |
| `references/interaction-and-touch.md` | Specifying interactive elements: targets, states, feedback, gestures, hover-vs-tap, loading/disabled |
| `references/layout-and-responsive.md` | Laying out screens, choosing breakpoints/grids/spacing, handling safe areas, preventing layout shift |
| `references/forms-and-feedback.md` | Designing forms, validation, errors, or the empty/loading/error/success states of any data surface |
| `references/visual-design.md` | Building the type scale, color token system, hierarchy, density, iconography, dark mode, or data display |
| `references/motion.md` | Adding or reviewing animation and transitions |

## Pre-delivery review checklist

Phrased as questions, in priority order. For a spec, these become acceptance criteria; for built UI, walk through them before declaring done.

**Foundations**

- Is there a one-line statement of *who* this is for and *what job* it does — and does every screen serve it?
- Is anything here actually out of scope for this version, written down?
- Do the key flows hold up end to end, including the unhappy branches?
- Do labels, buttons, empty states, and errors use the user's words and do real work (button text names what happens; errors give a fix)?

**Accessibility**

- Does the keyboard reach and operate everything, in visual order, with a visible focus indicator at each stop, no traps?
- Does all text meet 4.5:1 (3:1 for large text and meaningful icons/borders/focus rings)?
- Is every meaning carried by something other than color alone?
- Do images/icons that convey meaning have text alternatives, and decorative ones empty alt?
- Does it survive `prefers-reduced-motion` and 200% text size / zoom?
- Modals: focus moves in, is trapped, returns to the trigger on close? Form submit with errors: focus lands on the first bad field?

**Interaction**

- Does every action produce visible feedback within ~100ms?
- Are all targets ≥44×44 with ≥8px spacing, and clear of edges and gesture zones?
- Does each interactive element have all the states it needs (rest/hover/focus/active/disabled/loading/selected)?
- Is anything essential hidden behind hover?
- Do buttons disable + show progress during async work, without shifting layout?

**Layout & responsive**

- No horizontal page scroll on any viewport?
- Is space reserved for async content so nothing jumps?
- Tested on a small phone, a large phone, a tablet (portrait *and* landscape), and a wide desktop — and at 200% zoom?
- Is spacing drawn from one scale throughout?
- Is anything important hidden behind a fixed bar or the on-screen keyboard? Are safe-area insets respected?

**Forms & states**

- Does every input have a visible, persistent label, the right control, the right input type, and `autocomplete` set?
- Do errors sit by their field, name the cause and the fix, get announced, pull focus on submit, and leave the input intact?
- Are the empty (first-run), empty (no-results), loading, and error states designed for every data region — not just the full state? Does anything load with no timeout and no error path?
- Are destructive actions distinct, labeled with their consequence, and out of reflex range?
- Does submit show a busy state that blocks double-clicks and end in explicit success or a recoverable error?

**Visual**

- Exactly one primary action per screen?
- Body text ≥16px, line-height ~1.5, line length ~50–75 chars?
- Icons all vector, from one set, no emoji standing in for UI icons; icon-only buttons named?
- Colors referenced as semantic tokens, mapped per theme; accent color used sparingly?
- Light and dark both designed and contrast-checked? Does the most important thing on each screen survive the squint test?

**Motion**

- Does every animation express a cause → effect relationship (not decoration)?
- Is it fast (~150–300ms for micro-interactions), interruptible, non-blocking, and gone under `prefers-reduced-motion`?
- Is only `transform`/`opacity` animated (not layout properties)?

## Anti-patterns

Each is a symptom that an earlier step got skipped. The clause after the dash is *why* it bites.

- **Starting from a visual style or component kit** — you'll build a polished answer to a question nobody asked; structure first, skin last.
- **Placeholder text as the label** — it disappears on focus, gives screen readers nothing, self-destructs the moment the user types, and leaves nothing to check an answer against.
- **Color as the only status signal** — invisible to color-blind users and anyone where color is washed out; pair it with text or an icon.
- **Emoji as structural icons** — they render differently on every OS, can't take your stroke/size/color, and look amateur at any size that matters.
- **Hover-only affordances** (menus, actions, "edit" controls) — nonexistent on touch, unreachable by keyboard; they're just hidden.
- **Mystery-meat navigation** — unlabeled icons, ambiguous destinations; if a user has to click to find out what something does, the label failed.
- **Only the happy path designed** — real users hit empty lists, dropped connections, validation errors, and half-loaded screens far more than the pristine full state; "we'll add the error states later" means shipping the broken ones now.
- **Infinite spinner, no exit** — a load that can't fail in the design will hang forever in production; every async state needs a timeout and an error path.
- **Nested / competing scroll regions** — inner scrollers inside outer scrollers trap the user and fight their gestures; flatten them.
- **Spacing by vibes** — values picked ad hoc per component; the eye reads the inconsistency as sloppiness even when it can't name it.
- **`outline: none` with no replacement** — silently removes the only thing telling a keyboard user where they are.
- **Two co-equal primary buttons** — if everything is emphasized, nothing is; pick the one action you most want taken.
- **Dark mode by inversion** — flips brand colors into garish, low-contrast mud; dark mode is its own design pass.
- **`<div onclick>` as a button** — no role, no keyboard, no focus, nothing announced; use a real `<button>`.
- **Animating `width`/`height`/`top`/`left`** — layout thrash and dropped frames on real devices; animate `transform`/`opacity` instead.
