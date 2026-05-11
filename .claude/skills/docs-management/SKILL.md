---
name: docs-management
description: >-
  Owns the project's documentation corpus — its structure, form, routing, linking, and upkeep,
  and the fact that it's served live by the backend (markdown rendered on the fly). Use this skill
  whenever you create, edit, organize, move, or review anything under `docs/`; whenever you file
  architecture decisions, UX specs, feature ideas, entity definitions, or research / ideation notes
  into the docs; whenever you write or update a feature spec, an entity page, or a system-concern
  spec, or need to record a consequential decision and its rationale; whenever someone asks where a
  doc belongs or proposes a new doc or a new docs
  folder; whenever a path might be about to change (it's a URL now); whenever docs might have gone
  stale, contradictory, duplicated, or orphaned; and at the end of a `shape` cycle to judge whether
  the v1 documentation is actually complete. It keeps the doc tree small and predictable for
  humans, agents, and the live renderer alike; keeps the `spec/` canon lean; enforces
  one-fact-one-home, stable paths, and append-only decision history; and defines when documentation
  is "done."
---

# Documentation Management

> Documentation fails in two ways: it sprawls until no one reads it, or it drifts until no one
> trusts it. This skill prevents both — by giving every fact exactly one home, keeping the
> must-read core small, and keeping the corpus legible to a person reading it, an agent pulling one
> file into context, and the backend rendering it as a live site.

This skill owns the **form** of the documentation, not the **decisions** in it. Architecture work
makes and structures the architecture calls; UX work makes and structures the UX calls; ideation
and brainstorm produce raw product thinking. This skill decides **where each output lives, what
shape it takes, how the pieces link, and whether the set is complete and consistent** — and it
pushes back when a doc is in the wrong layer, duplicates another, contradicts one, or is about to
break its URL.

## The one habit this skill installs

**Before you write or move a doc, place it.** Name its destination path (which is now a URL), its
type (which template), and its frontmatter — then search the corpus for whether something already
owns that fact. If it does: update or link, never fork. If nothing does and nothing _should_: the
content may not be doc-worthy (it might be `misc/`), or the tree genuinely needs a new home — and
adding a home is a deliberate act (`references/structure.md` → "Evolving the tree"), not a reflex
`mkdir`.

## The doc tree

Three folders that matter, plus an assets bucket. `references/structure.md` is the authoritative
per-folder spec.

```
README.md                # the ONLY README in the repo, at the root: "what this is + see docs/"
docs/
├── spec/                # THE CANON: the high-level decisions & specs everyone works from. Lean. The "start here" of the live site.
│   ├── vision.md            # why this exists, who it's for, the bet, what success looks like
│   ├── scope-v1.md          # in / out / explicit non-goals for v1
│   ├── personas.md          # the roles and what each needs
│   ├── journeys.md          # the end-to-end flows that span features
│   ├── domain-model.md      # the ubiquitous language + the high-level entity map (per-entity detail → ref/entities/)
│   ├── architecture.md      # system topology, the stack, how the pieces fit, cross-cutting concerns
│   ├── envelope.md          # the operating envelope: tier, the "not built for" line, per-module exceptions
│   ├── nfr.md               # non-functional requirements — auth posture, audit, backups (RPO/RTO), perf budgets, availability, retention
│   ├── open-questions.md    # what's unsettled + the trigger that should make us revisit each
│   └── <concern>.md         # one lean file per system-wide concern or flow: auth.md, order-flow.md, pricing.md, tenancy.md, …
                             #   (decisions live in the doc that owns the area — see "Non-negotiables" — there is no ADR / decisions/ register)
├── ref/                 # EVERYTHING ELSE that's still documentation — detailed, look-it-up. The "reference" of the live site.
│   ├── features/            # per-feature working specs — the unit the build pipeline decomposes (problem · stories · requirements · UX · entities touched · edge cases · open Qs)
│   ├── entities/            # the entity catalog, grouped by domain (bounded context): sales/ catalog/ inventory/ purchasing/ customers/ …
│   ├── ux/                  # cross-cutting UX detail: information-architecture.md, components.md
│   ├── api/                 # endpoint reference (build-pipeline output)
│   ├── jobs/                # background jobs / cronjobs
│   ├── runbooks/            # operational procedures
│   └── integrations/        # third-party / external systems
├── assets/              # images & diagrams that docs embed — the ONLY place binary files live; the backend serves these as static files
└── misc/                # research, PDFs, exports, scratch, temporary — NOT the documentation; not part of the rendered site; no rules, no frontmatter
```

**The canon rule.** `spec/` is what every contributor must read. Every page you put there is a tax
on everyone. The test for `spec/`: _is this a high-level decision or spec everyone works from?_ If
not — it's `ref/` (detailed / per-feature) or `misc/` (not really documentation). If `spec/` ever
stops being readable in one sitting, something escaped into the wrong layer; pull it down to
`ref/`.

## The docs are served live — what that means for how you write them

The backend renders `docs/` as a browsable site — markdown → HTML, on the fly, behind the app's
auth — building the nav from the tree and frontmatter. So:

- **A path is a URL.** `docs/spec/auth.md` → `/docs/spec/auth`. Renaming or moving a file breaks
  that URL — bookmarks, links from issues and chat, links from other docs. Filenames are
  kebab-case, descriptive, and **stable**. If you genuinely must rename, leave a redirect (a stub
  at the old path pointing to the new one, or a backend redirect rule). Treat a doc's path like a
  public API.
- **Cross-link by path** — `docs/ref/entities/sales/order.md` — never "see above." The renderer
  resolves a path to a working link; "see above" resolves to nothing when the page is read alone.
- **`title` and `order` drive the nav.** Every doc has a `title` (the page heading and nav label).
  Set `order:` (an integer, lower first) when the doc's position within its section matters;
  otherwise sections are title-ordered. Don't encode order in filename prefixes (`01-…`) — that
  puts the order _in the URL_, so reordering breaks links.
- **`status: draft` is visible.** The site badges non-`stable` docs — fine to serve internally,
  just don't leave a half-written doc marked `stable`.
- **Images go in `docs/assets/`**, referenced by relative path; the backend serves that folder as
  static files. Nothing binary lives in `spec/` or `ref/`.
- **`misc/` is not rendered.** Don't link to a `misc/` file as a source of truth; if a `misc/`
  file matters, distil it into `spec/` or `ref/`.
- **No `README.md` or `index.md` anywhere under `docs/`.** The backend renders the landing page
  (the map of `spec/` and `ref/`) and the section overviews from the tree and frontmatter. The
  repo's single `README.md` is at the root and just orients ("what this is — see `docs/`").

## The routing map — where each output goes

When you have an output to file, this is the lookup. (Fuller version, with the templates and the
cross-links to make, in `references/structure.md`.)

| You have…                                                                   | It goes to…                                                                                                                                                                                                                                 |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Product vision / the core bet                                               | `spec/vision.md`                                                                                                                                                                                                                            |
| Scope / non-goals for v1                                                    | `spec/scope-v1.md`                                                                                                                                                                                                                          |
| A user role                                                                 | `spec/personas.md`                                                                                                                                                                                                                          |
| An end-to-end workflow that spans features                                  | `spec/journeys.md`                                                                                                                                                                                                                          |
| The ubiquitous language / the high-level entity map                         | `spec/domain-model.md` (per-entity detail → `ref/entities/`)                                                                                                                                                                                |
| The architecture overview (topology, stack, cross-cutting concerns)         | `spec/architecture.md` (+ a `spec/<concern>.md` per concern that earns its own doc)                                                                                                                                                         |
| The operating envelope (tier, the "not built for" line)                     | `spec/envelope.md`                                                                                                                                                                                                                          |
| A non-functional requirement                                                | `spec/nfr.md`                                                                                                                                                                                                                               |
| A system-wide concern or flow (auth, pricing, order-flow, tenancy, …)       | `spec/<concern>.md` — from the `spec` template                                                                                                                                                                                              |
| A consequential, costly-to-reverse decision                                 | the `spec/` doc that owns the area — `architecture.md` (topology / stack / data model), a `spec/<concern>.md` (a system concern), `domain-model.md` (the domain shape), `scope-v1.md` (an in/out-of-scope call) — recording the *why* (forces · alternatives weighed · consequences accepted · the concrete revisit trigger) woven into that doc. **No separate ADR / `decisions/` register.** |
| An open question / revisit trigger                                          | `spec/open-questions.md`                                                                                                                                                                                                                    |
| A feature (problem, stories, requirements, …)                               | `ref/features/<feature>.md` — from the `feature` template                                                                                                                                                                                   |
| Per-feature UX (flows, screen states, key screens)                          | the **UX** section of `ref/features/<feature>.md`                                                                                                                                                                                           |
| Cross-cutting UX — information architecture, component specs                | `ref/ux/information-architecture.md`, `ref/ux/components.md`                                                                                                                                                                                |
| An entity definition (fields, states, invariants)                           | `ref/entities/<domain>/<entity>.md` — from the `entity` template                                                                                                                                                                            |
| API / job / runbook / integration detail                                    | `ref/api/` · `ref/jobs/` · `ref/runbooks/` · `ref/integrations/`                                                                                                                                                                            |
| An image or diagram a doc embeds                                            | `docs/assets/…`, referenced by relative path from the doc                                                                                                                                                                                   |
| Research notes, a PDF, an export, a one-off script, anything not-yet-shaped | `misc/` — no template, no frontmatter, not part of the rendered site                                                                                                                                                                        |
| Raw ideation / brainstorm output                                            | distil it into the relevant `spec/*` or `ref/features/*`; a genuinely-promising-but-not-now idea → a line in `spec/open-questions.md` (or `spec/roadmap.md` if you keep one); otherwise drop it, or park it in `misc/` if you can't bear to |
| A doc that's now wrong and dead                                             | delete it — git keeps the history — or, if it's worth keeping visible, move it to `misc/` with a one-line "superseded by … / dropped because …" at the top                                                                                  |

If an output fits no row, stop: either it isn't doc-worthy (→ `misc/` or nothing), or you've found
a real gap in the structure — and changing the structure is a decision, not a reflex.

## The workflow

**1 — Filing pipeline output (the main job).** Identify what the output is → find its destination
in the routing map → search the corpus: does a doc already own this fact? **If yes**, update it in
place and bump `updated` — do not create a parallel doc, and don't introduce a _fresh_ duplicate
either: if the edit restates a concept another doc owns, link to that owner instead of repeating
it. Keep the doc readable as you go — a new section gets _placed_ in the right spot, not appended
at the bottom; a templated doc keeps its template's section order, a bespoke doc runs
overview → detail and common path → edge cases. **If no**, copy the right template from this
skill's `assets/templates/`, fill it, write the frontmatter (don't forget `title`; set `order:` if
position matters) → add `related:` links both ways → cross-link from the docs that bear on it. For
a decision: write it into the `spec/` doc that owns the area (see the routing map), with its
rationale — forces, alternatives weighed, consequences accepted, the revisit trigger — woven inline;
when an old decision is overtaken, fix that doc in place and bump `updated`. For an image: into
`docs/assets/`, referenced by relative path.

