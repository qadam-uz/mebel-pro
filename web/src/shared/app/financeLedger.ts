export type FinanceLedgerTab = 'expense' | 'income'

export interface FinanceOrderReference {
  id: string
  order_number: string
  contact_name?: string | null
}

export function financeLedgerTabFromPath(path: string): FinanceLedgerTab {
  return path.endsWith('/income') ? 'income' : 'expense'
}

export function financeOrderReferenceLabel(
  orderId: string | null,
  orders: FinanceOrderReference[],
  currentOrder?: FinanceOrderReference | null,
) {
  if (!orderId) return '—'
  const order =
    currentOrder?.id === orderId
      ? currentOrder
      : orders.find((candidate) => candidate.id === orderId)
  if (!order) return orderId
  return order.contact_name ? `${order.order_number} · ${order.contact_name}` : order.order_number
}
