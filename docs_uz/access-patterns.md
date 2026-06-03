---
title: Identity, access & tenancy
status: stable
owner: shape
updated: 2026-06-02
order: 50
---

# Identity, access & tenancy

v1 kim uchun qurilgan odamlar, kim oʻzining kimligini isbotlaydi, workshop user nima qila oladi
va har bir principal nimani koʻra oladi.

## Personas

Uchta app boʻylab toʻrtta odam — platform-ops console, workshop app va client app.

### Platform operator

Platformani yurituvchi jamoa. Yangi workshop'larni va ularning birinchi owner'ini onboard qiladi;
workshop'ni block yoki unblock qiladi; barcha workshop'lar boʻylab platformani incident'larga
kuzatadi; platform-wide job'larni va error monitor'ni boshqaradi. Workshop user emas — hech kimning
kundalik ishini yuritmaydi.

### Workshop owner

Furniture workshop'ga egalik qiluvchi yoki uni yurituvchi shaxs. Oʻz workshop'i ichidagi top
authority: workshop'ni boshidan oxirigacha tiklaydi (branches, stock, pricing, staff va har bir
branch platforma material catalog'idan nimani olib yurishi), staff permission'larini grant va
revoke qiladi, order pipeline va books'ni nazorat qiladi va owner-only richaglarni — staff va
branch yaratish, branch pricing belgilash va workshop-wide report'lar — ushlab turadi.

### Workshop staff

Branch xodimlari — order desk, warehouse, cutter, edge bander, accountant. **Fixed role'lar
emas**: har biri owner unga bergan per-branch permission set bilan ishlaydi, bir shaxs ularning
hammasini ushlab butun flow'ni yolgʻiz yurita oladi va hech qanday grant'siz yangi yaratilgan
member amal qilsa boʻladigan hech narsani koʻrmaydi. Amalda grant'lar order'larni verify qilish va
oldinga surish, cutting / banding ishi, stock va supplier'larni joriy holatda saqlash va income va
expense'larni yozishni qamraydi.

### Client

Workshop'ning mijozi — panel kestirishi kerak boʻlgan shaxs yoki kichik biznes, koʻpincha
first-time va koʻpincha workshop'lar boʻylab variantlarni solishtiradi. Talab boʻyicha oʻzini oʻzi
self-register qiladi va platforma uchun global, har bir order'da workshop va branch tanlaydi. Ham
desktop browser, ham telefondan foydalanadi; v1'da priority — desktop web tajribasi, keyinroq
mobile-first pass rejalashtirilgan. Faqat oʻz tomonini koʻradi — catalog, cutting result, oʻz
order'lari va order ready boʻlgach koʻrinadigan qarzdorligi — workshop'ning internal'lari haqida
hech narsa emas.

## Principals

Uchta principal turi — uchta auth surface, har bir front-end app uchun bittadan. Ular
bir-biriga overlap qilmaydi.

| Principal                              | Auth                                  | Bound to             | Capability                                                                     | App            |
| -------------------------------------- | ------------------------------------- | -------------------- | ------------------------------------------------------------------------------ | -------------- |
| **Platform user** ("superadmin")       | login + password; no permission model | no workshop          | platform-ops scope                                                             | superadmin app |
| **Workshop user — owner** (`is_owner`) | workshop code + login + password      | one workshop         | everything in the workshop on every branch, plus owner-only powers (see below) | workshop app   |
| **Workshop user — staff**              | workshop code + login + password      | one workshop         | exactly the `(permission, branch)` grants the owner gave them                  | workshop app   |
| **Client**                             | phone + Telegram OTP; no password     | no workshop (global) | own orders & cutting drafts; browse active branches of any workshop            | client app     |

## The model

- **Workshop user'lar** workshop `code` + login + password bilan kiradi. Code tenant namespaceni
  tanlaydi; login faqat shu workshop ichida unique. Owner'lar workshop provisioning chogʻida
  platform operator tomonidan yaratiladi.
- **Platform user'lar** login + password bilan kiradi va backend CLI orqali seed qilinadi (ular
  hierarchy'ning tepasida, shuning uchun ularni in-app yaratish uchun yuqoriroq principal mavjud
  emas).
- **Client'lar Telegram orqali yuborilgan one-time code bilan tasdiqlangan phone number bilan
  kiradi** — password yoʻq, fallback path yoʻq. Phone — bu identity; ular yangi raqam birinchi
  marta verify qilinganda oʻzini oʻzi self-register qiladi (faqat name).
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
      PG["permission grant<br/>branch-scoped"]
      B["branch · 1..N"]
      BMS["branch material<br/>selection"]
      SI["stock item"]
      BP["branch pricing"]

      W --> WU
      W --> B
      WU --> PG
      PG --> B
      B --> BMS
      B --> SI
      B --> BP

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
  | Platform operator | workshops bo'ylab platform-ops surfaces; workshop order-content yoki profile-edit scope yo'q |
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
