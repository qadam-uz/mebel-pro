---
title: Domain model
status: stable
owner: shape
updated: 2026-05-17
order: 45
---

# Domain model

System atrofida qurilgan til va asosiy noun'lar. Har bir entity boʻyicha tafsilot — field'lar,
state'lar, invariant'lar, child entity'lar, relationship'lar — [`ref/entities/`](ref/entities/)
da, har bir bounded context uchun bitta sahifada yashaydi.

## The main aggregates

- **Platform user** — platformani yurituvchi jamoa.
- **Workshop user** — workshop'ning shaxsi. Credential'lar va permission grant'lar toʻplamini olib
  yuradi; owner ulardan biri, full scope bilan. **Alohida "worker" entity yoʻq va role yoʻq** —
  cutter yoki edge bander shunchaki production grant'ni ushlab turgan workshop user; bir shaxs har
  bir grant'ni ushlab turishi mumkin. System hech qanday pay rate saqlamaydi.
- **Client** — workshop'ning mijozi; platforma uchun global, har bir order'da branch tanlaydi.
- **Workshop** — bitta furniture-cutting biznesi; tenant. Koʻp branch'ga ega.
- **Branch** — workshop'ning fizik joylashuvi. Oʻz stock'i, price'lari va material catalog'dan
  olib yuradigan selection'ga egalik qiladi.
- **Material** — ikki turdan biridan iborat platform-wide master record: **sheet** (kesiladigan
  board) yoki **edge** (edge-banding tape). Branch'lar qaysi birini olib yurishini tanlaydi va
  oʻz price'ini belgilaydi.
- **Stock item** — branch'ning bitta material boʻyicha on-hand balansi. **Supplier** — stock-in
  qayerdan kelgani (lightweight, talab boʻyicha qoʻshiladi).
- **Cutting result** — optimization run'ning output'i; gʻolib algoritmni nomlaydi.
- **Order** — client'ning branch'da panel kesilishi boʻyicha soʻrovi. Parts'ni, status history'ni
  va uni yakunlagan cutter / edger'ni (production report'lar oʻqiydigan input'lar) aggregate
  qiladi. U money ham, stock ham saqlamaydi.
- **Income** — workshop qabul qilgan money; order payment uni settle qiladigan order'ni olib
  yuradi.
- **Expense** — workshop sarflagan money: overhead'lar, u sotib oladigan consumable'lar va staff
  salary (accountant tomonidan hisoblanadi, system emas).

## Next

[`access-patterns.md`](access-patterns.md) — bu noun'larga kim nima qila oladi: principal'lar, access model va tenancy.
