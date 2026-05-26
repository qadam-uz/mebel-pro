---
title: Domain model
status: stable
owner: shape
updated: 2026-05-25
order: 45
---

# Domain model

System qurilgan til va asosiy noun'lar. Per-entity tafsilot — field'lar, state'lar,
invariant'lar, bola entity'lar, munosabatlar — [`ref/entities/`](ref/entities/)'da, har bir
bounded context uchun bitta sahifada yashaydi.

## The main aggregates

- **Platform user** — platform'ni boshqaradigan jamoa.
- **Workshop user** — workshop'ning odami. Credential'larni va permission grant'lar
  toʻplamini olib yuradi; owner ulardan biri, toʻliq scope bilan. **Alohida "worker"
  entity yoʻq va role yoʻq** — cutter yoki edge bander shunchaki production grant ushlab
  turgan workshop user; bir odam har bir grant'ni ushlab turishi mumkin. System pay rate
  saqlamaydi.
- **Client** — workshop'ning mijozi; platform'ga global, har bir order uchun branch
  tanlaydi. Yangi cutting draft'larni seed qiladigan ixtiyoriy preferred branch'ni olib
  yuradi.
- **Workshop** — bir furniture-cutting biznesi; tenant. Koʻp branch'larga ega.
- **Branch** — workshop'ning jismoniy joyi. Oʻzining stock'ini, price'larini va material
  catalog'idan oʻzi olib yuradigan tanlovni olib yuradi.
- **Manufacturer** — material'ni kim ishlab chiqarganini nomlovchi platform-wide master
  record (Egger, Kronospan, Rehau, …). Material identity manufacturer'ni oʻz ichiga
  oladi.
- **Material** — ikki turdan biridan iborat platform-wide master record: **panel**
  (kesiladigan board) yoki **edge** (edge-banding tape). Har bir material oʻzining
  manufacturer'ini nomlaydi. Branch'lar qaysi birini olib yurishini tanlaydi va
  oʻzining price'ini belgilaydi.
- **Stock item** — bir material uchun branch'ning on-hand balance'i. **Supplier** —
  stock-in qaerdan kelganini (yengil, kerak boʻlganda qoʻshiladi; manufacturer'dan
  farqli).
- **Cutting result** — optimization run'ining output'i; gʻolib algoritmni nomlaydi.
  Har bir panel material uchun kerakli panel'lar va har bir edge material uchun
  kerakli edge metr'larni qayd etadi.
- **Order** — client'ning branch'da kesilgan panel'larga soʻrovi. Part'larni, per-side
  edge tanlovlarini, status history'ni va uni tugatgan cutter / edger'ni (production
  report'lar oʻqiydigan input'lar) jamlaydi. Pul va stock ushlab turmaydi.
- **Income** — workshop olgan pul; order payment u settle qiladigan order'ni olib
  yuradi.
- **Expense** — workshop sarflagan pul: overhead'lar, sotib oladigan consumable'lar
  va staff salary (system emas, accountant hisoblaydi).

## Next

[`access-patterns.md`](access-patterns.md) — kim oʻsha noun'lar bilan nima qila oladi:
principal'lar, access model va tenancy.
