// Display formatting helpers. v1 conventions (docs/architecture.md):
//   money — integer tiyin in the API; "1 234 567 so'm" for display
//   phone — +998XXXXXXXXX stored; "+998 90 123 45 67" grouped for display
//   dimensions — millimetres
// Ported from the prototype's window.fmt / fmtSum / fmtTiyin.

// Group thousands with a thin space, matching the uz-UZ prototype output.
export function fmt(n: number): string {
  return (n || 0).toLocaleString('uz-UZ').replace(/[,  ]/g, ' ')
}

// Plain UZS sum (already in so'm, not tiyin).
export function fmtSum(n: number): string {
  return `${fmt(n)} so'm`
}

// The canonical money formatter: integer tiyin → "1 234 567 so'm".
export function fmtTiyin(tiyin: number): string {
  return fmtSum(Math.round((tiyin || 0) / 100))
}

// Tiyin → so'm number (no unit), for charts/inputs.
export function tiyinToSum(tiyin: number): number {
  return Math.round((tiyin || 0) / 100)
}

export function sumToTiyin(sum: number): number {
  return Math.round((sum || 0) * 100)
}

// Phone: store as +998XXXXXXXXX, display grouped "+998 90 123 45 67".
export function fmtPhone(phone: string | null | undefined): string {
  if (!phone) return ''
  const digits = phone.replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('998')) {
    const r = digits.slice(3)
    return `+998 ${r.slice(0, 2)} ${r.slice(2, 5)} ${r.slice(5, 7)} ${r.slice(7, 9)}`
  }
  return phone.startsWith('+') ? phone : `+${digits}`
}

// Dimensions in millimetres.
export function fmtMm(mm: number): string {
  return `${fmt(mm)} mm`
}

// ISO datetime → "DD.MM.YYYY" / "DD.MM.YYYY HH:MM".
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${fmtDate(iso)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function initialsOf(name: string | null | undefined): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}
