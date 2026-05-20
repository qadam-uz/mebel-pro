---
name: docs-management
description: >-
  Owns the project's `docs/` corpus — structure, routing, linking, upkeep — served live as markdown by the backend. Use whenever you create, edit, move, organize, or review docs; file an architecture decision, UX spec, feature, or entity page; ask where a doc belongs; or suspect docs are stale, duplicated, orphaned, or leaking between layers. Keeps the tree small; separates canon / `ref/features` / `ref/entities`; enforces one-fact-one-home, stable paths, and mermaid over ASCII.
---

# Documentation Management

> Documentation fails in two ways: it sprawls until no one reads it, or it drifts until no one
> trusts it. This skill prevents both — by giving every fact exactly one home, keeping the
> must-read core small, and keeping the corpus legible to a person reading it, an agent pulling
> one file into context, and the backend rendering it as a live site.

This skill owns the **form** of the documentation, not the **decisions** in it. Architecture
work makes the architecture calls; UX work makes the UX calls; ideation produces raw product
thinking. This skill decides **where each output lives, what shape it takes, how the pieces
link, and whether the set is complete and consistent** — and it pushes back when a doc is in the
wrong layer, duplicates another, contradicts one, or is about to break its URL.

## Three layers — what each owns, what leaks where

Every piece of content belongs in one of three layers. The most common defect is **leakage** — a
rule that sits in the wrong layer, or worse, in two. **Before you write a sentence, decide
which layer owns it.**

| Layer | What it owns | Belongs here |
| --- | --- | --- |
| **Canon** — flat at the top of `docs/` | the **model** and **normative rules** every contributor must know | the principals, tenancy boundaries, the operating envelope, topology, system-wide invariants, in / out of scope |
| **`ref/features/<domain>.md`** | the **mechanics** of one cohesive domain | domain rules, per-object state machines, operations in domain language, UX (screens, flows), permission catalogs, error codes as domain facts in edge cases |
| **`ref/entities/<context>.md`** | the **shape** of the entities in one bounded context | fields, types, lifecycle states, invariants |

**Leakage into canon — push it down to a feature.** Any of these in a canon doc means it has
escaped its layer:

- A hand-written endpoint table, request / response field names, error-code catalogs
- A permission catalog (`manage_workers`, `view_orders`, …)
- A wizard, screen, or form description — any per-feature UX
- A session table schema, an algorithm name, a library version (the *choice* of FastAPI is
  canon; column names and pinned versions are not)

Endpoint paths and HTTP-level schemas have a single home: the OpenAPI spec the backend
generates (rendered at `/api-docs`), curated under `ref/api/` when it earns it. **Feature docs
describe operations in domain language**, not in HTTP — that prevents the parallel-copy drift.

**Leakage out of canon — collapse it.** A feature doc that restates something the canon owns is
duplication, not clarity. Drop the restatement; let the canon doc be the single home, with one
critical inline link if a reader genuinely needs it:

- The principal types or the tenancy hierarchy
- A system-wide invariant ("money is integer tiyin", "no soft-delete columns")
- Topology every feature shares

**Why this matters.** Canon is mandatory reading — every line there is a tax everyone pays.
Features are reached when someone is working that domain — they earn their detail. Mixing the
layers robs the canon of its purpose: a contributor can no longer skim it and know everything
they need to start. The whole canon should be **readable in one sitting**; when it isn't, look
for leakage first.

## Place every piece of content before writing it

Three questions, every time:

1. **Which layer?** Canon, feature, or entity — apply the layer tests above.
2. **Which doc inside that layer?** Search the corpus first. If a doc already covers this
   concept, *update it in place* — don't start a parallel doc.
3. **Does it duplicate something elsewhere?** If yes, link from "Next" (or one critical inline
   reference); don't restate.

Skipping this trio is the leading cause of corpus drift: content lands in the wrong layer, in a
parallel doc, and quietly contradicts the rightful owner. **Place before you write.**

## The doc tree

