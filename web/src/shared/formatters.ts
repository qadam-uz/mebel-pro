export function formatTiyin(value: number): string {
  return new Intl.NumberFormat('uz-UZ', {
    style: 'currency',
    currency: 'UZS',
    maximumFractionDigits: 0,
  }).format(Math.round(value / 100))
}

export function formatDate(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
  return new Intl.DateTimeFormat('uz-UZ', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date)
}

export function formatStockQuantity(value: number, displayUnit: string): string {
  if (displayUnit === 'm') {
    return `${new Intl.NumberFormat('uz-UZ', {
      maximumFractionDigits: 3,
      minimumFractionDigits: value % 1000 === 0 ? 0 : 3,
    }).format(value / 1000)} m`
  }
  return `${new Intl.NumberFormat('uz-UZ').format(value)} ${displayUnit}`
}

export function parseDisplayQuantity(value: string, displayUnit: string): number {
  const normalized = Number(value.replace(',', '.'))
  if (!Number.isFinite(normalized)) return Number.NaN
  if (displayUnit === 'm') return Math.round(normalized * 1000)
  return Math.round(normalized)
}
