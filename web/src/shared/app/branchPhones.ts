import { uzPhone } from '@/shared/app/adminValidation'
import { translate } from '@/shared/i18n'

// A branch publishes one primary number (the one clients see on their orders)
// plus at most this many extras — mirrors MAX_ADDITIONAL_BRANCH_PHONES on the
// backend, which refuses a longer list (QAD-158).
export const MAX_ADDITIONAL_BRANCH_PHONES = 3

/**
 * A branch's published numbers in display order: the primary first, then the
 * extras as the branch ordered them.
 *
 * Decision 24 — wherever a client sees a branch's phone they see *all* of them,
 * each its own `tel:` link. A branch that publishes three lines has three
 * because the first two are busy, so showing one is showing the client the line
 * least likely to answer. Every client surface reads its list from here rather
 * than composing its own, which is how home and the order detail drifted into
 * a single number in the first place.
 *
 * Blanks are dropped and duplicates collapse: the write side already refuses
 * both (`additionalPhoneErrors`), but a display list keyed by number renders
 * badly against data that predates the rule.
 */
export function branchPhoneList(
  primary: string | null | undefined,
  additional?: readonly string[] | null,
): string[] {
  const seen = new Set<string>()
  const ordered: string[] = []
  for (const raw of [primary, ...(additional ?? [])]) {
    const value = raw?.trim()
    if (!value || seen.has(value)) continue
    seen.add(value)
    ordered.push(value)
  }
  return ordered
}

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
