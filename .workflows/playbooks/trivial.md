# Trivial flow

You were routed here by the triage table in [`AGENTS.md`](../../AGENTS.md): a
localized, low-risk change with **no design decisions**. The whole point of this
flow is to stay out of the way — no worktree, no `plan.md`, no `progress.md`, no
review fan-out. Make the change correctly and prove it.

## Steps

1. **Fix.** Make the change on the current branch. Read the immediate
   surroundings first so it matches the code around it.
2. **Verify.** Run the affected subproject's check gate from
   [`AGENTS.md`](../../AGENTS.md) → _Per-directory check gates_. For a
   UI-visible change, also look at it running — a green suite doesn't prove the
   layout is right.
3. **Stop.** Report what changed and the gate result. **Commit only when asked**
   (project convention) — don't push or merge on your own.

## Promote the moment it stops being trivial

If, while doing it, you hit **any** of these — stop and switch to
[`complex.md`](complex.md), restarting at its Plan stage:

- a decision with more than one defensible answer;
- a missing or contested requirement / acceptance criterion;
- the change spreading across more than one module, or adding surface
  (API, schema, entity, feature);
- the verify step failing in a way whose fix isn't obvious.

Finishing a secretly-complex task on this flow is the exact failure mode this
flow exists to avoid. **When unsure, promote.**
