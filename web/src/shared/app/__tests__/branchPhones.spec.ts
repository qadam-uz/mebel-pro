import { describe, expect, it } from 'vitest'

import { additionalPhoneErrors, branchPhoneList } from '@/shared/app/branchPhones'

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

// Decision 24: every client surface that shows a branch phone shows all of
// them, in this order.
describe('branchPhoneList', () => {
  it('puts the primary first and keeps the extras in their stored order', () => {
    expect(branchPhoneList(PRIMARY, ['+998903333333', '+998902222222'])).toEqual([
      PRIMARY,
      '+998903333333',
      '+998902222222',
    ])
  })

  it('is just the primary when a branch publishes one number', () => {
    expect(branchPhoneList(PRIMARY)).toEqual([PRIMARY])
    expect(branchPhoneList(PRIMARY, [])).toEqual([PRIMARY])
    expect(branchPhoneList(PRIMARY, null)).toEqual([PRIMARY])
  })

  it('drops blanks and collapses a repeat, so a list keyed by number stays valid', () => {
    expect(branchPhoneList(PRIMARY, ['', '   ', PRIMARY, '+998902222222'])).toEqual([
      PRIMARY,
      '+998902222222',
    ])
  })

  it('renders nothing rather than an empty link when there is no number at all', () => {
    expect(branchPhoneList(null, [])).toEqual([])
    expect(branchPhoneList('  ')).toEqual([])
  })
})
