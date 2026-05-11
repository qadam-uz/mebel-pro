---
title: Open questions
status: stable
owner: shape
updated: 2026-05-11
order: 90
related:
  - docs/spec/scope-v1.md
  - docs/spec/access.md
---

# Open questions

What's unsettled, who owns it, and the concrete trigger that should make us revisit. None of these
**block** the v1 build — they're scoped out of v1 deliberately and parked here so they aren't
re-litigated by accident.

| # | Question | Owner | Revisit when |
|---|---|---|---|
| Q1 | **Delegating workshop-wide permissions to non-owner staff.** v1 keeps `manage_branches` / `manage_pricing` / `manage_settings` / `view_reports` and user management owner-only ([`docs/spec/access.md`](access.md)). Should a workshop be able to grant these to a "branch manager" staff user? | shape | When a workshop with > ~5 staff per branch asks for it, or when an owner reports being a bottleneck for pricing/branch edits. |
| Q2 | **Payment gateway integration** (Payme / Click / Uzum Bank) and the `pending_payment` → gateway-redirect flow. The seams exist (payment-channel flags + credentials are stored; `order_payment.method` has gateway values reserved); v1 records payments manually ([`docs/spec/scope-v1.md`](scope-v1.md)). | shape | v1.1 planning, or when a workshop has a live merchant account ready. |
| Q3 | **BNPL** (Uzum Nasiya / Alif Nasiya): the `bnpl` payment option, provider redirect, callback, auto-cancel on rejection. | shape | After Q2 (gateways) is in; or when a workshop signs a BNPL contract. |
| Q4 | **Automatic refunds** via gateway reverse webhooks, replacing the manual offline + record flow. | shape | After Q2. |
| Q5 | **SMS / email channels** and the **Telegram notification bot** for client notifications. v1 is in-app only. | shape | v1.1; or when client engagement metrics show the in-app-only inbox isn't read. |
| Q6 | **Geocoding / maps** for delivery addresses and **distance-based delivery pricing**, replacing manual lat/lng + static fixed-fee zones. | shape | When a workshop's delivery area outgrows hand-maintained zones. |
| Q7 | **Cutting: top-N alternatives, async mode for > 100 parts, operator manual layout edits, per-branch kerf/edge-trim, multiple sheet sizes per material, `preferred` grain.** v1 is single-best, synchronous ≤ 100 parts, algorithm-only, global kerf/trim, one sheet size, `any`/`required` grain only. | shape | When a workshop reports the 100-part cap or the single-result limitation is blocking real jobs. |
| Q8 | **Order: batching, reorder, templates, partial fulfilment, complaint/return after `completed`, client ratings/feedback.** | shape | v1.1+ backlog grooming. |
| Q9 | **Multi-currency.** v1 is UZS only; money is integer tiyin throughout. | shape | If the platform expands beyond Uzbekistan. |
| Q10 | **Filevault delivery via presigned URLs** (vs streaming through the API) for receipt/PDF/image download, and ETag caching. | build | When file traffic shows the streaming path is a bandwidth concern. |
| Q11 | **A real notifications producer model** — should producing modules emit domain events the `notifications` module subscribes to, or call it directly? v1: producing modules call `notifications` directly. | build | When the number of notification-producing call sites makes direct calls hard to keep consistent. |
| Q12 | **Force-cancel and refund-revert as a delegable permission** rather than owner-only. v1: owner-only carve-out of `manage_orders`. | shape | If owners report being a bottleneck for exceptional cancellations. |
