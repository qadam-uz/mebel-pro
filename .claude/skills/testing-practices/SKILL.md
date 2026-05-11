---
name: testing-practices
description: Apply this skill when designing, writing, reviewing, or arguing about test strategies — backend, frontend, or end-to-end — in any language or framework. Use it whenever the user asks about the test pyramid, what to unit test versus integration test, why tests pass but bugs reach production, how to organize test folders, what to test in agent-driven development, when E2E tests are worth writing, mocking strategy, TDD outcomes, test naming, or how to decide whether a specific test is worth keeping. Also trigger when reviewing a pull request that contains tests, planning a CI test suite, debating mocks versus real dependencies, choosing between Playwright/Cypress/component tests, structuring `tests/` directories, or evaluating coverage metrics — even when the user does not explicitly say "testing strategy." Bias toward applying this skill, since testing decisions are easy to get wrong by default.
---

# Testing Practices

A framework-agnostic approach to deciding what to test, where, and why, built around a single rule: **every test must answer "would deleting this let a real bug through?"**

## Core Philosophy

The classical test pyramid (many unit tests, few E2E) was a cost optimization for an era when E2E tests were slow, flaky, and expensive. Modern tooling has changed those economics, but more importantly: unit tests with heavy mocks rarely catch the bugs that actually reach production. Most real bugs live at integration boundaries — wiring, contracts, real database behavior, real browser behavior, concurrency, deployment environments. Tests below that level verify the developer's mental model, not the system's actual behavior.

This is sharper in agent-driven development. When an LLM writes both the code and its unit tests, the tests inherit the same assumptions and blind spots as the code. They pass together, fail together, and miss the same bugs. Tests that run against real boundaries (real HTTP, real DB, real browser) are much harder to fake into green.

The prescription is not "no unit tests." It is **no test that does not justify its existence**.

## The Universal Decision Rule

For any test under consideration, answer:

> **If I delete this test, would a real bug ever escape because it is gone?**

If yes → keep or write it.
If no, or you cannot answer confidently → do not write it. Tests with no plausible failure mode are theater.

Two corollaries:

1. **The mock-count smell.** If a test requires mocking more than one collaborator, it is probably testing fiction. Move up a level — to system, integration, or E2E — where the real wiring runs.
2. **The regression exception.** Any past production bug deserves a permanent test, regardless of whether the unit-vs-system rules would otherwise place it.

## The Recommended Shape (Inverted Pyramid)

A modern, defensible suite looks like this:

- **Foundation: system / use-case / E2E tests.** Real boundaries. One test per user-observable behavior or use case. Most of the testing effort lives here.
- **Layer above: pure-logic unit tests.** Branching algorithms, parsers, validators, formatters, business rules. Fast, cheap, and they fail honestly when logic breaks.
- **Layer above: contract tests.** At every external boundary — third-party APIs, your own API consumed by another team, generated SDKs, message schemas.
- **Continuous: static analysis.** Strict type checking, lint rules, schema validation. The cheapest tests in the suite.
- **Production: observability.** Error tracking, structured logs, traces, feature flags, canary deploys, session replay. Catches the long tail no offline suite can.

What is deliberately missing or de-emphasized: most "component tests," most service-layer unit tests, and most mocked-everything integration tests. Their bug-catching ratio per maintenance hour is too low to justify their cost.

## Backend Test Layers

### System tests (the foundation)

Organize one test per **use case** — a business-level operation the system performs (`create-user`, `refresh-token`, `transfer-funds`, `process-order`). Each test:

- Starts the real application (in-process or as a subprocess)
- Calls the real entry point (HTTP, gRPC, message queue, CLI) — not internal functions
- Uses real or near-real dependencies: containerized database, real cache, real message broker
- Asserts user-observable outcomes: response shape, persisted state, emitted events, side effects

Different communities call these "subcutaneous tests," "component tests" (microservices sense), "acceptance tests," or "service-level tests." Pick one name and use it consistently. **Prefer names that signal intent (`usecase/`, `acceptance/`) over names that signal layer (`system/`, `integration/`)** — folder names act as instructions, especially to coding agents.

### Unit tests (selective)

Write a unit test when **all** of the following hold:

- The code is pure (no I/O, no framework dependencies, no global state)
- It has branching logic, edge cases, or non-trivial transformation
- A bug in it would not be caught by any system test, or would only be caught at the cost of expensive debugging

Typical good targets: domain calculations, validation rules, parsers, encoders/decoders, complex query builders, state machine transitions, pricing/permission/policy logic.

