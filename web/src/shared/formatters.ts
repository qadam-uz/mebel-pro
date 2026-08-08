import { intlLocale, translate, translatePlural } from '@/shared/i18n'

// The bare grouped figure, no unit. For columns of money where the unit is
// stated once in the header — repeating "so'm" on every cell of a statement
// costs the width that pushed the akt sverka sideways on a laptop.
export function formatSom(value: number): string {
  return new Intl.NumberFormat(intlLocale(), { maximumFractionDigits: 0 }).format(
    Math.round(value / 100),
  )
}

export function formatTiyin(value: number): string {
  // Pin the suffix to "so'm" deterministically rather than using the currency
  // formatter, whose ICU tables can render the English-looking code "UZS" on
  // trimmed/older builds. This keeps currency identical on every runtime and
  // matches the Uzbek SPA's own labels (Narx (so'm), Summa (so'm)).
  return `${formatSom(value)} ${translate('formats.currency.som')}`
}

// Parse a human-entered so'm amount into integer tiyin. Accepts the formats the
// app itself displays and people actually type: space/NBSP grouping ("12 500"),
// dot- or comma-grouped thousands ("1.500.000", "12,500"), and a comma or dot
// decimal mark ("12,5" / "12.5"). Returns null for anything unclear or <= 0 —
// callers must block the submit instead of coercing to 0 (a "12.500" read as
// 12,5 so'm once booked a 1000x-smaller expense with a success toast).
export function parseSomToTiyin(value: string): number | null {
  let text = value.trim().replace(/[\s ]/g, '')
  if (!text) return null
  if (/^\d{1,3}([.,]\d{3})+$/.test(text)) {
    text = text.replace(/[.,]/g, '')
  } else {
    text = text.replace(/,/g, '.')
  }
  if (!/^\d+(\.\d{1,2})?$/.test(text)) return null
  const som = Number(text)
  if (som <= 0) return null
  return Math.round(som * 100)
}

// Compact money for KPI-sized numerals: sums from 1 mln so'm up are scaled to
// "mln/mlrd" so the value always fits on one line; the exact amount travels in
// `full` for a title tooltip. The unit is returned separately so templates can
// render it smaller than the numeral.
export function formatTiyinParts(value: number): { amount: string; unit: string; full: string } {
  const som = Math.round(value / 100)
  const abs = Math.abs(som)
  const format = (amount: number, maximumFractionDigits: number) =>
    new Intl.NumberFormat(intlLocale(), { maximumFractionDigits }).format(amount)
  if (abs >= 1_000_000_000) {
    return {
      amount: format(som / 1_000_000_000, 2),
      unit: translate('formats.currency.billion'),
      full: formatTiyin(value),
    }
  }
  if (abs >= 1_000_000) {
    return {
      amount: format(som / 1_000_000, 2),
      unit: translate('formats.currency.million'),
      full: formatTiyin(value),
    }
  }
  return {
    amount: format(som, 0),
    unit: translate('formats.currency.som'),
    full: formatTiyin(value),
  }
}

// One unit for a whole row of figures. `formatTiyinParts` decides per figure, so
// a KPI row could show "540 855 so'm" beside "11,6 mln so'm" for the same period
// — two numbers you cannot compare without counting zeros (QAD-182). Scale is
// picked from the largest magnitude present and applied to every member, so the
// row reads as one ruler.
export function formatTiyinRow(values: number[]): Array<{
  amount: string
  unit: string
  full: string
}> {
  const peak = Math.max(0, ...values.map((value) => Math.abs(Math.round(value / 100))))
  const divisor = peak >= 1_000_000_000 ? 1_000_000_000 : peak >= 1_000_000 ? 1_000_000 : 1
  const unit =
    divisor === 1_000_000_000
      ? translate('formats.currency.billion')
      : divisor === 1_000_000
        ? translate('formats.currency.million')
        : translate('formats.currency.som')
  // Two decimals once scaled, none at so'm: "0,54 mln" keeps a small figure
  // legible next to a large one instead of collapsing it to "1 mln".
  const maximumFractionDigits = divisor === 1 ? 0 : 2
  return values.map((value) => ({
    amount: new Intl.NumberFormat(intlLocale(), { maximumFractionDigits }).format(
      Math.round(value / 100) / divisor,
    ),
    unit,
    full: formatTiyin(value),
  }))
}

