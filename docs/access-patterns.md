---
title: Identity, access & tenancy
status: stable
owner: shape
updated: 2026-08-31
order: 50
---

# Identity, access & tenancy

The humans v1 is built for, who proves who they are, what a workshop user may do, and what each
principal may see.

## Personas

Four humans across three apps — a platform-ops console, a workshop app, and a client app.

### Platform operator

The team running the platform. Onboards new workshops and their first owner; blocks or unblocks
a workshop; watches the platform across all workshops for incidents; operates platform-wide jobs
and the error monitor. Not a workshop user — does not run anyone's day-to-day.

### Workshop owner

The person who owns or runs the furniture workshop. Top authority inside their workshop: stands
the workshop up end-to-end (branches, stock, pricing, staff, and which decors — in which
formats — each branch carries), grants and revokes staff permissions, oversees the order
pipeline and the books, and holds the owner-only levers — creating staff and branches, setting
branch pricing, and the workshop-wide reports.

### Workshop staff

Branch employees — order desk, warehouse, cutter, edge bander, accountant. **Not fixed roles**:
each works within the per-branch permission set the owner grants them, one person may hold all of
them and run the whole flow alone, and a freshly created member with no grants sees nothing
actionable. In practice the grants cover verifying and progressing orders, the cutting / banding
work, keeping stock and suppliers current, and recording the workshop's income and expenses.

### Client

The workshop's customer — a person or a small business that needs panels cut, often first-time
and often comparing options across workshops. Self-registers on demand — or is registered at
the counter by workshop staff when they walk in without the app — and is global to the
platform, picking a workshop and a branch per order. Works from both a desktop browser and a
phone; in v1 the priority is the desktop web experience, with a mobile-first pass to follow. Sees
only their own side — catalog, cutting result, their orders, and what they owe once an order is
ready — nothing about the workshop's internals.

## Principals

Three principal types — three auth surfaces, one per front-end app. They don't overlap.

| Principal                              | Auth                                  | Bound to             | Capability                                                                     | App            |
| -------------------------------------- | ------------------------------------- | -------------------- | ------------------------------------------------------------------------------ | -------------- |
| **Platform user** ("superadmin")       | login + password; no permission model | no workshop          | platform-ops scope                                                             | superadmin app |
| **Workshop user — owner** (`is_owner`) | login + password                      | one workshop         | everything in the workshop on every branch, plus owner-only powers (see below) | workshop app   |
| **Workshop user — staff**              | login + password                      | one workshop         | exactly the `(permission, branch)` grants the owner gave them                  | workshop app   |
| **Client**                             | Telegram bot handshake; no password   | no workshop (global) | own orders & cutting drafts; browse active branches of any workshop            | client app     |

## The model

- **Workshop users** sign in with login + password. Login is unique across the whole platform,
  so the login alone names the account and the workshop follows from it — a login already in use
  anywhere is refused at creation. Owners are created by a platform operator during workshop
  provisioning.
- **Platform users** sign in with login + password and are seeded via a backend CLI (they're at
  the top of the hierarchy, so no higher principal exists to create them in-app).
- **Clients** sign in **through the platform's Telegram bot** — the browser shows a one-time
  link into the bot, the client confirms there, and on first contact shares their
  Telegram-verified phone. No password. The **phone is the identity**; the Telegram account is
  the credential linked to it, and they self-register on the first confirmed contact. A
  walk-in's client row may also be created by workshop staff resolving them by phone at the
  counter ([`ref/features/access-management.md`](ref/features/access-management.md)); the bot
  remains the **only** client login path — a staff-created row is claimed the first time its
  number's contact is shared there.
- **Sessions are opaque DB-backed tokens**, not JWTs — the system needs _instant revocation_
  (block, "log out everywhere", password change) and _fresh authorization_ (a new grant must
  apply on the next request). A user cannot reset their own password — a higher principal
  does it.
- **Workshop-staff capability is coarse-grained and branch-scoped.** A grant is a
  `(workshop user, permission, branch)` row; there is **no role taxonomy**. The owner holds
  every permission on every branch implicitly, plus a small set of **owner-only carve-outs**.
- **Multi-tenant isolation is enforced server-side** on every read and every write, scoped to
  the authenticated principal — client-supplied tenant ids are never trusted.

## Tenancy

The tenant is the **workshop**. One database, one app, many workshops.

- **Tenant hierarchy.**

  ```mermaid
  flowchart TD
      D[("<b>Decor</b><br/>platform-wide<br/>pattern identity")]
      DF[("<b>Decor format</b><br/>platform-wide<br/>one product")]
      Cl[("<b>Client</b><br/>platform-wide<br/>no tenant")]

      W["<b>Workshop</b><br/><i>(tenant)</i>"]
      WU["workshop user<br/>1 owner · N staff"]
      PG["permission grant<br/>branch-scoped"]
      B["branch · 1..N"]
      BM["branch material<br/>carry + price"]
      SI["stock item"]
      BP["branch pricing"]

      W --> WU
      W --> B
      WU --> PG
      PG --> B
      B --> BM
      B --> SI
      B --> BP

      DF -.->|a product of| D
      BM -.->|we carry| DF
      Cl -.->|places order at| B
  ```

One owner per workshop (exactly); a workshop user belongs to one workshop.
**The product is global** — decors *and* their formats are platform-level master records, so
one physical sheet has one id everywhere; a branch owns only **the decision to carry it and
its price**, and that branch material is what everything downstream points at.
**Clients are global** — bound to no workshop or branch; they pick a branch per order.

- **Scope by principal** (derived from the authenticated principal, never from client input):

  | Principal         | Read/write scope                                                                           |
  | ----------------- | ------------------------------------------------------------------------------------------ |
  | Platform operator | platform-ops surfaces across workshops; no workshop order-content or profile-edit scope     |
  | Workshop owner    | own workshop; all its branches                                                             |
  | Workshop staff    | own workshop; only branches they hold a relevant grant on                                  |
  | Client            | own orders / cutting drafts; browse active (+ temporarily-closed) branches of any workshop |

  Crossing these returns `forbidden` (or simply excludes rows on list endpoints).

- **Workshop blocking is a cascade.** A platform operator blocks a workshop: the owner's +
  staff's sessions are revoked immediately; their next login is rejected; **client sessions
  and orders are unaffected**; open orders **freeze** — no automatic transitions, and staff
  can't act because they can't log in. Unblocking doesn't restore sessions — users log in again.
- **Branch status governs visibility, not access destruction.**

  | Status               | Visible to clients               | Accepts new orders | Existing orders |
  | -------------------- | -------------------------------- | ------------------ | --------------- |
  | `active`             | yes                              | yes                | continue        |
  | `temporarily_closed` | yes — shown as closed (+ reason) | no                 | continue        |
  | `inactive`           | no                               | no                 | continue        |

  A branch is never deleted; changing its status doesn't touch staff sessions or grants.

## Next

[`architecture.md`](architecture.md) — the operating envelope and the technical shape built to
satisfy everything above.
