---
title: Personas
status: stable
owner: shape
updated: 2026-05-17
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
the workshop up end-to-end (branches, stock, pricing, staff, and what each branch carries from
the platform's material catalog), grants and revokes staff permissions, oversees the order
pipeline and the books, and holds the owner-only levers — creating staff and branches, setting
branch pricing, branch-to-branch stock transfers, and the workshop-wide reports and audit log.
Provisioned by the platform; cannot be created or demoted from inside the workshop.

## Workshop staff

Branch employees — order desk, warehouse, cutter, edge bander, accountant. **Not fixed
roles**: each logs in with a permission set the owner gave them on specific branches, what
they can do is exactly what those grants cover, and one person may hold all of them and run
the whole flow alone. A freshly created staff member with no grants can log in and see
nothing actionable. In practice the grants cover: verifying and progressing orders, doing
the cutting / banding work, keeping stock and suppliers current, and recording the
workshop's income and expenses.

## Client

The workshop's customer — a person or a small business that needs panels cut. Self-registers
on demand through social sign-in, no password; global to the platform, picks a workshop and a
branch per order. Often on a phone, often first-time, often comparing options across workshops
— so the experience is mobile-first. Sees only their own side: catalog, cutting result, their
orders, and what they owe (visible once an order is ready) — nothing about the workshop's
internals.

## Next

[`domain-model.md`](domain-model.md) — the language and the entity map these humans share.
