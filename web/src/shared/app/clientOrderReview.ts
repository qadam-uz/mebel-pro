// Pure derivations for the client order-confirmation page (ClientOrderNewView).
// Extracted so the "why is the CTA disabled", "does the itemized bill reconcile",
// and "what goes in the parts table" logic is testable without mounting the SFC —
// follows the cuttingResultsDisplay.ts pattern (CB-93).

import { isUzPhone } from '@/shared/app/clientUi'
import { sideLabels } from '@/shared/app/cuttingDisplay'
import { partDisplayName } from '@/shared/app/cuttingEditorDerived'
import { formatTiyin } from '@/shared/formatters'
import { translate, translatePlural } from '@/shared/i18n'
import { EDGE_SIDES, metres, type CuttingPart } from '@/shared/stores/cutting'
import type { OrderQuote } from '@/shared/stores/orders'

// ---- why the primary CTA is disabled --------------------------------------

// canPlace has exactly three failure causes, checked in this priority order —
// a missing quote outranks an incomplete contact field since there is nothing
// to submit yet either way.
export type CanPlaceBlocker = 'quote' | 'name' | 'phone'

const BLOCKER_KEYS: Readonly<Record<CanPlaceBlocker, string>> = {
  quote: 'client.orderNew.blockerQuote',
  name: 'client.orderNew.blockerName',
  phone: 'client.orderNew.blockerPhone',
}

export function canPlaceBlocker(input: {
  hasQuote: boolean
  name: string
  phone: string
}): CanPlaceBlocker | null {
  if (!input.hasQuote) return 'quote'
  if (!input.name.trim()) return 'name'
  if (!isUzPhone(input.phone)) return 'phone'
  return null
}

/** Copy for a blocker, or null when nothing blocks placing the order. */
export function canPlaceBlockerLabel(blocker: CanPlaceBlocker | null): string | null {
  return blocker ? translate(BLOCKER_KEYS[blocker]) : null
}

// ---- "Profildan tiklash" link visibility -----------------------------------

/** A reset-to-profile link is noise once the field already matches the profile
 *  value — show it only once the client has actually diverged from it. */
export function fieldDiffersFromProfile(
  current: string,
  profileValue: string | null | undefined,
): boolean {
  return current !== (profileValue ?? '')
}

// ---- itemized bill ----------------------------------------------------------

export interface OrderBillRow {
  key: string
  label: string
  detail: string
  amount_tiyin: number
}

/** Rebuilds the real per-line bill from the quote — replaces the three
 *  aggregate subtotal rows the page used to show. Reconciles exactly to
 *  `quote.total_tiyin` (backend invariant: subtotal_cutting = panels_used ×
 *  cutting_rate; material/edge line totals sum to their subtotals). */
export function buildBillRows(quote: OrderQuote): OrderBillRow[] {
  const rows: OrderBillRow[] = [
    {
      key: 'cutting',
      label: translate('client.common.cuttingService'),
      detail: translate('client.orderNew.billCuttingDetail', {
        panels: translatePlural('client.unit.panels', quote.panels_used),
        price: formatTiyin(quote.cutting_rate_tiyin),
      }),
      amount_tiyin: quote.panels_used * quote.cutting_rate_tiyin,
    },
  ]
  for (const line of quote.material_lines) {
    rows.push({
      key: `material:${line.material_id}`,
      label: line.material_name,
      detail: translatePlural('client.unit.panels', line.panels_used),
      amount_tiyin: line.line_total_tiyin,
    })
  }
  for (const line of quote.edge_lines) {
    rows.push({
      key: `edge:${line.material_id}`,
      // "Kromka" prefixed here (not bare) — the rail's cutting-stats block also
      // shows a "Kromka" figure (total banded length), a different meaning of
      // the same word. Money and metres must never share an unqualified label.
      label: translate('client.orderNew.billEdge', { material: line.material_name }),
      detail: metres(line.consumed_mm),
      amount_tiyin: line.line_total_tiyin,
    })
  }
  return rows
}

export function billRowsTotal(rows: OrderBillRow[]): number {
  return rows.reduce((sum, row) => sum + row.amount_tiyin, 0)
}

// ---- parts table ("Detallar") -----------------------------------------------

export interface PartReviewRow {
  key: string
  name: string
  materialLabel: string
  sizeLabel: string
  quantity: number
  edgeLabel: string
  followGrain: boolean
}

/** One row per snapshot part for the collapsed "Detallar" disclosure.
 *  `resolveMaterialName` is injected (rather than reading the cutting store)
 *  so this stays a pure function the caller can unit test. */
export function buildPartRows(
  parts: CuttingPart[],
  resolveMaterialName: (materialId: string) => string,
): PartReviewRow[] {
  return parts.map((part, index) => {
    const bandedSides = EDGE_SIDES.filter((side) => Boolean(part[side]))
    const material = resolveMaterialName(part.material_id)
    return {
      key: part.part_ref || `part-${index}`,
      name: partDisplayName(part, index),
      materialLabel:
        part.material_source === 'own'
          ? translate('client.orderNew.partOwnMaterial', { material })
          : material,
      sizeLabel: `${part.length_mm}×${part.width_mm} mm`,
      quantity: part.quantity,
      edgeLabel: bandedSides.length
        ? bandedSides.map((side) => sideLabels[side]).join(' · ')
        : translate('client.orderNew.partEdgeNone'),
      followGrain: part.follow_grain,
    }
  })
}