```
README.md                # the ONLY README in the repo, at the root: "what this is + see docs/"
docs/
├── index.md             # THE HOME: a Getting Started landing — vision in a paragraph + "Read in this order" → the canon, then features and entities. The ONLY index.md under docs/.
│
│ # THE CANON — flat at the top of docs/. High-level decisions & specs everyone works from. Lean.
├── scope.md             # in / out / explicit non-goals for v1
├── personas.md          # the roles and what each needs
├── domain-model.md      # the ubiquitous language + the high-level entity map (per-entity detail → ref/entities/)
├── access-patterns.md   # principals, the access model, tenancy — the one cross-cutting concern that earns its own canon doc today
├── architecture.md      # operating envelope · topology · stack · data-model invariants · quality requirements
│                        #   (decisions + their rationale live inside whichever canon or feature doc owns the area — no separate ADR / decisions/ register)
│
├── ref/                 # everything else that's still documentation — detailed, look-it-up.
│   ├── features/        # ONE PAGE PER COHESIVE DOMAIN — orders.md, cutting.md, catalog-inventory.md, workshop.md, notifications.md, platform.md, access-management.md. Each owns rules, UX, edge cases for its domain — operations in domain language, NOT a hand-written endpoint table (OpenAPI's job). Trivial CRUDs are sections inside the right home, not solo files.
│   ├── entities/        # ONE PAGE PER BOUNDED CONTEXT (sales.md, catalog.md, inventory.md, cutting.md, identity.md, workshop.md, support.md) — fields/states/invariants. **Not** one file per entity.
│   ├── api/             # endpoint reference — when it earns its own corner
│   ├── jobs/            # background jobs / cronjobs — when it earns its own corner
│   ├── runbooks/        # operational procedures — when it earns its own corner
│   └── integrations/    # third-party / external systems — when it earns its own corner
├── assets/              # images & diagrams docs embed — the ONLY place binary files live; the backend serves these as static files
└── misc/                # research, PDFs, exports, scratch, temporary — NOT the documentation; not rendered; no rules, no frontmatter
```

Outside `docs/` but worth knowing about:

- **`web/DESIGN.md`** — the frontend design system (tokens, primitives, composed components,
  the shell, route maps for the three SPAs, accessibility baseline). Lives next to the code it
  constrains, not under `docs/`. There is no `docs/ref/ux/` — do not recreate one.

## The docs are served live — what that means for how you write them

The backend renders `docs/` as a browsable site — markdown → HTML on the fly, behind the app's
auth — building the nav from the tree and frontmatter. So:

- **The home page is `docs/index.md`.** A one-paragraph vision + a numbered "Read in this
  order" ladder (canon → features → entities). **`docs/index.md` is the only `index.md`
  allowed under `docs/`** — section overviews render from the tree.
- **A path is a URL.** `docs/ref/features/orders.md` → `/docs/ref/features/orders`. Renaming
  or moving a file breaks bookmarks and inbound links. Filenames are kebab-case, descriptive,
  and **stable**. If you genuinely must rename, leave a redirect. Treat a doc's path like a
  public API.
- **`title` and `order` drive the nav.** Every doc has a `title` (heading + nav label). Set
  `order:` (integer, lower first) when position within a section matters; otherwise sections
  are title-ordered. Don't encode order in filename prefixes (`01-…`) — that puts the order
  *in the URL*.
- **`status: draft` is visible.** The site badges non-`stable` docs — fine to serve, just
  don't leave a half-written doc marked `stable`.
- **Images go in `docs/assets/`**, referenced by relative path. Nothing binary in the canon
  or `ref/`.
- **`misc/` is not rendered.** Don't link to a `misc/` file as a source of truth.
- **No `README.md` anywhere under `docs/`.** The repo's single `README.md` is at the root and
  just orients ("what this is — see `docs/`").

## Write less, not more

The corpus is read many more times than it's written. Bias toward subtraction.

- **State the call; don't relitigate it.** A decision is *what we do* with the *why* in one
  sentence — not three paragraphs comparing the road not taken. Long "X vs Y" essays belong in
  the conversation where the call was made, not in the canon.
