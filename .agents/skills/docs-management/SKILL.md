---
name: docs-management
description: >-
  Owns the project's `docs/` corpus — structure, routing, linking, upkeep — served live as markdown by the backend. Use whenever you create, edit, move, organize, or review docs; file an architecture decision, UX spec, feature, or entity page; ask where a doc belongs; or suspect docs are stale, duplicated, orphaned, or leaking between layers. Keeps the tree small; separates canon / `ref/features` / `ref/entities`; enforces one-fact-one-home, stable paths, and mermaid over ASCII.
---

# Documentation Management

This skill owns the **form** of the docs — where each output lives, what shape it takes, how
the pieces link — not the decisions in them. It pushes back when a doc sits in the wrong
layer, duplicates or contradicts another, or is about to break its URL.

## Three layers — what each owns

Every piece of content belongs in exactly one layer. The most common defect is **leakage** — a
rule in the wrong layer, or in two. Decide the layer before writing the sentence.

| Layer | Owns | Belongs here |
| --- | --- | --- |
| **Canon** — flat at the top of `docs/` | the **model** + **normative rules** every contributor must know | principals, tenancy, operating envelope, topology, system-wide invariants, in/out of scope |
| **`ref/features/<domain>.md`** | the **mechanics** of one cohesive domain | domain rules, state machines, operations in domain language, UX (flows, screens), permission catalogs, error codes as domain facts |
| **`ref/entities/<context>.md`** | the **shape** of one bounded context's entities | fields, types, lifecycle states, invariants |

Leakage tests:

- **Into canon** (push down to a feature): an endpoint table or request/response field names;
  a permission catalog (`manage_orders`, …); a wizard/screen/form description; a table
  schema, algorithm name, or pinned version (the *choice* of FastAPI is canon; column names
  are not).
- **Out of canon** (collapse the restatement): a feature doc repeating the principal types,
  the tenancy hierarchy, a system-wide invariant ("money is integer tiyin"), or shared
  topology — drop the copy, link the canon home once.

Canon is mandatory reading — every line taxes everyone; it must stay readable in one sitting,
and when it stops fitting, hunt leakage first.

**Place before you write** — every time: which layer? which doc inside it (search the corpus;
update in place, never fork a parallel doc)? does it duplicate something (link, don't
restate)? **One fact, one home:** a fact in two places is a defect — pick the most specific
owner (entity fact → `ref/entities/`, domain rule → `ref/features/`, system-wide → canon),
fix it there, link from the other. Two docs *disagreeing* is the same defect, plus a check
whether a recorded decision needs updating.

## The tree (today)

```
README.md              # the ONLY README in the repo, at the root: "what this is + see docs/"
docs/
├── index.md           # THE HOME at /docs: vision paragraph + numbered "Read in this order"
│                      #   ladder (canon → features → entities). The only index.md under docs/.
│ # THE CANON — flat at the top. Lean, normative, readable in one sitting.
├── scope.md           # in / out / explicit non-goals
├── domain-model.md    # ubiquitous language + high-level entity map (detail → ref/entities/)
├── access-patterns.md # personas + principals, the access model, tenancy
├── architecture.md    # operating envelope · topology · stack · data-model invariants · quality
└── ref/
    ├── features/      # ONE page per cohesive feature domain (nine today — `ls` for the inventory)
    └── entities/      # ONE page per bounded context (eight today — `ls`); NOT one file per entity
```

**Create on first need — none exist today; don't pre-create:** `ref/api/` · `ref/jobs/` ·
`ref/runbooks/` · `ref/integrations/` — long look-it-up reference, no rationale or narrative
(the *why* stays in canon and feature docs); `assets/` — images/diagrams docs embed by
relative path; `misc/` — the drawer (research, PDFs, exports, scratch; no frontmatter, no
rules, not audited). No loose files directly in `ref/`.

