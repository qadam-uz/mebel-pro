---
title: Order placement
status: stable
owner: shape
updated: 2026-05-11
order: 34
related:
  - docs/spec/orders.md
  - docs/spec/cutting.md
  - docs/ref/entities/sales/order.md
  - docs/ref/features/cutting-optimization.md
  - docs/ref/features/order-fulfillment.md
---

# Order placement

## Problem

A customer has a cutting they're happy with and wants to actually order it. They need to pick a
branch, confirm the parts, choose pickup or delivery (with the delivery fee shown up front), pick a
payment option, see the running total, and place the order — and then track it. Today this is a phone
call and a verbal price; the customer can't self-serve, and there's no record tying the order to a
specific customer and a specific cutting result.

## User stories

- As a **client**, I want to pick a branch (active ones accept orders; closed ones show as closed)
  before I start.
- As a **client**, I want to turn a cutting draft into an order: confirm the parts, choose pickup or
  delivery, see the price, pick how I'll pay, and confirm.
- As a **client**, I want the delivery fee resolved from my address before I commit, and a clear
  message if my address isn't in a delivery zone.
- As a **client**, I want my orders listed with their status, and a detail page with the timeline,
  items, cutting, payments, and refunds.
- As a **client**, I want to pay (in v1 there's no in-app gateway — the workshop records my payment;
  I'm told my order is awaiting that).

## Requirements

1. **Branch picker** — `list-branches?status=active,temporarily_closed` across **all** workshops
   (clients aren't tenant-scoped — [`docs/spec/access.md`](../../spec/access.md)); search by name/city;
   `active` branches link into the cutting wizard, `temporarily_closed` show the reason and a disabled
   CTA.
2. **Cutting** is the prerequisite — an order is created **from a `draft` cutting result** ([`docs/ref/features/cutting-optimization.md`](cutting-optimization.md)); there's no order without one.
3. `resolve-delivery-fee` (client): given `(branch_id, lat, lng)` returns `{ delivery_zone_id,
   delivery_zone_name, delivery_fee_tiyin }` or `delivery_out_of_zone` — no side effects; lets the
   wizard preview the fee before submit.
4. `create-order` (**client only** — [`docs/spec/orders.md`](../../spec/orders.md)): input
   `{ cutting_result_id (a draft owned by the client), branch_id, material_source, items[] (matching
   the cutting's parts), delivery_type, delivery_address? (street/city/lat/lng/note), delivery_zone_id?
   (from resolve), payment_option (full | advance — `bnpl` is a disabled v1 slot), note_client? }`.
   Validates the branch is `active`, the workshop active, the cutting draft is the client's and still
   `draft`. Computes and **snapshots** the price ([`docs/spec/orders.md`](../../spec/orders.md)) —
   cutting + materials (`shop`) + edge banding + delivery fee; discount 0. Creates the `order` in
   `new`, its `order_item`s with material/price snapshots, its first `order_status_event`. Binds the
   cutting result (`→ confirmed`, `order_id` set). In v1 there's no payment redirect — the order
   waits until workshop staff record a payment (or the owner approves pay-later) to move to
   `confirmed` ([`docs/spec/scope-v1.md`](../../spec/scope-v1.md)).
5. `list-my-orders` / `get-my-order` (client): the client's orders, with status; detail with the
   timeline (from `order_status_event`s), items (snapshots), the cutting summary + a layout link
   ([`docs/ref/features/cutting-optimization.md`](cutting-optimization.md)), payments, refunds.
6. `modify-my-order` / `cancel-my-order` (client; only `new` / `pending_payment`) — see [`docs/ref/features/order-modification.md`](order-modification.md), [`docs/ref/features/order-cancellation-and-refunds.md`](order-cancellation-and-refunds.md).
7. Every action audited; status changes write status-change-log rows; the workshop's branch staff get
   a notification on `order.created`.

## UX

In the **client app**:

- **Branch picker** (`/c/branches` — also the client home) — hero copy, search, a grid of branch
  cards (name, address, today's hours, status badge; `active` → "Start cutting" CTA;
  `temporarily_closed` → reason + disabled CTA). Empty: "No active branch found."
- **Cutting wizard** — see [`docs/ref/features/cutting-optimization.md`](cutting-optimization.md).
- **Order create wizard** (`/c/orders/new?cutting=:id`) — pre-check the draft is still `draft` (else
  redirect to its detail with a toast); a 3-step stepper with a sticky summary card (subtotals:
  cutting, material, edge banding, delivery, discount = 0; total in UZS from tiyin):
  1. **Confirm parts** — read-only parts list + the cutting summary + PDF link; a "need to change
     parts? go back to cutting" link (→ the cutting wizard with the parts pre-filled, which creates a
     new draft on the next run).
  2. **Delivery** — a toggle "pick up at the branch" / "delivery"; pickup shows the branch address +
     hours; delivery shows address fields (street, city, lat/lng numeric, note) and, on change, calls
     `resolve-delivery-fee` → shows the fee, or an inline "this address isn't in any delivery zone —
     choose pickup or another branch".
  3. **Payment** — a radio: "pay in full" (`full`) / "advance + balance" (`advance`, shows the
     advance % from the workshop settings + the computed advance and balance); a `bnpl` chip shown
     **disabled** with a "coming soon" pill. Confirm → `create-order`.
  - On success → `/c/orders/:id` with a banner: "Order placed — it'll be confirmed once the workshop
    records your payment" (and, for `advance`, the advance amount to pay). (When v1.1 adds gateways,
    a `payment_url` redirect + a "verifying payment" landing replaces that banner.)
  - On `cutting_result_not_usable` (race) → toast + back to the cutting wizard;
    `delivery_out_of_zone` / `branch_closed` / `workshop_blocked` → step 2 with an inline error.
