# Authoring & maintaining docs

How to write each kind of doc, the frontmatter and status rules, the cross-link discipline, how
to keep the corpus alive, and when the v1 documentation is "done." `references/structure.md`
covers *where* things go and the served-docs constraints; this covers *how* docs are written and
kept.

Contents: frontmatter & the status lifecycle · per-doc-type writing rules · cross-link
discipline · writing for humans, agents, and the renderer · one fact one home · superseding &
retiring · the corpus audits · the v1 documentation-completeness checklist.

## Frontmatter & the status lifecycle

Every `.md` under `docs/` except `misc/`:

```yaml
---
title: Orders                # the page heading and the nav label — the real title, not the filename
status: draft                # draft → in-review → stable → superseded
owner: shape                 # which pipeline or person owns it: shape | build | <name>
updated: 2026-05-13          # bump on every substantive edit — the staleness audit uses it
order: 30                    # optional — position within the section's nav; lower first; absent = title-ordered
related:                     # optional — only when two docs are tightly coupled and the "related" nav widget genuinely helps
  - docs/architecture.md
---
```

**Required:** `title`, `status`, `owner`, `updated`.

**Optional:** `order` (set when the section's reading order matters), `related` (use sparingly —
*not* a dumping ground for ambient cross-references; see *Cross-link discipline* below).

- **`draft`** — being written; not yet trustworthy. Fine in `ref/` while in progress; a `draft`
  sitting in a canon path at end-of-cycle is a gap. The live site badges it.
- **`in-review`** — content's there, awaiting a check.
- **`stable`** — current and trusted. Canon docs should be `stable` by end-of-cycle.
- **`superseded`** — no longer true; deleted (git keeps it) or moved to `misc/` with a banner.

`updated` is load-bearing — the audits use it to surface docs the code has outgrown. Bump it on
meaningful changes, not typo fixes.

## Per-doc-type writing rules

