import { describe, expect, it } from 'vitest'

import { additionalPhoneErrors } from '@/shared/app/branchPhones'

const PRIMARY = '+998901111111'

describe('additionalPhoneErrors', () => {
  it('passes a list of distinct, well-formed numbers', () => {
    expect(
      additionalPhoneErrors(['+998902222222', '+998903333333', '+998904444444'], PRIMARY),
    ).toEqual([undefined, undefined, undefined])
  })

  it('flags a badly formatted number with the same rule as the primary field', () => {
    expect(additionalPhoneErrors(['901234567'], PRIMARY)).toEqual([
      '+998XXXXXXXXX formatida kiriting.',
    ])
  })

  it('flags an empty row so a blank line can never be submitted', () => {
    expect(additionalPhoneErrors([''], PRIMARY)).toEqual([
      "Raqamni kiriting yoki qatorni o'chiring.",
    ])
  })

  it('flags a row that repeats the primary number', () => {
    expect(additionalPhoneErrors([PRIMARY], PRIMARY)).toEqual(['Bu asosiy raqam bilan bir xil.'])
  })

  it('flags only the later of two identical rows, so the first stays usable', () => {
    expect(additionalPhoneErrors(['+998902222222', '+998902222222'], PRIMARY)).toEqual([
      undefined,
      "Bu raqam ro'yxatda bor.",
    ])
  })

  it('returns messages index-aligned with the rows it was given', () => {
    expect(additionalPhoneErrors(['+998902222222', 'nope', '+998903333333'], PRIMARY)).toEqual([
      undefined,
      '+998XXXXXXXXX formatida kiriting.',
      undefined,
    ])
  })
})
