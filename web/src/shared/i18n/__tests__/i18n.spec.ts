import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  DEFAULT_LOCALE,
  i18n,
  initialLocale,
  isLocale,
  russianPluralIndex,
  setLocale,
} from '@/shared/i18n'

const STORAGE_KEY = 'mp-locale:v1'

afterEach(async () => {
  window.localStorage.clear()
  await setLocale(DEFAULT_LOCALE)
})

describe('initialLocale', () => {
  beforeEach(() => window.localStorage.clear())

  it('is Uzbek with nothing stored', () => {
    expect(initialLocale()).toBe('uz')
  })

  it('restores a stored preference', () => {
    window.localStorage.setItem(STORAGE_KEY, 'ru')
    expect(initialLocale()).toBe('ru')
  })

  it('ignores a stored value that is no longer a locale', () => {
    window.localStorage.setItem(STORAGE_KEY, 'en')
    expect(initialLocale()).toBe('uz')
  })
})

describe('isLocale', () => {
  it('accepts the three shipped locales and nothing else', () => {
    expect(isLocale('uz')).toBe(true)
    expect(isLocale('uz-Cyrl')).toBe(true)
    expect(isLocale('ru')).toBe(true)
    expect(isLocale('en')).toBe(false)
    expect(isLocale(undefined)).toBe(false)
  })
})

describe('russianPluralIndex', () => {
  const cases: Array<[number, number]> = [
    [1, 0],
    [21, 0],
    [101, 0],
    [2, 1],
    [3, 1],
    [4, 1],
    [22, 1],
    [5, 2],
    [11, 2],
    [12, 2],
    [14, 2],
    [25, 2],
    [0, 2],
  ]

  it.each(cases)('picks form %i → index %i', (count, index) => {
    expect(russianPluralIndex(count, 3)).toBe(index)
  })

  it('falls back to the last available form when a message has fewer', () => {
    expect(russianPluralIndex(5, 2)).toBe(1)
  })

  it('returns the only form when a message has one', () => {
    expect(russianPluralIndex(5, 1)).toBe(0)
  })
})

describe('setLocale', () => {
  it('switches messages, marks the document and remembers the choice', async () => {
    await setLocale('ru')

    expect(i18n.global.t('common.action.cancel')).toBe('Отмена')
    expect(document.documentElement.lang).toBe('ru')
    expect(document.documentElement.dataset.locale).toBe('ru')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('ru')
  })

  it('derives the Cyrillic catalog from the Uzbek one', async () => {
    await setLocale('uz-Cyrl')

    expect(i18n.global.t('common.action.cancel')).toBe('Бекор қилиш')
    expect(i18n.global.t('common.state.loading')).toBe('Юкланмоқда…')
    expect(document.documentElement.lang).toBe('uz-Cyrl')
  })

  it('serves the Uzbek message for a key the target locale has not translated yet', async () => {
    i18n.global.setLocaleMessage('ru', { common: { action: { cancel: 'Отмена' } } } as never)
    await setLocale('ru')

    expect(i18n.global.t('common.field.name')).toBe('Nomi')
  })
})