Outside `docs/`: **`web/DESIGN.md`** — the frontend design system (tokens, primitives,
composed components, the shell, SPA route maps, accessibility baseline) lives next to the
code it constrains. There is no `docs/ref/ux/` — do not recreate one.

Conventions: filenames kebab-case, descriptive, guessable; depth at most two levels below
`docs/` (`docs/ref/features/orders.md` is the floor — deeper means the grouping is wrong); no
`README.md` and no second `index.md` anywhere under `docs/`; no `_template.md` files —
templates live in this skill's `assets/templates/` (`canon.md`, `feature.md`, `entity.md`;
copy the right one on create, `entity.md` re-applied per entity inside a context page).

## The served site

`backend/app/docs_site.py` renders `docs/` live at `/docs` — markdown → HTML per request, no
build step; edit the file and refresh. The site, together with the OpenAPI UIs at `/api-docs`
(Swagger) and `/api-redoc` (ReDoc), sits behind **HTTP Basic** — `DOCS_AUTH_USERNAME` /
`DOCS_AUTH_PASSWORD`, dev default `docs`/`docs` — *not* the app's session auth. Implications:

- **A path is a URL.** `docs/ref/features/orders.md` → `/docs/ref/features/orders`. There is
  **no redirect mechanism** — an unresolved path silently 302s to the docs home, so a stale
  link never 404s where you'd notice. Don't rename or move a published path without updating
  **every inbound link in the same change** (grep the corpus).
- **Nav** is built from the tree + frontmatter: files sort above folders; a folder takes its
  lowest child's `order`. Don't encode order in filename prefixes (`01-…`) — that puts the
  order in the URL.
- Relative `.md` links are rewritten to site URLs — always link **by path**
  (`docs/architecture.md`), never "see above" or "the order doc". Headings become URL
  fragments and TOC entries — rename one deliberately, not casually. Fenced `mermaid` blocks
  render client-side as SVG.
- **Everything under `docs/` is served** — non-`.md` files as static bytes, `misc/`
  included; the only gate is Basic auth, so nothing goes there that can't stand that
  exposure. Names starting with `.` or `_` are hidden from the nav (still fetchable).
  `docs/index.md` is the home page (`README.md` is a code-level fallback — never use it).

## Frontmatter

Every `.md` under `docs/` except `misc/`:

```yaml
---
title: Orders        # required — page heading + nav label; the real title, not the filename echoed
status: draft        # required — draft → in-review → stable → superseded
updated: 2026-08-15  # required — bump on substantive edits (staleness audits use it), not typos
order: 30            # optional — nav position, integer, lower first (default 1000)
---
```

**These four keys are exactly what the renderer parses** (`status` and `updated` render as
badges); anything else is write-only. `owner:` — existing docs and the templates carry
`owner: shape`, a fossil from a retired workflow — and `related:` are inert: never add,
update, or reason from them (the fossil is harmless to leave when copying a template).

`draft` = badged, not yet trustworthy — fine in `ref/`, a gap in canon; never mark a
half-written doc `stable`. `in-review` = awaiting a check. `stable` = current and trusted —
where canon should sit. `superseded` = deleted or moved to `misc/`, never left in place.
Hold the frontmatter shape identical across docs — same keys, same order, same casing.

## The routing map

