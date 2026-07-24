import { describe, expect, it } from 'vitest'

import {
  dashboardFailureLine,
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

  it('names the cause and keeps code + trace for a backend-reported dashboard failure', () => {
    expect(
      dashboardFailureLine({ section: 'Moliya', code: 'permission_denied', traceId: 'ab12cd34' }),
    ).toBe("Moliya — ruxsat yo'q (permission_denied · trace: ab12cd34)")
  })

  it('keeps an unknown dashboard failure code visible so support is never blind', () => {
    expect(
      dashboardFailureLine({ section: 'Buyurtmalar', code: 'quota_exceeded', traceId: 'ff00' }),
    ).toBe('Buyurtmalar — kutilmagan xatolik (quota_exceeded · trace: ff00)')
  })

  it('reads a missing trace as "the backend never answered" and names the connection cause', () => {
    expect(
      dashboardFailureLine({ section: 'Ombor', code: 'inventory_load_failed', traceId: null }),
    ).toBe("Ombor — serverga ulanib bo'lmadi")
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