// Date-only strings ("2026-07-05") parse as UTC midnight via `new Date`, which
// shifts a calendar day for users west of Greenwich once local getters read it —
// build a local date from the parts instead. Full ISO datetimes carry an offset
// and parse correctly.
function parseDateValue(value: string | Date): Date {
  if (typeof value !== 'string') return value
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day)
  }
  return new Date(value)
}

export function formatDate(value: string | Date): string {
  const date = parseDateValue(value)
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${day}.${month}.${date.getFullYear()}`
}

const WEEKDAY_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'] as const
const MONTH_KEYS = [
  'jan',
  'feb',
  'mar',
  'apr',
  'may',
  'jun',
  'jul',
  'aug',
  'sep',
  'oct',
  'nov',
  'dec',
] as const

/**
 * The dashboard dateline — "7 avgust, juma".
 *
 * Composed from the catalog rather than `Intl.DateTimeFormat` for the same
 * reason `formatTiyin` pins its own currency suffix: ICU's date tables are
 * trimmed on some runtimes and quietly fall back to English month names. It
 * also needs its own month set. `formats.month.*` is capitalised nominative and
 * shared with the calendar header, but a day-of-month phrase wants a different
 * form — Russian needs the genitive ("7 августа", not "7 Август") — so the
 * words come from `formats.monthOf.*`, and the two sets stay separate.
 */
export function formatDayMonthWeekday(value: string | Date): string {
  const date = parseDateValue(value)
  return translate('formats.dayMonthWeekday', {
    day: date.getDate(),
    month: translate(`formats.monthOf.${MONTH_KEYS[date.getMonth()]}`),
    weekday: translate(`formats.weekday.${WEEKDAY_KEYS[date.getDay()]}`),
  })
}

// A signed percentage for a delta pill — "+18%", "−12%". The sign comes from the
// number formatter, not from a concatenated glyph, so the locale picks its own
// minus and its own spacing before the sign ("+18 %" in Russian).
export function formatSignedPercent(percent: number): string {
  return new Intl.NumberFormat(intlLocale(), {
    style: 'percent',
    maximumFractionDigits: 0,
    signDisplay: 'exceptZero',
  }).format(percent / 100)
}

export function formatDateTime(value: string | Date): string {
  const date = parseDateValue(value)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${formatDate(date)} ${hours}:${minutes}`
}

// Calendar-relative age ("bugun", "kecha", "5 kun oldin", …) for at-a-glance
// freshness; pair with the absolute date in a title attribute. Russian agrees
// the noun with the number, so the counted forms go through the plural rule
// rather than being concatenated.
export function formatRelative(value: string | Date): string {
  const date = parseDateValue(value)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const days = Math.round((startOfToday.getTime() - startOfDate.getTime()) / 86_400_000)
  if (days <= 0) return translate('formats.relative.today')
  if (days === 1) return translate('formats.relative.yesterday')
  if (days < 7) return translatePlural('formats.relative.days', days)
  if (days < 30) return translatePlural('formats.relative.weeks', Math.floor(days / 7))
  return translatePlural('formats.relative.months', Math.floor(days / 30))
}

export function formatDateInputValue(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// Localize a backend stock-unit enum for display. The API emits "metre" (edges)
// and "panel" (panels); map those (and any legacy piece/pcs) to short labels so
// a raw English enum never surfaces in the UI.
export function formatStockUnit(unit: string): string {
  if (unit === 'metre' || unit === 'm') return translate('formats.unit.metre')
  if (unit === 'panel') return translate('formats.unit.panel')
  if (unit === 'pcs' || unit === 'piece') return translate('formats.unit.piece')
  return unit
}

export function formatStockQuantity(value: number, displayUnit: string): string {
  if (displayUnit === 'm' || displayUnit === 'metre') {
    // metres use a dot decimal so 2.5 m is not misread as 2,500 m (every locale
    // we ship groups with a space and marks decimals with a comma)
    const metres = new Intl.NumberFormat(intlLocale(), { maximumFractionDigits: 3 })
      .format(value / 1000)
      .replace(',', '.')
    return `${metres} ${translate('formats.unit.metre')}`
  }
  return `${new Intl.NumberFormat(intlLocale()).format(value)} ${formatStockUnit(displayUnit)}`
}

export function parseDisplayQuantity(value: string, displayUnit: string): number {
  const normalized = Number(value.replace(',', '.'))
  if (!Number.isFinite(normalized)) return Number.NaN
  if (displayUnit === 'm' || displayUnit === 'metre') return Math.round(normalized * 1000)
  return Math.round(normalized)
}