- **A rationale paragraph earns its space when** it tells a future reader *what would have to
  change* to revisit the call. Otherwise it's noise; cut it.
- **One self-edit pass before saving.** Hunt for: hedging adjectives ("relatively", "fairly"),
  throat-clearing openers ("It's worth noting that…"), a sentence whose only job is to
  introduce the next paragraph, a heading restated in its first sentence. Cut them.
- **Length is a signal.** A canon doc creeping past ~200 lines, or a feature doc past ~500, is
  usually carrying detail that belongs a layer down — or it's two docs in one.

## Diagrams: mermaid first, tables for comparison, prose for rationale

Use the right shape for the content. In order of preference:

1. **Mermaid diagrams** for anything with nodes and edges — topology, tenant hierarchy, state
   machines, sequence flows, ER relationships. The backend renders them; they survive edits
   cleanly; the source diff is reviewable.
2. **Tables** for structured comparison — state semantics, role / scope matrices, field lists,
   routing maps. The reader scans the columns; prose hides the comparison.
3. **Numbered lists** for ordered steps; **bulleted lists** for unordered atoms.
4. **Prose** for rationale — the *why*, the trade-offs, the revisit trigger.

**ASCII diagrams are forbidden.** No box-and-pipe trees, no hand-drawn rectangles, no
indented-bullet hierarchies dressed up as structure. They drift the moment anyone edits them,
render poorly outside fixed-width fonts, and a mermaid block does the same job better. If you
find one in an existing doc, replace it.

## Cross-document references — minimize them

The corpus is **deliberately under-linked**. A doc wall-to-wall in blue is unreadable, and
every inline link is a maintenance cost when paths move.

- **Every doc ends with a "Next" line** — 2–4 links to what to read next. That's the *primary*
  way to guide reading. (Short docs without an obvious "next" can omit it.)
- **Inline cross-doc links only at critical points** — where omitting the link would force the
  reader to re-learn context, or where the linked doc is the *single* authoritative home for
  something the current doc is asserting. Examples that earn it: a feature doc pointing at the
  canon rule it relies on (`access-patterns.md`, `architecture.md`); an entity context page
  pointing at the feature that owns its rules. Examples that don't: ambient "see also" links,
  links to the same target twice, links to a closely related entity page mid-paragraph.
- **`related:` frontmatter is optional.** Use it only when two docs are tightly coupled and
  the rendered widget genuinely helps navigation.
- **Never "see above" or "the order doc."** Always link **by path** —
  `docs/ref/features/orders.md` — so the renderer resolves it.

If you find yourself adding the same cross-link three times in a doc, the doc is probably
restating something that lives elsewhere; collapse the prose and link once.

## Edits leave the doc coherent

Updating an existing doc is where consistency dies. The most common failures: appending new
content at the bottom regardless of section order; introducing fresh duplication with a
neighbouring doc; drifting the frontmatter shape; restating a rule that's already owned
elsewhere; replacing a mermaid diagram with ASCII because it was "easier." Hold these on every
edit:

- **Place new content; don't append it.** A templated doc keeps its template's section order
  (see `assets/templates/`); a bespoke doc runs overview → detail → edge cases. New content
  goes where it belongs, not at the bottom.
- **Re-check the three-layer test for *each* new paragraph.** An addition that introduces a
  permission name, an endpoint path, or a screen description in a canon doc is leakage — push
  it down before saving.
- **Re-read the doc top to bottom after the edit.** Does it still read like it was written
  once — same voice, no zig-zag between sections, no fresh duplication with a sibling doc? Fix
  it now if not. Every uncorrected edit makes the next one harder.
- **Hold the frontmatter shape stable** — same keys, same order, same casing. Bump `updated`
  on substantive changes; leave it for typo fixes.
- **Headings are URL fragments.** A link to `#rules` shouldn't rot. Rename a heading
  deliberately, not casually.
- **Match the corpus's voice.** Short, declarative, no emojis. If the rest of the doc uses
  tables for comparisons, you use tables — not a fresh prose version of the same idea.

A doc that's been edited a dozen times should still read like it was written once.

