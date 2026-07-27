# QAD-163 — copy audit for native-speaker review

**Read this file, not the diff.** Every user-visible string this branch changes is
listed below as before → after. The table is generated from
`git diff origin/main..HEAD`, so it cannot silently omit a change.

Nothing here is merged. This branch is open for your review as a native Uzbek
speaker.

---

## 1. Needs your ruling — one decision, not five

The ticket listed five terminology pairs to choose between. Counting real usage
dissolved four of them; **only one is a genuine split.**

| Concept | Counts (Vue templates) | Verdict |
|---|---|---|
| **`qism` vs `detal`** | `qism*` **33** · `detal*` **22** | ⬅ **your call — nothing was changed** |
| `buyurtma` vs `zakaz` | 262 · **0** | already settled, no `zakaz` anywhere |
| `ta'minotchi` vs `postavshik` | 21 · **0** | already settled |
| `ustama` vs `nadbavka` | 25 · **0** | already settled |
| `filial` vs `bo'lim` | 149 · 16 | `filial` dominant; the 16 are the unrelated sense of *section* (e.g. `Profil bo'limlari`), correctly left alone |

**Two corrections to my own ticket, found by counting rather than assuming:**

- **`kirim` vs `tushum` are not variants of one concept.** They are two different
  things in this product: **`Kirim`** is an inventory arrival (`Kirimlar`,
  `Kirim (faktura)`, `K-…` invoice numbers) and **`Tushum`** is finance income
  (`Tushum va xarajat`, `Tushumlar`). Standardising on one would have been a bug,
  not a cleanup. Nothing was changed.
- **`skidka` is already gone from user-visible copy.** The four remaining hits are
  in Python comments and docstrings (`debts.py`, `schemas.py`, `invoices.py`,
  `models.py`), where developer shorthand is fine. The one that *was* user-visible —
  in the akt sverka PDF — is changed to `chegirma` below.

**On `qism` / `detal`:** both appear in the cutting editor for the same thing — a
part on a drawing. Note some `qism` hits are the ordinary sense of *part of*
(`qismi`, `qismga`), which is not the same word choice; that distinction needs a
native ear, which is why nothing was touched. Tell me which you want and I will
apply it in one pass.

---

## 2. What changed by itself, without a ruling

Orthography and loanword fixes that are correct regardless of the above:

- `xujjat` → **`hujjat`** (correct Uzbek Latin)
- `skidka` → **`chegirma`** in the akt sverka PDF
- Backtick and curly-quote apostrophes → the correct `'` — `bo\`ldi` → `bo'ldi`,
  `qoldig'i` (with `‘`) → `qoldig'i`

Plus the ticket's 8-point standard applied across error maps, empty states,
buttons, placeholders and hints — all of it in the tables below.

---

## 3. Every changed string



## `backend/app/modules/cutting/pdf_document.py`

| Before | After |
|---|---|
| Kesish xujjati | Kesish hujjati |
| Mebel Pro — kesish xujjati | Mebel Pro — kesish hujjati |
| Mebel Pro — kesish xujjati | Mebel Pro — kesish hujjati |

## `backend/app/modules/finance/statement_pdf.py`

| Before | After |
|---|---|
| skidka {_money(row.discount_tiyin)} | chegirma {_money(row.discount_tiyin)} |

## `web/src/shared/app/__tests__/clientUi.spec.ts`

| Before | After |
|---|---|
| Tayyor bo`ldi | Tayyor bo'ldi |
| Tayyor bo`ldi | Tayyor bo'ldi |
| Ombor qoldig‘i manfiy | Ombor qoldig'i manfiy |

## `web/src/shared/app/__tests__/workshopOrderDetail.spec.ts`

| Before | After |
|---|---|
| converts a fixed adjustment from so’m to tiyin, grouping included | converts a fixed adjustment from so'm to tiyin, grouping included |

## `web/src/shared/app/adminUi.ts`

