import { describe, expect, it } from 'vitest'

import { transliterateMessages, transliterateText } from '@/shared/i18n/transliterate'

describe('transliterateText', () => {
  it('maps the plain alphabet', () => {
    expect(transliterateText('bekor qilish')).toBe('бекор қилиш')
    expect(transliterateText('material katalogi')).toBe('материал каталоги')
    expect(transliterateText('xarajat')).toBe('харажат')
  })

  it('treats o‘ and g‘ as single letters', () => {
    expect(transliterateText("so'm")).toBe('сўм')
    expect(transliterateText("to'lov")).toBe('тўлов')
    expect(transliterateText("yog'och")).toBe('ёғоч')
    expect(transliterateText("bo'lim")).toBe('бўлим')
  })

  it("keeps yo' apart from yo — the yo'q / ёқ trap", () => {
    expect(transliterateText("yo'q")).toBe('йўқ')
    expect(transliterateText("yo'l")).toBe('йўл')
    expect(transliterateText('yordam')).toBe('ёрдам')
    expect(transliterateText('quyosh')).toBe('қуёш')
    expect(transliterateText('dunyo')).toBe('дунё')
  })

  it('maps the remaining y-digraphs', () => {
    expect(transliterateText('yulduz')).toBe('юлдуз')
    expect(transliterateText('yaxshi')).toBe('яхши')
    expect(transliterateText('yer')).toBe('ер')
  })

  it('maps sh and ch', () => {
    expect(transliterateText('ishlab chiqarish')).toBe('ишлаб чиқариш')
    expect(transliterateText('kesish')).toBe('кесиш')
  })

  it('writes word-initial e as э and medial e as е', () => {
    expect(transliterateText('ertaga')).toBe('эртага')
    expect(transliterateText('emas')).toBe('эмас')
    expect(transliterateText('kelmoqda')).toBe('келмоқда')
    expect(transliterateText('Faol emas')).toBe('Фаол эмас')
  })

  it('writes a bare apostrophe as the tutuq belgisi', () => {
    expect(transliterateText("ta'minotchi")).toBe('таъминотчи')
    expect(transliterateText("san'at")).toBe('санъат')
    expect(transliterateText("ma'lumot")).toBe('маълумот')
  })

  it('carries capitalisation across, including digraphs', () => {
    expect(transliterateText('Bekor qilish')).toBe('Бекор қилиш')
    expect(transliterateText('Shu')).toBe('Шу')
    expect(transliterateText('Chizma')).toBe('Чизма')
    expect(transliterateText("O'chirish")).toBe('Ўчириш')
    expect(transliterateText('SHART')).toBe('ШАРТ')
  })

  it('accepts every apostrophe shape the repo has used', () => {
    expect(transliterateText('soʻm')).toBe('сўм')
    expect(transliterateText('so’m')).toBe('сўм')
    expect(transliterateText('so`m')).toBe('сўм')
  })

  it('leaves interpolation placeholders untouched', () => {
    expect(transliterateText('{count} ta detal')).toBe('{count} та детал')
    expect(transliterateText('Jami {total} so’m')).toBe('Жами {total} сўм')
    expect(transliterateText('{n} kun oldin')).toBe('{n} кун олдин')
  })

  it('leaves linked-message references untouched', () => {
    expect(transliterateText('@:common.action.cancel')).toBe('@:common.action.cancel')
    expect(transliterateText('Bekor: @:common.action.cancel')).toBe('Бекор: @:common.action.cancel')
  })

  it('leaves protected file formats and product names alone', () => {
    expect(transliterateText('PDF yuklab olish')).toBe('PDF юклаб олиш')
    expect(transliterateText('CSV yoki XML fayl')).toBe('CSV ёки XML файл')
    expect(transliterateText('Mebel Pro')).toBe('Mebel Pro')
    expect(transliterateText('2D-Place')).toBe('2D-Place')
  })

  it('leaves file extensions as tokens', () => {
    expect(transliterateText('CSV, XML yoki MAP (*.csv, *.xml, *.map)')).toBe(
      'CSV, XML ёки MAP (*.csv, *.xml, *.map)',
    )
  })

  it('still converts dotted letters — initials and a date mask are not extensions', () => {
    expect(transliterateText('F.I.Sh.')).toBe('Ф.И.Ш.')
    expect(transliterateText("Sana kk.oo.yyyy ko'rinishida")).toBe('Сана кк.оо.йййй кўринишида')
  })

  it('takes an Uzbek suffix onto a protected name without mangling the name', () => {
    expect(transliterateText("Excel'da tayyorlangan")).toBe("Excel'да тайёрланган")
    expect(transliterateText("PDF'ni yuklash")).toBe("PDF'ни юклаш")
  })

  it('passes numbers, punctuation and already-Cyrillic text through', () => {
    expect(transliterateText('12 500')).toBe('12 500')
    expect(transliterateText('Kirim — 3 dona')).toBe('Кирим — 3 дона')
    expect(transliterateText('БАЗИС paneli')).toBe('БАЗИС панели')
  })

  it('keeps the plural separator', () => {
    expect(transliterateText('{n} ta detal | {n} ta detal')).toBe('{n} та детал | {n} та детал')
  })

  it('handles a real sentence end to end', () => {
    expect(transliterateText("Bu chizmada detal yo'q")).toBe('Бу чизмада детал йўқ')
    expect(transliterateText('Buyurtma yaratish')).toBe('Буюртма яратиш')
    expect(transliterateText('Xodimlar sessiyalari darhol bekor qilinadi.')).toBe(
      'Ходимлар сессиялари дарҳол бекор қилинади.',
    )
  })
})

describe('transliterateMessages', () => {
  it('walks nested catalogs', () => {
    expect(
      transliterateMessages({
        common: { action: { cancel: 'Bekor qilish', close: 'Yopish' } },
        orders: { empty: "Buyurtma yo'q" },
      }),
    ).toEqual({
      common: { action: { cancel: 'Бекор қилиш', close: 'Ёпиш' } },
      orders: { empty: 'Буюртма йўқ' },
    })
  })

  it('lets an override replace a single message and leaves its siblings derived', () => {
    expect(
      transliterateMessages(
        { catalog: { ldsp: 'LDSP', note: 'Material tanlang' } },
        { catalog: { ldsp: 'ЛДСП' } },
      ),
    ).toEqual({ catalog: { ldsp: 'ЛДСП', note: 'Материал танланг' } })
  })
})
