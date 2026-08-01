import { formatStockUnit } from '@/shared/formatters'
import { translate } from '@/shared/i18n'
import type { MaterialKind } from '@/shared/stores/admin'

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

// A pre-filled 0 switched low-stock alerts off for every material ever attached,
// so new attachments start from a threshold that actually warns in time. UI-only
// defaults — existing branch materials keep whatever they were saved with.
const DEFAULTS: Record<MaterialKind, number> = { panel: 5, edge: 50 }

export function defaultLowStockThreshold(kind: MaterialKind): number {
  return DEFAULTS[kind] ?? DEFAULTS.panel
}

// Display unit for the threshold input. Defers to `formatStockUnit` so the
// threshold is never named differently from the quantity it is compared
// against — «5 dona» beside «5 panel» for one number was the QAD-182 defect.
export function thresholdUnit(kind: MaterialKind): string {
  return formatStockUnit(kind === 'edge' ? 'metre' : 'panel')
}