**2 — "Where does this go?"** Consult the tree and the routing map. Most things have an obvious
home. If something doesn't, that's a signal, not a licence to invent a folder — say so, and
propose the smallest structural change that fits. If it's not really documentation, it's `misc/`.

**3 — End-of-cycle audit (the gate).** At the end of a `shape` cycle, run the **v1 completeness
checklist** and the **corpus audits** (both in `references/authoring.md`): everything required
exists and is `stable`; no orphans, contradictions, or duplication; no `draft`s loitering in
`spec/`; no broken cross-links or dangling `assets/` references; no doc whose path looks like it's
been renamed without a redirect; `spec/` still readable in a sitting. Report the gaps. **The cycle
is not done until this passes** — the gap list _is_ the shape pipeline's remaining to-do.

## Non-negotiables (and why)

- **One fact, one home.** Two copies drift, and then no one knows which is right. Link, don't
  duplicate. If two docs disagree, that's a contradiction to resolve: pick the owner, fix the
  other to point at it.
- **The canon stays lean.** `spec/` is mandatory reading; bloat there is a cost everyone pays
  forever. Detail belongs in `ref/`; not-really-documentation belongs in `misc/`.
- **Paths are stable.** A path is a URL the moment the docs are served. Don't rename or move
  without a redirect. A new doc gets a new path; a reorganization is a deliberate, recorded move,
  not a drive-by.
