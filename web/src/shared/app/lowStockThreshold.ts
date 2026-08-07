import { formatStockUnit } from '@/shared/formatters'
import { translate } from '@/shared/i18n'
import { isTape } from '@/shared/app/materialLabel'
import type { DekorType } from '@/shared/stores/admin'

// QAD-159: the branch material's `min_stock` is the **low-stock alert threshold**,
// not a minimum the branch must hold. One place for its copy so the attach sheet,
// the edit form, and the table can never drift apart.
//
// Functions, not constants: a module-level string would freeze at whatever locale
// happened to be active when this module first evaluated.
export function lowStockThresholdLabel(): string {
  return translate('inventory.threshold.label')
}

export function lowStockThresholdColumn(): string {
  return translate('inventory.threshold.column')
}

export function lowStockThresholdHint(): string {
  return translate('inventory.threshold.hint')
}

// Prefill for the attach sheet's threshold input. **0 by default**, matching the
// server: a branch routinely registers its whole format list before it knows
// either a price or a sensible threshold, and QAD-159's 5 / 50 m prefill made
// that first pass lie about both. A 0 threshold only means the low-stock warning
// stays quiet until the shelf is empty — the row is still editable the moment the
// branch knows the number, and existing branch materials keep what they were
// saved with.
//
// A function, not a `const`, so a future per-unit default can take `tur` back
// without every caller changing shape.
export function defaultLowStockThreshold(): number {
  return 0
}

// Display unit for the threshold input. Defers to `formatStockUnit` so the
// threshold is never named differently from the quantity it is compared
// against — «5 dona» beside «5 panel» for one number was the QAD-182 defect.
export function thresholdUnit(tur: DekorType | null | undefined): string {
  return formatStockUnit(isTape(tur) ? 'metre' : 'panel')
}
