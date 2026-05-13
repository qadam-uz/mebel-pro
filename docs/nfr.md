---
title: Non-functional requirements
status: draft
owner: shape
updated: 2026-05-13
order: 60
---

# Non-functional requirements

The checklist of what the system must *be* — secure, traceable, recoverable, fast enough, usable.
Each line is a requirement; the **design that satisfies it** lives in [`access.md`](access.md)
(auth / authz / tenancy) and [`architecture.md`](architecture.md) (the operating envelope, the
data-model invariants, the API surface).

## Security & access posture

- Three principal types, three auth surfaces; passwords are strong (hashed at rest, never
  plaintext) and brute-force-protected; Telegram OAuth payloads are integrity-checked.
- **Instant session revocation** — blocking a principal or a workshop, or "log out everywhere",
  takes effect immediately; a permission/scope change takes effect on the next request.
- **Multi-tenant isolation** — every read and every write is scoped to the authenticated principal
  at the service layer; client-supplied tenant ids are never trusted; cross-tenant access →
  `forbidden`. Workshop-staff capability is coarse-grained and per-branch; payment-channel merchant
  credentials are owner-visible only.
- **Transport** — production traffic is HTTPS, the certificate provisioned and renewed
  automatically at the edge. The internal-only surfaces — the `/docs` site and the OpenAPI UIs —
  sit behind an extra HTTP Basic credential.

## Audit & traceability

- Every mutating use case writes an append-only `action_log` row; every order status transition
  writes an append-only `status_change_log` row.
- Every API response carries `X-Trace-ID`; errors include `trace_id` in the body.

## Data integrity

Integer-tiyin money (never float); soft delete only (no `DELETE` for workshops / branches /
materials / workers / users — history kept forever); snapshot pricing and immutable cutting
results; append-only audit & status logs; optimistic-lock on order status transitions; atomic
reserve / consume / release on stock.

## Availability, backup & retention

- Best-effort business-hours availability; no formal SLA. A single FastAPI process behind the Caddy
  edge; add replicas if load demands.
- **Backups:** nightly Postgres dump + WAL where the deployment supports it. **RPO ≤ 24 h,
  RTO ≤ 4 h.** Restores must be tested, not assumed. Object storage (MinIO/S3) provides its own
  durability/backup.
- **Retention:** operational data and the audit log are kept indefinitely in v1 (no purge job).
  Draft cutting results are the exception — pruned after 7 days. Expired session rows are pruned
  by a job.

## Performance budgets

- API reads: p95 < 500 ms under expected load.
- Cutting optimization: **5 s hard timeout**, synchronous; > 100 parts rejected; ≤ 30 parts target
  < 1 s. PDF generation: synchronous, in-process; seconds, not minutes.
- Background jobs run daily on the in-process scheduler.

## Observability

- Structured logging (structlog) with the trace id on every line. Health: `GET /api/v1/healthz`
  (liveness), `GET /api/v1/readyz` (DB check). The `platform` error monitor records application
  errors with code, count, last occurrence — surfaced in the superadmin app.

## Internationalization

- v1 ships **Uzbek only**. Strings are namespaced so adding `ru` / `en` is mechanical. Money,
  dates, phones (`+998XXXXXXXXX`), and dimensions (millimetres) have fixed display conventions.

## Accessibility

- Keyboard-operable, visible focus, AA contrast, color never the only signal, labels on every
  input, designed empty/loading/error states. The full design system + accessibility baseline are
  in [`web/DESIGN.md`](../web/DESIGN.md).

## Next

[`access.md`](access.md) — the auth, authz, and tenancy rules every feature obeys.
