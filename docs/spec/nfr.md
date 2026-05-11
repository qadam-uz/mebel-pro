---
title: Non-functional requirements
status: stable
owner: shape
updated: 2026-05-11
order: 60
related:
  - docs/spec/envelope.md
  - docs/spec/architecture.md
  - docs/spec/access.md
---

# Non-functional requirements

The checklist of what the system must *be* — secure, traceable, recoverable, fast enough, usable.
Each line is a requirement; the **design that satisfies it** lives where it's linked (mostly
[`docs/spec/access.md`](access.md) for auth/authz/tenancy and [`docs/spec/architecture.md`](architecture.md) → *Data model invariants* for integrity). All of this follows from [`docs/spec/envelope.md`](envelope.md) — read it for the reasoning.

## Security & access posture — design & detail in [`docs/spec/access.md`](access.md)

- Three principal types, three auth surfaces; passwords are strong (hashed at rest, never plaintext)
  and brute-force-protected; Telegram OAuth payloads are integrity-checked.
- **Instant session revocation** — blocking a principal or a workshop, or "log out everywhere", takes
  effect immediately; a permission/scope change takes effect on the next request.
- **Multi-tenant isolation** — every read and every write is scoped to the authenticated principal at
  the service layer; client-supplied tenant ids are never trusted; cross-tenant access → `forbidden`.
  Workshop-staff capability is coarse-grained and per-branch; payment-channel merchant credentials
  are owner-visible only.
- **Transport** — production traffic is HTTPS, the certificate provisioned and renewed automatically
  at the edge ([`docs/spec/architecture.md`](architecture.md) → *Topology* / *Deployment*). The
  internal-only surfaces — the `/docs` site and the OpenAPI UIs — sit behind an extra HTTP Basic
  credential ([`docs/spec/architecture.md`](architecture.md) → *Cross-cutting concerns → Documentation site*).

## Audit & traceability — see [`docs/spec/architecture.md`](architecture.md) → *Cross-cutting concerns*

- Every mutating use case writes an append-only `action_log` row; every order status transition
  writes an append-only `status_change_log` row ([`docs/ref/entities/support/action-log.md`](../ref/entities/support/action-log.md)).
- Every API response carries `X-Trace-ID`; errors include `trace_id` in the body.

## Data integrity — see [`docs/spec/architecture.md`](architecture.md) → *Data model — shape & invariants*

Integer-tiyin money (never float); soft delete only (no `DELETE` for workshops / branches /
materials / workers / users — history kept forever); snapshot pricing and immutable cutting results;
append-only audit & status logs; optimistic-lock on order status transitions; atomic
reserve / consume / release on stock. (`architecture.md` states each invariant and why; [`docs/spec/orders.md`](orders.md) and [`docs/spec/cutting.md`](cutting.md) describe where they bite.)

## Availability, backup & retention

- Best-effort business-hours availability; no formal SLA. A single FastAPI process behind the Caddy
  edge; add replicas if load demands.
- **Backups:** nightly Postgres dump + WAL where the deployment supports it. **RPO ≤ 24 h, RTO ≤ 4 h.**
  Restores must be tested, not assumed. Object storage (MinIO/S3) provides its own durability/backup.
- **Retention:** operational data and the audit log are kept indefinitely in v1 (no purge job). Draft
  cutting results are the exception — pruned after 7 days. Expired session rows are pruned by a job.

## Performance budgets

- API reads: p95 < 500 ms under expected load.
- Cutting optimization: **5 s hard timeout**, synchronous; > 100 parts rejected; ≤ 30 parts target
  < 1 s. PDF generation: synchronous, in-process; seconds, not minutes.
- Background jobs run daily on the in-process scheduler ([`docs/ref/features/platform-ops.md`](../ref/features/platform-ops.md)).

## Observability

- Structured logging (structlog) with the trace id on every line. Health: `GET /api/v1/healthz`
  (liveness), `GET /api/v1/readyz` (DB check). The `platform` error monitor records application
  errors with code, count, last occurrence — surfaced in the superadmin app ([`docs/ref/features/platform-ops.md`](../ref/features/platform-ops.md)).

## Internationalization

- v1 ships **Uzbek only**. Strings are namespaced so adding `ru` / `en` is mechanical. Money, dates,
  phones (`+998XXXXXXXXX`), and dimensions (millimetres) have fixed display conventions.

## Accessibility

- Keyboard-operable, visible focus, AA contrast, color never the only signal, labels on every input,
  designed empty/loading/error states — per the **ui-ux-mastery** discipline; see [`docs/ref/ux/components.md`](../ref/ux/components.md).
