---
name: docs-management
description: >-
  Owns the project's documentation corpus — its structure, form, routing, linking, and upkeep,
  and the fact that it's served live by the backend (markdown rendered on the fly). Use this skill
  whenever you create, edit, organize, move, or review anything under `docs/`; whenever you file
  architecture decisions, UX specs, feature ideas, entity definitions, or research / ideation
  notes into the docs; whenever you write or update a feature spec, an entity page, or a
  system-wide concern doc, or need to record a consequential decision and its rationale;
  whenever someone asks where a doc belongs or proposes a new doc or a new docs folder; whenever
  a path might be about to change (it's a URL now); whenever docs might have gone stale,
  contradictory, duplicated, or orphaned; and at the end of a `shape` cycle to judge whether the
  v1 documentation is actually complete. It keeps the doc tree small and predictable for humans,
  agents, and the live renderer alike; keeps the canon lean; reads like a real product docs site
  (one Getting Started landing, then progressive complexity); enforces one-fact-one-home, stable
  paths, append-only decision history, and **minimal cross-document references** (a single "Next"
  block per doc, not a thicket of inline links); and defines when documentation is "done."
---

# Documentation Management

> Documentation fails in two ways: it sprawls until no one reads it, or it drifts until no one
> trusts it. This skill prevents both — by giving every fact exactly one home, keeping the
> must-read core small, and keeping the corpus legible to a person reading it, an agent pulling
> one file into context, and the backend rendering it as a live site.

This skill owns the **form** of the documentation, not the **decisions** in it. Architecture
work makes and structures the architecture calls; UX work makes and structures the UX calls;
ideation and brainstorm produce raw product thinking. This skill decides **where each output
lives, what shape it takes, how the pieces link, and whether the set is complete and
consistent** — and it pushes back when a doc is in the wrong layer, duplicates another,
contradicts one, or is about to break its URL.

## The one habit this skill installs

**Before you write or move a doc, place it.** Name its destination path (which is now a URL),
its type (which template), and its frontmatter — then search the corpus for whether something
already owns that fact. If it does: update or link, never fork. If nothing does and nothing
_should_: the content may not be doc-worthy (it might be `misc/`), or the tree genuinely needs a
new home — and adding a home is a deliberate act (`references/structure.md` → "Evolving the
tree"), not a reflex `mkdir`.

## The doc tree

```
README.md                # the ONLY README in the repo, at the root: "what this is + see docs/"
docs/
├── index.md             # THE HOME: a Getting Started landing — vision in a paragraph + "Read in this order" → the canon, then features and entities. The only `index.md` allowed under docs/.
│
│ # THE CANON — flat at the top of docs/. The high-level decisions & specs everyone works from. Lean.
├── scope.md          # in / out / explicit non-goals for v1
├── personas.md          # the roles and what each needs
├── journeys.md          # the end-to-end flows that span features
├── domain-model.md      # the ubiquitous language + the high-level entity map (per-entity detail → ref/entities/)
├── architecture.md      # system topology, the stack, how the pieces fit, cross-cutting concerns
├── envelope.md          # the operating envelope: tier, the "not built for" line, per-module exceptions
├── nfr.md               # non-functional requirements — auth posture, audit, backups (RPO/RTO), perf budgets, availability, retention
├── access.md            # auth / authz / tenancy — a system-wide concern that earns a canon doc
├── open-questions.md    # what's unsettled + the trigger that should make us revisit each
│                        #   (decisions live in the canon doc that owns the area — see "Non-negotiables" — there is no ADR / decisions/ register)
│
├── ref/                 # EVERYTHING ELSE that's still documentation — detailed, look-it-up.
│   ├── features/            # ONE WORKING SPEC PER COHESIVE DOMAIN — orders.md, cutting.md, catalog-inventory.md, workshop.md, notifications.md, platform.md. Each page owns rules, endpoints, UX, edge cases for its domain. Trivial CRUDs are sections inside the right home, not their own files.
│   ├── entities/            # ONE PAGE PER BOUNDED CONTEXT (sales.md, catalog.md, …) — each lists its entities with fields/states/invariants. **Not** one file per entity.
│   ├── api/                 # endpoint reference (build-pipeline output) — when it earns its own corner
│   ├── jobs/                # background jobs / cronjobs — when it earns its own corner
│   ├── runbooks/            # operational procedures — when it earns its own corner
│   └── integrations/        # third-party / external systems — when it earns its own corner
├── assets/              # images & diagrams that docs embed — the ONLY place binary files live; the backend serves these as static files
└── misc/                # research, PDFs, exports, scratch, temporary — NOT the documentation; not part of the rendered site; no rules, no frontmatter
```

Outside `docs/` but worth knowing about:

- **`web/DESIGN.md`** — the deterministic design system for the frontend (tokens, primitives,
  composed components, the shell, route maps for the three SPAs, accessibility baseline).
  Lives next to the code it constrains, not under `docs/`. Pre-existing `docs/ref/ux/` is **gone** —
  do not recreate it.

**The canon rule.** The flat top-level of `docs/` is what every contributor must read. Every
page you put there is a tax on everyone. The test for the canon: _is this a high-level decision
or spec everyone works from?_ If not — it's a feature domain (→ `ref/features/`), an entity
context (→ `ref/entities/`), exhaustive reference (→ `ref/api|jobs|runbooks|integrations/`), or
not really documentation (→ `misc/`). If the canon ever stops being readable in one sitting,
something escaped into the wrong layer; pull it down to `ref/`.

## The docs are served live — what that means for how you write them

The backend renders `docs/` as a browsable site — markdown → HTML, on the fly, behind the app's
auth — building the nav from the tree and frontmatter. So:

- **The home page is `docs/index.md`.** It's a real **Getting Started** landing: one paragraph
  of vision, then a numbered "Read in this order" ladder (canon → features → entities →
  open-questions). Complexity rises down the list. **`docs/index.md` is the only `index.md`
  allowed anywhere under `docs/`** — don't add a section-level `index.md`; the backend renders
  section overviews automatically from the tree.
- **A path is a URL.** `docs/ref/features/orders.md` → `/docs/ref/features/orders`;
  `docs/architecture.md` → `/docs/architecture`. Renaming or moving a file breaks that URL —
  bookmarks, links from issues and chat, links from other docs. Filenames are kebab-case,
  descriptive, and **stable**. If you genuinely must rename, leave a redirect (a stub at the old
  path pointing to the new one, or a backend redirect rule). Treat a doc's path like a public
  API.
- **`title` and `order` drive the nav.** Every doc has a `title` (the page heading and nav
  label). Set `order:` (an integer, lower first) when the doc's position within its section
  matters; otherwise sections are title-ordered. Don't encode order in filename prefixes
  (`01-…`) — that puts the order _in the URL_, so reordering breaks links.
- **`status: draft` is visible.** The site badges non-`stable` docs — fine to serve internally,
  just don't leave a half-written doc marked `stable`.
- **Images go in `docs/assets/`**, referenced by relative path; the backend serves that folder
  as static files. Nothing binary lives in the canon or `ref/`.
- **`misc/` is not rendered.** Don't link to a `misc/` file as a source of truth; if a `misc/`
  file matters, distil it into the canon or `ref/`.
- **No `README.md` anywhere under `docs/`.** The repo's single `README.md` is at the root and
  just orients ("what this is — see `docs/`"); the backend renders the docs landing from
  `docs/index.md` and the section overviews from the tree.

## Cross-document references — minimize them

The corpus is **deliberately under-linked**. Two reasons: a doc that's wall-to-wall blue is
unreadable; and every inline link is a maintenance cost when paths move.

**The rules:**

- **Every doc ends with a "Next" line** — at most 2–4 links to the docs a reader should pick up
  next. That's the *primary* way to guide reading. (For very short docs that don't need one,
  omit it.)
- **Inline cross-document links only at critical points** — when omitting the link would force
  the reader to re-learn context, or when the linked doc is the *single* authoritative home for
  something the current doc is asserting. Examples that earn an inline link: a feature doc
  pointing at the canon doc that holds the cross-cutting rule it relies on (`access.md`,
  `architecture.md`); an entity context page pointing at the feature page that owns its rules;
  a route map pointing at the design system. Examples that don't: ambient "see also" links the
  reader already knows about, links to a closely related entity page mid-paragraph, links to
  the same target two or three times.
- **`related:` frontmatter is optional.** Use it only when two docs are tightly coupled and the
  rendered "related" widget genuinely helps navigation. Most docs don't need it. (It was
  required in earlier versions of this skill — it isn't now.)
- **Never "see above" or "the order doc."** When you *do* link, link **by path** —
  `docs/ref/features/orders.md` — so the renderer resolves it and the link survives a
  single-page read.

If you find yourself wanting to add the same cross-link three times in a doc, the doc is
probably restating something that lives elsewhere; collapse the prose and link once.

## What kinds of docs there are

The corpus has just a handful of doc shapes. Pick the one that fits; don't invent more.

- **`docs/index.md`** — the Getting Started landing. Edit it when the canon list changes; keep
  it short.
- **`docs/<canon>.md`** — canon. The lean, normative docs everyone reads, flat at the top of
  `docs/`. Decisions live here, with their rationale woven inline. Template: `canon.md` for a
  system-wide concern that earns its own doc (e.g. `access.md`). `architecture.md`,
  `envelope.md`, `nfr.md`, `domain-model.md`, `scope.md`, `personas.md`, `journeys.md`,
  `open-questions.md` are bespoke (no template — they're one-off shapes).
- **`docs/ref/features/<domain>.md`** — a working spec for a **cohesive feature domain** (e.g.
  `orders.md` covers placement + fulfilment + modification + cancellation/refunds + the
  warehouse contract + the per-screen UX, all in one page; not one file per CRUD). Problem ·
  domain rules · stories · endpoints · UX · edge cases. Trivial CRUDs (a single endpoint with a
  form behind it — worker registry, password change, etc.) become **sections inside the right
  home doc**, not solo files. Template: `feature.md`.
- **`docs/ref/entities/<context>.md`** — one page per bounded context (sales, catalog,
  inventory, cutting, identity, workshop, support). Each lists its entities with fields,
  states, invariants. Template: `entity.md` (re-applied per entity inside the page).
- **`docs/ref/api/` · `ref/jobs/` · `ref/runbooks/` · `ref/integrations/`** — long, look-it-up
  reference, mostly produced by the build pipeline. Add the subfolder when it earns one.
- **`docs/assets/`** — images & diagrams. Reference by relative path.
- **`docs/misc/`** — the drawer. No rules, no frontmatter, not rendered.

## The routing map — where each output goes

When you have an output to file, this is the lookup. (Fuller version, with the templates and
the cross-links to make, in `references/structure.md`.)

| You have… | It goes to… |
|---|---|
| Product vision / the core bet & the Getting Started ladder | `docs/index.md` |
| Scope / non-goals for v1 | `docs/scope.md` |
| A user role | `docs/personas.md` |
| An end-to-end workflow that spans features | `docs/journeys.md` |
| The ubiquitous language / the high-level entity map | `docs/domain-model.md` (per-entity detail → `ref/entities/<context>.md`) |
| The architecture overview (topology, stack, cross-cutting concerns) | `docs/architecture.md` |
| The operating envelope (tier, the "not built for" line) | `docs/envelope.md` |
| A non-functional requirement | `docs/nfr.md` |
| Auth / authz / tenancy rules that every feature obeys | `docs/access.md` |
| A *new* system-wide concern that genuinely earns its own canon doc | `docs/<concern>.md` — from the `canon` template. **High bar** — most "concerns" are really feature domains and belong in `ref/features/`. |
| A consequential, costly-to-reverse decision | the canon doc that owns the area — `architecture.md` (topology / stack / data model), `domain-model.md` (the domain shape), `scope.md` (an in/out-of-scope call), `access.md` / another canon concern doc — or, when the decision is bounded to one feature domain, the `ref/features/<domain>.md` for that domain. Record the *why* (forces · alternatives weighed · consequences accepted · the concrete revisit trigger) woven into that doc. **No separate ADR / `decisions/` register.** |
| An open question / revisit trigger | `docs/open-questions.md` |
| A cohesive feature domain (problem, rules, stories, endpoints, UX, edge cases) | `docs/ref/features/<domain>.md` — from the `feature` template |
| A trivial CRUD that doesn't earn its own file | a section in the right `docs/ref/features/<domain>.md` |
| Per-feature UX (flows, screen states, key screens) | the **UX** section of `docs/ref/features/<domain>.md` |
| Cross-cutting UX / design system / component specs / route maps | **`web/DESIGN.md`** — *not* under `docs/`. Lives in the web repo next to the code it constrains. |
| An entity definition (fields, states, invariants) | a section in `docs/ref/entities/<context>.md` — from the `entity` template |
| API / job / runbook / integration detail | `docs/ref/api/` · `ref/jobs/` · `ref/runbooks/` · `ref/integrations/` |
| An image or diagram a doc embeds | `docs/assets/…`, referenced by relative path from the doc |
| Research notes, a PDF, an export, a one-off script, anything not-yet-shaped | `docs/misc/` — no template, no frontmatter, not part of the rendered site |
| Raw ideation / brainstorm output | distil it into the relevant `docs/<canon>.md` or `docs/ref/features/*`; a genuinely-promising-but-not-now idea → a line in `docs/open-questions.md`; otherwise drop it, or park it in `misc/` if you can't bear to |
| A doc that's now wrong and dead | delete it — git keeps the history — or, if it's worth keeping visible, move it to `misc/` with a one-line "superseded by … / dropped because …" at the top |

If an output fits no row, stop: either it isn't doc-worthy (→ `misc/` or nothing), or you've
found a real gap in the structure — and changing the structure is a decision, not a reflex.

## The workflow

**1 — Filing pipeline output (the main job).** Identify what the output is → find its
destination in the routing map → search the corpus: does a doc already own this fact? **If
yes**, update it in place and bump `updated` — do not create a parallel doc, and don't introduce
a _fresh_ duplicate either: if the edit restates a concept another doc owns, link to that owner
instead of repeating it. Keep the doc readable as you go — a new section gets _placed_ in the
right spot, not appended at the bottom; a templated doc keeps its template's section order, a
bespoke doc runs overview → detail and common path → edge cases. **If no**, copy the right
template from this skill's `assets/templates/`, fill it, write the frontmatter (don't forget
`title`; set `order:` if position matters) → end with a tight "Next" block when one helps.
For a decision: write it into the canon or feature doc that owns the area, with its rationale —
forces, alternatives weighed, consequences accepted, the revisit trigger — woven inline; when an
old decision is overtaken, fix that doc in place and bump `updated`. For an image: into
`docs/assets/`, referenced by relative path.

**2 — "Where does this go?"** Consult the tree and the routing map. Most things have an obvious
home. If something doesn't, that's a signal, not a licence to invent a folder — say so, and
propose the smallest structural change that fits. If it's not really documentation, it's
`misc/`. If it's a frontend design system concern, it's `web/DESIGN.md`, not `docs/`.

**3 — End-of-cycle audit (the gate).** At the end of a `shape` cycle, run the **v1 completeness
checklist** and the **corpus audits** (both in `references/authoring.md`): everything required
exists and is `stable`; no orphans, contradictions, or duplication; no `draft`s loitering in
the canon; no broken cross-links or dangling `assets/` references; no doc whose path looks like
it's been renamed without a redirect; the canon still readable in a sitting. Report the gaps.
**The cycle is not done until this passes** — the gap list _is_ the shape pipeline's remaining
to-do.

## Non-negotiables (and why)

- **One fact, one home.** Two copies drift, and then no one knows which is right. Link, don't
  duplicate. If two docs disagree, that's a contradiction to resolve: pick the owner, fix the
  other to point at it.
- **The canon stays lean.** The flat top-level of `docs/` is mandatory reading; bloat there is a
  cost everyone pays forever. Detail belongs in `ref/`; not-really-documentation belongs in
  `misc/`; frontend design belongs in `web/DESIGN.md`.
- **Paths are stable.** A path is a URL the moment the docs are served. Don't rename or move
  without a redirect. A new doc gets a new path; a reorganization is a deliberate, recorded
  move, not a drive-by.
- **Decisions live with what they decide.** A consequential, costly-to-reverse decision is
  recorded *inside the doc that owns the area* — `architecture.md` for topology / stack /
  data-model calls, `domain-model.md` for the domain shape, `scope.md` for in/out-of-scope
  calls, `access.md` (or another canon concern doc) for that concern's calls, a
  `ref/features/<domain>.md` for a decision bounded to that domain — with the *why* (the forces
  in play, the alternatives weighed, the consequences accepted, the concrete revisit trigger)
  woven into its prose. There is **no separate ADR genre and no `decisions/` folder.** A doc
  that states a normative call also states why it's that call. When a decision is overtaken,
  fix the doc in place and bump `updated` — git keeps the history; a served site shouldn't
  carry a known-wrong call.
- **Cross-references are sparse on purpose.** A doc ends with a "Next" line (2–4 links);
  inline cross-doc links only at critical points; `related:` frontmatter is optional. The
  corpus should read like docs, not a glossary index. (See *Cross-document references* above.)
- **Every doc has minimal frontmatter.** `title` (always), `status`, `owner`, `updated`, +
  optional `order` and optional `related:`. It's how a person, an agent, and the renderer all
  see what something is, whether it's trustworthy, how fresh it is, and where it sits.
  (`misc/` is exempt — it isn't documentation.)
- **Write for all three readers.** Stable, predictable headings (a link to `#requirements`
  shouldn't rot — it's a URL fragment now). Tables for structured facts, prose for rationale.
  Each doc self-contained enough to make sense pulled into a context window — or loaded as a
  single page — alone.
- **An edit leaves the doc coherent, not just longer.** _Place_ new content — don't bolt it onto
  the bottom; sections stay in a logical reading order (a templated doc keeps its template's
  order; otherwise overview → detail, common path → edge cases) so the doc reads top to bottom
  without backtracking. And re-check "one fact, one home" _on every edit_, not just at
  creation — an addition that restates a concept another doc owns is a duplication bug even
  when the doc it lands in is the right home for everything else. A doc edited five times
  should still read like it was written once.
- **File the call; don't make it.** The product, architecture, and UX _decisions_ — the
  substance — are made elsewhere; this skill files them and keeps the corpus consistent. Where
  form and substance meet (a feature spec's UX section, an entity's invariants), the surrounding
  doc is this skill's; the content inside it is not. If a decision is missing or two are in
  conflict, flag it — don't paper over it with one you invented.

## What this skill produces

A small, well-formed `docs/` tree the backend can render as-is: a Getting Started landing at
`docs/index.md`, a lean canon flat at the top of `docs/`, a handful of domain-grouped feature
pages under `ref/features/` (each owning rules + UX for its domain), one page per bounded
context under `ref/entities/`, images in `docs/assets/`, nothing named `README.md` or extra
`index.md`s anywhere under `docs/`; and, at end-of-cycle, an audit report — the gap list plus a
verdict on v1 doc-completeness. The templates themselves live in this skill's
`assets/templates/` (you copy from there; there are no `_template.md` files cluttering `docs/`).

## References & assets

- `references/structure.md` — the authoritative per-folder spec: what belongs in `index.md`,
  the canon (flat at the top of `docs/`), `ref/` (and each `ref/` subfolder), `assets/`, and
  `misc/`, and what doesn't (and where it goes instead); naming conventions; depth limits; the
  full routing map with templates and cross-links; the served-docs constraints in detail; and
  how (rarely, deliberately) to evolve the tree.
- `references/authoring.md` — the frontmatter schema and `status` lifecycle; per-doc-type
  writing rules; the cross-link discipline; the corpus audits; and the v1
  documentation-completeness checklist.
- `assets/templates/` — `feature.md`, `entity.md`, `canon.md`. Copy the right one when creating
  a new doc of that type. (There is no ADR template — decisions are recorded inside the canon
  or feature doc that owns the area.)
