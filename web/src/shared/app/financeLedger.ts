import { formatOrderNumber } from '@/shared/formatters'

export type FinanceLedgerTab = 'expense' | 'income'

export function financeLedgerTabFromPath(path: string): FinanceLedgerTab {
  return path.endsWith('/income') ? 'income' : 'expense'
}

/**
 * The period total under the ledger filters: recorded rows only.
 *
 * The count beside it stays the number of rows on screen, so «Hammasi» shows
 * all fourteen rows and the sum of the eleven that are still money. A voided
 * row is a cancelled record, not a smaller one — adding it to a total is the
 * one way this line could lie to whoever is reconciling a till. With the filter
 * on «Bekor qilingan» the total is therefore 0, which is the truth.
 */
export function ledgerRecordedTotalTiyin(
  rows: readonly { amount_tiyin: number; status: 'recorded' | 'voided' }[],
): number {
  return rows.reduce((sum, row) => (row.status === 'recorded' ? sum + row.amount_tiyin : sum), 0)
}

export interface OrderSettlementView {
  total_tiyin: number
  recorded_tiyin: number
  balance_tiyin: number
}

/** The order an income points at, as the income row itself carries it. */
export interface FinanceIncomeOrder extends OrderSettlementView {
  order_number: string
  contact_name: string
}

/**
 * The settlement as the income form must frame it.
 *
 * When editing, the income's own amount already sits inside the order's
 * `recorded_tiyin`, so the stored balance answers a question nobody is asking
 * ("what is left if this payment stands untouched?"). Pulling the row back out
 * gives the frame the operator is actually in: what the other records cover,
 * and how much this one may take. Pass null when creating and the settlement
 * comes through unchanged.
 */
export function incomeSettlementView(
  settlement: OrderSettlementView | null | undefined,
  editingAmountTiyin: number | null,
): OrderSettlementView | null {
  if (!settlement) return null
  const own = editingAmountTiyin ?? 0
  return {
    total_tiyin: settlement.total_tiyin,
    recorded_tiyin: Math.max(settlement.recorded_tiyin - own, 0),
    balance_tiyin: settlement.balance_tiyin + own,
  }
}

/**
 * The largest order payment still accepted, or null when nothing caps it
 * (other income, or no order picked yet).
 *
 * Deliberately the same number the form shows as «Qoldiq» — one formula, so
 * the summary line and the fill button can never disagree. It reproduces the
 * server's `exclude_income_id` cap exactly.
 */
export function orderPaymentCeilingTiyin(
  settlement: OrderSettlementView | null | undefined,
  editingAmountTiyin: number | null,
): number | null {
  return incomeSettlementView(settlement, editingAmountTiyin)?.balance_tiyin ?? null
}

/** Whether the typed amount is over what the order can still take. */
export function exceedsOrderBalance(
  amountTiyin: number | null,
  ceilingTiyin: number | null,
): boolean {
  if (ceilingTiyin === null || amountTiyin === null) return false
  return amountTiyin > ceilingTiyin
}

/**
 * The ledger's BUYURTMA cell. The order travels on the income row, so no order
 * lookup can fail here — the raw-id fallback only survives for an income whose
 * order the server could not resolve at all.
 */
export function financeIncomeOrderLabel(
  orderId: string | null,
  order: FinanceIncomeOrder | null | undefined,
): string {
  if (!orderId) return '—'
  if (!order) return orderId
  return `${formatOrderNumber(order.order_number)} · ${order.contact_name}`
}
