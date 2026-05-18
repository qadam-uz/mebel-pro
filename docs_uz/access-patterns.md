---
title: Identity, access & tenancy
status: stable
owner: shape
updated: 2026-05-14
order: 50
---

# Identity, access & tenancy

Kim oʻzining kimligini isbotlaydi, workshop user nima qila oladi, har bir principal nimani koʻra
oladi.

## Principals

Uchta principal turi — uchta auth surface, har bir front-end app uchun bittadan. Ular
bir-biriga overlap qilmaydi.

| Principal                              | Auth                                  | Bound to             | Capability                                                                     | App            |
| -------------------------------------- | ------------------------------------- | -------------------- | ------------------------------------------------------------------------------ | -------------- |
| **Platform user** ("superadmin")       | login + password; no permission model | no workshop          | full platform scope                                                            | superadmin app |
| **Workshop user — owner** (`is_owner`) | login + password                      | one workshop         | everything in the workshop on every branch, plus owner-only powers (see below) | workshop app   |
| **Workshop user — staff**              | login + password                      | one workshop         | exactly the `(permission, branch)` grants the owner gave them                  | workshop app   |
| **Client**                             | Telegram OAuth only; no password      | no workshop (global) | own orders & cutting drafts; browse active branches of any workshop            | client app     |

## The model

- **Workshop va platform user'lar** login + password bilan kiradi. Owner'lar workshop
  provisioning chogʻida platform operator tomonidan yaratiladi; platform user'lar backend CLI
  orqali seed qilinadi (ular hierarchy'ning tepasida, shuning uchun ularni in-app yaratish uchun
  yuqoriroq principal mavjud emas).
- **Client'lar faqat Telegram OAuth bilan kiradi** — password yoʻq, fallback path yoʻq. Ular
  birinchi handshake'da oʻzini oʻzi self-register qiladi; phone number talab qilinadi.
- **Session'lar — JWT emas, opaque DB-backed token'lar**, chunki system'ga _instant revocation_
  (block, "log out everywhere", password change) va _fresh authorization_ (yangi grant keyingi
  request'da apply boʻlishi kerak) zarur. User oʻz password'ini oʻzi reset qila olmaydi —
  yuqoriroq principal buni qiladi.
- **Workshop-staff capability coarse-grained va branch-scoped.** Grant — bu
  `(workshop user, permission, branch)` qatori; **role taxonomy yoʻq**. Owner har bir branch'da
  har bir permission'ni implicit ushlaydi, plus kichik **owner-only carve-out** toʻplam.
- **Multi-tenant isolation server-side** har bir read va har bir write'da, authenticated
  principal'ga scope qilingan holda enforce qilinadi — client-supplied tenant id'larga hech
  qachon ishonilmaydi.

## Tenancy

Tenant — **workshop**. Bitta database, bitta app, koʻp workshop.

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

Har bir workshop'da bitta owner (aynan); workshop user bitta workshop'ga tegishli.
**Material'lar global** — platforma darajasidagi master record'lar, har bir branch'ning selection'i
tomonidan reference qilinadi.
**Client'lar global** — hech qanday workshop yoki branch'ga bound emas; ular har bir order'da
branch tanlaydi.

- **Scope by principal** (authenticated principal'dan derive qilinadi, hech qachon client
  input'dan emas):

  | Principal         | Read/write scope                                                                           |
  | ----------------- | ------------------------------------------------------------------------------------------ |
  | Platform operator | all workshops, all branches                                                                |
  | Workshop owner    | own workshop; all its branches                                                             |
  | Workshop staff    | own workshop; only branches they hold a relevant grant on                                  |
  | Client            | own orders / cutting drafts; browse active (+ temporarily-closed) branches of any workshop |

  Bularni cross qilish `forbidden` qaytaradi (yoki list endpoint'larda shunchaki qatorlarni
  exclude qiladi).

- **Workshop blocking — cascade.** Platform operator workshop'ni block qiladi: owner'ning +
  staff'ning session'lari darhol revoke qilinadi; ularning keyingi login'i reject qilinadi;
  **client'lar taʼsirlanmaydi**; ochiq order'lar **freeze** boʻladi — avtomatik transition yoʻq
  va staff amal qila olmaydi, chunki ular login qila olmaydi. Unblock session'larni tiklamaydi —
  user'lar qaytadan login qiladi.
- **Branch status visibility'ni governs qiladi, access destruction'ni emas.**

  | Status               | Visible to clients               | Accepts new orders | Existing orders |
  | -------------------- | -------------------------------- | ------------------ | --------------- |
  | `active`             | yes                              | yes                | continue        |
  | `temporarily_closed` | yes — shown as closed (+ reason) | no                 | continue        |
  | `inactive`           | no                               | no                 | continue        |

  Branch hech qachon delete qilinmaydi; uning status'ini oʻzgartirish staff session'lariga yoki
  grant'lariga tegmaydi.

## Next

[`architecture.md`](architecture.md) — operating envelope va yuqoridagi hamma narsani satisfy
qilish uchun qurilgan technical shape.