- **My orders** (`/c/orders`) — filter chips (All / Active = new+pending+confirmed+in_production+ready+in_delivery /
  Completed / Cancelled), search by order number, cards (order number, branch, date, status badge,
  total, a primary action — "Pay info" if awaiting payment, "Track" otherwise), pagination. Empty:
  "No orders yet — start from a cutting."
- **Order detail** (`/c/orders/:id`) — header (order number, branch, status badge, created/confirmed/
  completed times, total) with status-appropriate actions ("Modify" / "Cancel" only in
  `new`/`pending_payment`; "Track" expands the timeline otherwise); cards/tabs: Overview (items
  snapshots, pricing breakdown, delivery info, notes), Cutting (the SVG + PDF link; a note if the
  bound result is invalidated), Payments (the `order_payment` list — type, method, amount, status,
  paid_at; a note about how payment works in v1), Refunds (only if any), Timeline (the status events
  — who/when, stale waits highlighted).
- States: every screen has loading/empty/error; the wizard validates each step; no infinite spinners;
  mobile-first throughout.
- Accessibility: the wizard steps are clearly labelled and keyboard-navigable; the delivery toggle
  and payment radios are real form controls; inline errors are announced and sit by their field; the
  branch cards are real radio options.

Shared components (`Stepper`, sticky summary, status badge, order timeline, data table/cards): [`docs/ref/ux/components.md`](../ux/components.md).

## Entities touched

- [`docs/ref/entities/sales/order.md`](../entities/sales/order.md) — created in `new`.
- [`docs/ref/entities/sales/order-item.md`](../entities/sales/order-item.md) — created with material/price snapshots.
- [`docs/ref/entities/sales/order-status-event.md`](../entities/sales/order-status-event.md) — the creation event.
- [`docs/ref/entities/cutting/cutting-result.md`](../entities/cutting/cutting-result.md) — the draft is bound (`→ confirmed`).
- [`docs/ref/entities/identity/client.md`](../entities/identity/client.md) — the owner.
- [`docs/ref/entities/workshop/branch.md`](../entities/workshop/branch.md), [`docs/ref/entities/catalog/material.md`](../entities/catalog/material.md), [`docs/ref/entities/catalog/branch-pricing.md`](../entities/catalog/branch-pricing.md) — read for validation & pricing.
- [`docs/ref/entities/support/action-log.md`](../entities/support/action-log.md), [`docs/ref/entities/support/status-change-log.md`](../entities/support/status-change-log.md), [`docs/ref/entities/support/notification.md`](../entities/support/notification.md).

## Edge cases

- **Draft already used / not the client's / not `draft`** → `cutting_result_not_usable`; redirect to
  its detail.
- **Branch went `inactive`/`temporarily_closed` between the cutting and the order** → `branch_closed`;
  the client picks another branch.
- **Workshop blocked** between cutting and order → `workshop_blocked`.
- **Delivery address out of all zones** → `delivery_out_of_zone`; switch to pickup or another branch.
- **Branch pricing incomplete** → order creation fails at pricing; the client sees a "this branch
  can't take orders right now" message (the owner must finish pricing).
- **Material price changed since the draft** → the order prices at the price as of confirmation, then
  snapshots it.
- **Client double-submits the confirm** → the app disables the button + shows a busy state to prevent
  a duplicate order (order creation is not idempotent — each POST makes a new order).

## Out of scope

- In-app payment via a gateway / a payment redirect — v1.1 ([`docs/spec/scope-v1.md`](../../spec/scope-v1.md)); v1's order waits for staff to record the payment.
- BNPL — v1.1 (the chip is a disabled placeholder).
- `pay_later` as a client option — only workshop staff/owner mark an order pay-later.
- Operator-created orders — never.
- Reorder / order templates / batching — future.
- Geocoded address entry — v1 is manual lat/lng.

## Open questions

- Payment gateway + the `pending_payment` redirect flow — owner: shape — [`docs/spec/open-questions.md`](../../spec/open-questions.md) Q2.
