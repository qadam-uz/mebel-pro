import { metres } from '@/shared/stores/cutting'
import { translate, translatePlural } from '@/shared/i18n'
import type { OrderPriceLine } from '@/shared/stores/orders'

/** One thing the client has to hand over before the saw can start. */
export interface OwnMaterialRow {
  materialId: string
  materialName: string
  /** Ready-to-print amount in that material's own unit — sheets or metres. */
  amount: string
}

/**
 * What the client brings, read off an order's price lines.
 *
 * The order stores the split rather than a flag: `own_panels` / `own_mm` sit
 * beside the charged figures on every line, so this is a projection, not a
 * second source of truth. Lines with nothing owed by the client drop out, which
 * is why an ordinary order yields an empty list and the callers render nothing.
 */
export function ownMaterialRows(priceLines: OrderPriceLine[]): OwnMaterialRow[] {
  return priceLines.flatMap((line) => {
    const owed = line.kind === 'panel' ? line.own_panels : line.own_mm
    if (!owed || owed <= 0) return []
    return [
      {
        materialId: line.material_id,
        materialName: line.material_name,
        amount: line.kind === 'panel' ? translatePlural('orders.unit.sheets', owed) : metres(owed),
      },
    ]
  })
}

/** Whether an order expects anything from the client at all. */
export function hasOwnMaterial(priceLines: OrderPriceLine[]): boolean {
  return ownMaterialRows(priceLines).length > 0
}

/**
 * The one-line summary for a list row or a chip — "2 list + 1 material".
 * Returns null when the order expects nothing, so a caller can `v-if` on it.
 */
export function ownMaterialSummary(priceLines: OrderPriceLine[]): string | null {
  const rows = ownMaterialRows(priceLines)
  if (rows.length === 0) return null
  return translate('orders.own.summary', { count: rows.length })
}
