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

export function formatDateInputValue(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function formatStockQuantity(value: number, displayUnit: string): string {
  if (displayUnit === 'm' || displayUnit === 'metre') {
    // metres use a dot decimal so 2.5 m is not misread as 2,500 m (uz-UZ uses a comma decimal)
    const metres = new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 3 })
      .format(value / 1000)
      .replace(',', '.')
    return `${metres} m`
  }
  return `${new Intl.NumberFormat('uz-UZ').format(value)} ${displayUnit}`
}

export function parseDisplayQuantity(value: string, displayUnit: string): number {
  const normalized = Number(value.replace(',', '.'))
  if (!Number.isFinite(normalized)) return Number.NaN
  if (displayUnit === 'm' || displayUnit === 'metre') return Math.round(normalized * 1000)
  return Math.round(normalized)
}
