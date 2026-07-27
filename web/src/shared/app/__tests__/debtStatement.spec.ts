import { describe, expect, it } from 'vitest'

import {
  balanceDirection,
  directionLabel,
  periodTurnover,
  statementLines,
} from '@/shared/app/debtStatement'

function row(amount_tiyin: number, balance_after_tiyin: number) {
  return { amount_tiyin, balance_after_tiyin }
}

describe('statementLines', () => {
  it('puts a payment in the shrinking column on the supplier side', () => {
    // Stored: a delivery is negative (we owe more), our payment is positive.
    const lines = statementLines([row(-10_000, -10_000), row(4_000, -6_000)], 'suppliers', 0)
    expect(lines[0].debit).toBe(10_000)
    expect(lines[0].credit).toBeNull()
    expect(lines[1].debit).toBeNull()
    expect(lines[1].credit).toBe(4_000)
  })

  it('puts a payment in the shrinking column on the client side too', () => {
    // Stored with the opposite sign — the column must not follow the sign.
    const lines = statementLines([row(10_000, 10_000), row(-4_000, 6_000)], 'clients', 0)
    expect(lines[0].debit).toBe(10_000)
    expect(lines[0].credit).toBeNull()
    expect(lines[1].debit).toBeNull()
    expect(lines[1].credit).toBe(4_000)
  })

  it('reports the balance unsigned with its direction beside it', () => {
    const lines = statementLines([row(-4_000, -4_000)], 'clients', 0)
    expect(lines[0].balance).toBe(4_000)
    expect(lines[0].direction).toBe('we_owe')
  })

  it('flags the direction only where it changes', () => {
    const lines = statementLines(
      [row(5_000, 5_000), row(1_000, 6_000), row(-9_000, -3_000), row(-1_000, -4_000)],
      'clients',
      0,
    )
    expect(lines.map((line) => line.directionChanged)).toEqual([true, false, true, false])
  })

  it('seeds the first comparison from the opening balance', () => {
    // Opening already leans "they owe", so the first row repeating it is not news.
    const lines = statementLines([row(1_000, 6_000)], 'clients', 5_000)
    expect(lines[0].directionChanged).toBe(false)
  })

  it('treats a settled balance as its own direction', () => {
    const lines = statementLines([row(-5_000, 0), row(-1_000, -1_000)], 'clients', 5_000)
    expect(lines.map((line) => line.direction)).toEqual(['settled', 'we_owe'])
    expect(lines.map((line) => line.directionChanged)).toEqual([true, true])
  })
})

describe('balanceDirection / directionLabel', () => {
  it('names each direction and says nothing at zero', () => {
    expect(directionLabel(balanceDirection(10))).toBe('bizga qarzi')
    expect(directionLabel(balanceDirection(-10))).toBe('qarzimiz')
    expect(directionLabel(balanceDirection(0))).toBe('')
  })
})

describe('periodTurnover', () => {
  it('swaps the two totals between sides', () => {
    const statement = { period_increase_tiyin: 4_000, period_decrease_tiyin: 10_000 }
    expect(periodTurnover(statement, 'suppliers')).toEqual({ debit: 10_000, credit: 4_000 })
    expect(periodTurnover(statement, 'clients')).toEqual({ debit: 4_000, credit: 10_000 })
  })
})
