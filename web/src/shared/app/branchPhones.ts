import { uzPhone } from '@/shared/app/adminValidation'
import { translate } from '@/shared/i18n'

// A branch publishes one primary number (the one clients see on their orders)
// plus at most this many extras — mirrors MAX_ADDITIONAL_BRANCH_PHONES on the
// backend, which refuses a longer list (QAD-158).
export const MAX_ADDITIONAL_BRANCH_PHONES = 3

/**
 * Per-row messages for a branch's additional-phone list, index-aligned with
 * `additional` (`undefined` = that row is fine). Rows are checked against the
 * format rule, the primary number, and every earlier row — the same three rules
 * the backend enforces, so a valid form never round-trips into a server error.
 */
export function additionalPhoneErrors(
  additional: readonly string[],
  primary: string,
): Array<string | undefined> {
  const seen = new Set<string>()
  return additional.map((raw) => {
    const value = raw.trim()
    if (!value) return translate('forms.phone.errorEmptyRow')
    const format = uzPhone(value)
    if (format) return format
    if (value === primary.trim()) return translate('forms.phone.errorSameAsPrimary')
    if (seen.has(value)) return translate('forms.phone.errorDuplicate')
    seen.add(value)
    return undefined
  })
}
