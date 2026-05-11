# Envelope tiers — playbooks

`SKILL.md` says: locate the system on the five envelope axes, then design to the level each axis
demands — no higher, no lower. This file turns that into concrete playbooks. Find the tier the
system actually sits at and build to it; resist the tier above it unless a *named, present*
requirement (with a number) forces the move.

**The tiers:** 0 — Throwaway / spike · 1 — Internal tool · 2 — Public product · 3 — High-traffic /
high-scale · 4 — High-assurance / governance / regulated.

**Most real systems are a mix.** A system can be Tier 1 overall and have one Tier-4 module inside
it. Find the high-stakes seam and concentrate rigor there — don't average it out (averaging
under-builds the critical part and over-builds everything else). There's a worked example of this
at the end.

A note on the axes: tiers 0→3 mostly track the **scale / latency / lifespan** axes. Tier 4 tracks
the **criticality / consistency / security** axes and is *largely independent of scale* — a
governance system can be tiny in traffic and still Tier 4. So "what tier is this?" is really two
questions: how big and busy is it, and how much does it matter if it's wrong.

---

## Tier 0 — Throwaway / spike

*What it is:* a one-off script, a data migration you run once, a prototype built to answer a
question ("does this API give us what we need?", "is this layout any good?"), a benchmark. Lifespan
is days to a few weeks, then it's deleted or rewritten.

**Do:** whatever is fastest. One file. Hardcode values. Skip tests. Skip abstractions. Skip the
error handling beyond "crash with a readable message." Optimize for time-to-answer.

**Don't:** build it "properly" — that's wasted effort on something with no future to protect.
Don't run real production secrets, real PII, or real money through a spike. And the big one:
**don't let a spike quietly become production.** If it survives — if people start depending on it —
that is a *new decision*, not a continuation; stop and re-evaluate it at Tier 1 (or higher), and
budget the rewrite. The most expensive systems in the world are Tier 0 code that nobody re-tiered.

---

## Tier 1 — Internal tool  ← *the furniture-business app this skill was built around*

*What it is:* a back-office or line-of-business app. Tens to low thousands of internal users,
behind company auth. Not directly handling money or legal records (if it is, that part is Tier 4 —
see below). Flat-ish growth. One to three developers. Expected to run for years with occasional
edits. *Example: an internal app for a furniture business — quoting, orders, inventory, customers
— used by a few hundred staff.*

**Do:**
- A **modular monolith** — one deployable, with clean module boundaries *inside* it. (FastAPI
  backend, Vue frontend, talking over a normal HTTP/JSON API, as in this repo.)
- **One relational database** (Postgres). Schema migrations from day one. Normalize; denormalize
  only a specific column when a specific query proves it needs it.
- **Synchronous everything** until something is measurably too slow. A function call beats a queue.
- **Boring, widely-known tech.** The stack a new hire already knows. Excitement is a cost here.
- **Tests on the logic that matters** — the pricing math, the state machines, the things that
  would be embarrassing to get wrong — not 100% coverage of CRUD glue.
- **Backups you have actually restored at least once.** An untested backup is a hope, not a backup.
- **One deploy target**, one environment story, simple CI. Logs you can grep.
- Real **auth, least privilege, and an audit trail on anything sensitive** (who changed a price,
  who saw a customer's data). *Internal* does not mean *unguarded* — employees, contractors, and
  compromised laptops are inside the perimeter.

**Don't** (this is the over-engineering list, and for a Tier-1 app every item here makes it
*worse* — more failure modes, more ops, more cognitive load — for users you will never have):
- microservices, a service per noun, a separate frontend micro-app per page
- a message queue / event bus / event sourcing / CQRS
- read replicas, sharding, a caching layer (Redis-in-front-of-everything)
- Kubernetes, a service mesh, multi-region
- NoSQL "for scale", a graph database "for flexibility", a search cluster before search is a
  measured pain
- a generic plugin system, an abstraction layer over the database "in case we switch"

*When something gets slow:* **measure the specific thing, fix the specific thing** — add the
index, denormalize the one column, add the one targeted cache, paginate the one endpoint. Do not
re-platform. A Tier-1 app that's slow is almost always slow because of one missing index or one
N+1 query, not because it needed to be a distributed system.

---

## Tier 2 — Public product

*What it is:* customer-facing, on the public internet. Thousands to hundreds of thousands of
users, real growth, holds PII (accounts, contact info, maybe payment tokens via a processor). A
handful to a few dozen engineers. Multi-year horizon.

**Do:**
- Still **probably a monolith**, or a *small* number of services split on real seams — a
  different scaling profile, a different team, a different release cadence, a different data
  owner — *not* on diagram aesthetics. A split is justified when it *reduces* coupling; if it
  doesn't, it's just latency and ops you added for free.
- **Managed Postgres**; a **read replica** once reads genuinely dominate and you've measured it;
  a **CDN** for static assets; a **cache** where you've measured a hot read path.
- A **job queue** for genuinely slow or spiky work — email, exports, webhooks, image processing —
  not for everything.
- Real **authn/authz** (sessions or OAuth/OIDC), **rate limiting**, **input validation as a
  rule**, **secret management** (not env files in the repo).
- **Observability**: structured logs, metrics, traces; **error tracking** (Sentry-style);
  dashboards for the few numbers that matter; alerts that page only on real problems.
- **Safe deploys**: rolling or blue-green, migrations that are backward-compatible during the
  rollout, a rollback path. Someone on call.

