---
title: Operating envelope
status: stable
owner: shape
updated: 2026-05-11
order: 50
related:
  - docs/spec/architecture.md
  - docs/spec/nfr.md
  - docs/spec/scope-v1.md
---

# Operating envelope

The system's situation, on five axes — and the **"not built for"** line. Design to the level each
axis demands, no higher, no lower. ADRs ([`docs/spec/`]()) reason from this
envelope; if the envelope changes, revisit them.

## Tier

**Tier 2 — internal/business application.** A multi-tenant SaaS for a modest population of furniture
workshops and their customers. Not a throwaway tool; not a high-traffic consumer product; not (yet)
a high-assurance/regulated system — but it does move money, so one axis (criticality) gets real
rigor.

## The five axes

| Axis | Where we are | Consequence |
|---|---|---|
| **Scale + trajectory** | Tens of workshops, low hundreds of branches, low thousands of clients, low tens of thousands of orders/year. Flat-to-modest growth — no viral curve. Read-heavy; the heaviest single op is cutting optimization (≤ 100 parts, synchronous, 5 s budget). | A single Postgres, a single FastAPI process (scale out replicas if ever needed), no sharding, no caching layer until something is *measured* slow. Design for today. |
| **Criticality / blast radius** | Orders carry money (advance/balance, refunds) and reserve real warehouse stock. A wrong refund or a double-charge is real harm. Stock counts back-real inventory. Nothing legal/regulatory; no auditor inspects the data. | **Money in integer tiyin, never float.** Reserve/consume/release is atomic (row-lock the stock row). Every mutating action and every order status change is written to an append-only audit log. Webhook-style ingestion (none in v1, but the seam exists) is idempotent. Refunds are manual and require a bank-reference note — the system *tracks*, it doesn't *move* money in v1. |
| **Security & privacy** | Public on the internet. Holds: personal data (names, phones, Telegram IDs of clients), workshop staff credentials, workshop payment-gateway credentials (stored, unused in v1), refund receipts. Worth attacking for the stored credentials. | Hard authn/authz on every request; opaque DB-backed sessions with instant revocation; password hashing (argon2/bcrypt) + brute-force lockout; payment credentials visible only to the workshop owner; multi-tenant data isolation enforced at the service layer on *every* read and write; untrusted input (cutting dimensions, Telegram OAuth payloads) validated and signature-checked. |
| **Latency / performance** | Back-office-ish. Page loads in "a second or two" are fine. The one user-visible expensive operation is cutting optimization — bounded at 5 s synchronous; bigger jobs are rejected, not queued (v1). | No async/queue on the hot path; cutting runs in-process within its time budget. Background jobs (cleanup, overdue/stale notifications) run on an in-process scheduler, not a separate worker fleet. |
| **Lifespan × churn × team** | Intended to run for years; moderate change rate; a small team. | A **modular monolith** (one FastAPI app, business modules inside it), not microservices — see [`docs/spec/architecture.md`](architecture.md). Boring, widely-known tech (FastAPI, SQLAlchemy, Postgres, Vue, Tailwind). Structure that a two-person team can operate at 3 a.m. No portal/embassy ceremony, no per-module hexagonal layering — modules are Python packages that call each other through their service layer. |

## Not built for

- **High traffic.** No multi-region, no read-replica routing, no aggressive caching, no CDN for app
  data. If a tenant brings 100× the expected order volume, capacity work happens *then* — it is not
  pre-built.
- **Regulatory/audit-grade guarantees.** The audit log is append-only and useful, but the system is
  not designed to answer "prove the exact state on date X" to a regulator, nor to retain data under
  a legal-hold regime. No tamper-evidence beyond append-only rows.
- **Real-money movement in v1.** No gateway integration, no automatic refunds, no settlement
  reconciliation. Money changes hands offline; the system records it. (The seams exist for v1.1.)
- **Offline / unreliable-network operation.** It's a web app talking to an API; it assumes
  connectivity.
- **Heavy analytics / BI.** Dashboards are simple aggregates over the operational DB, not a
  warehouse.

## Per-module exceptions

- **Cutting** — the only module with a hard latency/correctness budget on a *synchronous* path
  (≤ 100 parts, 5 s). Results are immutable snapshots; the algorithm may be replaced without
  touching past results ([`docs/spec/cutting.md`](cutting.md)).
- **Orders** — the highest-criticality module: idempotent ingestion seams, optimistic-lock on
  status transitions, atomic stock reserve, append-only status history, mandatory reasons on
  cancel/refund/force-cancel.
- **Identity** — the highest-security module: opaque sessions, instant revocation, brute-force
  lockout, owner-only sight of payment credentials.