## What kinds of docs there are

A handful of shapes. Pick the one that fits; don't invent more.

- **`docs/index.md`** — the Getting Started landing. Edit it when the canon list changes.
- **`docs/<canon>.md`** — canon. The lean, normative docs. Decisions live here, with their
  rationale woven inline. Template: `canon.md` for a *new* cross-cutting concern that genuinely
  earns one (high bar — most "concerns" are feature domains and belong in `ref/features/`).
  Existing canon docs (`architecture`, `domain-model`, `scope`, `personas`, `access-patterns`)
  are bespoke shapes.
- **`docs/ref/features/<domain>.md`** — a working spec for a **cohesive feature domain**
  (orders covers placement + fulfilment + modification + refunds + UX on one page; not one
  file per CRUD). Problem · domain rules · stories · UX · edge cases. **No endpoint table**
  — operations are named in domain language; HTTP shape is OpenAPI's job (rendered at
  `/api-docs`; curated reference under `ref/api/` when it earns one). Trivial CRUDs (worker
  registry, password change) become **sections inside the right home**, not solo files.
  Template: `feature.md`.
- **`docs/ref/entities/<context>.md`** — one page per bounded context. Each entity gets an
  H2 inside the page. Template: `entity.md` (re-applied per entity).
- **`docs/ref/api/` · `ref/jobs/` · `ref/runbooks/` · `ref/integrations/`** — long,
  look-it-up reference. Add the subfolder when it earns one.
- **`docs/assets/`** — images and diagrams. Reference by relative path.
- **`docs/misc/`** — the drawer. No rules, no frontmatter, not rendered.

## The routing map — where each output goes

(Fuller version, with templates and the cross-links to make, in `references/structure.md`.)

| You have… | It goes to… |
|---|---|
| Product vision / Getting Started ladder | `docs/index.md` |
| Scope / non-goals for v1 | `docs/scope.md` |
| A user role | `docs/personas.md` |
| The ubiquitous language / the high-level entity map | `docs/domain-model.md` (per-entity detail → `ref/entities/<context>.md`) |
| Auth / authz / tenancy — the *model* every feature obeys | `docs/access-patterns.md` |
| Architecture (envelope · topology · stack · data-model invariants · quality requirements) | `docs/architecture.md` |
| A *new* system-wide concern that genuinely earns its own canon doc | `docs/<concern>.md` — from the `canon` template. **High bar.** |
| A consequential, costly-to-reverse decision | the canon or feature doc that owns the area — with the rationale (forces · alternatives · consequences · revisit trigger) woven inline. **No separate ADR / `decisions/` register.** |
| A cohesive feature domain (problem · rules · stories · UX · edge cases) | `docs/ref/features/<domain>.md` — from the `feature` template |
| A trivial CRUD | a section in the right `docs/ref/features/<domain>.md` |
| Per-feature UX (flows, screen states, key screens) | the **UX** section of `docs/ref/features/<domain>.md` |
| Cross-cutting UX / design system / component specs / route maps | **`web/DESIGN.md`** — *not* under `docs/`. |
| An entity definition (fields, states, invariants) | a section in `docs/ref/entities/<context>.md` — from the `entity` template |
| HTTP endpoint shape (paths, request / response schemas, status codes) | the OpenAPI spec (live at `/api-docs` and `/api-redoc`); curated reference under `docs/ref/api/` when it earns one. **Not** a hand-written table inside a feature doc. |
| API / job / runbook / integration detail | `docs/ref/api/` · `ref/jobs/` · `ref/runbooks/` · `ref/integrations/` |
| An image or diagram a doc embeds | `docs/assets/…`, referenced by relative path |
| Research notes, a PDF, an export, scratch | `docs/misc/` — no template, no frontmatter, not rendered |
| Raw ideation / brainstorm output | distil into the canon or feature doc that owns the area; otherwise drop it, or park in `misc/` if you can't bear to |
| A doc that's wrong and dead | delete it (git keeps history) — or move to `misc/` with a "superseded by …" banner |

