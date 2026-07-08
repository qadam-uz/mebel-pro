export function formatTiyin(value: number): string {
  // Pin the suffix to "so'm" deterministically rather than using the currency
  // formatter, whose ICU tables can render the English-looking code "UZS" on
  // trimmed/older builds. This keeps currency identical on every runtime and
  // matches the Uzbek SPA's own labels (Narx (so'm), Summa (so'm)).
  const amount = new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 0 }).format(
    Math.round(value / 100),
  )
  return `${amount} so'm`
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
    new Intl.NumberFormat('uz-UZ', { maximumFractionDigits }).format(amount)
  if (abs >= 1_000_000_000) {
    return { amount: format(som / 1_000_000_000, 2), unit: "mlrd so'm", full: formatTiyin(value) }
  }
  if (abs >= 1_000_000) {
    return { amount: format(som / 1_000_000, 2), unit: "mln so'm", full: formatTiyin(value) }
  }
  return { amount: format(som, 0), unit: "so'm", full: formatTiyin(value) }
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

export function formatDateTime(value: string | Date): string {
  const date = parseDateValue(value)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${formatDate(date)} ${hours}:${minutes}`
}

// Calendar-relative age in Uzbek ("bugun", "kecha", "5 kun oldin", …) for
// at-a-glance freshness; pair with the absolute date in a title attribute.
export function formatRelativeUz(value: string | Date): string {
  const date = parseDateValue(value)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const days = Math.round((startOfToday.getTime() - startOfDate.getTime()) / 86_400_000)
  if (days <= 0) return 'bugun'
  if (days === 1) return 'kecha'
  if (days < 7) return `${days} kun oldin`
  if (days < 30) return `${Math.floor(days / 7)} hafta oldin`
  return `${Math.floor(days / 30)} oy oldin`
}

export function formatDateInputValue(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// Localize a backend stock-unit enum for display. The API emits "metre" (edges)
// and "panel" (panels); map those (and any legacy piece/pcs) to short Uzbek
// labels so a raw English enum never surfaces in the UI.
export function formatStockUnit(unit: string): string {
  if (unit === 'metre' || unit === 'm') return 'm'
  if (unit === 'panel') return 'panel'
  if (unit === 'pcs' || unit === 'piece') return 'dona'
  return unit
}

export function formatStockQuantity(value: number, displayUnit: string): string {
  if (displayUnit === 'm' || displayUnit === 'metre') {
    // metres use a dot decimal so 2.5 m is not misread as 2,500 m (uz-UZ uses a comma decimal)
    const metres = new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 3 })
      .format(value / 1000)
      .replace(',', '.')
    return `${metres} m`
  }
  return `${new Intl.NumberFormat('uz-UZ').format(value)} ${formatStockUnit(displayUnit)}`
}

export function parseDisplayQuantity(value: string, displayUnit: string): number {
  const normalized = Number(value.replace(',', '.'))
  if (!Number.isFinite(normalized)) return Number.NaN
  if (displayUnit === 'm' || displayUnit === 'metre') return Math.round(normalized * 1000)
  return Math.round(normalized)
}
