// Pure derivations for the client order-confirmation page (ClientOrderNewView).
// Extracted so the "why is the CTA disabled", "does the itemized bill reconcile",
// logic is testable without mounting the SFC —
// follows the cuttingResultsDisplay.ts pattern (CB-93).

import { isUzPhone } from '@/shared/app/clientUi'
import { formatTiyin } from '@/shared/formatters'
import { translate, translatePlural } from '@/shared/i18n'
import { metres } from '@/shared/stores/cutting'
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
        panels: translatePlural('client.unit.sheets', quote.panels_used),
        price: formatTiyin(quote.cutting_rate_tiyin),
      }),
      amount_tiyin: quote.panels_used * quote.cutting_rate_tiyin,
    },
  ]
  for (const line of quote.material_lines) {
    rows.push({
      key: `material:${line.material_id}`,
      label: line.material_name,
      detail: translatePlural('client.unit.sheets', line.panels_used),
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
      // `line_total_tiyin` is the tape AND the banding labour, so the detail
      // says so — §7.4's «… · 5,15 m · material + xizmat». Without it the
      // metres read as the whole basis of a figure they only half explain.
      detail: `${metres(line.consumed_mm)} · ${translate('client.orderNew.billEdgeBasis')}`,
      amount_tiyin: line.line_total_tiyin,
    })
  }
  return rows
}

export function billRowsTotal(rows: OrderBillRow[]): number {
  return rows.reduce((sum, row) => sum + row.amount_tiyin, 0)
}

// ---- parts table ("Detallar") -----------------------------------------------
