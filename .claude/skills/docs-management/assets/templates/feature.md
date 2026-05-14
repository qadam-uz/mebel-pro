---
title: <Feature domain name>
status: draft
owner: shape
updated: <YYYY-MM-DD>
# order: <int>          # optional — position within ref/features/ in the nav
# related: …            # optional — only when tight coupling makes the "related" widget genuinely useful
---

# <Feature domain name>

<One-paragraph framing of what this domain covers — and, if the feature depends on a
cross-cutting canon rule (`docs/access-patterns.md` for auth / authz / tenancy,
`docs/architecture.md` for a data-model invariant), one critical inline link. This page is the
**single home** for the domain's **mechanics** — rules, UX, edge cases. The cross-cutting
*model* (principal types, tenancy hierarchy, topology) lives in canon; don't restate it here.>

## Problem
<What's broken or missing, and for whom. The user pain — not the solution.>

## Domain rules
<The normative statements that govern this domain — the state machine, the invariants, the
who-may-do-what, the warehouse contract or pricing model if it has one. **If a rule is a real
decision, say why it's that rule right here** — the forces in play, the alternatives weighed,
the consequences accepted, the concrete revisit trigger. No separate ADR file.>

## User stories
- As a <role>, I want <capability> so that <outcome>.
- …

## UX
<The interface design for this feature: the key flows, screen states, and primary screens.
Use mermaid for flows and state diagrams; component specs live in `web/DESIGN.md` — link only
when a reader would otherwise have to guess what the component is. Raster images go in
`docs/assets/`, referenced by relative path. No ASCII art.>

## Edge cases
- <The awkward case> → <what should happen>
- …

## Next (optional)
<2–4 links to docs a reader should pick up next — an adjacent feature page, the entity context
page, the canon doc the feature relies on. Skip this section if no link earns it.>

<!--
Notes for the author:
- This is the MECHANICS layer. Domain rules, state machines per object, permission catalogs
  in prose, screens, error codes, edge cases — all welcome. What does NOT belong: the
  principal types or the tenancy hierarchy (canon: docs/access-patterns.md), system-wide
  invariants like integer-tiyin money or no-soft-delete (canon: docs/architecture.md), or any
  topology every feature shares. See SKILL.md → "Three layers — what each owns" for the
  leakage tests.
- NO endpoint table. Operations live in domain language inside Domain rules / User stories
  ("the client confirms a cutting result"). HTTP-level shape (paths, request/response schemas,
  status codes) is the OpenAPI spec's job — rendered live at /api-docs and /api-redoc, with
  ref/api/ as the curated home when it earns one. Naming a specific status code in Edge cases
  is fine when the UX has to react to it (`optimization_timeout` → 504) — that's a domain fact,
  not an endpoint table.
- "Out of scope" is NOT a section in this template. Out-of-scope for v1 lives in
  docs/scope.md — one home. Do not restate it here.
- Trivial CRUDs (a single operation with a form behind it — a registry, a password reset)
  belong as sections inside the right home doc, not as a solo file.
- Entities the feature touches: link them inline where they first matter, not as a separate
  "Entities touched" section. The single home for entities is docs/ref/entities/<context>.md.
-->
