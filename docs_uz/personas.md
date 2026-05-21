---
title: Personas
status: stable
owner: shape
updated: 2026-05-22
order: 30
---

# Personas

v1 kim uchun qurilgan odamlar. Ulardan toʻrttasi, uchta app boʻylab — platform-ops console, workshop
tomoni uchun workshop app va customer tomoni uchun client app.

## Platform operator

Platformani yurituvchi jamoa. Yangi workshop'larni va ularning birinchi owner'ini onboard qiladi;
workshop'ni block yoki unblock qiladi; barcha workshop'lar boʻylab platformani incident'larga
kuzatadi; platform-wide job'larni va error monitor'ni boshqaradi. Workshop user emas — hech kimning
kundalik ishini yuritmaydi.

## Workshop owner

Furniture workshop'ga egalik qiluvchi yoki uni yurituvchi shaxs. Oʻz workshop'i ichidagi top
authority: workshop'ni boshidan oxirigacha tiklaydi (branches, stock, pricing, staff va har bir
branch platforma material catalog'idan nimani olib yurishi), staff permission'larini grant va
revoke qiladi, order pipeline va books'ni nazorat qiladi va owner-only richaglarni — staff va
branch yaratish, branch pricing belgilash va workshop-wide report'lar — ushlab turadi.
Platforma tomonidan provision qilinadi; workshop ichidan yaratib yoki demote qilib boʻlmaydi.

## Workshop staff

Branch xodimlari — order desk, warehouse, cutter, edge bander, accountant. **Fixed role'lar
emas**: har biri owner unga muayyan branch'larda bergan permission set bilan kiradi, ular nima
qila olishi aynan shu grant'lar qamragan narsadir va bir shaxs ularning hammasini ushlab, butun
flow'ni yolgʻiz yurita oladi. Hech qanday grant'siz yangi yaratilgan staff member kira oladi va
amal qilsa boʻladigan hech narsani koʻrmaydi. Amalda grant'lar quyidagilarni qamraydi: order'larni
verify qilish va oldinga surish, cutting / banding ishini bajarish, stock va supplier'larni joriy
holatda saqlash va workshop'ning income va expense'larini yozish.

## Client

Workshop'ning mijozi — panel kestirishi kerak boʻlgan shaxs yoki kichik biznes. Talab boʻyicha
Telegram orqali tasdiqlangan phone number bilan parolsiz oʻzini oʻzi self-register qiladi; platforma uchun global, har bir
order'da workshop va branch tanlaydi. Ham desktop browser, ham telefondan foydalanadi; v1'da
priority — desktop web tajribasi, keyinroq mobile-first pass rejalashtirilgan. Koʻpincha
first-time, koʻpincha workshop'lar boʻylab variantlarni solishtiradi. Faqat oʻz
tomonini koʻradi: catalog, cutting result, oʻz order'lari va qarzdorligi (order ready boʻlgach
koʻrinadi) — workshop'ning internal'lari haqida hech narsa emas.

## Next

[`domain-model.md`](domain-model.md) — bu odamlar boʻlishadigan til va entity map.
