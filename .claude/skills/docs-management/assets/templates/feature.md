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
cross-cutting canon rule (`docs/access.md` for auth/authz/tenancy, `docs/architecture.md` for a
data-model invariant), link to it inline. This page is the **single home** for everything about
the domain: rules, endpoints, UX, edge cases. No separate "spec" doc — the rules live here.>

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

## Endpoints
<Optional: a short table of the API the feature exposes. Useful for domains with many
operations.>

| Endpoint | Caller | What |
|---|---|---|
| `…` | … | … |

## UX
<The interface design for this feature: the key flows, screen states, and primary screens.
Component specs live in `web/DESIGN.md` — link only when a reader would otherwise have to guess
what the component is. Diagrams → `docs/assets/`, referenced by relative path.>

## Edge cases
- <The awkward case> → <what should happen>
- …

## Next (optional)
<2–4 links to docs a reader should pick up next — an adjacent feature page, the entity context
page, the canon doc the feature relies on. Skip this section if no link earns it.>

<!--
Notes for the author:
- "Out of scope" is NOT a section in this template. Out-of-scope for v1 lives in
  docs/scope.md — one home. Do not restate it here.
- Trivial CRUDs (a single endpoint with a form behind it — a registry, a password reset) belong
  as sections inside the right home doc, not as a solo file.
- Entities the feature touches: link them inline where they first matter, not as a separate
  "Entities touched" section. The single home for entities is docs/ref/entities/<context>.md.
-->