- **Decisions live with what they decide.** A consequential, costly-to-reverse decision is recorded
  *inside the `spec/` doc that owns the area* — `architecture.md` for topology / stack / data-model
  calls, a `spec/<concern>.md` for that concern's calls, `domain-model.md` for the domain shape,
  `scope-v1.md` for the in/out-of-scope calls — with the *why* (the forces in play, the alternatives
  weighed, the consequences accepted, the concrete revisit trigger) woven into its prose. There is
  **no separate ADR genre and no `decisions/` folder.** A doc that states a normative call also
  states why it's that call. When a decision is overtaken, fix the doc in place and bump `updated` —
  git keeps the history; a served site shouldn't carry a known-wrong call.
- **Every doc has frontmatter.** `title / status / owner / updated / related` (+ optional
  `order`). It's how a person, an agent, and the renderer all see what something is, whether it's
  trustworthy, how fresh it is, and where it sits. (`misc/` is exempt — it isn't documentation.)
- **Write for all three readers.** Stable, predictable headings (a link to `#requirements`
  shouldn't rot — it's a URL fragment now). Cross-link by path, never "see above." Tables for
  structured facts, prose for rationale. Each doc self-contained enough to make sense pulled into a
  context window — or loaded as a single page — alone.
- **An edit leaves the doc coherent, not just longer.** _Place_ new content — don't bolt it onto
  the bottom; sections stay in a logical reading order (a templated doc keeps its template's order;
  otherwise overview → detail, common path → edge cases) so the doc reads top to bottom without
  backtracking. And re-check "one fact, one home" _on every edit_, not just at creation — an
  addition that restates a concept another doc owns is a duplication bug even when the doc it lands
  in is the right home for everything else. A doc edited five times should still read like it was
  written once.
- **File the call; don't make it.** The product, architecture, and UX _decisions_ — the substance
  — are made elsewhere; this skill files them and keeps the corpus consistent. Where form and
  substance meet (a feature spec's UX section, an entity's invariants), the surrounding doc is
  this skill's; the content inside it is not. If a decision is missing or two are in conflict, flag
  it — don't paper over it with one you invented.

## What this skill produces

A small, well-formed `docs/` tree the backend can render as-is: every output filed at its canonical
path, in its template's shape, with complete frontmatter and two-way `related:` links; images in
`docs/assets/`; nothing named `README.md` or `index.md` under `docs/`; and, at end-of-cycle, an
audit report — the gap list plus a verdict on v1 doc-completeness. The templates themselves live in
this skill's `assets/templates/` (you copy from there; there are no `_template.md` files cluttering
`docs/`).

## References & assets

- `references/structure.md` — the authoritative per-folder spec: what belongs in `spec/`, `ref/`
  (and each `ref/` subfolder), `assets/`, and `misc/`, and what doesn't (and where it goes
  instead); naming conventions; depth limits; the full routing map with templates and cross-links;
  the served-docs constraints in detail; and how (rarely, deliberately) to evolve the tree.
- `references/authoring.md` — the frontmatter schema and `status` lifecycle; per-doc-type writing
  rules (`spec/` vs `ref/features/` vs `ref/entities/` vs the rest), and how a `spec/` doc carries
  the rationale for the decisions it states; writing for humans, agents, and the renderer at once;
  superseding and retiring (delete, or `misc/`); the corpus audits; and the v1
  documentation-completeness checklist.
- `assets/templates/` — `feature.md`, `entity.md`, `spec.md`. Copy the right one when creating a new
  doc of that type. (There is no ADR template — decisions are recorded inside the `spec/` doc that
  owns the area; see "Non-negotiables".)
