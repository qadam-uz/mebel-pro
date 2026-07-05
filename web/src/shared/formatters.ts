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

export function formatDate(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${day}.${month}.${date.getFullYear()}`
}

// Calendar-relative age in Uzbek ("bugun", "kecha", "5 kun oldin", …) for
// at-a-glance freshness; pair with the absolute date in a title attribute.
export function formatRelativeUz(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
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
