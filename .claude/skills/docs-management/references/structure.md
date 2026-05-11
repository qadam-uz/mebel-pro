# docs/ structure — the authoritative spec

`SKILL.md` summarizes the tree; this file governs. For each folder: what belongs, what doesn't
(and where it goes instead), the naming convention, the depth limit. Then: the served-docs
constraints in full, the full routing map (with templates and the cross-links to make), and the
rules for evolving the tree.

Contents: the tree · conventions everywhere · the served-docs constraints · per-folder spec
(spec/ · ref/ and its subfolders · assets/ · misc/) · how decisions are recorded · the full routing
map · evolving the tree.

## The tree

```
README.md                # the ONLY README in the repo, at the root: "what this is + see docs/"
docs/
├── spec/                # the canon — high-level decisions & specs everyone works from. Lean.
│   ├── vision.md
│   ├── scope-v1.md
│   ├── personas.md
│   ├── journeys.md
│   ├── domain-model.md      # ubiquitous language + the high-level entity map; per-entity detail → ref/entities/
│   ├── architecture.md
│   ├── envelope.md
│   ├── nfr.md
│   ├── open-questions.md
│   └── <concern>.md         # one lean file per system-wide concern/flow: auth.md, order-flow.md, pricing.md, tenancy.md, …
│                            #   (decisions + their rationale live inside whichever spec/ doc owns the area — no separate ADR / decisions/ register)
├── ref/                 # everything else that's still documentation — detailed, look-it-up.
│   ├── features/
│   │   └── <feature>.md     # quoting.md, inventory-adjustments.md, …
│   ├── entities/
│   │   ├── sales/<entity>.md
│   │   ├── catalog/<entity>.md
│   │   ├── inventory/<entity>.md
│   │   ├── purchasing/<entity>.md
│   │   ├── customers/<entity>.md
│   │   └── …
│   ├── ux/
│   │   ├── information-architecture.md
│   │   └── components.md
│   ├── api/
│   ├── jobs/
│   ├── runbooks/
│   └── integrations/
├── assets/              # images & diagrams docs embed — the only place binary files live
└── misc/                # research, PDFs, exports, scratch, temporary — not the documentation
```

## Conventions that apply everywhere

