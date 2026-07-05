// Shared date-range presets for list filters (workshop app).
//
// Every from/to filter surface (orders, inventory transactions, finance
// ledgers, worker production) offers the same preset vocabulary; "custom"
// is what the calendar range picker emits when the user clicks out a span
// by hand. Dates are LOCAL calendar days (not UTC) so "Bugun" matches what
// the wall clock says.

export type DateRangePreset =
  | 'all'
  | 'today'
  | 'week'
  | 'month'
  | 'last_month'
  | 'days30'
  | 'custom'

export interface DateRangeValue {
  from: string | null
  to: string | null
}

export const DATE_RANGE_PRESET_LABELS: Record<DateRangePreset, string> = {
  all: 'Barcha sanalar',
  today: 'Bugun',
  week: 'Oxirgi 7 kun',
  month: 'Joriy oy',
  last_month: "O'tgan oy",
  days30: 'Oxirgi 30 kun',
  custom: 'Maxsus oraliq',
}

export const UZ_MONTHS = [
  'Yanvar',
  'Fevral',
  'Mart',
  'Aprel',
  'May',
  'Iyun',
  'Iyul',
  'Avgust',
  'Sentabr',
  'Oktabr',
  'Noyabr',
  'Dekabr',
] as const

// Monday-first, matching the local calendar convention.
export const UZ_WEEKDAYS = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'] as const

/**
 * The weeks of a month as a Monday-first matrix of ISO dates; cells outside
 * the month are null. `monthIndex` is 0-based like `Date#getMonth()`.
 */
export function monthGrid(year: number, monthIndex: number): (string | null)[][] {
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate()
  const lead = (new Date(year, monthIndex, 1).getDay() + 6) % 7
  const cells: (string | null)[] = Array.from({ length: lead }, () => null)
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(isoDate(new Date(year, monthIndex, day)))
  }
  while (cells.length % 7 !== 0) cells.push(null)
  const weeks: (string | null)[][] = []
  for (let index = 0; index < cells.length; index += 7) {
    weeks.push(cells.slice(index, index + 7))
  }
  return weeks
}

export function isoDate(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * The [from, to] window a preset stands for, as YYYY-MM-DD or null (open end).
 * `all` is fully open; `custom` returns open ends too — the caller keeps the
 * user-entered values instead of deriving them.
 */
export function presetRange(preset: DateRangePreset, now: Date = new Date()): DateRangeValue {
  if (preset === 'today') {
    const today = isoDate(now)
    return { from: today, to: today }
  }
  if (preset === 'week') {
    const start = new Date(now)
    start.setDate(now.getDate() - 6)
    return { from: isoDate(start), to: isoDate(now) }
  }
  if (preset === 'month') {
    return {
      from: isoDate(new Date(now.getFullYear(), now.getMonth(), 1)),
      to: isoDate(now),
    }
  }
  if (preset === 'last_month') {
    return {
      from: isoDate(new Date(now.getFullYear(), now.getMonth() - 1, 1)),
      to: isoDate(new Date(now.getFullYear(), now.getMonth(), 0)),
    }
  }
  if (preset === 'days30') {
    const start = new Date(now)
    start.setDate(now.getDate() - 29)
    return { from: isoDate(start), to: isoDate(now) }
  }
  return { from: null, to: null }
}
