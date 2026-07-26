import type { MaterialKind } from '@/shared/stores/admin'

// QAD-159: the branch material's `min_stock` is the **low-stock alert threshold**,
// not a minimum the branch must hold. One place for its copy so the attach sheet,
// the edit form, and the table can never drift apart.
export const LOW_STOCK_THRESHOLD_LABEL = 'Kam qoldiq chegarasi'
export const LOW_STOCK_THRESHOLD_COLUMN = 'Chegara'
export const LOW_STOCK_THRESHOLD_HINT =
  'Zaxira shu miqdorga tushganda ogohlantiramiz. 0 = faqat butunlay tugaganda.'

// A pre-filled 0 switched low-stock alerts off for every material ever attached,
// so new attachments start from a threshold that actually warns in time. UI-only
// defaults — existing branch materials keep whatever they were saved with.
const DEFAULTS: Record<MaterialKind, number> = { panel: 5, edge: 50 }

export function defaultLowStockThreshold(kind: MaterialKind): number {
  return DEFAULTS[kind] ?? DEFAULTS.panel
}

// Display unit for the threshold input: panels count in pieces, edge tape in
// metres (the API stores edge stock in millimetres).
export function thresholdUnit(kind: MaterialKind): string {
  return kind === 'edge' ? 'm' : 'dona'
}
