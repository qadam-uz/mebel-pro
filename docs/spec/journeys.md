---
title: Journeys
status: stable
owner: shape
updated: 2026-05-11
order: 40
related:
  - docs/spec/personas.md
  - docs/spec/orders.md
  - docs/ref/features/workshop-provisioning.md
  - docs/ref/features/order-placement.md
  - docs/ref/features/order-fulfillment.md
---

# Journeys

The end-to-end flows that span features. Single-feature flows live in the feature spec; these are
the ones that cross several. Each step links the feature that owns it.

## J1 — Workshop onboarding (platform operator + workshop owner)

1. Platform operator creates a **workshop** + its first **owner** user (one action, atomic) →
   [`docs/ref/features/workshop-provisioning.md`](../ref/features/workshop-provisioning.md). Owner gets a temporary password and `force_password_change`.
2. Owner logs into the **seh** app → forced password change → in.
3. Owner creates **branches** → [`docs/ref/features/branch-management.md`](../ref/features/branch-management.md).
4. Owner adds **materials** per branch (with images) → [`docs/ref/features/material-catalog.md`](../ref/features/material-catalog.md).
5. Owner records opening **stock** (stock-in) per material → [`docs/ref/features/inventory-management.md`](../ref/features/inventory-management.md).
6. Owner sets **pricing** (cutting model + edge-banding rates) per branch → [`docs/ref/features/branch-pricing.md`](../ref/features/branch-pricing.md).
7. Owner adds **workers** per branch → [`docs/ref/features/worker-management.md`](../ref/features/worker-management.md).
8. Owner creates **staff** users and grants per-branch permissions → [`docs/ref/features/workshop-user-management.md`](../ref/features/workshop-user-management.md).
9. Owner reviews **workshop settings** — delivery on/off, delivery zones + fees, payment-channel
   flags (stored, inactive in v1), default advance % → part of workshop-provisioning's settings.
10. The branch is now visible to clients and ready to take orders.

Branches: `docs/ref/entities/workshop/branch.md`. Materials moved through it: `docs/ref/entities/catalog/material.md`, `docs/ref/entities/inventory/stock-item.md`.

## J2 — Client cutting + ordering (client)

1. Client opens the **client app**, authenticates / self-registers via **Telegram OAuth** →
   [`docs/ref/features/client-onboarding.md`](../ref/features/client-onboarding.md).
2. Client picks a **branch** (active or temporarily-closed; only active ones accept new orders) →
   [`docs/ref/features/order-placement.md`](../ref/features/order-placement.md).
3. Client picks a **material** and a **material source** (`own` / `shop`), enters a **parts list**
   (dimensions, quantity, grain, edge banding), runs the **optimizer** →
   [`docs/ref/features/cutting-optimization.md`](../ref/features/cutting-optimization.md). Sees the SVG layout, waste %, sheets used, edge length, a downloadable PDF. Iterates until satisfied — each run is a new draft.
4. Client converts the **draft** into an **order**: confirms parts, chooses pickup or delivery
   (delivery → address + zone fee), chooses a payment option (`full` / `advance`; `bnpl` slot
   disabled in v1), confirms → order created in `new` → [`docs/ref/features/order-placement.md`](../ref/features/order-placement.md). The cutting result becomes `confirmed` and bound to the order.
5. Client pays — in v1 there is no gateway: the order sits until workshop staff record the payment
   (cash / bank). On payment recorded, the order becomes `confirmed`; if `shop` material, stock is
   reserved automatically.
6. Client tracks the order through `confirmed` → `in_production` → `ready` → (`in_delivery`) →
   `completed`, with a status timeline and notifications → [`docs/ref/features/notifications-inbox.md`](../ref/features/notifications-inbox.md), [`docs/spec/orders.md`](orders.md).
7. If something changes early (`new` / `pending_payment`): client modifies (re-optimizes + re-prices)
   or cancels with a reason → [`docs/ref/features/order-modification.md`](../ref/features/order-modification.md), [`docs/ref/features/order-cancellation-and-refunds.md`](../ref/features/order-cancellation-and-refunds.md).

Entities: `docs/ref/entities/sales/order.md`, `docs/ref/entities/cutting/cutting-result.md`.

## J3 — Workshop order fulfilment (workshop staff with `manage_orders`)

1. Staff sees a **new order** in the branch queue (Kanban / table) → [`docs/ref/features/order-fulfillment.md`](../ref/features/order-fulfillment.md).
2. Staff records the **payment** the client made (cash / bank) → order → `confirmed`; stock reserved
   if `shop` → [`docs/ref/features/order-fulfillment.md`](../ref/features/order-fulfillment.md), [`docs/ref/features/inventory-management.md`](../ref/features/inventory-management.md). (Alternatively, the owner approves **pay-later** with a mandatory reason → `confirmed` without payment.)
3. Staff moves the order to **in_production** (optionally assigning a worker), opens the **cutting
   PDF**, the panels get cut.
4. Staff marks the order **ready**. Stock is consumed automatically (`shop`). If an advance was
   paid, the balance must be recorded before handover.
5. Handover: for **pickup**, staff marks **completed** on collection; for **delivery**, staff
   assigns a **driver** → `in_delivery` → marks **completed** on delivery → [`docs/ref/features/worker-management.md`](../ref/features/worker-management.md).
6. At any allowed point: staff applies a **discount** (reason mandatory), or cancels (reason
   mandatory) — cancellation of a paid order creates a **pending refund**; the owner force-cancels
   an in-production+ order in exceptional cases → [`docs/ref/features/order-cancellation-and-refunds.md`](../ref/features/order-cancellation-and-refunds.md).

## J4 — Refund (workshop staff with `manage_orders`)

1. An order is cancelled (or modified down) with a payment on it → the system creates a **pending
   refund** record → [`docs/ref/features/order-cancellation-and-refunds.md`](../ref/features/order-cancellation-and-refunds.md).
2. The pending refund shows in the branch refund queue; if it sits > 7 days it is flagged stale and
   the owner is notified → [`docs/ref/features/notifications-inbox.md`](../ref/features/notifications-inbox.md).
3. Staff move the money **offline** (bank transfer / cash) and **record** the refund: method, amount,
   a mandatory note (bank reference / receipt), optional receipt scan → refund `completed`, payment
   `refunded`, client notified.
4. On dispute, the owner can **revert** a completed refund (exceptional, audited).

## J5 — Workshop blocked / unblocked (platform operator)

1. Platform operator blocks a **workshop** → `blocked`; the workshop's owner + staff sessions are
   revoked immediately; their next login is rejected. Clients are unaffected. Open orders freeze in
   place (no automatic transitions). See [`docs/spec/access.md`](access.md), [`docs/spec/access.md`](access.md).
2. Unblock → `active`; sessions are **not** restored — users log in again.