- **Filenames:** kebab-case, descriptive, **stable** — `order-flow.md`, not `OrderFlow.md`,
  `ORDER_FLOW.md`, or `orderflow.md`. A filename is part of a URL (see "The served-docs
  constraints"); renaming breaks links. Do it deliberately, and leave a redirect.
- **Depth:** at most three levels under `docs/` (`docs/ref/entities/sales/order.md` is the floor).
  Deeper means the grouping is wrong — flatten or regroup.
- **Frontmatter:** every `.md` under `docs/` except `misc/` carries it (schema in
  `references/authoring.md`). No exceptions.
- **Cross-link by path:** `docs/ref/entities/sales/order.md`, not "the order doc" or "see above."
  Two-way: if A links B because B is relevant to A, B's `related:` should usually list A.
- **No `README.md` or `index.md` under `docs/`.** Only the repo root has a `README.md`. The
  backend renders the docs landing page and the section overviews; don't hand-write them.
- **No `_template.md` files in `docs/`.** Templates live in this skill's `assets/templates/`; copy
  from there.

## The served-docs constraints

The backend renders `docs/` as a browsable site — markdown → HTML on the fly, behind the app's
auth, with the nav built from the tree + frontmatter. The implications:

- **A path is a URL.** `docs/spec/auth.md` → `/docs/spec/auth`. Treat a doc's path like a public
  API: stable. If you must rename or move, leave a redirect — a stub at the old path that points to
  the new one, or a backend redirect rule. Don't break a URL casually; never rename for cosmetics.
- **`title` is the page heading and the nav label.** Every doc has one. Make it the real title of
  the thing, not the filename echoed back.
- **`order:` sets position within a section.** Optional integer; lower comes first; absent means
  title-ordered. Use it where the reading order matters (`vision` before `architecture` before
  `open-questions`), skip it where it doesn't. Do not encode order in filename prefixes (`01-…`) —
  that puts the order *in the URL*, so reordering breaks links.
- **`status: draft` shows.** The site badges non-`stable` docs. Serving a draft internally is fine;
  mislabelling a half-written doc `stable` is not.
- **Images:** in `docs/assets/`, referenced by relative path; the backend serves that folder
  static. Organize `assets/` however stays navigable — mirroring the using doc's path
  (`assets/spec/architecture/context.png`) is one good way; flat-with-descriptive-names is fine for
  a small set. Nothing binary in `spec/` or `ref/`.
- **`misc/` isn't rendered.** It's a drawer, not a section. Don't link a doc to a `misc/` file as
  its source of truth; if the `misc/` file matters, distil it into `spec/` or `ref/`.

## Per-folder spec

### `spec/` — the canon
- **Belongs:** the high-level decisions and specs **everyone works from** — product framing
  (`vision`, `scope-v1`, `personas`, `journeys`), the domain model (`domain-model` — the words and
  the high-level shape), the system view (`architecture`, `envelope`, `nfr`), the open-questions
  register, and one lean file per system-wide concern or flow (`auth`, `order-flow`, `pricing`,
  `tenancy`, …). **The decisions and their rationale live inside these docs**, woven in where each
  belongs (`architecture` for topology / stack / data-model calls, a `spec/<concern>.md` for that
  concern's calls, `domain-model` for the domain shape, `scope-v1` for the in/out-of-scope calls) —
  there is no separate ADR genre and no `decisions/` folder (see "Recording decisions" below).
- **Doesn't:** per-feature detail (→ `ref/features/`); per-entity field lists (→ `ref/entities/`);
  exhaustive technical reference (→ `ref/`); not-really-documentation (→ `misc/`). A `spec/` doc
  *states what must be true — and why it's that way* — and links out for detail.
- **The test:** *is this a high-level decision or spec everyone works from?* If no, it's not
  `spec/`. The whole of `spec/` should be readable in one sitting; if it isn't, something escaped
  into the wrong layer — find it and pull it down to `ref/`.
- **Shape:** flat files only — nothing nested under `spec/` (no `decisions/` or any other subfolder).
- **Naming:** `kebab-case.md`; concern/flow docs are named for the concern (`order-flow.md`), not
  "spec" anything.

### Recording decisions (no ADR register)
There is **no ADR genre and no `spec/decisions/` folder**. A consequential, costly-to-reverse
decision is recorded **inside the `spec/` doc that owns the area** — `architecture.md` for topology /
stack / data-model calls, a `spec/<concern>.md` for a concern's calls, `domain-model.md` for the
domain shape, `scope-v1.md` for the in/out-of-scope calls — woven into that doc's prose with: the
**forces** in play (the operating envelope, the constraints, what's costly to reverse), the
**alternatives** weighed and why they lost, the **consequences** accepted (what it makes easier, what
it costs, what it forecloses), and the concrete **revisit trigger** (a number, an event, a date — not
"periodically"). A `spec/` doc that states a normative call also states why it's that call. When the
decision is overtaken, fix that doc in place and bump `updated` — git keeps the history; a served
site shouldn't carry a known-wrong call. (Routing for "I have a decision to file" is the
"A consequential, costly-to-reverse decision" row in the full routing map below.)

### `ref/` — everything else that's still documentation
- **Belongs:** the detailed, look-it-up material, organized into the subfolders below. `ref/` is
  the bulk of the live site by page count and the part that grows fastest — especially once the
  build pipeline starts producing API / job / runbook docs against running code.
- **Doesn't:** the high-level canon (→ `spec/`); binaries (→ `assets/`); scratch (→ `misc/`).
- **Shape:** the named subfolders below; if something genuinely doesn't fit one, that's a signal —
  either it's actually `spec/`, or it warrants a new `ref/` subfolder (a deliberate call, not a
  reflex). Avoid loose files directly in `ref/`.

  - **`ref/features/`** — one working spec per feature area, from the `feature` template: problem ·
    user stories · requirements · UX (the interface design for this feature) · entities touched
    (links into `ref/entities/`) · edge cases · out-of-scope · open questions. This is the unit the
    `build` pipeline decomposes into work. Flat until it's ~15 files, then group by area. Named for
    the feature — `quoting.md`, `inventory-adjustments.md`.
  - **`ref/entities/`** — the entity catalog, one file per entity: `ref/entities/<domain>/<entity>.md`
    from the `entity` template — what it is · fields · states/lifecycle · invariants · relationships
    (links to other entity pages) · owner. Grouped by domain (bounded context); a reasonable
    starting grouping for a furniture business: `sales/`, `catalog/`, `inventory/`, `purchasing/`,
    `customers/`, and `production/` if the business builds/assembles in-house. Adjust to the real
    domain model — but a domain with one or two entities is a single file, not a folder of stubs.
    This is the **single home** for "what is an X"; `spec/` and `ref/features/` *link* here, never
    redefine.
  - **`ref/ux/`** — cross-cutting UX detail: `information-architecture.md` (the nav model, the page
    map), `components.md` (the shared component inventory & specs). Per-feature UX lives in the UX
    section of `ref/features/<x>.md`, not here. (The design content that fills these comes from
    elsewhere; this skill owns their placement, naming, and frontmatter.)
  - **`ref/api/`** — endpoint reference; **`ref/jobs/`** — background jobs and cronjobs;
    **`ref/runbooks/`** — operational procedures; **`ref/integrations/`** — third-party / external
    systems. Mostly produced by the `build` pipeline against running code; can be long; can be
    generated / derived. Keep each internally structured so it stays navigable.

### `assets/` — images & diagrams
- **Belongs:** the image, diagram, and exported-figure files that `spec/` and `ref/` docs embed.
  The backend serves this folder as static files; docs reference assets by relative path.
- **Doesn't:** anything not embedded by a doc (→ `misc/`); markdown (→ `spec/` / `ref/`).
- Organize for navigability — mirroring the using doc's path is one good convention; flat with
  descriptive filenames is fine while the set is small.

### `misc/` — the drawer
- **Belongs:** research notes, PDFs, vendor docs, exports, one-off scripts, screenshots not
  embedded anywhere, temporary working files, the occasional dead doc you want to keep visible
  (stamped "superseded by … / dropped because …" at the top). Things that aren't *the
  documentation* but that you don't want loose in the repo root or lost.
- **Doesn't:** anything `spec/` or `ref/` should own. If a `misc/` file becomes a source of truth,
  that's a sign it should be distilled into a real doc — do that, then the `misc/` original is
  background material or can go.
- **No rules:** no required frontmatter, no naming convention, not part of the rendered site, not
  audited. It's a drawer. Keep it from becoming a swamp by occasionally clearing out what's served
  its purpose — but don't agonize over it.

## The full routing map

| You have… | Path | Template | Cross-link to | Notes |
|---|---|---|---|---|
| Product vision / the core bet | `docs/spec/vision.md` | — | `scope-v1.md` | Canon. Keep it short. |
| Scope / non-goals for v1 | `docs/spec/scope-v1.md` | — | `vision.md`, the `ref/features/*` it scopes | Canon. The "out" list matters as much as the "in" list. |
| A user role | `docs/spec/personas.md` | — | the `journeys.md` & `ref/features/*` they touch | One file, a section per role. |
| An end-to-end workflow spanning features | `docs/spec/journeys.md` | — | each `ref/features/*` step touches; the `ref/entities/*` it moves | Cross-feature flows only; single-feature flows live in the feature spec. |
| Ubiquitous-language term / the high-level entity map | `docs/spec/domain-model.md` | — | `ref/entities/<domain>/<entity>.md` | Canon — the lean view. Per-entity detail → `ref/entities/`; don't restate it here, link. |
| The architecture overview (topology, stack, cross-cutting concerns) | `docs/spec/architecture.md` (+ a `spec/<concern>.md` per concern that earns its own doc) | `spec.md` for the concern docs | `envelope.md`, `nfr.md`, `domain-model.md` | Canon. Carries the topology / stack / data-model **decisions and their rationale** inline. Diagrams welcome (images in `docs/assets/`); keep prose lean. |
| The operating envelope (tier, the "not built for" line) | `docs/spec/envelope.md` | — | `architecture.md`, `nfr.md` | Canon. The system's "not built for" statement — pin it down; the architecture/concern docs reason from it. |
| A non-functional requirement | `docs/spec/nfr.md` | — | `envelope.md`, `architecture.md`, the concern docs that satisfy it | A terse requirements checklist; the design that satisfies each lives where it's linked. |
| A system-wide concern or flow (auth, pricing, order-flow, tenancy, …) | `docs/spec/<concern>.md` | `spec.md` | `architecture.md`, the `ref/features/*` it shapes, `ref/entities/*` | Canon. One lean file each. Carries that concern's **decisions and their rationale** inline. Detail / procedures → `ref/`. |
| A consequential, costly-to-reverse decision | **the `spec/` doc that owns the area** — `architecture.md` (topology / stack / data model), a `spec/<concern>.md` (a system concern), `domain-model.md` (the domain shape), `scope-v1.md` (an in/out-of-scope call) — recording the *why* (forces · alternatives weighed · consequences accepted · the concrete revisit trigger) woven into that doc | (none — no ADR template) | n/a (it's part of an existing doc) | **No separate ADR / `decisions/` register.** When the decision is overtaken, fix the doc in place and bump `updated`. See "Recording decisions" above. |
| An open question / revisit trigger | `docs/spec/open-questions.md` | — | the doc the question bears on | Canon. Each question gets an owner and a concrete revisit trigger; mirror feature-spec blocking questions up here. |
| A feature (problem, stories, requirements, …) | `docs/ref/features/<feature>.md` | `feature.md` | `spec/scope-v1.md`, `spec/journeys.md`, the `ref/entities/*` touched, related `ref/features/*` | The build pipeline's unit. Fill every section. |
| Per-feature UX (flows, states, key screens) | the **UX** section of `docs/ref/features/<feature>.md` | (part of `feature.md`) | `ref/ux/information-architecture.md`, `ref/ux/components.md` | A section of the feature spec; the design content fills it. |
| Cross-cutting UX — information architecture, component specs | `docs/ref/ux/information-architecture.md` / `docs/ref/ux/components.md` | — | `spec/personas.md`, the `ref/features/*` they shape | Cross-cutting only. |
| An entity definition (fields, states, invariants) | `docs/ref/entities/<domain>/<entity>.md` | `entity.md` | the other entity pages it relates to; the `ref/features/*` & `spec/*` that own its rules | The single home for "what is an X." Update `spec/domain-model.md`'s map when the set of entities changes. |
| API / job / runbook / integration detail | `docs/ref/api/` · `docs/ref/jobs/` · `docs/ref/runbooks/` · `docs/ref/integrations/` | — | the `ref/features/*` / `spec/*` it implements | Mostly build-pipeline output. Keep each subfolder internally structured. |
| An image or diagram a doc embeds | `docs/assets/…` | — | (referenced by relative path from the doc) | The only place binary files live. |
| Research notes, a PDF, an export, a scratch file, a dead doc to keep visible | `docs/misc/` | — | — | Not the documentation. No template, no frontmatter, not rendered, not audited. |
| Raw ideation / brainstorm output | distil into the relevant `docs/spec/*` or `docs/ref/features/*`; promising-but-not-now → a line in `spec/open-questions.md`; otherwise drop, or park in `misc/` | — | — | Raw notes are not a doc. Give them a home or let them go. |
| A doc that's now wrong and dead | delete it (git keeps history) — or move to `docs/misc/` with a "superseded by … / dropped because …" banner if it's worth keeping visible | — | — | Fix any `related:` links and `assets/` references that now dangle. |

If an output fits no row: it's either not doc-worthy (→ `misc/` or nothing), or you've found a real
gap — see below.

## Evolving the tree

Adding a `ref/` subfolder, or a new `spec/` doc, is a deliberate act — same test as any
architecture move: *what concrete present need does this serve, and does it pull its weight?*
(Yes — the same "does it pull its weight?" discipline, applied to the docs themselves.) If the
honest answer is "it felt tidier," don't. When you do change the structure:

- make the **smallest** change that fits — a new file before a new subfolder; a new `ref/`
  subfolder before a new top-level folder under `docs/`;
- a new top-level folder under `docs/` is a *high* bar — `spec/`, `ref/`, `assets/`, `misc/` is
  meant to be the whole list;
- never fork the structure per-feature or per-team — one tree, one set of conventions;
- if it's a significant reshape, record the decision (with its rationale and revisit trigger) in
  `architecture.md` — or in `domain-model.md` if it's the entity tree — and watch the URLs: a reshape
  that moves files needs redirects;
- update the repo-root `README.md` only if the top-level shape changed; the backend handles the
  rest.

What does **not** need ceremony — the tree working as designed: a `ref/features/<x>.md`, a
`ref/entities/<domain>/<entity>.md`, a `ref/api/*` page, a section added to `personas.md` /
`nfr.md` / `journeys.md`, a `spec/<concern>.md` for a concern that genuinely is system-wide, a
decision (with its rationale) recorded inside `architecture.md` / a concern doc / `scope-v1.md`, an
image in `assets/`.
