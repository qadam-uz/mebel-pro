---
title: <Bounded context name — e.g. Sales, Catalog, Inventory>
status: draft
owner: shape
updated: <YYYY-MM-DD>
# order: <int>
---

# <Bounded context name>

<One-paragraph framing of what this context owns — link the doc that holds the normative
rules (the feature page that owns the domain — e.g. `docs/ref/features/orders.md` for sales —
or a canon doc like `docs/access-patterns.md`), and tell the reader where to look for those
rules vs. the field shapes they're about to see.>

<!--
This file is the single home for the entities of one bounded context — NOT one entity per
file. Each entity below gets an H2 (## <Entity name>), and inside the H2 the four fixed sections
in this order: What it is · Fields · States / lifecycle · Invariants. Cross-reference other
entities in this same page with an anchor link (`#order-payment`), and entities in another
context by `docs/ref/entities/<other-context>.md#entity-name`. No "Relationships" section — the
relationships are obvious from the field types and `docs/domain-model.md`'s entity map. No
"Owner" section — the rules live in the feature page (or canon doc) this page's framing
paragraph links to.
-->

## <Entity name>

<One or two sentences — the concept this represents in the business.>

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `<name>` | `<type>` | <required? unique? FK to …? default?> |

Lifecycle: <if it has a state machine, the states and the allowed transitions in a short
paragraph or a tiny diagram; otherwise omit this paragraph>.

Invariants: <one paragraph of "what must always hold," each clause naming where it's enforced
(DB constraint / service rule). Keep it tight; ~5 invariants is plenty.>

## <Next entity name>

<…repeat the same four blocks…>
