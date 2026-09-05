---
title: Workshop administration
status: draft
owner: shape
updated: 2026-09-05
order: 40
---

# Workshop administration

The owner-and-staff surfaces for keeping a workshop running — the home dashboard, workshop
settings, and branch CRUD. The **audit viewer** over a workshop's action and status logs is
specified here too, but in v1 it is a **superadmin-app surface only** — workshop owners get no
in-app audit screen yet (see [`scope.md`](../../scope.md)). Sign-in, sessions, provisioning, and
staff management live in [`access-management.md`](access-management.md); income, expenses, and the
worker-production reports live in [`finance.md`](finance.md).

## Workshop home (Asosiy)

`/workshop` — the app's home path, the redirect target for every refused route, and the one screen
every signed-in workshop user sees, zero-grant staff included (the gating and the "nothing here
for you" state are in
[`access-management.md`](access-management.md#workshop-app-access-matrix)). It answers the three
questions an owner opens the day with: **what came in, what is waiting, where the work is stuck.**
It is not a report — each thing it raises carries the action that resolves it.

The head carries the page title with the selected branch and today's date beneath it, and a
**7 / 14 / 30 day** period switch that drives the chart and its total. Below it, four sections in
reading order:

| Section | What it shows | Where the numbers come from |
| --- | --- | --- |
| **KPI row** — four cards | today's income · orders in production, with their value · client debt · low-stock materials, naming how many are negative | [`finance.md`](finance.md#finance-summary) · this module's order counts · [`catalog-inventory.md`](catalog-inventory.md) |
| **Sizdan kutilmoqda** — a work list | one row per condition that needs a person: new orders unconfirmed, ready orders not collected, a material gone negative, a branch with no cutter assigned. Each row is a title, a detail line, and the action that clears it | the module the condition belongs to |
| **Stansiyalar** | Kesish and Krom, each with who is on it and how many orders are queued, plus a text link to the queues. **Hidden while the selected branch runs `simple`** — it has no assignments to report ([`orders.md`](orders.md#production-mode)) | [`orders.md`](orders.md) → production stations |
| **Savdo** | income per day over the chosen period as a bar chart, the period total in the panel head | [`finance.md`](finance.md#finance-summary) |

Two rules the screen exists to hold:

- **Exactly one work-list row carries the primary button** — the most urgent one. Every other
  action on the page is neutral, so the eye lands on the one thing to do first.
- **A row appears when it applies**; the **button** is what follows the reader's grant. Someone
  who cannot run the action still sees the stall — retargeted to the page they can open, or with
  no button at all — because an instruction the reader cannot carry out is worse than a row that
  only reports. A panel with nothing in it says so; it does not disappear.

While an owner's setup is incomplete, the setup checklist sits above all of this
([`onboarding.md`](onboarding.md)). Panel geometry, the chart's colour ramp and the work-list
button rules are the design system's:
[`web/DESIGN.md`](https://github.com/qadam-uz/mebel-pro/blob/main/web/DESIGN.md).

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
  and logo, plus the workshop-level **Mijoz havolasi** card — the link and QR that pin a
  client to the workshop rather than to one branch ([`client-entry.md`](client-entry.md)).
  Contact phone and address are branch fields.

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
  branch's material catalog is built up.
- **Read the branch number** — creation assigns a permanent `branch_no`. It addresses the
  branch's own client link and printed QR (`/w/{code}/{branch_no}`,
  [`client-entry.md`](client-entry.md)), and it is the middle segment of every **legacy**
  order number the branch printed before numbers went global
  ([`sales.md`](../entities/sales.md)). It is shown, never edited: printed QR codes must not
  rot, and an owner holding a paper `#26-1-0003` still has to be able to find out which branch
  the `1` is.
- **The production mode is not an owner control.** A branch is born `simple` and stays there:
  the current plan (**Start**) offers simple mode only, and the radio group that used to sit
  with the cutting settings was removed on 2026-09-05. The branch closes an order with one
  **Tayyor** tap; the per-stage choreography of assignment, start taps and station queues is
  implemented but unreachable ([`orders.md`](orders.md#production-mode) owns the behaviour and
  the plan decision). The setting itself survives on the branch API, which is how the demo
  seed and the E2E suite still drive a `full` branch, and it returns to owners with a future
  plan.
- **Change status** — `active` ↔ `temporarily_closed` ↔ `inactive`. `temporarily_closed` may
  carry an optional reason. **Status changes do not revoke staff sessions or grants** — a
  staff grant on an `inactive` branch just stays inert until the branch is reactivated. A
  branch is never deleted.

Setting a branch to `inactive` while it has open orders is allowed (those orders finish
normally); the UI warns and lists how many.

Visibility for read operations:
- Owner sees every branch of their workshop.
- Staff see only branches they hold a grant on.
- Clients may see `active` and `temporarily_closed` branches of any workshop. What the client
  app *offers* them is narrower once they are pinned to a workshop — one workshop's branches,
  not the platform's ([`client-entry.md`](client-entry.md)).

### UX

- **Branches list** (`/workshop/branches`) — simple table: branch number (leading, in tabular
  figures), name, address, primary phone, status badge, action. **+ Branch** (owner). Empty:
  "No branches yet — add one to start taking orders."
- **Branch create dialog** — modal form: name, primary phone, address, an add/remove list for
  the additional phones (capped at three, with the cap explained when reached).
- **Branch detail** (`/workshop/branches/:id`) — the header carries the branch number, so one
  branch page is enough to decode a printed legacy document (`#26-1-…`) or a branch QR.
  Below it, an owner-only editable branch form: branch contact, **the location** — a map the
  owner clicks to place the branch's pin, on OpenStreetMap tiles so there is no API key and
  nothing to configure per deployment; the saved pair is what renders a client's **Xaritada
  ko'rish** link, which opens Yandex Maps, since that is what people here navigate with —
  pricing (entered in so'm), cutting settings (kerf + edge trim, in mm), edge settings (the
  glue-and-trim overhang, in mm), material settings (whether the branch takes a client's own
  sheets), and status controls. It does not duplicate materials, stock, staff, or order
  management; those stay in their own sidebar sections. Edge settings are their own group
  rather than a third cutting setting: the overhang is consumed at the bander, and it is the
  one branch millimetre that moves what the client is billed for tape
  ([`orders.md`](orders.md#pricing)). It also carries the **Mijoz havolasi** card — this
  branch's client link, its QR, and the print sheet for the counter
  ([`client-entry.md`](client-entry.md) owns it).
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

- [`catalog-inventory.md`](catalog-inventory.md) — what a branch carries from the platform
  catalog, its prices, and its stock.
- [`client-entry.md`](client-entry.md) — the client link and QR these screens publish, and
  what following one does to the client app.
