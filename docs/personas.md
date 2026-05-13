---
title: Personas
status: stable
owner: shape
updated: 2026-05-13
order: 30
---

# Personas

The humans v1 is built for. Four of them, across three apps — a platform-ops console, a workshop
app for the workshop side, and a client app for the customer side.

## Platform operator

The team running the platform. Onboards new workshops and their first owner; blocks or unblocks
a workshop; watches the platform across all workshops for incidents; operates platform-wide
jobs and the error monitor. Not a workshop user — does not run anyone's day-to-day.

## Workshop owner

The person who owns or runs the furniture workshop. Top authority inside their workshop: stands
the workshop up end-to-end (branches, stock, pricing, workers, staff, and what each branch
carries from the platform's material catalog), grants and revokes staff permissions, oversees
the order pipeline and the books, and holds the few owner-only levers — force-cancelling an
order already in production, reversing a completed refund. Provisioned by the platform; cannot
be created or demoted from inside the workshop.

## Workshop staff

Branch employees — order desk, warehouse, cutter, driver, branch manager. Each one logs in with
a permission set the owner gave them on specific branches; what they can do is whatever those
permissions cover, and a freshly created staff member with no permissions yet can log in and
see nothing actionable. In practice: progressing orders for their branch, recording cash and
bank payments, processing refunds, and keeping stock, workers, and the branch's material
selection current.

## Client

The workshop's customer — a person or a small business that needs panels cut. Self-registers
on demand through social sign-in, no password; global to the platform, picks a workshop and a
branch per order. Often on a phone, often first-time, often comparing options across workshops
— so the experience is mobile-first. Sees only their own side: catalog, cutting result, their
orders, payments, refunds — nothing about the workshop's internals.

## Next

[`domain-model.md`](domain-model.md) — the language and the entity map these humans share.