| Before | After |
|---|---|
|  | APIError |
|  | Amal bajarilmadi |
|  | apiValidationMessage |
|  | adminValidation.ts |
|  | Bu amal uchun ruxsatingiz yo'q. |
|  | Bu amal uchun ruxsatingiz yo'q. |
|  | O'z hisobingizni bloklab bo'lmaydi. |
|  | Oxirgi faol adminni bloklab bo'lmaydi — avval boshqasini qo'shing. |
|  | Admin topilmadi — ro'yxatni yangilang. |
|  | Bu login band. Boshqa login tanlang. |
|  | Parol yetarlicha kuchli emas — katta/kichik harf va raqam ishlating. |
|  | Ustaxona topilmadi — ro'yxatni yangilang. |
|  | Bu holat allaqachon qo'yilgan. |
|  | Sababni yozing. |
|  | Ishlab chiqaruvchi topilmadi — ro'yxatni yangilang. |
|  | Bu ishlab chiqaruvchi allaqachon bor. |
|  | Material topilmadi — ro'yxatni yangilang. |
|  | Xatolik yozuvi topilmadi — ro'yxatni yangilang. |
|  | Bunday fon vazifa ro'yxatdan o'tmagan. |
|  | Bildirishnoma topilmadi — ro'yxatni yangilang. |
|  | Bu fayl turini yuklab bo'lmaydi — JPEG yoki PNG tanlang. |
|  | Bu fayl turi rasm sifatida biriktirilmaydi. |
|  | Fayl juda katta — kichikroq rasm tanlang. |
|  | Fayl topilmadi — rasmni qaytadan yuklang. |
|  | Fayl ombori javob bermayapti. Birozdan so'ng qayta urinib ko'ring. |

## `web/src/shared/app/clientUi.ts`

| Before | After |
|---|---|
| Ombor qoldig‘i manfiy | Ombor qoldig'i manfiy |

## `web/src/shared/app/workshopUi.ts`

| Before | After |
|---|---|
| koʻrib chiqish kerak | ko'rib chiqish kerak |
| toʻxtatilgan | to'xtatilgan |

## `web/src/shared/components/AppShell.vue`

| Before | After |
|---|---|
| Workshop navigation | Ustaxona navigatsiyasi |
| Buyurtma, mijoz, xodim yoki material... | Buyurtma, mijoz, xodim yoki material |
| Superadmin navigation | Platforma navigatsiyasi |

## `web/src/shared/components/BranchMaterialAttachSheet.vue`

| Before | After |
|---|---|
| Material qidirish... | Material nomi yoki dekor kodi |

## `web/src/shared/components/ConfirmDialog.vue`

| Before | After |
|---|---|
| Confirm | Tasdiqlash |
| Cancel | Bekor qilish |
| Working | Bajarilmoqda… |

## `web/src/shared/components/CuttingEdgePickerModal.vue`

| Before | After |
|---|---|
| Kromka qidirish… | Kromka nomi yoki dekor kodi |

## `web/src/shared/components/FilePicker.vue`

| Before | After |
|---|---|
| Yuklanmoqda... | Yuklanmoqda… |

## `web/src/shared/components/ImageUploadField.vue`

| Before | After |
|---|---|
| Rasm yuklanmoqda... | Rasm yuklanmoqda… |

## `web/src/shared/components/NotificationsMenu.vue`

| Before | After |
|---|---|
| Bildirishnomalar | Bildirishnomalar |
| Notifications | `Bildirishnomalar — ${notifications.unread} o'qilmagan` |
| `Bildirishnomalar - ${notifications.unread} o'qilmagan` | lmadi. Qayta urinib ko |
| Hammasini o'qilgan deb belgilash |  |
| Mark all read |  |
| Bildirishnomalar yuklanmoqda |  |
| Loading notifications |  |
| Bildirishnomalarni yuklab bo'lmadi. |  |
| Notifications could not be loaded. |  |
| Bildirishnoma yo'q. |  |
| Nothing new. |  |

## `web/src/shared/components/ProjectDropdown.vue`

| Before | After |
|---|---|
| No context | Tanlanmagan |

## `web/src/shared/composables/useStaffLogin.ts`

| Before | After |
|---|---|
| Credentials do not match an active account. | Login yoki parol noto'g'ri. |
| Account is locked. Try again later. | Hisob vaqtincha bloklangan. Birozdan so'ng urinib ko'ring. |
| Account is blocked. | Hisob bloklangan — ustaxona rahbariga murojaat qiling. |
| Too many attempts. Try again later. | Juda ko'p urinish. Birozdan so'ng urinib ko'ring. |
| API is not reachable. | Server bilan bog'lanib bo'lmadi. Internet aloqasini tekshiring. |
| Sign-in failed. | Kirib bo'lmadi. Qayta urinib ko'ring. |

