---
title: Identity, access & tenancy
status: stable
owner: shape
updated: 2026-05-22
order: 50
---

# Identity, access & tenancy

Who proves who they are, what a workshop user may do, what each principal may see.

## Principals

Three principal types — three auth surfaces, one per front-end app. They don't overlap.

| Principal                              | Auth                                  | Bound to             | Capability                                                                     | App            |
| -------------------------------------- | ------------------------------------- | -------------------- | ------------------------------------------------------------------------------ | -------------- |
| **Platform user** ("superadmin")       | login + password; no permission model | no workshop          | full platform scope                                                            | superadmin app |
| **Workshop user — owner** (`is_owner`) | login + password                      | one workshop         | everything in the workshop on every branch, plus owner-only powers (see below) | workshop app   |
| **Workshop user — staff**              | login + password                      | one workshop         | exactly the `(permission, branch)` grants the owner gave them                  | workshop app   |
| **Client**                             | phone + Telegram OTP; no password     | no workshop (global) | own orders & cutting drafts; browse active branches of any workshop            | client app     |

## The model

- **Workshop & platform users** sign in with login + password. Owners are created by a
  platform operator during workshop provisioning; platform users are seeded via a backend CLI
  (they're at the top of the hierarchy, so no higher principal exists to create them in-app).
- **Clients** sign in with a **phone number verified by a one-time code sent over Telegram** —
  no password, no fallback path. The phone is the identity; they self-register (name only) the
  first time a new number is verified.
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
      M[("<b>Material</b><br/>platform-wide<br/>master record")]
      Cl[("<b>Client</b><br/>platform-wide<br/>no tenant")]

      W["<b>Workshop</b><br/><i>(tenant)</i>"]
      WU["workshop user<br/>1 owner · N staff"]
      B["branch · 1..N"]
      BMS["branch material<br/>selection"]
      SI["stock item"]
      BP["branch pricing"]
      Wk["worker"]

      W --> WU
      W --> B
      B --> BMS
      B --> SI
      B --> BP
      B --> Wk

      BMS -.->|picks from| M
      Cl -.->|places order at| B
  ```

One owner per workshop (exactly); a workshop user belongs to one workshop.
**Materials are global** — master records at the platform level, referenced by each branch's selection.
**Clients are global** — bound to no workshop or branch; they pick a branch per order.

- **Scope by principal** (derived from the authenticated principal, never from client input):

  | Principal         | Read/write scope                                                                           |
  | ----------------- | ------------------------------------------------------------------------------------------ |
  | Platform operator | all workshops, all branches                                                                |
  | Workshop owner    | own workshop; all its branches                                                             |
  | Workshop staff    | own workshop; only branches they hold a relevant grant on                                  |
  | Client            | own orders / cutting drafts; browse active (+ temporarily-closed) branches of any workshop |

  Crossing these returns `forbidden` (or simply excludes rows on list endpoints).

- **Workshop blocking is a cascade.** A platform operator blocks a workshop: the owner's +
  staff's sessions are revoked immediately; their next login is rejected; **clients are
  unaffected**; open orders **freeze** — no automatic transitions, and staff can't act because
  they can't log in. Unblocking doesn't restore sessions — users log in again.
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
