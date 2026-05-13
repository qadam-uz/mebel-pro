---
title: <System-wide concern name>
status: draft
owner: shape
updated: <YYYY-MM-DD>
# order: <int>          # optional — position within the canon nav (lower first); set when the reading order matters
# related: …            # optional — only when tight coupling makes the "related" widget genuinely useful
---

# <System-wide concern name>

<One short paragraph framing what this concern is and where the broader context lives (link
`architecture.md` only if a reader genuinely needs it for the rules below; otherwise skip the
link). State what must be true; link out for detail; keep this canon-lean.>

<!--
Use this template ONLY for a *new* system-wide concern that genuinely earns its own canon
doc — a cross-cutting concern every feature has to obey (the existing example is
`docs/access.md`: auth / authz / tenancy). The bar is high: most "concerns" are really feature
domains and belong in `docs/ref/features/<domain>.md`, where their rules and UX live together
on one page.

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
<The main path, step by step (a numbered list, or a small diagram → `docs/assets/`). Branches
and failure paths go below.>

## Edge cases & failure paths
- <Case> → <what happens>
- …

## Next (optional)
<2–4 links to docs a reader should pick up next — the feature page that implements this, the
entity context page, an adjacent canon doc. Skip this section if no link earns it.>
