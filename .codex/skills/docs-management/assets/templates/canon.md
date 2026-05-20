---
title: <System-wide concern name>
status: draft
owner: shape
updated: <YYYY-MM-DD>
# order: <int>          # optional — position within the canon nav (lower first); set when the reading order matters
# related: …            # optional — only when tight coupling makes the "related" widget genuinely useful
---

# <System-wide concern name>

<One short paragraph framing what this concern is. State what must be true; link out for
detail; keep this canon-lean.>

<!--
Use this template ONLY for a *new* system-wide concern that genuinely earns its own canon
doc — a cross-cutting concern every feature has to obey (the existing example is
`docs/access-patterns.md`: principals, the access model, tenancy). The bar is high: most
"concerns" are really feature domains and belong in `docs/ref/features/<domain>.md`, where
their mechanics and UX live together on one page.

This is the MODEL layer. What belongs: the abstract model, the normative rules every feature
obeys, the rationale woven inline. What does NOT belong: endpoint paths, request / response
field names, permission catalogs, session-table schemas, screen / wizard descriptions, error
code catalogs, library versions — push all of that down to the feature doc that implements
this concern. See SKILL.md → "Three layers — what each owns" for the leakage tests.

The canon doc lives flat at the top of `docs/` — `docs/<concern>.md`, not under any subfolder.
There is no `spec/` directory; the canon is the flat top-level of `docs/`.
-->

## Actors
- <role / system> — <their part in this>
- …

## Rules
- <A normative statement — what must be true. **If the rule is a real decision, say why it's
  that rule right here** — the forces in play (the operating envelope, the constraints), the
  alternatives weighed and why they lost, the trade-offs accepted, the concrete revisit
  trigger. There is no separate ADR file; the rationale travels with the rule.>
- …

## Flow
<The main path. Prefer a mermaid diagram; a numbered list is fine for short flows. Branches
and failure paths go below. No ASCII art.>

## Edge cases & failure paths
- <Case> → <what happens>
- …

## Next (optional)
<2–4 links to docs a reader should pick up next — the feature page that implements this, the
entity context page, an adjacent canon doc. Skip this section if no link earns it.>
