import { describe, expect, it } from 'vitest'

import {
  stockTransactionTypeLabel,
  workshopDraftStatus,
  workshopErrorMessage,
} from '@/shared/app/workshopUi'

describe('workshop UI helpers', () => {
  it('maps backend/action error codes to Uzbek operator copy', () => {
    expect(workshopErrorMessage('order_version_conflict')).toContain('Buyurtma boshqa joyda')
    expect(workshopErrorMessage('permission_denied')).not.toContain('permission_denied')
    expect(workshopErrorMessage('expense_save_failed')).not.toContain('expense_save_failed')
  })

  it('hides unknown raw codes behind a generic recovery message', () => {
    expect(workshopErrorMessage('future_raw_code')).toBe("Amal bajarilmadi. Qayta urinib ko'ring.")
    expect(workshopErrorMessage(null)).toBe("Amal bajarilmadi. Qayta urinib ko'ring.")
  })

  it('derives a saved-draft status from readiness (drafts carry no DB status)', () => {
    const ready = workshopDraftStatus(true)
    expect(ready.label).toContain('buyurtma berish mumkin')
    expect(ready.pill).toBe('pill p-rdy')

    const inProgress = workshopDraftStatus(false)
    expect(inProgress.label).toBe('Tahrirlanmoqda')
    expect(inProgress.pill).toBe('pill p-new')
  })

  it('localizes stock transaction types', () => {
    expect(stockTransactionTypeLabel('stock_in')).toBe('Kirim')
    expect(stockTransactionTypeLabel('consume')).toBe('Sarf')
    expect(stockTransactionTypeLabel('restore')).toBe('Qaytarish')
    expect(stockTransactionTypeLabel('adjust')).toBe('Tuzatish')
  })
})
