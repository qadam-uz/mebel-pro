---
title: <Entity name>
status: draft
owner: shape
updated: <YYYY-MM-DD>
related:
  - docs/spec/domain-model.md
---

# <Entity name>

## What it is
<One or two sentences — the concept this represents in the business.>

## Fields
| Field | Type | Meaning | Constraints |
|---|---|---|---|
| <name> | <type> | <what it holds> | <required? unique? range? default? FK to …?> |

## States / lifecycle
<If it has a state machine: the states and the allowed transitions (a list or a small diagram).
Otherwise: "No lifecycle states.">

## Invariants
- <What must always be true of this entity — and where it's enforced (DB constraint / service rule).>
- …

## Relationships
- <relation> → `docs/ref/entities/<domain>/<other-entity>.md` (<cardinality, e.g. one-to-many>)
- …

## Owner
<Which feature or concern owns this entity's rules — link `docs/ref/features/<x>.md` or
`docs/spec/<concern>.md`.>
