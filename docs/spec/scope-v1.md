---
title: Scope — v1
status: stable
owner: shape
updated: 2026-05-11
order: 20
related:
  - docs/spec/vision.md
  - docs/spec/envelope.md
  - docs/spec/orders.md
  - docs/spec/open-questions.md
---

# Scope — v1

v1 is **the smallest system a real workshop and a real customer can use end to end**. The "out" list
below carries as much weight as the "in" list — and where v1 substitutes a manual path for an
integration (payments, refunds), the *why* and the v1.1 plan are here.

## In scope

**Identity & access** ([`docs/spec/access.md`](access.md))

- Platform operators provision workshops and their first owner ([`docs/ref/features/workshop-provisioning.md`](../ref/features/workshop-provisioning.md)).
- Workshop owners create workshop staff and grant them coarse, per-branch permissions ([`docs/ref/features/workshop-user-management.md`](../ref/features/workshop-user-management.md)).
- Clients self-register on demand via Telegram OAuth ([`docs/ref/features/client-onboarding.md`](../ref/features/client-onboarding.md)).
- Opaque, DB-backed sessions; instant revocation; brute-force lockout for password logins.
- Multi-tenant data isolation enforced at the service layer on every read & write.

**Workshop modelling** ([`docs/spec/access.md`](access.md) for the tenancy rules)

- Branches with status (`active` / `temporarily_closed` / `inactive`) ([`docs/ref/features/branch-management.md`](../ref/features/branch-management.md)).
- Per-branch material catalog with images ([`docs/ref/features/material-catalog.md`](../ref/features/material-catalog.md)).
- Per-branch warehouse: stock-in, adjust, view, branch-to-branch transfer; automatic reserve / consume / release driven by orders ([`docs/ref/features/inventory-management.md`](../ref/features/inventory-management.md)).
- Per-branch workers (cutter / driver / assembler — not system users) ([`docs/ref/features/worker-management.md`](../ref/features/worker-management.md)).
- Per-branch cutting & edge-banding pricing ([`docs/ref/features/branch-pricing.md`](../ref/features/branch-pricing.md)).
- Workshop settings: delivery on/off, static delivery zones with fees, payment-channel flags & merchant credentials (stored, **inert in v1** — see below), default advance %, currency (UZS).

**Cutting** ([`docs/spec/cutting.md`](cutting.md), [`docs/ref/features/cutting-optimization.md`](../ref/features/cutting-optimization.md))

- 2D guillotine optimization (FFD + recursive guillotine splitting) — synchronous, ≤ 100 parts, 5 s.
- Sheet layouts, waste %, sheets used, cut length, edge-banding length by thickness; PDF cutting map; client-side SVG.
- Cutting result lifecycle: `draft → confirmed → invalidated`; 7-day draft cleanup.

**Orders** ([`docs/spec/orders.md`](orders.md))

- Client-only order creation from a cutting draft ([`docs/ref/features/order-placement.md`](../ref/features/order-placement.md)); material source `own` / `shop`; pickup / delivery.
- Snapshot pricing (every component frozen at order time); re-pricing on modify ([`docs/ref/features/order-modification.md`](../ref/features/order-modification.md)).
- Workshop order workflow: status transitions, discount (mandatory reason), pay-later approval, driver assignment, recording cash/bank payments, advance + balance ([`docs/ref/features/order-fulfillment.md`](../ref/features/order-fulfillment.md)).
- Cancellation + **manual** refund tracking ([`docs/ref/features/order-cancellation-and-refunds.md`](../ref/features/order-cancellation-and-refunds.md)).

**Cross-cutting**

- File storage (MinIO/S3): material images, workshop logo, refund/delivery receipts, cutting PDFs.
- Audit log: every mutating action + every order status change ([`docs/ref/features/audit-log.md`](../ref/features/audit-log.md)).
- In-app notifications inbox ([`docs/ref/features/notifications-inbox.md`](../ref/features/notifications-inbox.md)).
- Platform ops: scheduled-jobs console, error monitor ([`docs/ref/features/platform-ops.md`](../ref/features/platform-ops.md)); background jobs (expire stale draft cuttings, notify pay-later overdue, notify stale refunds, prune expired sessions, daily low-stock summary).

## Out of scope (v1) — explicit

- **Online payment gateways** (Payme, Click, Uzum Bank) and **BNPL** (Uzum Nasiya, Alif Nasiya) —
  **v1.1**. In v1, payments are **recorded** manually by workshop staff (cash / bank transfer) and
  refunds are moved offline and recorded ([`docs/spec/orders.md`](orders.md)). *Why:* each gateway is
  a non-trivial integration — merchant account, vendor SDK, sandbox, signature verification, callback
  handling — and a real workshop already takes payment at the counter, so recording that is a genuine
  substitute, not an artificial one; the order/refund model, the dashboard, and the SLA views all
  work without it. *The v1.1 plan:* light up `initiate-payment` + the `pending_payment → gateway
  redirect` flow, add the signed webhook handler (idempotent on the external ref) — the data model
  already keeps the seams: `order_payment.method` reserves the gateway values, the workshop settings
  hold the (inert) merchant credentials, the order has a `pending_payment` state and a
  `reserve_status` field. Then BNPL; then automatic refunds (gateway reverse webhooks). See
  [`docs/spec/open-questions.md`](open-questions.md) Q2–Q4.
- **SMS / email channels**, **a Telegram notification bot** — v1.1; v1 is **in-app only** (the client
  is reached in-app on the order page; Telegram is sign-in only). [`docs/spec/open-questions.md`](open-questions.md) Q5.
- **Geocoding / maps** for delivery addresses, and **distance-based delivery pricing** — v1 takes
  manual lat/lng and uses static, workshop-entered fixed-fee zones. Q6.
- **Delegating workshop-wide capabilities** (branches, pricing, settings, reports, user management,
  branch transfers, force-cancel, refund-revert) to non-owner staff — v1: owner-only. Q1, Q12.
- **Operator-created orders** — orders are client-only, always.
- **Cutting:** top-N alternative results, async mode for > 100 parts, operator manual layout editing,
  per-branch/per-material kerf & edge-trim, multiple sheet sizes per material, `preferred` grain,
  custom sheet sizes for `own` material, 3D nesting, CNC router paths — out / v1.1+. Q7.
- **Order:** batching, reorder, templates, partial fulfilment, complaint/return after `completed`,
  client ratings/feedback — v1.1+. Q8.
- **Multi-currency** — v1 is UZS only (money is integer tiyin throughout). Q9.
- **Filevault presigned-URL delivery** (vs streaming) — v1 streams through the API. Q10.
- **Multi-org admins, branch-level settings overrides, supplier management, auto purchase orders,
  remnant tracking, barcode/QR scanning** — future.

These slots stay as labelled placeholders in the UI so the layout doesn't shift when v1.1 lights
them up.
