---
title: <Concern or flow name>
status: draft
owner: shape
updated: <YYYY-MM-DD>
# order: <int>          # optional — position within spec/ in the nav
related:
  - docs/spec/architecture.md
---

# <Concern or flow name>

## Purpose
<What this concern or flow is, and why it matters — one short paragraph. This is canon: keep it
lean. State what must be true; link out for detail.>

## Actors
- <role / system> — <their part in this>
- …

## Rules
- <A normative statement — what must be true. **If the rule is a real decision, say why it's that
  rule right here** — the forces in play (the operating envelope, the constraints), the alternatives
  weighed and why they lost, the trade-offs accepted, the concrete revisit trigger. There is no
  separate ADR file; the rationale travels with the rule. Link `docs/ref/…` for the detail,
  `docs/ref/entities/…` for the entities involved.>
- …

## Flow
<The main path, step by step (a numbered list, or a small diagram → docs/assets/). Branches and
failure paths go below.>

## Edge cases & failure paths
- <Case> → <what happens>
- …

## See also
- `docs/spec/architecture.md` — <the broader system context this fits into>
- `docs/ref/…` — <the detailed reference>
- `docs/ref/features/….md` — <the feature(s) that implement it>
