# Complex flow

You were routed here by the triage table in [`AGENTS.md`](../../AGENTS.md).
Goal: from a single request, produce code that is **decided, documented, built,
verified, and reviewed** — that actually works as intended, with sufficient
non-flaky tests and no functional or visual defects — with as little human
babysitting as the invocation asked for.

This is a **gated pipeline**, not a single pass. Each stage emits a durable
artifact the next stage (and any fresh subagent) reads. Iterate _within_ a
stage; advance only when its gate's exit criteria are met.

## Operating model — applies to every stage

- **Isolation.** All work happens in a git worktree under `.worktrees/<branch>/`
  on a feature branch off the integration branch (default `main`). Created in
  Plan, the moment the first file is written.
- **Two artifacts, one home each** (both `.workflows/*.md`, gitignored, per-run,
  living inside the worktree):
  - **`plan.md` = intent** — framing, decisions, acceptance criteria, steps.
    Written once in Plan; edited only on a loop-back.
  - **`progress.md` = state** — the externalized state machine: current stage,
    per-step status (_by plan step id, never re-listing them_), gate findings
    and their resolution, loop counters vs budget, escalations, branch +
    integration target. A crashed or compacted run resumes from
    `plan.md` + `progress.md`.
  - Schemas at the bottom of this file.
- **One orchestrator.** A single driver owns the state machine and is the **only
  writer of `progress.md`**. Fan-out subagents return results _to_ it; it
  records them. Parallel writers would race.
- **Falsifiable gates.** Every gate states explicit exit criteria. Nothing
  advances on "looks fine."
- **Bounded loops.** Every review→fix loop has a budget (**default ≤3 rounds**).
  On exhaustion, **escalate** — never loop forever, never quit silently.
- **Reviews are fan-out + arbiter.** A review spawns one agent per named lens,
  then a single arbiter dedups, drops false positives, and resolves conflicts
  before anything is acted on or shown to a human.
- **Gates vs escalations — not the same thing:**
  - **Gates** are _planned_ human stops, passed as arguments when the flow is
    invoked (e.g. `gates: [plan, merge]`). **Default: none** → the flow runs
    end-to-end and merges automatically.
  - **Escalations** are _unplanned_ stops the flow **must** raise regardless of
    gate config: a loop budget is exhausted, a contested finding can't be
    resolved, or an **irreversible / destructive** operation comes up that the
    flow can't self-authorize (data-loss migration, history rewrite, deleting
    user data, secret rotation). Escalations can't be turned off — they're the
    autonomous-mode safety valve. "No gates" means _no planned stops_, not
    _never stops_.

---

## 1. Plan

**Do:**

1. **Explore** the relevant existing code so the plan is grounded, not
   hypothetical.
2. **Clarify, interactively, until it converges.** State the goal, the key
   decisions, and what's out of scope back to the human and get a "right track"
   _before_ writing anything. This is the cheap catch for _solving the wrong
   problem_ — it happens even when no `plan` gate is set, because it's
   conversation, not a stop.
3. **Create the worktree** (if not already in one) — the first file-writing
   moment.
4. **Write the polished docs.** Encode the target state into `docs/` via the
   project docs standarts — fully guideline-compliant, not a draft (writing
   them is itself a design check).
5. **Write `plan.md`** (see schema). It carries the _consequential_ how:
   contracts, seams, decisions + rationale, ordered steps, test plan — **not**
   line-level code. Test for any item: _"if I get this wrong, does Plan-review
   catch it and is it expensive to fix after coding?"_ → in the plan;
   _"cheap to change, Execution-review catches it?"_ → leave it to Execute.
6. **Initialize `progress.md`.**

**Exit criteria:** docs encode the target state; `plan.md` has every section
populated; every acceptance criterion is testable and mapped to a planned test;
clarification has converged. If a `plan` gate is set, the human approves here.

## 2. Plan review → fix

Fan-out, **design-altitude first** ("is the approach right?") _before_ any
step-level nits, across these lenses:

- **architecture / DDD** — boundaries, layering, coupling
- **simplicity / YAGNI** — is anything over-built
- **UX & flows** — for user-facing work
- **security** — authz, input handling, data exposure
- **testability** — can each acceptance criterion actually be proven
- **ops** — failure modes & rollback
- **docs correctness** — layer leakage, routing, docs-management rules