**Don't:**
- a service per noun; an event bus you can't name a consumer for
- eventual consistency where a user expects to see their own write immediately ("read-your-writes"
  — violate it and you get a flood of "the site is broken" reports that aren't)
- premature sharding; a service mesh for five services; multi-region before a single region is
  actually maxed or latency genuinely demands it
- a microservice extracted "to be ready" — extract it when the seam is real and the split pays now

---

## Tier 3 — High-traffic / high-scale

*What it is:* the request rate, data volume, or concurrency genuinely *is* large now, or genuinely
*will be* within the planning horizon — millions of users, high QPS, large or fast-growing data.

**Do** (these stop being optional here): horizontal scaling and **stateless services**;
**aggressive caching** at multiple layers; **async processing of everything expensive**, off the
hot path; **backpressure and load-shedding** so overload degrades instead of collapses;
**graceful degradation** (the core path survives when a dependency is down); careful
**connection-pool and capacity math**; **partitioning / sharding** of the data that's too big for
one node; and *deliberately choosing* which operations are allowed to be **eventually consistent**
so the hot path isn't bottlenecked on coordination. Here, "we'll just add a server later" is the
under-engineering failure — the architecture has to anticipate the load.

**Two cautions, both important:**
1. **Prove you're here.** A real traffic number, a real growth curve, a real data-size projection.
   Most systems that *believe* they're Tier 3 are Tier 1 or 2 with ambitions. Designing for
   Tier-3 load you don't have is the textbook over-engineering mistake, and it's expensive — it
   slows everything down forever for traffic that never arrives.
2. **Even here, scale the hot parts, not the whole system.** Most of even a very large system is
   low-traffic — admin panels, settings, reporting, onboarding. Build *those* like Tier 1. Reserve
   the Tier-3 machinery for the genuinely hot paths. A uniformly "web-scale" system is mostly
   wasted effort.

---

## Tier 4 — High-assurance / governance / regulated

*What it is:* the system holds records an **auditor, regulator, or court** will inspect; or data
that **determines someone's rights, benefits, money, identity, or legal status**; or it's
money-movement-critical or safety-critical. The governing axis is **criticality + consistency +
security**, and it's *largely independent of scale* — a governance app for 200 users is still
Tier 4. *Example: a system of record for a regulated process — permits, licenses, compliance
filings, entitlements, official decisions.*

**Required — not "phase 2", not "if we have time":**
- A **strongly consistent, transactional store** — ACID, real serializable-or-close transactions
  around the operations that must be atomic. "Eventually" is not acceptable for the state of
  record.
- An **append-only, tamper-evident audit log** of every state change: who, what, when, *why*,
  before/after. It must be replayable — you can reconstruct the state at any past moment. Don't
  build this as a "nice to have" you bolt on later; the schema and the write path have to assume
  it from the start.
- **Immutability of history.** You *supersede* records; you don't overwrite or hard-delete the
  past. The history *is* the asset.
- **Strict least-privilege access control**, itself audited (who accessed which record, when).
- **Validation that cannot be bypassed** — enforced at the data layer (constraints, checks,
  server-side rules), not merely in the UI. Assume someone will hit the API directly.
- **Encryption** in transit and at rest; disciplined **secret management**.
- **PII handled per the applicable regime** — data residency, retention limits, the
  right-to-erasure-vs-audit-retention tension. Resolve that tension *explicitly* and write the
  decision down; don't let it be implicit.
- **Backups *and tested restores*.** Plus a documented, tested answer to two questions an auditor
  will ask: "prove the system's state on date X" and "show the complete history of record Y."

**The failure to refuse here is *under*-engineering** — "just put it in a JSON column and update
in place", "we'll add the audit log later", "the form validates it so we're fine", "we'll worry
about who-can-see-what once we ship." An agent must not propose the casual version *just because it
is less code*. On these systems, the rigor is the point, and skipping it isn't a shortcut, it's a
defect — sometimes a legal one.

**But Tier 4 ≠ Tier 3.** Being high-criticality does *not* license high-scale machinery. A
regulated app for a few hundred users is still a **monolith with one careful database** — it's
just a *very* careful one: every write audited, every history immutable, every access checked. Add
queues, replicas, and services only if the *scale* axis independently puts you at Tier 2–3. Don't
let "this matters a lot" turn into "so let's make it complicated" — make it *careful*, which is a
different thing.

---

## Worked example: a mixed system

Take the internal furniture-business app (Tier 1 overall). Most of it — quoting, the product
catalog, customer contact info, order entry, the dashboard — is straightforwardly Tier 1: modular
monolith, one Postgres, sync, boring, tested where it matters, backed up. Build it that way and
stop; don't add a queue, don't add Redis, don't split services.

Now suppose — illustratively; substitute whatever the real high-stakes seam turns out to be — one
slice of it records **price-override approvals** that finance and an external auditor review each
quarter: who approved a discount beyond policy, when, on what justification. That *module* is
Tier 4: its records are append-only and immutable, every change is audit-logged
with the approver and reason, access to it is least-privilege and logged, and there's a tested way
to show "every override on order #1234, in order." You build *that one module* to Tier 4 standards
— and you do **not** therefore upgrade the whole app: the catalog doesn't need an audit log, the
dashboard doesn't need immutability.

That's the move in general: don't pick one tier for the whole system and apply it uniformly. Find
where the stakes actually are, build *that* to the tier the stakes demand, and build the rest to
the (usually lower) tier *its* stakes demand. Uniform rigor over-builds the easy parts and, worse,
tempts you to under-build the hard one to keep the average reasonable.
