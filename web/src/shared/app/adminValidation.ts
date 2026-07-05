import { ApiError, apiErrorCode } from '@/shared/api/client'

export type FieldErrors<Field extends string> = Partial<Record<Field, string>>

const UZ_PHONE_RE = /^\+998\d{9}$/

export function clearFieldErrors<Field extends string>(errors: FieldErrors<Field>) {
  for (const key of Object.keys(errors) as Field[]) delete errors[key]
}

export function requiredText(value: string, message = "Bu maydonni to'ldiring."): string | null {
  return value.trim() ? null : message
}

export function uzPhone(value: string): string | null {
  return UZ_PHONE_RE.test(value.trim()) ? null : '+998XXXXXXXXX formatida kiriting.'
}

export function tempPassword(value: string): string | null {
  if (!value) return null
  if (value.length < 8) return 'Kamida 8 belgi kiriting.'
  if (!/[a-z]/.test(value) || !/[A-Z]/.test(value) || !/\d/.test(value)) {
    return 'Katta/kichik harf va raqam ishlating.'
  }
  return null
}

export function positiveDecimal(value: string): string | null {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? null : 'Musbat son kiriting.'
}

// Optional non-negative integer (blank is allowed → null). Guards fields like
// tiyin rates from silently becoming NaN when non-numeric text is submitted.
export function nonNegativeInteger(value: string, message = 'Butun son kiriting.'): string | null {
  if (!value.trim()) return null
  const number = Number(value)
  return Number.isInteger(number) && number >= 0 ? null : message
}

// Optional non-negative amount (blank is allowed → null). Used for so'm price
// fields, which may carry decimals when a legacy tiyin rate is not a round
// number of so'm; the caller rounds back to integer tiyin on submit.
export function nonNegativeAmount(
  value: string,
  message = "To'g'ri qiymat kiriting.",
): string | null {
  if (!value.trim()) return null
  const number = Number(value)
  return Number.isFinite(number) && number >= 0 ? null : message
}

export function positiveInteger(value: string): string | null {
  const number = Number(value)
  return Number.isInteger(number) && number > 0 ? null : 'Musbat butun son kiriting.'
}

export function focusFirstFieldError<Field extends string>(
  errors: FieldErrors<Field>,
  order: readonly Field[],
  idByField: Record<Field, string>,
) {
  const first = order.find((field) => errors[field])
  if (!first) return
  requestAnimationFrame(() => document.getElementById(idByField[first])?.focus())
}

function apiValidationMessage(code: string | null): string {
  switch (code) {
    case 'full_name_required':
    case 'login_required':
    case 'owner_login_required':
    case 'manufacturer_name_required':
    case 'material_name_required':
    case 'material_color_required':
    case 'workshop_name_required':
    case 'branch_name_required':
    case 'branch_address_required':
    case 'reason_required':
      return "Bu maydonni to'ldiring."
    case 'invalid_phone':
      return '+998XXXXXXXXX formatida kiriting.'
    case 'invalid_coordinates':
      return 'Lat va Lng birga kiritiladi.'
    case 'invalid_latitude':
      return '-90 dan 90 gacha kiriting.'
    case 'invalid_longitude':
      return '-180 dan 180 gacha kiriting.'
    case 'invalid_current_password':
      return "Joriy parol noto'g'ri."
    case 'login_exists':
      return 'Bu login band.'
    case 'manufacturer_name_exists':
      return 'Bu ishlab chiqaruvchi allaqachon bor.'
    case 'weak_password':
      return 'Parol yetarlicha kuchli emas.'
    case 'manufacturer_not_found':
      return 'Ishlab chiqaruvchini tanlang.'
    case 'invalid_thickness':
      return 'Musbat qalinlik kiriting.'
    case 'invalid_panel_size':
      return "Panel uzunligi va eni musbat bo'lishi, uzunlik enidan kichik bo'lmasligi kerak."
    case 'invalid_panel_material':
      return "Panel maydonlarini to'ldiring."
    case 'invalid_grain':
      return "Tola yo'nalishini belgilang."
    default:
      return 'Maydon qiymatini tekshiring.'
  }
}

function validationErrors(error: unknown): Array<{ loc?: unknown; msg?: unknown }> {
  if (!(error instanceof ApiError) || typeof error.body !== 'object' || error.body === null) {
    return []
  }
  const details = (error.body as { details?: unknown }).details
  if (typeof details !== 'object' || details === null) return []
  const errors = (details as { errors?: unknown }).errors
  return Array.isArray(errors) ? (errors as Array<{ loc?: unknown; msg?: unknown }>) : []
}

export function fieldErrorsFromApi<Field extends string>(
  error: unknown,
  codeMap: Partial<Record<string, Field>>,
  locMap: Partial<Record<string, Field>> = {},
): FieldErrors<Field> {
  const fields: FieldErrors<Field> = {}
  const code = apiErrorCode(error)
  if (code && codeMap[code]) fields[codeMap[code]] = apiValidationMessage(code)
  for (const item of validationErrors(error)) {
    const loc = Array.isArray(item.loc) ? item.loc.map(String) : []
    const key = loc.join('.')
    const field = locMap[key] ?? locMap[loc[loc.length - 1] ?? '']
    if (field) fields[field] = apiValidationMessage(code)
  }
  return fields
}
