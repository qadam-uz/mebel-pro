import { describe, expect, it } from 'vitest'

import {
  exceedsOrderBalance,
  financeIncomeOrderLabel,
  financeLedgerTabFromPath,
  incomeSettlementView,
  ledgerRecordedTotalTiyin,
  orderPaymentCeilingTiyin,
} from '@/shared/app/financeLedger'

describe('finance ledger routing', () => {
  it('maps the income deep-link to the income tab', () => {
    expect(financeLedgerTabFromPath('/workshop/finance/income')).toBe('income')
  })

  it('keeps every other finance ledger path on expenses', () => {
    expect(financeLedgerTabFromPath('/workshop/finance/expenses')).toBe('expense')
    expect(financeLedgerTabFromPath('/workshop/finance')).toBe('expense')
  })
})

// QAD-123: the ledger used to name an order out of a loaded page of orders,
// so any income against an older order — and every income at all for a user
// without order permissions — degraded to a raw UUID. The order now travels on
// the income row.
describe('finance income order labels', () => {
  const order = {
    order_number: 'ORD-2026-000003',
    contact_name: 'Ali Valiyev',
    total_tiyin: 5_000_000,
    recorded_tiyin: 2_000_000,
    balance_tiyin: 3_000_000,
  }

  it('names the order from the income row itself', () => {
    expect(financeIncomeOrderLabel('order-1', order)).toBe('ORD-2026-000003 · Ali Valiyev')
  })

  it('shows a dash for an income with no order', () => {
    expect(financeIncomeOrderLabel(null, null)).toBe('—')
  })

  it('falls back to the raw id only when the server could not resolve the order', () => {
    expect(financeIncomeOrderLabel('order-1', null)).toBe('order-1')
  })
})

// QAD-123: the amount field must reject an over-payment before the round trip,
// and must never invent one while an existing income is being edited.
describe('order payment headroom', () => {
  const settlement = { total_tiyin: 5_000_000, recorded_tiyin: 2_000_000, balance_tiyin: 3_000_000 }

  it('caps a new payment at the remaining balance', () => {
    expect(orderPaymentCeilingTiyin(settlement, null)).toBe(3_000_000)
    expect(exceedsOrderBalance(3_000_000, 3_000_000)).toBe(false)
    expect(exceedsOrderBalance(3_000_001, 3_000_000)).toBe(true)
  })

  it('adds the edited income back, so raising it is not read as an over-payment', () => {
    // The 2 000 000 already sits inside recorded_tiyin; editing it to the full
    // order total must stay legal.
    expect(orderPaymentCeilingTiyin(settlement, 2_000_000)).toBe(5_000_000)
    expect(exceedsOrderBalance(5_000_000, 5_000_000)).toBe(false)
    expect(exceedsOrderBalance(5_000_001, 5_000_000)).toBe(true)
  })

  it('caps nothing until an order settlement is known', () => {
    expect(orderPaymentCeilingTiyin(null, null)).toBeNull()
    expect(exceedsOrderBalance(9_000_000, null)).toBe(false)
    expect(exceedsOrderBalance(null, 3_000_000)).toBe(false)
  })

  // The screen must not print two different numbers under one word: the
  // summary's Qoldiq and the Qoldiq button are the same figure by construction.
  it('shows the edited income back out of "recorded", so the summary equals the fill button', () => {
    const settled = { total_tiyin: 5_000_000, recorded_tiyin: 5_000_000, balance_tiyin: 0 }
    const view = incomeSettlementView(settled, 5_000_000)

    expect(view).toEqual({ total_tiyin: 5_000_000, recorded_tiyin: 0, balance_tiyin: 5_000_000 })
    expect(view?.balance_tiyin).toBe(orderPaymentCeilingTiyin(settled, 5_000_000))
  })

  it('leaves the settlement untouched while creating', () => {
    expect(incomeSettlementView(settlement, null)).toEqual(settlement)
  })
})

describe('finance ledger period total', () => {
  // The line under the filters is a money figure. With the status filter on
  // «Hammasi» the rows include voided ones, and a voided row is a cancelled
  // record, not a smaller one — summing it would overstate the day's take to
  // whoever is reconciling a till.
  it('sums the recorded rows and ignores the voided ones', () => {
    expect(
      ledgerRecordedTotalTiyin([
        { amount_tiyin: 1_000_000, status: 'recorded' },
        { amount_tiyin: 2_500_000, status: 'voided' },
        { amount_tiyin: 400_000, status: 'recorded' },
      ]),
    ).toBe(1_400_000)
  })

  it('totals 0 for an all-voided period rather than special-casing it', () => {
    expect(ledgerRecordedTotalTiyin([{ amount_tiyin: 2_500_000, status: 'voided' }])).toBe(0)
  })

  it('totals 0 when nothing is loaded', () => {
    expect(ledgerRecordedTotalTiyin([])).toBe(0)
  })
})
