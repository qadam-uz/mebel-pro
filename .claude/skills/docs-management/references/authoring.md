# Authoring & maintaining docs

How to write each kind of doc, the frontmatter and status rules, how to keep the corpus alive, and
when the v1 documentation is "done." `references/structure.md` covers *where* things go and the
served-docs constraints; this covers *how* docs are written and kept.

Contents: frontmatter & the status lifecycle · per-doc-type writing rules · writing for humans,
agents, and the renderer · one fact one home · superseding & retiring · the corpus audits · the v1
documentation-completeness checklist.

## Frontmatter & the status lifecycle

Every `.md` under `docs/` except `misc/`:

```yaml
---
title: Orders                # the page heading and the nav label — the real title, not the filename
status: draft                # draft → in-review → stable → superseded
owner: shape                 # which pipeline or person owns it: shape | build | <name>
updated: 2026-05-11          # bump on every substantive edit — the staleness audit uses it
order: 30                    # optional — position within the section's nav; lower first; absent = title-ordered
related:                     # paths to closely-related docs; two-way where it makes sense
  - docs/spec/orders.md
  - docs/ref/entities/sales/order.md
---
```

- **`draft`** — being written; not yet trustworthy. Fine in `ref/` while in progress; a `draft`
  sitting in a `spec/` canon path at end-of-cycle is a gap. The live site badges it.
- **`in-review`** — content's there, awaiting a check.
- **`stable`** — current and trusted. `spec/` docs should be `stable` by end-of-cycle.
- **`superseded`** — no longer true; deleted (git keeps it) or moved to `misc/` with a banner.

`updated` is load-bearing — the audits use it to surface docs the code has outgrown. Bump it on
meaningful changes, not typo fixes.

## Per-doc-type writing rules

### `spec/` docs — lean, normative, mandatory; rationale included
Lead with the point; don't bury it. Headings stable and predictable — a link to `#rules` should
still resolve next quarter, because it's a URL fragment now. Prefer a tight structure — short
sections, tables for the facts — over prose sprawl. State **what must be true** *and why it's that
way* — the forces in play, the alternatives weighed, the trade-offs accepted, the concrete revisit
trigger — woven into the relevant section, **not** kept in a separate ADR/`decisions/` register.
(`architecture.md` carries the topology/stack/data-model decisions; a `spec/<concern>.md` carries
that concern's decisions; `domain-model.md` carries the domain-shape decisions; `scope-v1.md`
carries the in/out-of-scope calls — each with its why.) Link `ref/` for the detail, `ref/entities/`
for entity specifics. Length is a signal: a long `spec/` doc is usually carrying detail that belongs
in `ref/`, or it's two docs. The whole of `spec/` is meant to be read in a sitting — protect that.

### `ref/features/<x>.md` — the working spec
From the `feature` template. Sections: **Problem** (what's broken or missing, and for whom — the
user pain, not the solution) · **User stories** · **Requirements** (functional; numbered if it
helps the build pipeline reference them) · **UX** (the interface design for this feature — flows,
screen states, key screens; link `ref/ux/*` for cross-cutting patterns; diagrams in `docs/assets/`)
· **Entities touched** (links into `ref/entities/`) · **Edge cases** · **Out of scope** (explicit
— what this feature is *not* doing, so it doesn't creep in) · **Open questions** (each with an
owner; mirror blocking ones up into `spec/open-questions.md`). Concrete and complete *for this
feature*. Not canon.

> **No separate decision register.** There is no ADR genre and no `spec/decisions/` folder. A
> consequential, costly-to-reverse decision is recorded **inside the `spec/` doc that owns the
> area** — woven into its prose with the forces in play, the alternatives weighed, the consequences
> accepted, and the concrete revisit trigger. When a decision is overtaken, fix that doc in place
> and bump `updated`; git keeps the history. (Routing: see `references/structure.md` → the full
> routing map.)

