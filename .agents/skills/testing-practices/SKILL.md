---
name: testing-practices
description: >-
  Apply when designing, writing, reviewing, or arguing about test strategy — backend, frontend, or E2E. Use for deciding what to test and where a test belongs (pytest vs. Vitest vs. Playwright), mocking strategy, whether a test earns its keep, or when reviewing a PR with tests. Bias toward applying it — testing is easy to get wrong.
---

# Testing Practices

One rule governs everything: **if I delete this test, would a real bug ever escape because it
is gone?** Yes → keep or write it. No, or you can't answer confidently → don't. Tests with no
plausible failure mode are theater.

Why the bar is set there: most real bugs live at integration boundaries — wiring, contracts,
real database behavior, real browser behavior — not inside pure functions. And when the same
agent writes both the code and its mocked unit tests, the tests inherit the code's assumptions
and blind spots: they pass together, fail together, and miss the same bugs. Tests against real
boundaries are much harder to fake into green.

Three corollaries:

1. **The mock-count smell.** A test that fakes more than one *meaningful* collaborator is
   probably testing fiction — move up a level to where the real wiring runs. One faked
   boundary (the API client, the OTP gateway) around real branching logic is fine.
2. **The regression exception.** Any past production bug deserves a permanent test, regardless
   of where the rules below would otherwise place it. Tag it with the bug id in the test name
   (the existing `CB-xx` convention) so nobody later "cleans it up".
3. **A gated test needs an executing home.** A `skipif`-gated test (env-var opt-in) must have
   a place that actually runs it — a CI step with the env set, at minimum. A test that never
   executes anywhere is documentation wearing a test's clothes; when adding one, wire up where
   it runs in the same change.

## Where a test goes in this repo

| Layer | Home | What belongs there |
|---|---|---|
| System / use-case (the foundation) | `backend/tests/` — pytest, real app via httpx `ASGITransport` | One test per business operation, called through the real HTTP entry point; assert response shape + persisted state. Handlers, services, repositories, wiring are all covered here — don't unit-test them separately. |
| Pure-logic unit | `backend/tests/` (pytest) · `web/src/**/__tests__/` (Vitest) | Only code that is pure (no I/O, framework, DOM, global state) **and** has branching or edge cases. |
| Browser journey | `e2e/tests/` — Playwright | One spec per user-facing flow, named by feature. Conventions (locators, web-first assertions, parallel safety, API seeding) are owned by `e2e/AGENTS.md`. |
| Manual verification pass | AGENTS.md → "verify like a user" | Layout, visual hierarchy, copy quality, keyboard/focus feel — what automation can't assert. Runs per change; derive release-audit scenarios from the feature docs + `web/DESIGN.md` on demand. |
| Static analysis | mypy `strict` · `vue-tsc` · ruff · ESLint | First-class tests; part of every check gate. Replaces the "did I pass the wrong shape" unit-test class. |
| Production observability | error monitor · structured logs · `X-Trace-ID` | The layer that catches what every offline suite misses. Treat a recurring monitored error as a failing test: fix it and add the regression test. |

**Database fidelity:** the system suite runs on in-memory SQLite by default — fast and
hermetic, but SQLite is not Postgres. Locking (`FOR UPDATE`), enum enforcement, and
transaction isolation differ. Behavior that depends on them belongs in the Postgres-gated
tests (`POSTGRES_CONCURRENCY=1` + a throwaway `DATABASE_URL`), and the whole suite can run
against real Postgres via `DATABASE_URL` when a change touches locking or constraints.

Don't duplicate across layers: a flow proven in Playwright doesn't need a mocked Vitest twin;
a route covered by a pytest system test doesn't need a handler unit test. If a store's logic
is unit-tested, the E2E journey still owns the end-to-end proof — keep both only when each
would catch a bug the other can't.

## Folder-by-folder verdicts

Match by **role**, not literal folder name.

**Backend**

| Folder role | Unit test? | Why |
|---|---|---|
| Domain logic, business rules, calculations | Yes | Pure, branching — exactly what unit tests are for |
| Validators, parsers, encoders | Yes | Pure, edge cases matter |
| State machines, workflow logic | Yes | Branching, regression-prone |
| Use cases / application services | No | System tests cover them; unit tests here mock everything |
| HTTP handlers, repositories, DI wiring, config | No | Wiring; system tests cover |
| Infrastructure adapters (S3, Telegram) | Contract test | Against a sandbox or wire-level fake — and wired to run in CI (corollary 3) |
| Middleware with logic (auth, rate limit) | Yes for the logic | Plus a system test end-to-end |
| Migrations | System test | Run them, assert resulting schema |

**Frontend**

| Folder role | Unit test? | Why |
|---|---|---|
| Utilities, formatters, parsers, validators | Yes | Pure functions, branches, locale edge cases |
| Pure composables / store getters | Yes | Pure transformations with branches |
| Stores / composables with real branching (batching, retry, error taxonomy, autosave) | Yes, faking only the API client | Logic, not wiring — `orders.spec.ts` batching is the model. Pure pass-through store actions: No, E2E covers |
| The shared API client | Yes for its logic | 401 refresh-retry, error mapping, query building are branching logic with regression ids (`CB-08`, `CB-98`, `CB-100`) — not a trivial wrapper. A wrapper without logic: No |
| Interactive primitives (dropdown, modal, tabs, inputs) | Yes for the keyboard/ARIA contract | Focus trap/return, `aria-*` state, key handling per `web/DESIGN.md` — Playwright covers these only incidentally. Caveat: jsdom simulates focus, it doesn't render; visual truth stays with the manual pass |
| Presentational components, pages, views | No | E2E + manual pass cover; mocked render tests pass while real bugs ship |
| Router guards | Yes for guard logic; no for route config | Declarative config has no behavior |
| i18n, types, constants | No | Static analysis is the test |

## Authoring heuristics

- Name tests by behavior (`creates_user_and_sends_otp`), not code structure.
- One test, one user-observable assertion; test through the public seam, never internals.
- Real dependencies beat mocks whenever fidelity is affordable.
- Failure messages must let a stranger diagnose the failure alone.
- Delete tests aggressively when they no longer map to a real failure mode — but a test
  carrying a bug id, or asserting a keyboard/ARIA contract, maps to one by definition.

## Anti-patterns to flag in review

Coverage as a goal · mocked-everything "integration" tests · asserting "method X was called"
instead of outcomes · a `*.test.ts` per wiring file · snapshot tests of component output ·
"every component has a test" (journeys have behavior; components don't — primitives' keyboard
contracts are the exception, not the license) · TDD with heavy mocks (both the code and its
tests ship the same bug) · a skipped-by-default test with no CI home.