| You have… | It goes to… |
|---|---|
| Product vision / Getting Started ladder | `docs/index.md` — update the ladder when the canon set changes |
| Scope / non-goals | `docs/scope.md` — the "out" list matters as much as the "in" |
| A user role | the **Personas** section of `docs/access-patterns.md` |
| Ubiquitous-language term / entity map | `docs/domain-model.md` (per-entity detail → `ref/entities/`) |
| The access model (principals · access · tenancy) | `docs/access-patterns.md` — the *model*; mechanics → `ref/features/access-management.md` |
| Architecture (envelope · topology · stack · invariants · quality) | `docs/architecture.md` |
| A *new* system-wide concern | `docs/<concern>.md` from the `canon` template — **high bar**; most "concerns" are feature domains |
| A consequential, costly-to-reverse decision | the canon or feature doc that owns the area — see "Recording decisions" |
| A cohesive feature domain | `docs/ref/features/<domain>.md` from the `feature` template |
| A trivial CRUD | a section in the right feature page, never a solo file (workshop user management lives in `access-management.md`) |
| Per-feature UX (flows, screen states) | the **UX** section of the feature page; component specs → `web/DESIGN.md` |
| Design system / component specs / SPA route maps | **`web/DESIGN.md`** — not under `docs/` |
| An entity definition (fields, states, invariants) | a section in `docs/ref/entities/<context>.md` (`entity` template); update `domain-model.md`'s map when the set changes |
| HTTP endpoint shape (paths, schemas, status codes) | the OpenAPI spec (`/api-docs`, `/api-redoc`); curated `ref/api/` when it earns one — never hand-written in a feature doc |
| API / job / runbook / integration detail | `ref/api/` · `ref/jobs/` · `ref/runbooks/` · `ref/integrations/` (create on first need) |
| Research, PDFs, exports, scratch | `docs/misc/`; distil raw ideation into the owning doc first — raw notes are not a doc |
| A doc that's wrong and dead | delete or retire — see "Editing, superseding, retiring" |

If an output fits no row, it's either not doc-worthy (→ `misc/` or nothing) or a real
structural gap — and changing the structure is a deliberate act, not a reflex `mkdir`.

**Recording decisions.** There is no ADR genre, no `decisions/` register, no ADR template. A
decision lives inside the doc that owns the area, woven into its prose with: the **forces**
in play, the **alternatives** weighed and why they lost, the **consequences** accepted, and a
concrete **revisit trigger** (a number, an event, a date — not "periodically"). A doc that
states a normative call also states why.

## Writing rules per doc type

- **`docs/index.md`** — one-paragraph vision + a numbered "Read in this order" ladder through
  canon → features → entities; optionally a pointer to the root README for local setup.
  ≤ 80 lines. The test: a new contributor reads it in ~2 minutes and knows what to read next.
- **Canon (`docs/<canon>.md`)** — lean, normative, rationale woven in. Lead with the point;
  state what must be true *and why*; link `ref/` for detail. Existing canon docs are bespoke
  shapes; only a *new* concern uses the `canon` template. Past ~200 lines is a signal the doc
  carries a layer's-down detail — or is two docs.
- **`ref/features/<domain>.md`** — template sections: **Problem** (the user pain, not the
  solution) · **Domain rules** (state machine, invariants, who-may-do-what — the *why* next
  to any real decision) · **User stories** · **UX** (flows, screen states, key screens;
  mermaid inline, raster images in `docs/assets/`) · **Edge cases**. **No endpoint table** —
  operations are named in domain language ("the client confirms a cutting result"); HTTP
  shape is OpenAPI's job. Sole exception: a status code in Edge cases when the UX must react
  to it (`optimization_timeout` → 504). **No "Out of scope" section** — `docs/scope.md` is
  the one home. Don't restate canon; one critical inline link at most. Past ~500 lines is a
  signal.
- **`ref/entities/<context>.md`** — each entity gets an H2 following the `entity` template:
  **What it is** · **Fields** (table) · **States / lifecycle** · **Invariants** (and where
  each is enforced — DB constraint vs. service rule). Cross-reference within the page by
  anchor (`sales.md#order-payment`). The single home for "what is an X" — features and canon
  link to a section, never redefine.

## Style

**Write less, not more.** State the call; don't relitigate it — "X vs Y" essays belong in the
conversation where the call was made. A rationale paragraph earns its space only when it
tells a future reader *what would have to change* to revisit the call. Self-edit before
saving: cut hedges, throat-clearing openers, sentences that only introduce the next
paragraph, headings restated in their first sentence.