## `web/src/shared/stores/cuttingImport.ts`

| Before | After |
|---|---|
| Bu fayl turi qo'llab-quvvatlanmaydi - faqat CSV, XML yoki MAP. БАЗИС-Мебельщик'da «Спецификация в CSV/XML», 2D-Place'da esa MAP orqali saqlang. | Bu fayl turi qo'llab-quvvatlanmaydi — faqat CSV, XML yoki MAP. БАЗИС-Мебельщик'da «Спецификация в CSV/XML», 2D-Place'da esa MAP orqali saqlang. |
| Fayl 1 MB dan katta | Fayl 1 MB dan katta — faylni bo'lib yuklang. |
| Fayl bo'sh | Faylda qator yo'q — to'ldirilgan faylni tanlang. |
| Ustunlar mosligi noto'g'ri | Ustunlar mosligi noto'g'ri — ustunlarni qayta belgilang. |
| Faylda ${total} dona detal - bir optimallashtirishga eng ko'pi 300 dona. Faylni bo'lib yuklang | import qilib bo'lmadi |
| Faylda detal ko'p - bir optimallashtirishga eng ko'pi 300 dona. Faylni bo'lib yuklang | Faylni o'qib bo'lmadi — XML buzilgan yoki to'liq emas. |
|  | 2D-Place MAP faylni o'qib bo'lmadi. |
|  | Needs your ruling |
|  | MAP faylda 50 mm dan kichik detal bor. |
|  | Faylda ${total} dona detal — bir optimallashtirishga eng ko'pi 300 dona. Faylni bo'lib yuklang. |
|  | Faylda detal ko'p — bir optimallashtirishga eng ko'pi 300 dona. Faylni bo'lib yuklang. |

## `web/src/shared/views/AdminDashboardView.vue`

| Before | After |
|---|---|
| Ish qayta ishga tushirildi | Fon vazifa qayta ishga tushirildi |
| Ish ishga tushmadi | Fon vazifa ishga tushmadi. |

## `web/src/shared/views/AdminLoginView.vue`

| Before | After |
|---|---|
| Login yoki parol noto'g'ri. |  |
| Hisob vaqtincha bloklangan. Birozdan so'ng urinib ko'ring. |  |
| Hisob bloklangan. |  |
| Juda ko'p urinish. Birozdan so'ng urinib ko'ring. |  |
| Server bilan bog'lanib bo'lmadi. |  |
| Kirib bo'lmadi. |  |

## `web/src/shared/views/AdminManufacturersView.vue`

| Before | After |
|---|---|
| Ishlab chiqaruvchi saqlanmadi | Ishlab chiqaruvchi saqlanmadi. |
| Amal bajarilmadi | Ishlab chiqaruvchi holatini o'zgartirib bo'lmadi. |
| LDSP . asosiy brand | LDSP · asosiy brend |

## `web/src/shared/views/AdminMaterialsView.vue`

| Before | After |
|---|---|
| Rasmni yuklab bo'lmadi. Boshqa fayl bilan qayta urinib ko'ring. | rasmni yuklab bo'lmadi |
| Rasmni yuklab bo'lmadi | Rasmni yuklab bo'lmadi. Boshqa fayl bilan qayta urinib ko'ring. |
| Amal bajarilmadi | Material holatini o'zgartirib bo'lmadi. |
| Material nomi | Material nomi yoki dekor kodi |

## `web/src/shared/views/AdminNotificationsView.vue`

| Before | After |
|---|---|
| Belgilab bo'lmadi | Bildirishnomani o'qilgan deb belgilab bo'lmadi. Qayta urinib ko'ring. |
| Belgilab bo'lmadi | Hammasini o'qilgan deb belgilab bo'lmadi. Qayta urinib ko'ring. |
| Hammasi o'qilgan deb belgilandi | Hammasi o'qilgan deb belgilandi |

## `web/src/shared/views/AdminPlatformErrorsView.vue`