Do **not** write unit tests for: HTTP/gRPC handlers, repositories that just call the DB, application services that orchestrate other services, dependency-injection wiring, configuration loaders, simple CRUD passthroughs. These are wiring — system tests cover them, and unit tests for them either mock everything (useless) or duplicate the system test (wasteful).

### Contract tests

If your service calls external APIs or is called by external clients, add contract tests at those boundaries — Pact, schema diffing, OpenAPI conformance, or a small set of real calls against a sandbox. They catch the bug class system tests cannot: "the other side changed."

## Frontend Test Layers

### E2E tests (the foundation)

Organize tests by **user journey**, not by page or component. A journey is a complete path a real user takes (sign up → verify → first action; search → filter → purchase; create → edit → publish). Each test:

- Runs in a real browser
- Hits the real or staging backend, or a high-fidelity network-level mock
- Interacts via user-visible affordances (roles, labels, visible text) — not test IDs or component internals where avoidable
- Asserts user-observable outcomes

Modern browser-automation tools have largely eliminated the historical "E2E is too flaky / too slow" objection. Auto-waiting, parallelization, trace viewers, and network interception make these stable enough to be the **primary** layer.

### Unit tests (selective)

Same rule as backend: pure logic only. On the frontend that typically means:

- Formatters (date, currency, number, address)
- Parsers and validators
- Pure utility and helper functions
- Pure store getters / reducers / selectors
- Pure custom hooks / composables (no network, no router, no global state, no DOM)
- Complex form-validation rule sets
- Pure routing-guard logic

Do **not** write unit tests for: UI components, pages, route components, API clients, store actions that just call APIs, providers/contexts, i18n wiring, plugins or directives without logic. The framework-rendering test with stacked mocks (router + store + i18n + queries) is the canonical example of a test that passes while real bugs ship.

### Static analysis as a first-class test

Strict type checking is the highest-leverage test on the frontend. Treat it as part of the test suite, non-negotiable in CI. It replaces the entire class of "did I pass the wrong shape" unit tests that frontend teams historically wrote by hand.

### Visual regression (when appearance matters)

E2E tests verify behavior, not appearance. If layout, spacing, or visual fidelity matters to the product, add visual regression on critical screens — screenshot diffing, hosted services, or built-in browser-automation screenshots all work.

### Contract tests against the backend

If frontend and backend are separate codebases or teams, generate the API client from a schema (OpenAPI, GraphQL SDL, gRPC) and let the type system enforce the contract. If generation is not possible, write a small set of contract tests that hit a real backend and assert the response shapes the frontend depends on.

## Folder-by-Folder Verdicts

Apply the decision rule to common folder roles. The names below are illustrative — match by **role**, not by literal folder name.

### Backend

| Folder role                                  | Unit test?    | Why                                                                 |
| -------------------------------------------- | ------------- | ------------------------------------------------------------------- |
| Domain logic, business rules, calculations   | Yes           | Pure, branching, exactly what unit tests are for                    |
| Validators, parsers, encoders                | Yes           | Pure, edge cases matter                                             |
| State machines, workflow logic               | Yes           | Branching, regression-prone                                         |
| Use cases / application services             | No            | System tests cover them; unit tests here mock everything            |
| HTTP / gRPC / queue handlers                 | No            | Wiring; system tests cover                                          |
| Repositories / data access                   | No            | Test against real DB in system tests; mocked repo tests are fiction |
| Infrastructure adapters (email, S3, payment) | Contract test | Test against a sandbox or wire-level fake                           |
| Configuration, DI wiring, bootstrap          | No            | Wiring; a system test that covers startup is enough                 |
| Middleware with logic (auth, rate limit)     | Yes for logic | Plus a system test that exercises it end-to-end                     |
| Migrations                                   | System test   | Run them, assert resulting schema and data                          |

### Frontend

