import { describe, expect, it } from 'vitest'
import { fmt, fmtPhone, fmtSum, fmtTiyin, initialsOf } from '@/shared/format'

describe('money formatting', () => {
  it('groups thousands with a space', () => {
    expect(fmt(1234567)).toBe('1 234 567')
    expect(fmt(0)).toBe('0')
  })

  it('formats so’m', () => {
    expect(fmtSum(1234567)).toBe("1 234 567 so'm")
  })

  it('converts integer tiyin to a so’m string', () => {
    // 314 200 000 tiyin = 3 142 000 so'm
    expect(fmtTiyin(314200000)).toBe("3 142 000 so'm")
    expect(fmtTiyin(0)).toBe("0 so'm")
    // rounds to the nearest so'm
    expect(fmtTiyin(150)).toBe("2 so'm")
  })
})

describe('phone formatting', () => {
  it('groups a +998 number', () => {
    expect(fmtPhone('+998901003030')).toBe('+998 90 100 30 30')
    expect(fmtPhone('998901003030')).toBe('+998 90 100 30 30')
  })

  it('returns empty for nullish', () => {
    expect(fmtPhone(null)).toBe('')
    expect(fmtPhone(undefined)).toBe('')
  })
})

describe('initials', () => {
  it('takes first + last initials', () => {
    expect(initialsOf('Hasan Karimov')).toBe('HK')
    expect(initialsOf('Akmal')).toBe('A')
    expect(initialsOf(null)).toBe('?')
  })
})