### `docs/index.md` — Getting Started landing
The home page. Open with a one-paragraph product summary (what it is, who it's for, the bet);
then a numbered **"Read in this order"** ladder that walks a new contributor through the canon
(scope → domain model → access patterns → architecture), then features, then
entities. Optionally close with a brief pointer to the repo-root README for local setup, and a
one-line note on how the docs are served. Keep it short — ≤ 80 lines is a good ceiling. When
the canon set changes, update the ladder.

### Canon docs (`docs/<canon>.md`) — lean, normative, mandatory; rationale included
The canon owns the **model** and the **normative rules** every contributor must know; the
mechanics that implement those rules belong in `ref/features/`. (See `SKILL.md` → "Three
layers — what each owns" for the leakage tests.) Lead with the point; don't bury it. Headings
stable and predictable — a link to `#rules` should still resolve next quarter, because it's a
URL fragment now. Prefer a tight structure — short sections, **mermaid diagrams** for
structure, **tables** for comparison, prose for rationale — over prose sprawl. State **what
must be true** *and why it's that way* — the forces in play, the alternatives weighed, the
trade-offs accepted, the concrete revisit trigger — woven into the relevant section, **not**
kept in a separate ADR / `decisions/` register. (`architecture.md` carries the topology /
stack / data-model decisions; `domain-model.md` carries the domain-shape decisions; `scope.md`
carries the in / out-of-scope calls; `access-patterns.md` or another canon concern doc carries
that concern's decisions — each with its why.) Link `ref/` for the detail, `ref/entities/` for
entity specifics. Length is a signal: a long canon doc is usually carrying detail that belongs
in `ref/`, or it's two docs. The whole canon is meant to be read in a sitting — protect that.

A *new* canon concern doc is created from the `canon` template; existing canon docs
(`architecture`, `scope`, `domain-model`, `access-patterns`) are bespoke shapes — no template.

### `ref/features/<domain>.md` — the working spec for a cohesive domain
From the `feature` template. **One file per cohesive domain, not per CRUD.** This page is the
**single home** for the domain's **mechanics** — rules, UX, edge cases. Sections:
**Problem** (what's broken or missing, and for whom — the user pain, not the solution) ·
**Domain rules** (the state machine, invariants, who-may-do-what, pricing or warehouse contract
if any — *and where a rule is a real decision, the why right next to it*) · **User stories**
(or stories-flavoured framing) · **UX** (the interface design — flows, screen states, key
screens; component specs live in `web/DESIGN.md`; mermaid diagrams inline, raster images in
`docs/assets/`) · **Edge cases**. Trivial CRUDs are **sections inside the right home**, not
solo files (a worker registry lives in `workshop.md`'s "Workers" section).

> **No endpoint table.** Operations are named in domain language inside Domain rules / User
> stories. The HTTP shape — paths, request / response schemas, status codes — is the OpenAPI
> spec's job, rendered live at `/api-docs` and `/api-redoc` and curated under `ref/api/` when
> it earns one. A hand-written endpoint table inside a feature doc is a parallel copy that
> drifts. The exception: citing a specific status code in **Edge cases** when the UX must
> react to it (`optimization_timeout` → 504) — that's a domain fact, not an endpoint table.

> **Don't restate canon here.** The principal types, the tenancy hierarchy, system-wide
> invariants live in canon (`access-patterns.md`, `architecture.md`). One critical inline link
> at most; let the canon doc be the single home.

> **No "Out of scope" section in feature docs.** Out-of-scope for v1 is in
> `docs/scope.md` — one home. A feature page doesn't restate it.

### `ref/entities/<context>.md` — the entity catalog for a bounded context
**One page per bounded context, not one per entity.** Each entity gets an H2 inside the page,
following the `entity` template: **What it is** (one or two sentences — the business concept)
· **Fields** (name · type · meaning · constraints; in a table) · **States / lifecycle** (the
state machine, if any) · **Invariants** (what must always hold, and where it's enforced — DB
constraint vs. service rule). Use **anchor links** within the page (`sales.md#order-payment`)
when cross-referencing. The page is the **single home** for "what is an X" in that context;
features and canon docs link to a section, never redefine.

### `ref/api/`, `ref/jobs/`, `ref/runbooks/`, `ref/integrations/` — reference
Exhaustive, informative, look-it-up. Answer "what exactly is X" / "how exactly does X work."
Can be long; can be generated / derived. No rationale (that's the canon and feature docs — they
carry the *why*), no narrative. Keep each subfolder internally structured.

### `misc/` — no rules
No required frontmatter, no naming convention, not rendered, not audited.

## Cross-link discipline

The corpus is **deliberately under-linked**. Read the rules in `SKILL.md` → *Cross-document
references — minimize them*. The short version:

- **End each doc with a "Next" line** (2–4 links to what to read next). For a small doc that
  doesn't need one, omit it.
- **Inline cross-doc links only at critical points** — where omitting the link would force the
  reader to re-learn context, or where the linked doc is the single authoritative home for
  something the current doc is asserting.
- **`related:` frontmatter is optional.** Don't fill it just to fill it.
- **Link by path, never "see above" or "the order doc."**

If a doc has more than ~5 inline cross-doc links, it's probably restating something that lives
elsewhere — collapse the prose and link once.

## Writing for humans, agents, and the renderer at once

The same disciplines serve all three:

- **Stable, predictable headings** — humans skim by them; agents anchor links to them; the
  renderer turns them into URL fragments and a per-page TOC. Don't rename a heading casually.
- **Cross-link by path** — `docs/ref/entities/sales.md`, never "the sales doc" or "see above."
- **Self-contained** — each doc makes sense alone. State its own context briefly, link out for
  depth, don't assume the reader just read a sibling.
- **Structure the facts, prose the rationale** — tables and lists for "what"; paragraphs for
  "why." All three readers parse the former faster and need the latter spelled out.
- **One fact, one home** (below) — so no reader has to reconcile two versions.
- **Predictable, stable filenames** — kebab-case, named for the thing; an agent should be able
  to *guess* the path, and the path is a URL.
- **`title` and `order` set well** — the title is what shows in the nav and the page heading;
  pick it deliberately. Set `order:` where the section's reading order matters.

## One fact, one home

Before adding content, search the corpus for where that fact lives — or should. If it's there:
update it (and bump `updated`), or link to it. If it's in two places already: that's a defect —
pick the rightful owner (usually the most specific home: an entity fact → `ref/entities/...`;
a feature-domain rule or behaviour → `ref/features/...`; a system-wide rule → the canon doc
that owns it), fix it there, make the other link to it. If two docs *disagree*: a
contradiction — resolve it the same way, and check whether a decision needs recording or
updating. Duplication is the single failure mode this skill exists to prevent; treat it as a
bug, not a style nit.

## Updating a doc

Every edit is a chance to make the doc worse — longer, lumpier, out of order, quietly
contradicting a neighbour. Three things to hold each time you touch one:

- **No fresh duplication.** Before you add a paragraph, ask whether the concept already lives
  somewhere — in this doc, or (more dangerous) in another. If it does, link to the owner; don't
  restate it.
- **Place new content; don't append it.** A new section goes where it *belongs*, not at the
  bottom. A templated doc keeps its template's section order. After the edit, the doc should
  still read top to bottom without making the reader jump around.
- **Keep it easy to read.** If a section has grown into a wall, split it or push the detail
  down a layer (into `ref/`). If a heading has drifted from the content, fix the heading — but
  deliberately: headings are URL fragments. Bump `updated`. A doc that's been edited a dozen
  times should still read like it was written once.

## Superseding & retiring

- **A canon or feature doc that's now partly wrong** — including a decision (and its rationale)
  that's been overtaken: fix it in place — it's normative, there's exactly one current truth —
  and bump `updated`; git keeps the history. Don't leave a known-wrong paragraph standing "for
  now."
- **A doc that's wholly dead** (approach abandoned, feature dropped): **delete it** — git keeps
  the history. If it's genuinely worth keeping *visible*, move it to `misc/` with a one-line
  banner at the top — "Superseded by `docs/...`" / "Dropped because …, <date>" — and `status:
  superseded` if you keep frontmatter on it. There is no `archive/`.
- Whatever you supersede / delete / move: fix any `related:` links and `assets/` references
  that now dangle, and (if a canon or `ref/` path changed) leave a redirect.

## The corpus audits

Run these at end-of-cycle, and any time on request:

- **Orphans** — a doc nothing links to from `docs/index.md` or another doc, and that isn't
  reachable from the nav root. Either wire it in (a "Next" link from the docs it bears on) or,
  if it's stranded because it's dead, delete it / move it to `misc/`.
- **Contradictions** — two docs that disagree on a fact. Resolve (pick the owner, fix the
  other to link); check whether a decision is implicated.
- **Duplication** — the same fact maintained in two homes. Collapse to one; link from the
  other.
- **Layer leakage** — a canon doc carrying feature mechanics (endpoint paths, permission
  catalogs, screen descriptions, session-table schemas), or a feature doc restating canon
  rules (principal types, tenancy hierarchy, money-as-tiyin). Push leakage down to the right
  layer, or collapse the restatement and link once. (See `SKILL.md` → "Three layers — what
  each owns" for the tests.)
- **Section coherence** — a doc whose sections are out of logical reading order (templated
  doc breaking template order; bespoke doc not running overview → detail → edge cases), or
  whose headings have drifted from the content beneath them. Re-order; re-head (deliberately
  — headings are URL fragments).
- **Cross-link bloat** — a doc with > ~5 inline cross-doc links is probably restating something
  that lives elsewhere; collapse and link once.
- **ASCII art** — any box-and-pipe diagram or hand-drawn tree in a rendered doc. Replace with
  mermaid (or a real image in `docs/assets/`).
- **Hand-written endpoint tables in feature docs** — a `| Endpoint | … |` table or a paragraph
  listing `POST /api/v1/...` paths inside `ref/features/*`. The OpenAPI spec is the single
  home for HTTP shape; convert the prose to domain-language operations and drop the table.
- **Stale drafts in the canon** — any `status: draft` in a canon path at end-of-cycle is a
  gap; finish it or move it out of the canon.
- **Broken links** — any path in body text or `related:` that doesn't resolve; any `assets/`
  reference that points at a missing file. Fix or remove.
- **Renamed-without-redirect** — a canon or `ref/` doc whose path looks new and whose old
  path 404s with no redirect.
- **Canon bloat** — count the flat files at the top of `docs/` and eyeball the total length.
  If the canon is no longer readable in one sitting, something escaped — find it and pull it
  down to `ref/`.
- **Stale content** — docs whose `updated` is far back while the thing they describe has moved
  on. Flag for refresh.
- **Frontmatter health** — every `docs/` doc outside `misc/` has `title`, `status`, `owner`,
  `updated`; the shape (keys, casing) is identical across docs.
- **Forbidden artefacts** — no `README.md` under `docs/`; no extra `index.md` (only
  `docs/index.md` is allowed); no `docs/spec/` directory (the canon is flat); no `docs/ref/ux/`
  (the frontend design system lives in `web/DESIGN.md`).

Report the audit as: **✅ clean**, or a list of findings — each with the specific doc and the
specific fix.

## The v1 documentation-completeness checklist

This is the `shape` pipeline's finish line — what "full documentation that covers everything
for v1" actually means. The cycle isn't done until every box holds:

- [ ] `docs/index.md` exists, is `stable`, and contains a one-paragraph vision + a "Read in
  this order" ladder that covers the canon, features, and entities.
- [ ] `docs/scope.md` exists and is `stable` — and is the single home for what's out of v1.
- [ ] `docs/domain-model.md` exists; every bounded context it names has a page under
  `ref/entities/`; every entity referenced anywhere in the canon or `ref/features/` has a
  section under its bounded-context page.
- [ ] `docs/access-patterns.md` exists and is `stable` — its **Personas** section covers every
  role that touches v1, followed by the principals, the access model, and tenancy. Its mechanics
  live in `ref/features/access-management.md`, not in the canon doc.
- [ ] `docs/architecture.md` exists and is `stable`; it carries the operating envelope (tier,
  the "not built for" line), the topology, the stack, the data-model invariants, and the
  quality requirements (audit, performance, observability, i18n).
- [ ] Every cross-cutting concern that genuinely earns a canon doc has one at
  `docs/<concern>.md` (today: `docs/access-patterns.md`).
- [ ] Every in-scope **feature domain** has a `ref/features/<domain>.md` with all template
  sections filled — problem, domain rules, stories, UX, edge cases. No hand-written endpoint
  tables (OpenAPI is the HTTP-shape home). Trivial CRUDs are sections inside the right home,
  not solo files.
- [ ] Every consequential, costly-to-reverse decision is recorded — with its rationale (forces
  · alternatives weighed · trade-offs accepted) and a concrete revisit trigger — **inside the
  canon or feature doc that owns the area**. No separate ADR / `decisions/` register; no
  decision left implicit.
- [ ] **`web/DESIGN.md` exists and covers the design system the v1 SPAs need** — tokens,
  primitives, composed components, the shell, the route maps, the accessibility baseline.
  (Lives in the web repo, not under `docs/`.)
- [ ] Every doc has a `title` and a current `status`; the corpus audits come back clean — no
  orphans, contradictions, duplication, layer leakage, broken links, dangling `assets/`
  references, stale drafts in the canon, renamed-without-redirect paths, ASCII art used in
  place of mermaid diagrams, or forbidden artefacts (no `docs/README.md`, no extra `index.md`s,
  no `docs/spec/` directory, no `docs/ref/ux/`).
- [ ] The canon is still readable in one sitting — a person can read the flat top-level of
  `docs/` start to finish and come away understanding all of v1, and it didn't take them all
  day.
- [ ] The site renders: every `docs/` page outside `misc/` loads, the nav is sensible, no
  broken internal links.

When every box holds, the docs are v1-complete and the `shape` pipeline can hand off to
`build`. Until then, the unchecked boxes are the `shape` pipeline's to-do list.
