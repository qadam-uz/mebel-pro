// Password strength — ≥8 chars, an upper, a lower, a digit. Mirrors the
// prototype's window.pwStrength. Returns the per-rule flags + a 0..4 score.

export interface PasswordStrength {
  ok: boolean
  score: number
  len: boolean
  hasU: boolean
  hasL: boolean
  hasD: boolean
}

export function pwStrength(value: string): PasswordStrength {
  const v = value || ''
  const hasU = /[A-Z]/.test(v)
  const hasL = /[a-z]/.test(v)
  const hasD = /\d/.test(v)
  const len = v.length >= 8
  const score = [hasU, hasL, hasD, len].filter(Boolean).length
  return { ok: hasU && hasL && hasD && len, score, len, hasU, hasL, hasD }
}
