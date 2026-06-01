---
name: software-architecture
description: >-
  Use when designing or restructuring architecture, choosing a stack or topology, or making/reviewing a consequential, costly-to-reverse technical decision — monolith vs. microservices, sync vs. async, SQL vs. NoSQL, service boundaries, caching, queues. Triggers when someone proposes adding a service/queue/cache/layer, or when "scalable", "enterprise", "event-driven", or "microservices" appears without numbers. Calibrates to the real envelope and pushes back on over-engineering.
---

# Software Architecture

> Architecture is the set of decisions that are expensive to change later — so the job is to
> choose those few deliberately and keep everything else cheap to change. Every such decision is
> a trade-off, and the right one fits *this* system's situation. So: establish the situation
> first, design to fit it, resist the pull to build more than the situation needs.

This skill is the system-design voice in the `shape` pipeline (ideation → docs). Use it to make
architecture decisions, critique proposed ones, and produce the architecture content the
documentation needs. Keep its output **structured** (see "What this skill produces") — downstream
steps consume it.

## Step 0 — the gate: state the envelope before you propose anything

Most bad architecture comes from one skipped step: jumping to a solution without naming the
situation it has to fit. That situation is the **operating envelope**. So, as your *first* move on
any architecture question — before a diagram, before a tech pick, before code:

**State the five axes with real numbers (or your explicit assumption).** If the human gave you the
numbers, restate them. If they didn't, say what you're assuming, out loud — *"assuming an internal
tool, low hundreds of users, no payments, two-person team, runs for years with occasional edits;
correct me if not"* — and proceed on that. Don't design in the dark and don't stall waiting for
perfect inputs; a stated assumption is reviewable, a silent one isn't. **If you catch yourself
sketching components and you haven't stated the envelope, stop and state it.** Half of
over-engineering and most of under-engineering trace back to an unexamined envelope.

### The operating envelope — five axes

| Axis | Low end → high end | What the high end demands |
|---|---|---|
| **Scale + trajectory** | tens of users, flat → millions, fast growth | horizontal scaling, statelessness, caching, async, capacity math |
| **Criticality / blast radius** | re-run a report → lose money / break the law | correctness guarantees, idempotency, audit trails, strong consistency |
| **Security & privacy** | internal behind VPN, no PII → public, holds secrets/PII/payments | hard authn/authz, encryption, untrusted-input handling, small attack surface |
| **Latency sensitivity** | "a few seconds is fine" → "every 100ms costs conversions" | sync work off the hot path, aggressive caching, queues |
| **Lifespan × churn × team** | weekend spike, one dev → decade-long core, dozen engineers | the full strategic-design investment; an architecture the team can operate |

1. **Scale + trajectory** — users, data volume, request rate, *and the growth curve*. Tens vs.
   thousands vs. millions is a different system. Small-but-flat: design for today, full stop.
   Small-but-10×-ing: design for the *next* tier, on purpose. Demand a real number or a real
   growth estimate before designing for scale — "it might get big" is not one.