| Folder role                                           | Unit test?                             | Why                                                |
| ----------------------------------------------------- | -------------------------------------- | -------------------------------------------------- |
| Utilities, lib, helpers                               | Yes                                    | Pure functions, branches                           |
| Formatters, parsers                                   | Yes                                    | Locale and edge cases                              |
| Validators, schemas                                   | Yes                                    | Rules have branches                                |
| Domain / business logic                               | Yes                                    | Top priority if it exists                          |
| Composables / hooks (pure)                            | Yes                                    | If no network/router/store/DOM                     |
| Composables / hooks (wrapping queries, router, store) | No                                     | Wiring; E2E covers                                 |
| Store getters / reducers / selectors (pure)           | Yes                                    | Pure transformations with branches                 |
| Store actions / effects (calling APIs)                | No                                     | Wiring; E2E covers                                 |
| Design-system primitives (Button, Input, Modal)       | No (use Storybook + visual regression) | No behavior worth unit-testing                     |
| App-level components                                  | No                                     | E2E covers; unit tests here are theater            |
| Pages, views, route components                        | No                                     | Pure wiring                                        |
| API clients / services                                | Generate from schema or contract test  | Don't unit-test fetch wrappers                     |
| Router config / guards                                | Yes for guard logic; no for routes     | Logic deserves a test, declarative config does not |
| Plugins, directives                                   | Yes for the logic; no for wiring       |                                                    |
| i18n, types, constants                                | No                                     | Static analysis is the test                        |

## Authoring Heuristics

When writing or reviewing a test:

- **Name tests by behavior, not by code structure.** `creates_user_and_sends_verification_email` beats `UserService.createUser_test_case_1`.
- **One test, one user-observable assertion.** Multi-step setup is fine; multi-purpose assertions are not.
- **Test through the public seam.** If a test reaches into internals (private methods, component state, framework lifecycle), it will break on every refactor and rarely catch real bugs.
- **Real dependencies beat mocks whenever fidelity is affordable.** Containers, ephemeral test environments, and in-memory equivalents (only when behavior is genuinely equivalent) are usually worth the setup cost.
- **Failure messages are part of the test.** A test that fails with "expected true, got false" is half-broken. Assert with enough context that a stranger can diagnose the failure alone.
- **Delete tests aggressively.** A green suite is worthless if half of it tests fiction. When a test no longer maps to a real failure mode, remove it.

## Production Observability is Part of the Test Strategy

No offline suite catches everything. Treat production as the final test environment:

- **Error tracking** with stack traces, breadcrumbs, user context — catches bugs no test will
- **Structured logs and traces** — let you reconstruct what happened without reproducing
- **Feature flags** — make rollouts reversible; failed experiments aren't outages
- **Canary / staged deploys** — let a fraction of traffic find the bug before everyone does
- **Frontend session replay** — catches "the UI did something weird" bugs no assertion can predict
- **Synthetic monitoring** — periodic real E2E runs against production for the critical journeys

Budget for these the same way you budget for tests. In agent-driven development, where code velocity outpaces test-suite curation, production signals become the dominant feedback loop.

## When the User Asks "Should I Write This Test?"

Walk the decision flow:

1. Is the file's code pure (no I/O, no framework, no network, no DOM, no global state)? If no → it is system/E2E territory, not unit.
2. Does the code have branching, edge cases, or non-trivial logic? If no → there is nothing to test.
3. Would deleting the proposed test let a real bug through? If you cannot answer yes confidently → do not write it.
4. Has this area had a production bug before? If yes → write a regression test regardless of the above.

If the user is asking because a system or E2E test would be expensive to write, the answer is usually still "write the system test." Cheap unit tests that do not catch real bugs are **negative-value** — they create maintenance load and false confidence.

## Anti-Patterns to Flag

When reviewing a test strategy, file, or PR, surface these:

- **Coverage as a goal.** Coverage measures executed lines, not caught bugs. High coverage with mocked dependencies is the canonical false-confidence trap.
- **Mocked-everything "integration" tests.** If the test mocks the DB, the cache, the queue, and the HTTP client, it is a unit test wearing makeup.
- **Tests that assert implementation, not behavior.** Asserting "method X was called with arguments Y" instead of asserting the user-visible outcome locks the implementation in place and catches nothing real.
- **Per-file test files for wiring.** A `UserController.test.ts` next to `UserController.ts` that mocks the service layer is almost always wasted code.
- **TDD with heavy mocks.** TDD is a design tool. With mocks, it designs the test to match the code's assumptions, then both ship the same bug together. Use TDD with real or near-real dependencies, or accept that the resulting tests are documentation, not safety.
- **"Every component has a test."** Components do not have behavior worth unit-testing in isolation. Journeys do.
- **Snapshot tests for component output.** They fail on every change, get rubber-stamped, and catch almost nothing.

## Closing Note

The honest pyramid is shaped by **where bugs live**, not where tests are cheap. For most modern systems, bugs live at integration boundaries — between code and DB, code and browser, frontend and backend, code and its deployment environment. Test there first, hardest, and most. Drop down to unit tests only for pure logic that genuinely deserves isolation. Trust production observability for the rest. Everything else is overhead — and overhead that creates false confidence is worse than no test at all.
