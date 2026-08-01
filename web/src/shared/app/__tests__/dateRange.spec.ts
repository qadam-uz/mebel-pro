import { describe, expect, it } from 'vitest'

import {
  isoDate,
  monthGrid,
  monthNames,
  presetRange,
  weekdayShortNames,
} from '@/shared/app/dateRange'

// Local-calendar reference point: Saturday, 4 July 2026.
const NOW = new Date(2026, 6, 4)

describe('isoDate', () => {
  it('zero-pads month and day', () => {
    expect(isoDate(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})

describe('presetRange', () => {
  it('today is a single-day window', () => {
    expect(presetRange('today', NOW)).toEqual({ from: '2026-07-04', to: '2026-07-04' })
  })

  it('week covers the last 7 days inclusive', () => {
    expect(presetRange('week', NOW)).toEqual({ from: '2026-06-28', to: '2026-07-04' })
  })

  it('month runs from the 1st to today', () => {
    expect(presetRange('month', NOW)).toEqual({ from: '2026-07-01', to: '2026-07-04' })
  })

  it('last_month is the full previous calendar month', () => {
    expect(presetRange('last_month', NOW)).toEqual({ from: '2026-06-01', to: '2026-06-30' })
  })

  it('last_month crosses a year boundary', () => {
    expect(presetRange('last_month', new Date(2026, 0, 15))).toEqual({
      from: '2025-12-01',
      to: '2025-12-31',
    })
  })

  it('days30 covers the last 30 days inclusive', () => {
    expect(presetRange('days30', NOW)).toEqual({ from: '2026-06-05', to: '2026-07-04' })
  })

  it('all and custom leave both ends open', () => {
    expect(presetRange('all', NOW)).toEqual({ from: null, to: null })
    expect(presetRange('custom', NOW)).toEqual({ from: null, to: null })
  })
})

describe('calendar vocabulary', () => {
  it('names all twelve months and seven Monday-first weekdays', () => {
    expect(monthNames()).toHaveLength(12)
    expect(monthNames()[0]).toBe('Yanvar')
    expect(monthNames()[11]).toBe('Dekabr')
    expect(weekdayShortNames()).toEqual(['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'])
  })
})

describe('monthGrid', () => {
  it('pads a Wednesday-start month on both ends (July 2026)', () => {
    const weeks = monthGrid(2026, 6)
    expect(weeks).toHaveLength(5)
    expect(weeks[0]).toEqual([
      null,
      null,
      '2026-07-01',
      '2026-07-02',
      '2026-07-03',
      '2026-07-04',
      '2026-07-05',
    ])
    expect(weeks[4]).toEqual([
      '2026-07-27',
      '2026-07-28',
      '2026-07-29',
      '2026-07-30',
      '2026-07-31',
      null,
      null,
    ])
  })

  it('starts flush when the 1st is a Monday (June 2026)', () => {
    const weeks = monthGrid(2026, 5)
    expect(weeks[0]?.[0]).toBe('2026-06-01')
    expect(weeks).toHaveLength(5)
    expect(weeks[4]).toEqual(['2026-06-29', '2026-06-30', null, null, null, null, null])
  })

  it('handles a Sunday-start month (February 2026)', () => {
    const weeks = monthGrid(2026, 1)
    expect(weeks[0]).toEqual([null, null, null, null, null, null, '2026-02-01'])
    expect(weeks[4]).toEqual([
      '2026-02-23',
      '2026-02-24',
      '2026-02-25',
      '2026-02-26',
      '2026-02-27',
      '2026-02-28',
      null,
    ])
  })

  it('every week has exactly seven cells', () => {
    for (const weeks of [monthGrid(2026, 0), monthGrid(2024, 1), monthGrid(2025, 11)]) {
      for (const week of weeks) expect(week).toHaveLength(7)
    }
  })
})