If an output fits no row: it's either not doc-worthy (→ `misc/` or nothing), or you've found a
real gap in the structure — and changing the structure is a deliberate act, not a reflex
`mkdir`.

## The workflow

1. **Filing pipeline output (the main job).** Identify what the output is → find its
   destination in the routing map → search the corpus: does a doc already own this fact?
   **If yes**, update it in place and bump `updated` — don't fork, and don't restate something
   another doc owns; link instead. **If no**, copy the right template from
   `assets/templates/`, fill it, write the frontmatter (don't forget `title`; set `order:` if
   position matters), end with a tight "Next" block when one helps. For a decision: write it
   into the canon or feature doc that owns the area, with the rationale (forces · alternatives
   · consequences · revisit trigger) woven inline; when an old decision is overtaken, fix that
   doc in place. For an image: into `docs/assets/`, referenced by relative path.

2. **"Where does this go?"** Consult the tree and the routing map. Most things have an obvious
   home. If something doesn't, that's a signal, not a licence to invent a folder — say so and
   propose the smallest structural change that fits. If it's not really documentation, it's
   `misc/`. If it's a frontend design system concern, it's `web/DESIGN.md`.

3. **End-of-cycle audit (the gate).** At the end of a `shape` cycle, run the **v1 completeness
   checklist** and the **corpus audits** (both in `references/authoring.md`): everything
   required exists and is `stable`; no orphans, contradictions, duplication, leakage between
   layers, broken cross-links, dangling `assets/` references, `draft`s loitering in the canon,
   renamed-without-redirect paths, ASCII art smuggled past the diagram rule, or forbidden
   artefacts (no `docs/README.md`, no extra `index.md`s). Report the gaps. **The cycle is not
   done until this passes** — the gap list *is* the shape pipeline's remaining to-do.

## What this skill enforces — the short list

- **Right layer, right doc, no parallel home.** Canon = model + rules. Features = mechanics.
  Entities = shape. Place before you write.
- **Lean prose, lean canon.** State the call; don't relitigate it. Cut hedges, throat-clearing,
  and rationale that doesn't tell the next reader what would have to change.
- **Mermaid for diagrams, tables for comparison, prose for rationale.** No ASCII art.
- **Sparse cross-refs.** "Next" at the bottom; inline only at critical points; `related:`
  optional.
- **Stable paths and headings** — they're URLs and URL fragments now.
- **Decisions live with what they decide** — no ADR register; the *why* travels with the rule.
- **Edits leave the doc coherent** — place new content, re-read top-to-bottom, hold the
  frontmatter steady, match the corpus's voice.
- **Frontmatter has `title`, `status`, `owner`, `updated`** on every doc outside `misc/`;
  `order` and `related` are optional.
- **File the call; don't make it.** Form is this skill's. The architecture, UX, and product
  decisions are made elsewhere; this skill files them and flags conflicts.

## What this skill produces

A small, well-formed `docs/` tree the backend can render as-is: a Getting Started landing at
`docs/index.md`, a lean canon flat at the top of `docs/`, a handful of domain-grouped feature
pages under `ref/features/` (each owning rules + UX for its domain), one page per bounded
context under `ref/entities/`, images in `docs/assets/`, nothing named `README.md` or extra
`index.md`s anywhere under `docs/`; and, at end-of-cycle, an audit report — the gap list plus a
verdict on v1 doc-completeness. The templates themselves live in this skill's
`assets/templates/`.

## References & assets

- `references/structure.md` — the authoritative per-folder spec: what belongs where, naming
  conventions, depth limits, the full routing map with templates and cross-links, the
  served-docs constraints, and how (rarely, deliberately) to evolve the tree.
- `references/authoring.md` — the frontmatter schema and `status` lifecycle; per-doc-type
  writing rules; the cross-link discipline; the corpus audits; the v1
  documentation-completeness checklist.
- `assets/templates/` — `feature.md`, `entity.md`, `canon.md`. Copy the right one when creating
  a new doc of that type. (No ADR template — decisions are recorded inside the canon or feature
  doc that owns the area.)