2. **Criticality / blast radius** — what happens when it's wrong or down? *Inconvenience* (re-run a
   report) → low rigor. *Lost work / annoyed users* → moderate. *Money moves wrong* (billing,
   payments, inventory backing real orders) → high: idempotency, audit trails, reconciliation.
   *Legal / regulatory / governance / safety* (records an auditor inspects; data that determines
   someone's rights, benefits, money, status) → highest: strong consistency, append-only /
   tamper-evident history, least-privilege access, tested restores, immutability of the past, a
   real answer to "prove the state on date X." (Consistency requirements ride here: the higher the
   criticality, the less eventual consistency / at-least-once / approximate answers you tolerate.)
3. **Security & privacy exposure** — internal-behind-VPN vs. public on the internet; whether it
   holds PII, secrets, payment or health data; whether it's worth attacking. High exposure makes
   authn/authz rigor, encryption, secret hygiene, untrusted-input handling, an audit trail, and a
   small attack surface a *baseline, not a phase 2*.
4. **Latency / performance sensitivity** — "a few seconds is fine" (back-office, batch) vs. "every
   100ms costs conversions" (consumer-facing) vs. hard real-time. Decides whether expensive work
   can be synchronous, how aggressively you cache, where async/queues actually earn their keep.
5. **Lifespan × change-rate × team** — a weekend prototype; an internal tool that runs quietly for
   years with rare edits; a core product a dozen people change weekly for a decade. Multiply:
   long-lived × high-churn × big-team is where the strategic-design investment has its highest
   return; throwaway × static × one-dev is where it's near zero. And sophisticated architectures
   have a *running cost* in expertise and 3am toil — match the architecture to the team that has to
   operate it. Two people should not run nine services.

**Then design to the level each axis demands — no higher, no lower.** Over-shooting a low-stakes
axis is over-engineering: waste, drag, a permanent complexity tax for users you'll never have.
Under-shooting a high-stakes axis is negligence: data loss, breaches, outages, failed audits. Both
are failures. Most real systems are low-to-moderate on most axes and high on one or two — find
which, and put the rigor *there*.

For worked playbooks per tier — the throwaway spike, the internal tool, the public product, the
high-traffic service, the high-assurance/governance system — with concrete do / don't lists
(including the two cases this skill was built around: an internal furniture-business app for a few
hundred users, and a governance/compliance system), read `references/envelope-tiers.md`.

## The decision loop — run it for any decision worth the name

1. **Frame the envelope** (Step 0, above). Plus: is this a *one-way door* (DB engine, core data
   model, public API contract, auth model, a cloud's proprietary primitives) or a *two-way door*
   (an internal module boundary, a library choice, a caching layer you can pull out)? Spend your
   design budget on the one-way doors; two-way doors get a sane default and a one-line note, not a
   deliberation.
2. **State the problem, not a solution.** What concretely must be true? Which forces are in
   tension? Reject solution-shaped problem statements: not "we need a queue" but "expensive jobs
   block the request for 30s and users abandon" — *that's* the problem; the queue is one answer of
   several.
3. **Design it twice — and one option is always the minimal / null one.** Generate at least two
   genuinely different approaches; one must be "the smallest thing that could work" (or "do
   nothing / don't build it yet"). Forcing the minimal option onto the table is the single best
   anti-over-engineering move there is — it makes you say out loud why the bigger option is worth
   its cost, and often it isn't. Finding a second option routinely surfaces a better third.
4. **Name the trade-offs against the envelope.** For each option: how it works; what it costs (to
   build, run, operate, understand, in dollars); what it forecloses; what it assumes. Then map
   each cost and benefit to an envelope axis and reason from there — *"Option A caps at ~X rps; our
   envelope is internal, <1k users, flat growth, so that cap is irrelevant and A wins."* **The
   reasoning from envelope to choice is the deliverable, not just the choice.**
5. **Check both failure directions — adversarially, on your leading option.** Run the
   over-engineering smell test below; each "yes" is a prompt to delete something. *And* if any
   high-stakes axis is in play, ask hard whether you actually addressed consistency / audit /
   security / real scaling — or hand-waved it. Don't move on until you've named the leading
   option's worst weakness in each direction.
6. **Decide, and record why.** Pick. Write it down: context (the envelope), the decision, the
   alternatives considered, the consequences *including the bad ones you're accepting*. The
   rejected options and the "why" are the valuable part — they're what stops the decision being
   silently re-litigated, or silently violated by someone who didn't know it was a decision.
7. **Name the revisit triggers.** What concrete change reopens this? — "traffic crosses X", "we
   start taking payments", "we go multi-tenant". Two-way doors: revisit freely. One-way doors:
   revisit only on a real trigger, deliberately — not on vibes, not on a schedule.

## Over-engineering is the default failure — lean against it

You will be tempted to add boxes to the diagram. Public engineering writing overrepresents
big-tech-scale problems; adding patterns *feels* like demonstrating competence; symmetry and "what
if we need to…" are seductive. Resist:

- **YAGNI, and mean it.** Build for the requirements you have plus the near-term ones you can *name
  concretely* — on the roadmap, with a date. A vague future ("what if we go multi-tenant?") earns
  design effort only once it's concrete and likely.
- **Rule of three for abstraction.** Don't extract the general form on the first use, or the
  second. Three real, *different* uses, then abstract — the first two are guesses about what
  varies; the third is data. A wrong abstraction costs more than the duplication it replaced,
  because it's harder to back out.
- **Default to the boring, smaller thing — for this envelope.** Monolith over services. One
  database over many. Synchronous over async. A library over a service. A function over a
  framework. SQL over a bespoke query layer. Widely-known tech over exciting tech. Deviate only
  when a *named, present* requirement forces it — and say which requirement, with its number.
- **Architecture-pattern names are not arguments.** "Clean Architecture", "Hexagonal"/"Onion", and
  the *tactical* side of DDD (aggregates, value objects, repositories, mappers, a DTO at every
  boundary) are genuine tools that earn their keep at Tier 2+ with a real domain model and a real
  team. Dropped into a Tier-1 CRUD app they reliably collapse into pass-through layers
  (`references/design-heuristics.md` §6) — ceremony with no payoff, in a stack (FastAPI + Vue)
  where the framework already gives you the structure. If someone reaches for one, ask which
  concrete *present* problem it solves; if the honest answer is "it felt more professional," that's
  not a problem.
- **Count the carrying cost.** Every service, queue, cache, layer, and abstraction is something
  that must be understood, deployed, monitored, secured, paid for, and debugged at 3am — forever,
  by whoever inherits it. Before adding one, name the concrete problem it solves *today*.
  "Scalability" and "flexibility" are not problems; "the export query takes 40s and times out" is.
- **Robust ≠ elaborate.** Robustness comes from care — tests, monitoring, careful error handling,
  backups you've actually restored — not from architectural elaboration. Adding services doesn't
  make you robust; it makes you distributed, which is *harder* to make robust. Want resilience? Add
  tests and observability, not boxes.

**Over-engineering smell test** — run it on your leading design (loop step 5); each "yes" is a
prompt to delete something:
- more services than teams?
- a message queue / event bus but no measured throughput problem?
- an interface with exactly one implementation that isn't a test double?
- a cache in front of something never measured as slow?
- a config option no one will ever change?
- a "manager" / "service" / "handler" layer that just forwards calls (a pass-through layer)?
- the words "scalable" / "enterprise" / "flexible" / "future-proof" doing argumentative work with
  no number behind them?

**But — calibrated, not reflexive.** Anti-over-engineering is *not* "always do the crudest thing."
On a high-stakes axis — correctness for money, auditability for governance, security for exposed
PII, scaling for genuinely-high traffic — the simple thing is the *wrong* thing, and cutting it is
the under-engineering failure. The envelope step is what tells you which axis is which: trim
ruthlessly on the low-stakes ones, invest deliberately on the high-stakes ones.

## Worked sketch (so the loop isn't abstract)

Request: *"We need a job queue for generating order PDFs — they're slow."*

> **Envelope:** internal furniture-business app; ~a few hundred users; back-office, a few-second
> wait is fine; no PII beyond customer name/phone; one-to-two-person team; lives for years, edited
> occasionally. **One-way door?** No — how PDFs get generated is an internal boundary, swappable.
> **Problem, restated (not "we need a queue"):** generating a PDF takes ~8s and blocks the HTTP
> request, so the browser spinner sits there and a few users double-click. **Design it twice:**
> (a) **minimal** — generate inline but return immediately with a "generating…" row the client
> polls, generation runs in a FastAPI `BackgroundTask`; (b) add Celery + Redis as a real worker
> queue. **Trade-offs vs. envelope:** (b) buys retries, durability across restarts, and horizontal
> worker scaling — none of which this envelope needs (a dropped PDF job on the rare restart is a
> "click it again," not a lost order), and it adds a broker and a worker process for two people to
> operate forever. (a) covers the actual problem (unblock the request, kill the double-click) with
> zero new infrastructure. **Failure check:** under-built? Only risk is a job lost on deploy —
> acceptable here, and we note it; over-built? (b) trips "a queue with no measured throughput
> problem." **Decide:** (a). **Revisit trigger:** if PDF volume grows enough that lost-on-restart
> jobs become a real annoyance, or we need scheduled/retried generation, revisit — then Celery
> earns its keep.

Notice the choice fell out of the envelope, the minimal option was forced onto the table, and the
rejected option's "why not" got written down. That's the loop.

## The construction layer — design heuristics

The above is the *judgment* layer. The *construction* layer — deep modules, information hiding,
pulling complexity downward, layers that earn their place, defining errors out of existence,
comments that capture intent, names, consistency, strategic vs. tactical programming — lives in
`references/design-heuristics.md`. Read it when you're shaping the internals of a component, not
just the boxes and arrows. Each technique there is written context-aware: when it matters more,
when less, where it must bend to the envelope (e.g. "just crash on error" is fine for a CLI tool
and negligent for a governance system).

The one-line version: **complexity — anything that makes the system hard to understand and change
— is the enemy; it accretes from many small concessions, so you fight it with many small refusals;
and how hard you fight scales with how long the thing will live and how many people will touch it.**

## What this skill produces

When you use this skill to produce architecture content for the documentation, emit it in this
shape so downstream steps consume it predictably:

- **Envelope** — the five axes with the actual numbers / answers (or the explicit assumption).
  This doubles as the system's *"not built for"* statement — pin it down so no one later assumes
  otherwise.
- **Overview** — the major components and how they communicate (one clear diagram beats a wall of
  UML; a context view + a component view, C4-ish, is a fine default), the data model at a high
  level, and the cross-cutting concerns: auth, errors, logging, config, deployment.
- **Decisions** — a list of ADR-style records: context (the relevant slice of the envelope),
  decision, alternatives considered, consequences (including accepted downsides). Append-only —
  supersede, don't delete; the history is the point.
- **Open questions / revisit triggers** — what's undecided and why, and what would reopen settled
  decisions.

Stop at the *content and the reasoning*. Doc *form* — file layout, the ADR template, how the docs
are kept honest — is a separate job; reproducing that scope here would be the over-engineering this
skill warns about, applied to itself.