**Shapes, in order of preference:** (1) **mermaid** for anything with nodes and edges —
topology, state machines, sequences, ER; (2) **tables** for structured comparison — state
semantics, role matrices, field lists; (3) numbered lists for ordered steps, bullets for
unordered atoms; (4) **prose** for rationale only. **ASCII diagrams are forbidden** — they
drift on edit and render poorly; replace any you find with mermaid.

**Cross-links: the corpus is deliberately under-linked.** Each doc ends with a "Next" line —
2–4 links to read next (omit for short docs with no obvious next). Inline cross-doc links
only at critical points: where omitting one forces the reader to re-learn context, or where
the target is the single authoritative home for something this doc asserts. More than ~5
inline cross-doc links means the doc is restating what lives elsewhere — collapse and link
once. Each doc stays self-contained — never assume the reader just read a sibling.

## Editing, superseding, retiring

- **Place new content; don't append it.** A templated doc keeps its template's section
  order; a bespoke doc runs overview → detail → edge cases.
- **Re-run the layer test per new paragraph** — a permission name, endpoint path, or screen
  description landing in canon is leakage; push it down before saving.
- **Re-read top to bottom after the edit** — same voice, no zig-zag, no fresh duplication
  with a sibling; match the corpus's forms (tables where it uses tables). A doc edited a
  dozen times should still read like it was written once.
- **Partly wrong normative doc** (including an overtaken decision): fix in place, bump
  `updated` — there is exactly one current truth; no known-wrong paragraph stands "for now".
- **Wholly dead doc:** delete it — git keeps history. If genuinely worth keeping visible,
  move to `misc/` with a one-line banner ("Superseded by `docs/…`" / "Dropped because …,
  date") and `status: superseded`. There is no `archive/`. Either way, fix every inbound
  link and `assets/` reference that now dangles.

## Evolving the tree

A new `ref/` subfolder or canon doc is a deliberate act — name the concrete present need and
make the **smallest** change that fits: a new file before a new subfolder; a `ref/` subfolder
before a new top-level folder. The top level of `docs/` is meant to stay: flat canon +
`index.md` + `ref/` + (on need) `assets/` + `misc/` — the flat canon exists *because* a
`spec/` subdirectory didn't pull its weight; don't reintroduce it. A new canon doc's test:
*every contributor must read this* — most candidates are feature domains. One tree; never
fork per-feature or per-team. Record a significant reshape (rationale + revisit trigger) in
`architecture.md`, or `domain-model.md` for the entity tree. No ceremony for the tree working
as designed: a new feature page for a genuinely new domain, a section added to an existing
page, a ladder update in `index.md`.

## The corpus audit

Run on request or after a large docs change. Report **clean**, or findings — each with the
specific doc and the specific fix:

- **Orphans** — docs unreachable from `index.md` or any "Next" line: wire in or delete.
- **Contradictions / duplication** — two docs disagreeing on or both maintaining a fact:
  pick the owner, fix there, link from the other.
- **Layer leakage** — endpoint paths / permission catalogs / screen descriptions in canon;
  canon rules restated in features.
- **Broken links** — paths or `assets/` refs that don't resolve (the renderer 302s home
  silently, so only a grep catches these); renamed paths with un-updated inbound links.
- **Endpoint tables** in `ref/features/*` — convert to domain-language operations.
- **ASCII art** in any rendered doc — replace with mermaid.
- **Stale docs** — `draft` loitering in canon; `updated` far behind the code it describes.
- **Frontmatter health** — `title`, `status`, `updated` on every doc outside `misc/`;
  uniform shape.
- **Canon bloat** — no longer readable in one sitting: find what escaped, pull it down.
- **Forbidden artefacts** — `README.md` under `docs/`, a second `index.md`, `docs/spec/`,
  `docs/ref/ux/`, `_template.md` files.