| Before | After |
|---|---|
| Amal bajarilmadi | Xatolikni hal qilingan deb belgilab bo'lmadi. |
| Amal bajarilmadi | Xatolikni qayta ochib bo'lmadi. |

## `web/src/shared/views/AdminPlatformJobsView.vue`

| Before | After |
|---|---|
| Ish muvaffaqiyatsiz tugadi | Fon vazifa xatolik bilan tugadi — jurnalni ko'ring. |
| Ish ishga tushirildi | Fon vazifa ishga tushirildi |
| Ish ishga tushmadi | Fon vazifa ishga tushmadi. |

## `web/src/shared/views/AdminPlatformUsersView.vue`

| Before | After |
|---|---|
| Admin amali bajarilmadi | Admin saqlanmadi. |
| Parolni qaytarib bo'lmadi | Parolni tiklab bo'lmadi. |
| Oxirgi faol adminni bloklab bo'lmaydi | Adminni bloklab bo'lmadi. |
| Adminni bloklab bo'lmadi | Adminni blokdan chiqarib bo'lmadi. |
| Adminni blokdan chiqarib bo'lmadi |  |

## `web/src/shared/views/AdminWorkshopDetailView.vue`

| Before | After |
|---|---|
| Ustaxonani bloklab bo'lmadi | Ustaxonani bloklab bo'lmadi. |
| Ustaxonani blokdan chiqarib bo'lmadi | Ustaxonani blokdan chiqarib bo'lmadi. |
| Rahbarning parolini tiklab bo'lmadi | Rahbarning parolini tiklab bo'lmadi. |

## `web/src/shared/views/AdminWorkshopsView.vue`

| Before | After |
|---|---|
| Ustaxonani bloklab bo'lmadi | Ustaxonani bloklab bo'lmadi. |
| Ustaxonani blokdan chiqarib bo'lmadi | Ustaxonani blokdan chiqarib bo'lmadi. |
| Ustaxona qo'shilmadi | Ustaxona qo'shilmadi. |

## `web/src/shared/views/ClientBranchesView.vue`

| Before | After |
|---|---|
| Ustaxona yoki shahar nomi bo'yicha qidirish... | Ustaxona yoki shahar nomi |

## `web/src/shared/views/ClientOrdersView.vue`

| Before | After |
|---|---|
| Buyurtma raqami... |  |

## `web/src/shared/views/ClientProfileView.vue`

| Before | After |
|---|---|
|  | q — joriy sessiya keyingi yangilashda ko |

## `web/src/shared/views/WorkshopBranchDetailView.vue`

| Before | After |
|---|---|
| Vaqtincha yopiq | Vaqtincha yopiq |
| sabab bilan ko`rinadi | sabab bilan ko'rinadi |

## `web/src/shared/views/WorkshopCatalogView.vue`

| Before | After |
|---|---|
| Material qidirish... | Material nomi yoki dekor kodi |

## `web/src/shared/views/WorkshopFinanceDebtsView.vue`

| Before | After |
|---|---|
| Mijozning qarzi oshadi | Mijozning qarzi oshadi |
| daftar qarzi, qo`shimcha | daftar qarzi, qo'shimcha |
| Qarz yo`q | Qarz yo'q |
| skidka ${formatTiyin(row.discount_tiyin)} | chegirma ${formatTiyin(row.discount_tiyin)} |
| Ta'minotchi nomi... | Ta'minotchi nomi |
| Mijoz nomi yoki telefoni... | Mijoz nomi yoki telefoni |

## `web/src/shared/views/WorkshopFinanceExpensesView.vue`

| Before | After |
|---|---|
| ${invoice.invoice_no} · ${invoice.supplier_name ?? 'ta | ${invoice.invoice_no} · ${invoice.supplier_name ?? "ta'minotchisiz"} |
| ${invoice.supplier_name ?? 'ta | ${invoice.supplier_name ?? "ta'minotchisiz"} · ${invoice.branch_name ?? 'filialsiz'} |
| } · ${invoice.branch_name ??  | Aksessuar |
| Aksessuar | mayda ta'minot |
| mayda ta`minot | Transport |
| Transport | yetkazish/yo'l |
| yetkazish/yo`l | Soliqlar |
| Soliqlar | majburiy to'lovlar |
| majburiy to`lovlar | Maosh |
| Maosh | xodim to'lovi |
| xodim to`lovi | Buyurtma to'lovi |
| Buyurtma to'lovi | buyurtmaga bog'langan |
| buyurtmaga bog`langan | Boshqa tushum |
| Boshqa tushum | qo'lda yozuv |
| qo`lda yozuv | Bank |
| Bank | o'tkazma yoki karta |
| o`tkazma yoki karta | K-0007 yoki ta'minotchi |
| K-0007 yoki ta`minotchi | To'lanmagan kirim topilmadi |
| To`lanmagan kirim topilmadi | expenseForm.vendor |
| expenseForm.vendor | Masalan: Oq Mramor MChJ |
| incomeForm.note | incomeForm.note |
|  | Masalan: Kapital bank, kassa 2 |

