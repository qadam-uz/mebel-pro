import { describe, expect, it } from 'vitest'

import { financeLedgerTabFromPath, financeOrderReferenceLabel } from '@/shared/app/financeLedger'

describe('finance ledger routing', () => {
  it('maps the income deep-link to the income tab', () => {
    expect(financeLedgerTabFromPath('/workshop/finance/income')).toBe('income')
  })

  it('keeps every other finance ledger path on expenses', () => {
    expect(financeLedgerTabFromPath('/workshop/finance/expenses')).toBe('expense')
    expect(financeLedgerTabFromPath('/workshop/finance')).toBe('expense')
  })
})

describe('finance order reference labels', () => {
  it('shows the readable order number and customer when metadata is loaded', () => {
    expect(
      financeOrderReferenceLabel('order-1', [
        { id: 'order-1', order_number: 'ORD-2026-000003', contact_name: 'Ali Valiyev' },
      ]),
    ).toBe('ORD-2026-000003 · Ali Valiyev')
  })

  it('prefers the current order detail over the list entry', () => {
    expect(
      financeOrderReferenceLabel(
        'order-1',
        [{ id: 'order-1', order_number: 'ORD-2026-000003', contact_name: 'Old name' }],
        { id: 'order-1', order_number: 'ORD-2026-000003', contact_name: 'Fresh name' },
      ),
    ).toBe('ORD-2026-000003 · Fresh name')
  })

  it('falls back to the raw id only when metadata is unavailable', () => {
    expect(financeOrderReferenceLabel('order-1', [])).toBe('order-1')
    expect(financeOrderReferenceLabel(null, [])).toBe('—')
  })
})