Arbiter synthesizes. **Clear finding → fix. Contested / unclear finding →
adjudicate (a deciding pass) or escalate — never silently drop.** Loop within
budget.

**Exit criteria:** no unresolved blocking finding; the approach is sound at the
design altitude; `plan.md` / docs updated to match any accepted change.

## 3. Execute

- Run in the **main session** by default. **Fan out to subagents only if
  `plan.md` carved the work into independent, non-overlapping slices** — each
  subagent gets its **own worktree**, and an **integration step** stitches +
  re-verifies the whole afterward. If the work can't be cleanly partitioned, do
  it serially.
- Implement **code + tests together**, following each subproject's `AGENTS.md`
  and the **testing-practices** skill for the unit/integration/E2E split.
- **Execution may not invent architecture.** Hit an architectural fork `plan.md`
  didn't settle? That's a _plan defect_ → loop back to Plan (within budget).
  Don't wing it — unreviewed design must not leak into code.
- Update `progress.md` as steps complete.

**Exit criteria:** every plan step done or explicitly deferred in `progress.md`;
a test exists for each acceptance criterion.

## 4. Execution review → fix

Reviewer is **fresh-eyes** — a subagent that did _not_ write the code (the
author re-confirms their own blind spots). Two arms:

1. **Review** across lenses: correctness / bugs · stack-idiom code quality ·
   security · **test quality** (sufficient, right pyramid level, non-flaky) ·
   performance.
2. **Verify** — _all_ of:
   - the subproject **check gate(s)** from `AGENTS.md` (lint · format · types ·
     tests · build) — green;
   - **runtime / visual** check for any UI change (drive it, screenshot, look —
     a green suite doesn't prove the layout is right);
   - **acceptance-criteria check** — each criterion in `plan.md` is demonstrably
     satisfied by a test or an observed behavior.

Arbiter synthesizes; clear → fix, contested → adjudicate / escalate; loop within
budget.

**Exit criteria:** check gates green; every acceptance criterion demonstrably
met; no unresolved blocking finding; no known visual or functional defect.

## 5. Land

1. **Rebase** onto the integration branch.
2. **Re-run the full check gate** — your earlier green was against the old base;
   a clean rebase can still break semantically. Never `rebase → push`.
3. **Push**, open a **PR** whose body summarizes the problem + acceptance
   criteria (link, don't restate the plan).
4. **Merge gate.** If a `merge` gate is set → stop for human. If not → merge
   automatically **only on CI green**. Per the _fail-safe_ convention,
   outward / irreversible steps lean closed: auto-merge is the explicit no-gate
   behavior, never a fallback when something is uncertain.

> ⚠️ If the integration branch is `main`, CI **auto-deploys to prod** on merge
> (`AGENTS.md` → Per-directory check gates). No-gate mode therefore =
> unattended production deploy. Fine for low-risk runs; point bigger work at a
> non-deploying branch, or set a `merge` gate.

---

## `plan.md` schema

```markdown
# <feature / change title>

## Problem

What's wrong or needed, and why now.

## Approach

The chosen solution shape + key decisions and WHY (X over Y because Z).

## Acceptance criteria

Each one testable. This is the contract verify/review measure against.

## Out of scope

Explicit non-goals.

## Affected docs

The `docs/` pages this changes (the "what").

## Contracts & seams

New API routes (method/path, request/response), schema/migrations, entities,
cross-module signatures, and where it wires into existing code.

## Steps

Ordered; each an independently testable / committable unit. Mark which may run
in parallel (fan-out partition).

## Test plan

Each acceptance criterion → the pyramid level that proves it.

## Risks & rollback
```

## `progress.md` schema

```markdown
# Run: <branch> → <integration target>

## Stage

Current stage + status, e.g. "4 · execution review · round 2/3".

## Steps

plan step id → done | in-progress | blocked

## Gate log

Plan-review / Execution-review: findings + their resolution.

## Loop counters

<loop name>: n / budget

## Escalations

Raised + the human decision received.
```