## `web/src/shared/views/WorkshopInventoryView.vue`

| Before | After |
|---|---|
| Ta`minotchini tanlang. | Ta'minotchini tanlang. |
| Skidka oraliq jamidan katta bo`la olmaydi. | Chegirma oraliq jamidan katta bo'la olmaydi. |
| Material qidirish... | Material nomi yoki dekor kodi |
| invoiceSearch | invoiceSearch |
| K-0007 yoki ta`minotchi... | K-0007 yoki ta'minotchi |
| To`lov holati | To'lov holati |
| Ta`minotchi | Ta'minotchi |
| invoiceForm.note | invoiceForm.note |
| Filtr bo`yicha kirim topilmadi | Masalan: yuk mashinasi bilan keldi |
| Qidiruv yoki to`lov holatini o`zgartiring. | Filtrga mos kirim topilmadi |
| st-empty !border-0 !py-8 | Qidiruvni yoki to'lov holatini o'zgartiring. |
| st-empty !border-0 !py-8 | st-empty !border-0 !py-8 |
|  | st-empty !border-0 !py-8 |

## `web/src/shared/views/WorkshopLoginView.vue`

| Before | After |
|---|---|
| Login yoki parol noto'g'ri. |  |
| Hisob vaqtincha bloklangan. Birozdan so'ng urinib ko'ring. |  |
| Hisob bloklangan. |  |
| Juda ko'p urinish. Birozdan so'ng urinib ko'ring. |  |
| Server bilan bog'lanib bo'lmadi. |  |
| Kirib bo'lmadi. |  |

## `web/src/shared/views/WorkshopOrderDetailView.vue`

| Before | After |
|---|---|
| qalinlik yo‘q | qalinlik yo'q |
| qalinlik yo‘q | qalinlik yo'q |

## `web/src/shared/views/WorkshopOrdersView.vue`

| Before | After |
|---|---|
| kesuvchi yo‘q | kesuvchi yo'q |
| kromka ustasi yo‘q | kromka ustasi yo'q |
| Bu buyurtmani orqaga qaytarib bo‘lmaydi. | Bu buyurtmani orqaga qaytarib bo'lmaydi. |
| Faqat keyingi bosqichga o‘tkazish mumkin. | Faqat keyingi bosqichga o'tkazish mumkin. |
| Bu o‘tishni hozir bajarib bo‘lmaydi (ruxsat yoki tayinlash kerak). | Bu o'tishni hozir bajarib bo'lmaydi — ruxsat yoki tayinlash kerak. |
|  | Filtrga mos buyurtma topilmadi |
|  | Hali buyurtma yo'q |
|  | Filtrlarni o'zgartiring yoki tozalang. |
|  | Mijoz buyurtma bergach yoki «+ Yangi buyurtma» orqali yozilgach shu yerda ko'rinadi. |

## `web/src/shared/views/WorkshopUsersView.vue`

| Before | After |
|---|---|
| bo'sh qoldirilsa avtomatik yaratiladi | Bo'sh qoldirilsa avtomatik yaratiladi |
| Ism yoki login... | Ism yoki login |
| st-empty !border-0 !py-8 | st-empty !border-0 !py-8 |
|  | Mos xodim topilmadi |
|  | Hali xodim yo'q |
|  | Ism yoki login bo'yicha qidiruvni o'zgartiring. |
|  | «+ Yangi xodim» orqali birinchi xodimni qo'shing. |


---

**139 strings removed/replaced, 158 written, across 39 files.**
