---
title: Workshop administration
status: draft
owner: shape
updated: 2026-07-27
order: 40
---

# Workshop administration

The owner-and-staff surfaces for keeping a workshop running — workshop settings and branch
CRUD. The **audit viewer** over a workshop's action and status logs is specified here too,
but in v1 it is a **superadmin-app surface only** — workshop owners get no in-app audit screen
yet (see [`scope.md`](../../scope.md)). Sign-in, sessions,
provisioning, and staff management live in [`access-management.md`](access-management.md);
income, expenses, and the worker-production reports live in [`finance.md`](finance.md).

## Workshop settings

The workshop's mutable profile:

- **Profile** — name and logo. Editable by the workshop's owner. Platform
  operators can view the operational summary for incident response, but v1 gives them no edit path.
- **Currency** — UZS, fixed in v1; named here for future-proofing.

Delivery zones, advance %, and payment channels are **not in v1** — v1 is pickup-only and an
order moves no money ([`scope.md`](../../scope.md)); they return with delivery and a gateway.

Owner-only power covered by `is_owner` (see the access-management permission catalog):
editing settings.

### UX (superadmin app)

- **Workshops list** (`/admin/workshops`) — table: name, owner login, branch count, created,
  status badge. Status filter; name/owner search;
  **+ Workshop** (provisioning is in access-management). Empty: "No workshops yet." The owner
  is identified by login here — the stable operational handle.
- **Workshop detail** — header (name, status, created); tabs: **Profile** (read-only name,
  owner login, created date, status), **Branches** (read-only list, branch number first —
  support traces a reported order number back to a branch here), **Block** (block / unblock
  with a mandatory reason;
  destructive-styled; warns that staff sessions are revoked and open orders freeze). When the
  workshop is blocked, the detail shows the **reason captured at block time** in the danger
  banner.

### UX (workshop app)

- **Workshop settings** (`/workshop/settings`, owner-only): a single profile form with name
  and logo. Contact phone and address are branch fields.

## Branches

A workshop owns one or more branches. Each branch has a physical address, published phone
numbers, and a `status` — semantics in [`access-patterns.md`](../../access-patterns.md#tenancy).
A branch publishes **no opening schedule**: `status` plus `closed_reason` is the single
availability answer, and a timetable nobody maintains was a weaker second one. The data model
still keeps an optional `(lat, lng)` coordinate pair (no geocoder in v1; see the entity
reference), but the branch UI does not collect it — the API/DB fields stay for future use.

After platform provisioning creates the first branch, branch operations are **owner only**:

- **Create / edit a branch** — name, address, phones. A branch publishes one **primary** phone
  plus up to **three additional** numbers (landline, director's mobile, WhatsApp). The primary
  is the number order records and every compact surface carry; the additional numbers appear
  only on the client-facing branch page. Extras follow the primary's format rule and may not
  duplicate it or each other.
  Creating a branch also creates an empty `branch_pricing` row; stock items appear as the
  branch's material selection is built up.
- **Read the branch number** — creation assigns a permanent `branch_no` that becomes the middle
  segment of every order number and cutting map the branch prints
  ([`sales.md`](../entities/sales.md)). It is shown, never edited: an owner holding a printed
  `#26-1-0003` has to be able to find out which branch the `1` is, and the number is the only
  part of that document that identifies one.
- **Change status** — `active` ↔ `temporarily_closed` ↔ `inactive`. `temporarily_closed` may
  carry an optional reason. **Status changes do not revoke staff sessions or grants** — a
  staff grant on an `inactive` branch just stays inert until the branch is reactivated. A
  branch is never deleted.

Setting a branch to `inactive` while it has open orders is allowed (those orders finish
normally); the UI warns and lists how many.

Visibility for read operations:
- Owner sees every branch of their workshop.
- Staff see only branches they hold a grant on.
- Clients see `active` and `temporarily_closed` branches of any workshop (per the picker).

### UX

- **Branches list** (`/workshop/branches`) — simple table: branch number (leading, monospace),
  name, address, primary phone, status badge, action. **+ Branch** (owner). Empty: "No branches
  yet — add one to start taking orders."
- **Branch create dialog** — modal form: name, primary phone, address, an add/remove list for
  the additional phones (capped at three, with the cap explained when reached).
- **Branch detail** (`/workshop/branches/:id`) — the header carries the branch number together
  with the order-number prefix it produces (`#26-1-…`), so one branch page is enough to decode a
  printed document. Below it, an owner-only editable branch form: branch contact, pricing
  (entered in so'm), cutting settings (kerf + edge trim, in mm), and status controls. It does
  not duplicate materials, stock, staff, or order management; those stay in their own sidebar
  sections.
- A `temporarily_closed` branch shows a banner with the reason; an `inactive` branch shows an
  inactive banner.

## Audit viewer

Two append-only logs back this feature: the **action log** (every mutating use case writes a
row — actor, action, entity, branch, masked details) and the **status change log** (every
order status transition). Both are write-only at source; this feature only reads them.

In v1 the viewer lives **only in the superadmin app** — platform operators see everything
across workshops, with a workshop filter. The workshop owner has **no in-app audit viewer**
yet (the logs are still recorded against their workshop).

### UX

- In the superadmin app: an **Audit** section with two tabs — **Action log** (filters: action
  type / family, module, actor search, entity type + id, date range, branch, **workshop**;
  rows with a JSON-collapsible `details` preview) and **Status changes** (filters: entity type
  + id, from→to, actor, date range; rows showing the transition). Each row links to the
  affected entity where one exists. Read-only; no workshop scoping.
- States: loading (skeleton rows), empty, error (with `trace_id`); the `details` expander
  reveals masked JSON.
- Export & paging: the loaded page exports to CSV; the list loads the latest N rows with a
  "load more" control to page further back, since the append-only history is otherwise only
  reachable as its newest slice.

## Edge cases

- **Set a branch `inactive` with open orders** — allowed; the warning lists how many; those
  orders complete normally.
- **`temporarily_closed` branch in a client's branch picker** — shown with the reason and a
  disabled "start cutting" CTA.
- **Sensitive fields in audit `details`** — masked at write time; never shown.

## Next

[`catalog-inventory.md`](catalog-inventory.md) — what a branch carries from the platform
catalog, its prices, and its stock.
