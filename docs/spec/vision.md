---
title: Vision
status: stable
owner: shape
updated: 2026-05-11
order: 10
related:
  - docs/spec/scope-v1.md
  - docs/spec/personas.md
---

# Vision

## What this is

**Mebel Pro** is a B2B2C platform for furniture-panel cutting in Uzbekistan. It digitizes the
operations of a furniture workshop — branches, materials, warehouse, workers, pricing, orders — and
puts a self-serve cutting-and-ordering surface in front of that workshop's customers.

One line:

> Furniture-cutting workshops run their operations in one system; their customers go online to
> optimize a cutting plan and order panels cut to size.

## Who it's for

- **Furniture workshops** (the tenants) — small-to-mid shops with one or more branches that cut
  sheet material (DSP, MDF, plywood) to customer dimensions. Today they take orders by phone and
  paper, optimize cutting by hand or with a desktop tool, and track stock in a notebook.
- **Their customers** (clients) — people and small businesses who need panels cut. Today they
  describe parts over the phone; they can't see the cutting plan, the waste, or the price until the
  shop tells them.
- **The platform operator** — us: onboards workshops, keeps the system running.

## The bet

Two pains, one product:

1. **For the workshop:** their operations live in a dozen disconnected places. One system that
   models branches → materials → stock → pricing → orders, with a real cutting optimizer and an
   audit trail, removes the phone-and-paper layer and the per-order arithmetic.
2. **For the customer:** ordering is opaque and slow. Letting them build the parts list, run the
   optimizer themselves, see the layout and the waste %, and place the order online — with the shop
   only handling production and handover — shifts data entry to the person who has the data, cuts
   no-shows, and frees the shop's staff for the work that needs them.

## What success looks like

- A workshop can stand up its world (branches, materials, stock, pricing, staff) and start taking
  online orders without a spreadsheet.
- A client can go from "I need these panels" to a placed, priced order — with a cutting layout they
  can see and a PDF the shop floor can cut from — in one sitting, on a phone.
- Every order has one owner (the client who placed it), one priced snapshot, one cutting result,
  and a full status history; nothing about it is reconstructed from memory.
- The shop's day is spent on production and handover, not on order intake and price math.

## What this is not

The boundaries are in [`docs/spec/scope-v1.md`](scope-v1.md) (v1 in/out) and pinned hard in
[`docs/spec/envelope.md`](envelope.md) (the operating envelope — the "not built for" line).
