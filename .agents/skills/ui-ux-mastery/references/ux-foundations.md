# UX Foundations — users, jobs, structure, flows, content

## When this matters

Before any pixels: whenever you're deciding *what* an interface should contain, how it's organized, what the v1 scope is, or how someone moves through it. This is the layer the rest of the skill rests on — a screen built on the wrong information architecture is wrong no matter how well it's executed. If you catch yourself choosing colors or components before you can state the user's job in one sentence, stop and come back here.

## Principles

### 1. Name the user and the job before anything else

You can't design an interface without knowing who's using it and what outcome they're after. "Job to be done" framing beats "feature" framing because it keeps you honest about the *result the user wants*, not the thing you happened to decide to build. A job statement reads like:

> *"When I `<situation>`, I want to `<motivation>`, so I can `<expected outcome>`."*

Everything downstream gets judged against it. If a screen, field, or step doesn't serve the job, that's a finding.

### 2. Design for the context of use, not the demo

The same screen, used by a stressed person on a phone in bad light, is a different design problem than the one used by a power user on a big monitor for the hundredth time. Ask: first-time or repeat? Focused or distracted? What device, what connection, what's at stake if they get it wrong? The contexts at the extremes — rushed, anxious, small screen, recovering from an error — are where designs break. Design for those, not the comfortable middle, and the middle takes care of itself.

### 3. Scope is a design decision — make it explicit

"What's *not* in this version" is as much a part of the spec as what is. An unstated scope balloons silently; a stated one lets everyone push back now instead of after it's built. Write the in-scope list *and* the deliberately-out list. "Out of scope, for now" is a complete, respectable answer.

### 4. Information architecture: group and label by the user's model, not yours

How content and features are grouped — and what the groups are called — determines whether people can find anything. Use the words your users use, not internal jargon or the names of the teams/database tables behind the features. A navigation label that makes sense on the org chart but not in the user's head is a dead end. When you're unsure how things should group, that's a signal to test it — even informally: write the labels on cards, ask a couple of people to sort them, see where their model differs from yours.

### 5. Map flows as steps, before you design screens

A user flow is the sequence of steps to complete a job: trigger → … → done. Draw it as steps first, because a screen that's flawless in isolation can still sit at a broken point in a flow — too many steps, a dead end, a place where the user loses their work, a fork with no way back. And every flow has unhappy branches (validation fails, the network drops, the item's already gone) — those aren't edge cases, they *are* the flow; map where each branch lands and how the user recovers.

### 6. Fewer steps, less to decide, less to remember

Every step is a chance to drop out. Every decision is cognitive load. Every thing the user must carry in their head from a previous screen is a thing they'll forget. So: collapse steps where you can safely do it; carry context forward so the user doesn't re-enter it; default the obvious choice; and prefer **recognition** (pick from what's shown) over **recall** (remember it and type it). The goal isn't "minimal" for its own sake — it's removing the friction that doesn't earn its place.

### 7. Content is part of the design

Labels, button text, empty-state copy, error messages, headings, helper text — these *are* the interface as much as the layout is, and they're usually the cheapest thing to get right and the most often left as filler. "Submit" tells the user nothing; "Send invite" tells them exactly what's about to happen. Write button labels as the verb phrase for what happens next. Write error messages as cause + fix. Write empty states as "here's what goes here and how to add it", not a shrug. Plain language, the user's vocabulary, no internal jargon.

## Heuristics & checklist

- Can you state the user and their job in one sentence? If not, you're not ready to design.
- Is there an explicit out-of-scope list?
- Are the key flows drawn as steps, with their unhappy branches and recovery paths?
- Does every screen and nav label use the user's vocabulary?
- For each flow: how many steps, how many decisions, how much must the user remember between screens? Can any of those drop?
- Do button labels name what happens? Do empty states explain themselves? Do errors give a fix?
- **Nielsen's 10 heuristics** are a fast gut-check on any flow:
  1. Visible system status — the user always knows what's going on.
  2. Match between system and the real world — speaks the user's language and conventions.
  3. User control and freedom — undo, back, escape hatches, no dead ends.
  4. Consistency and standards — same thing means the same thing everywhere; follow platform conventions.
  5. Error prevention — design out the mistake rather than just messaging it.
  6. Recognition over recall — show options; don't make the user remember them.
  7. Flexibility and efficiency — accelerators for experts, gentle defaults for novices.
  8. Aesthetic and minimalist design — nothing on screen competes with the essentials for attention.
  9. Help users recognize, diagnose, and recover from errors — plain-language messages, a way out.
  10. Help and documentation — available where it's needed, when it's needed.

## Common mistakes

- **Solutioning before framing** — "it'll be a dashboard with cards" before knowing the job; the *form* is an output of the problem, not the input.
- **Designing the screen, not the flow** — perfecting a screen that sits in a 7-step flow that should be 3.
- **Internal-vocabulary labels** — naming a section after the team that owns it or the table behind it.
- **Unbounded scope** — no "not now" list, so the v1 quietly becomes a v3.
- **Treating errors and empties as edge cases** — in many products they're the most-hit states; designing only the full happy path ships the rest broken.
- **Throwaway copy** — "Submit", "Error occurred", "No data" — text that does no work for the user when it could do a lot.
- **Skipping IA validation** — shipping your mental model of how things group as if it were the users', then wondering why nobody finds anything.