### `ref/entities/<domain>/<entity>.md` — the entity page
From the `entity` template. Sections: **What it is** (one or two sentences — the business concept)
· **Fields** (name · type · meaning · constraints) · **States / lifecycle** (the state machine, if
any) · **Invariants** (what must always hold, and where it's enforced — DB constraint vs. service
rule) · **Relationships** (to other entities — links, with cardinality) · **Owner** (which feature
or concern owns this entity's rules). The **single home** for this entity — everything else links
here, nothing else redefines it.

### `spec/<concern>.md` — a system-wide concern or flow
From the `spec` template. Sections: **Purpose** (what this concern / flow is and why it matters —
one short paragraph; this is canon, keep it lean) · **Actors** · **Rules** (the normative statements
**and, where a rule is a real decision, why it's that rule** — the forces, the alternatives weighed,
the trade-offs accepted, the revisit trigger — inline, right where the rule is; link `ref/*` for the
detail, `ref/entities/` for the entities) · **Flow** (the main path; branches and failures below) ·
**Edge cases & failure paths** · **See also** (the related reference pages and features).

### `ref/ux/*`, `ref/api/*`, `ref/jobs/*`, `ref/runbooks/*`, `ref/integrations/*` — reference
Exhaustive, informative, look-it-up. Answer "what exactly is X" / "how exactly does X work." Can be
long; can be generated / derived. No rationale (that's the `spec/` docs — they carry the *why*), no
narrative. Keep each subfolder internally structured. For `ref/ux/*`: placement, naming, and
frontmatter are this skill's; the design content that fills them comes from elsewhere.

### `misc/` — no rules
No required frontmatter, no naming convention, not rendered, not audited. Keep it tidy by
occasionally clearing what's done its job; don't over-think it.

## Writing for humans, agents, and the renderer at once

The same disciplines serve all three:

- **Stable, predictable headings** — humans skim by them; agents anchor links to them; the renderer
  turns them into URL fragments and a per-page TOC. Don't rename a heading casually.
- **Cross-link by path** — `docs/ref/entities/sales/order.md`, never "the order doc" or "see
  above." A doc may be read in isolation — pulled into a context window, or loaded as one page —
  where "see above" points at nothing.
- **Self-contained** — each doc makes sense alone. State its own context briefly, link out for
  depth, don't assume the reader just read a sibling.
- **Structure the facts, prose the rationale** — tables and lists for "what"; paragraphs for "why."
  All three readers parse the former faster and need the latter spelled out.
- **One fact, one home** (below) — so no reader has to reconcile two versions.
- **Predictable, stable filenames** — kebab-case, named for the thing; an agent should be able to
  *guess* the path, and the path is a URL, so don't churn it.
- **`title` and `order` set well** — the title is what shows in the nav and the page heading; pick
  it deliberately. Set `order:` where the section's reading order matters.

## One fact, one home

Before adding content, search the corpus for where that fact lives — or should. If it's there:
update it (and bump `updated`), or link to it. If it's in two places already: that's a defect —
pick the rightful owner (usually the most specific home: an entity fact → `ref/entities/...`; a
system rule → `spec/...`; a feature behaviour → `ref/features/...`), fix it there, make the other
link to it. If two docs *disagree*: a contradiction — resolve it the same way, and check whether a
decision needs recording or updating. Duplication is the single failure mode this skill exists to
prevent; treat it as a bug, not a style nit.

## Updating a doc

Every edit is a chance to make the doc worse — longer, lumpier, out of order, quietly contradicting
a neighbour. Three things to hold each time you touch one:

- **No fresh duplication.** Before you add a paragraph, ask whether the concept already lives
  somewhere — in this doc, or (more dangerous) in another. If it does, link to the owner; don't
  restate it. "One fact, one home" is a check on every edit, not a rule that only applies when a
  doc is born — a duplicate introduced by an update is exactly as much of a bug as one in a new
  file.
- **Place new content; don't append it.** A new section goes where it *belongs*, not at the bottom
  because that's where the cursor was. A templated doc (feature spec, entity page, concern spec)
  keeps its template's section order — fit the addition into the right slot. A bespoke doc
  keeps a logical reading flow: overview before detail, the common path before the edge cases, the
  *what* before the *why-this-way*. After the edit, the doc should still read top to bottom without
  making the reader jump around.
- **Keep it easy to read.** If a section has grown into a wall, split it or push the detail down a
  layer (into `ref/`). If a heading has drifted from the content beneath it, fix the heading — but
  deliberately: headings are URL fragments now (see `references/structure.md` → "The served-docs
  constraints"), so renaming one is a small breaking change. Bump `updated`. A doc that's been
  edited a dozen times should still read like it was written once.

## Superseding & retiring

- **A `spec/` doc that's now partly wrong** — including a decision (and its rationale) that's been
  overtaken: fix it in place — it's normative, there's exactly one current truth — and bump
  `updated`; git keeps the history. Don't leave a known-wrong paragraph, or a known-wrong decision,
  standing "for now."
- **A doc that's wholly dead** (approach abandoned, feature dropped): **delete it** — git keeps the
  history, and a served site shouldn't carry corpses. If it's genuinely worth keeping *visible* (a
  cautionary tale, a frequently-asked "why don't we…"), move it to `misc/` with a one-line banner
  at the top — "Superseded by `docs/...`" / "Dropped because …, <date>" — and `status: superseded`
  if you keep frontmatter on it. There is no `archive/`.
- Whatever you supersede / delete / move: fix any `related:` links and `assets/` references that now
  dangle, and (if a `spec/` or `ref/` path changed) leave a redirect.

## The corpus audits

Run these at end-of-cycle, and any time on request:

- **Orphans** — a doc nothing links to and that isn't reachable from the nav root. Either wire it
  in (a `related:` link from the docs it bears on) or, if it's stranded because it's dead, delete
  it / move it to `misc/`.
- **Contradictions** — two docs that disagree on a fact. Resolve (pick the owner, fix the other to
  link); check whether a decision is implicated.
- **Duplication** — the same fact maintained in two homes. Collapse to one; link from the other.
- **Section coherence** — a doc whose sections are out of logical reading order, or whose headings
  have drifted from the content beneath them. Re-order; re-head (deliberately — headings are URL
  fragments).
- **Stale drafts in the canon** — any `status: draft` in a `spec/` path at end-of-cycle is a gap;
  finish it or move it out of `spec/`.
- **Broken links** — any path in body text or `related:` that doesn't resolve; any `assets/`
  reference that points at a missing file. Fix or remove.
- **Renamed-without-redirect** — a `spec/` or `ref/` doc whose path looks new and whose old path
  404s with no redirect. Add the redirect (or restore the path).
- **`spec/` bloat** — count the `spec/` files and eyeball the total length. If the canon is no
  longer readable in one sitting, something escaped — find it and pull it down to `ref/`.
- **Stale content** — docs whose `updated` is far back while the thing they describe has moved on.
  Flag for refresh (you may not fix them all in one pass — name them).
- **Frontmatter health** — every `docs/` doc outside `misc/` has `title`, `status`, `owner`,
  `updated`; nothing in `spec/` or `ref/` is missing what the renderer needs.

Report the audit as: **✅ clean**, or a list of findings — each with the specific doc and the
specific fix.

## The v1 documentation-completeness checklist

This is the `shape` pipeline's finish line — what "full documentation that covers everything for
v1" actually means. The cycle isn't done until every box holds:

- [ ] `spec/vision.md` and `spec/scope-v1.md` exist and are `stable`.
- [ ] `spec/personas.md` covers every role that touches v1.
- [ ] `spec/journeys.md` covers every end-to-end flow in scope.
- [ ] `spec/architecture.md`, `spec/envelope.md`, `spec/nfr.md` exist and are `stable`; the
  envelope names the tier, states the explicit "not built for" line, and calls out any per-module
  exception.
- [ ] `spec/domain-model.md` exists; every entity it names has a page under `ref/entities/`; every
  entity referenced anywhere in `spec/` or `ref/features/` has a page under `ref/entities/`.
- [ ] Every in-scope feature has a `ref/features/<x>.md` with all template sections filled —
  including a UX section.
- [ ] Every consequential, costly-to-reverse decision is recorded — with its rationale (forces ·
  alternatives weighed · trade-offs accepted) and a concrete revisit trigger — **inside the `spec/`
  doc that owns the area** (architecture/stack/data-model → `architecture.md`; a system concern → its
  `spec/<concern>.md`; the domain shape → `domain-model.md`; an in/out-of-scope call → `scope-v1.md`).
  No separate ADR/`decisions/` register; no decision left implicit.
- [ ] `spec/open-questions.md` has no *blocking* unknowns left; the remaining ones each have an
  owner and a concrete revisit trigger.
- [ ] `ref/ux/information-architecture.md` exists; `ref/ux/components.md` covers the shared
  components v1 needs.
- [ ] Every doc has a `title` and a current `status`; the corpus audits come back clean — no
  orphans, contradictions, duplication, broken links, dangling `assets/` references, stale drafts
  in the canon, or renamed-without-redirect paths.
- [ ] `spec/` is still readable in one sitting — a person can read it (plus `spec/domain-model.md`)
  start to finish and come away understanding all of v1, and it didn't take them all day.
- [ ] The site renders: every `docs/` page outside `misc/` loads, the nav is sensible, no broken
  internal links.

When every box holds, the docs are v1-complete and the `shape` pipeline can hand off to `build`.
Until then, the unchecked boxes are the `shape` pipeline's to-do list.
