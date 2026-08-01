import { describe, expect, it } from 'vitest'

import { ru } from '@/shared/i18n/locales/ru'
import { uz } from '@/shared/i18n/locales/uz'
import cyrillicOverrides from '@/shared/i18n/overrides/uz-Cyrl.json'
import { transliterateMessages, type MessageTree } from '@/shared/i18n/transliterate'

function keyPaths(tree: MessageTree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return typeof value === 'string' ? [path] : keyPaths(value, path)
  })
}

/** vue-i18n picks a plural form by index, so a message that offers three forms
 *  in one locale and one in another silently renders the wrong noun rather than
 *  failing. Counted per message so the catalogs stay in step. */
function pluralForms(tree: MessageTree, prefix = ''): Map<string, number> {
  const out = new Map<string, number>()
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof value === 'string') {
      if (value.includes('|')) out.set(path, value.split('|').length)
    } else {
      for (const [nested, count] of pluralForms(value, path)) out.set(nested, count)
    }
  }
  return out
}

const uzKeys = keyPaths(uz)

describe('message catalogs', () => {
  it('ru defines exactly the keys uz defines', () => {
    const ruKeys = keyPaths(ru)
    expect([...ruKeys].sort()).toEqual([...uzKeys].sort())
  })

  it('uz-Cyrl is derived, so it defines exactly the keys uz defines', () => {
    const cyrillic = transliterateMessages(uz, cyrillicOverrides)
    expect([...keyPaths(cyrillic)].sort()).toEqual([...uzKeys].sort())
  })

  it('every uz-Cyrl override names a key that still exists', () => {
    const overridePaths = keyPaths(cyrillicOverrides as MessageTree).filter(
      (path) => path !== '$comment',
    )
    for (const path of overridePaths) expect(uzKeys).toContain(path)
  })

  it('a Russian plural message offers the three forms Russian needs', () => {
    for (const [path, forms] of pluralForms(ru)) {
      expect(forms, `${path} must offer one/few/many`).toBe(3)
    }
  })

  it('no message is left empty in any catalog', () => {
    for (const [name, tree] of [
      ['uz', uz],
      ['ru', ru],
    ] as const) {
      for (const path of keyPaths(tree)) {
        const value = path
          .split('.')
          .reduce<string | MessageTree>((node, key) => (node as MessageTree)[key], tree)
        expect(String(value).trim(), `${name}.${path} is empty`).not.toBe('')
      }
    }
  })
})

describe('derived uz-Cyrl catalog', () => {
  const cyrillic = transliterateMessages(uz, cyrillicOverrides)

  /** Splits on everything that is not a letter — an apostrophe included, so a
   *  protected name with an Uzbek ending (`Excel'да`) reads as two words. */
  const words = (value: string) => value.split(/[^A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ]+/).filter(Boolean)

  it('never leaves a word half-converted', () => {
    const mixed: string[] = []
    for (const path of keyPaths(cyrillic)) {
      const value = path
        .split('.')
        .reduce<string | MessageTree>((node, key) => (node as MessageTree)[key], cyrillic) as string
      for (const word of words(value)) {
        if (/[A-Za-z]/.test(word) && /[А-Яа-яЁёЎўҚқҒғҲҳ]/.test(word)) mixed.push(`${path}: ${word}`)
      }
    }
    expect(mixed).toEqual([])
  })

  it('writes э only where a word starts', () => {
    for (const path of keyPaths(cyrillic)) {
      const value = path
        .split('.')
        .reduce<string | MessageTree>((node, key) => (node as MessageTree)[key], cyrillic) as string
      expect(value, path).not.toMatch(/[А-Яа-яЁёЎўҚқҒғҲҳ]э/i)
    }
  })
})
