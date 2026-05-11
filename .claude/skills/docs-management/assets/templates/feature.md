---
title: <Feature name>
status: draft
owner: shape
updated: <YYYY-MM-DD>
# order: <int>          # optional — position within ref/features/ in the nav
related:
  - docs/spec/scope-v1.md
---

# <Feature name>

## Problem
<What's broken or missing, and for whom. The user pain — not the solution.>

## User stories
- As a <role>, I want <capability> so that <outcome>.
- …

## Requirements
1. <Functional requirement — numbered so the build pipeline can reference it.>
2. …

## UX
<The interface design for this feature: the key flows, screen states, and primary screens.
Link `docs/ref/ux/information-architecture.md` and `docs/ref/ux/components.md` for cross-cutting
patterns rather than restating them. Diagrams → `docs/assets/`, referenced by relative path.>

## Entities touched
- `docs/ref/entities/<domain>/<entity>.md` — <how this feature uses or changes it>
- …

## Edge cases
- <The awkward case> → <what should happen>
- …

## Out of scope
- <What this feature explicitly does not do — name it so it doesn't creep in.>
- …

## Open questions
- <Question> — owner: <who> — <if it blocks the build, also list it in docs/spec/open-questions.md>
- …
