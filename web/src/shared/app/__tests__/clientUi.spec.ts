import { describe, expect, it } from 'vitest'

import {
  clientErrorLabel,
  clientGreetingName,
  clientHomeSubtitle,
  clientNextPhaseLabel,
  clientNotificationBody,
  clientNotificationIconName,
  clientNotificationTitle,
  clientPhaseIndex,
  clientPhaseProgress,
  clientStatusPillClass,
  formatPercent,
  formatRelativeDate,
  isUzPhone,
  normalizeUzPhone,
} from '@/shared/app/clientUi'
import type { NotificationItem } from '@/shared/stores/notifications'

function notification(overrides: Partial<NotificationItem>): NotificationItem {
  return {
    id: 'n1',
    recipient_type: 'client',
    recipient_id: 'c1',
    event_code: 'order.confirmed',
    entity_type: 'order',
    entity_id: 'o1',
    payload: {},
    created_at: '2026-06-19T09:00:00Z',
    read_at: null,
    ...overrides,
  }
}

describe('client UI helpers', () => {
  it('normalizes and validates Uzbek phone numbers', () => {
    expect(normalizeUzPhone('+998 90 123 45 67')).toBe('+998901234567')
    expect(normalizeUzPhone('901234567')).toBe('+998901234567')
    expect(normalizeUzPhone('0901234567')).toBe('+998901234567')
    expect(normalizeUzPhone('998901234567')).toBe('+998901234567')
    expect(normalizeUzPhone('8 998 90 123 45 67')).toBe('+998901234567')
    expect(isUzPhone('+998 90 123 45 67')).toBe(true)
    expect(isUzPhone('901234567')).toBe(true)
    expect(isUzPhone('+997901234567')).toBe(false)
  })

  it('maps client order phases and status pills', () => {
    expect(clientPhaseIndex('new')).toBe(0)
    expect(clientPhaseIndex('edge_banding')).toBe(2)
    expect(clientPhaseIndex('completed')).toBe(4)
    expect(clientPhaseIndex('cancelled')).toBe(-1)
    expect(clientStatusPillClass('ready')).toContain('client-pill-ready')
    expect(clientStatusPillClass('cancelled')).toContain('client-pill-danger')
  })

  it('drives the dashboard progress bar and next-phase hint from the order phase', () => {
    // monotonic fill across the five phases; ready is near-complete, completed is full
    expect(clientPhaseProgress('new')).toBe(14)
    expect(clientPhaseProgress('cutting')).toBe(55)
    expect(clientPhaseProgress('ready')).toBe(85)
    expect(clientPhaseProgress('completed')).toBe(100)
    // off-track statuses read as empty rather than NaN
    expect(clientPhaseProgress('cancelled')).toBe(0)
    // next-phase label points one step ahead; the final phase has none
    expect(clientNextPhaseLabel('new')).toBe('Tasdiqlandi')
    expect(clientNextPhaseLabel('cutting')).toBe('Tayyor')
    expect(clientNextPhaseLabel('ready')).toBe('Topshirildi')
    expect(clientNextPhaseLabel('completed')).toBeNull()
    expect(clientNextPhaseLabel('cancelled')).toBeNull()
  })

  it('greets with the first given name, falling back when no real name is set', () => {
    expect(clientGreetingName({ full_name: 'Dilshod Karimov', name: null })).toBe('Dilshod')
    expect(clientGreetingName({ full_name: null, name: 'Aziza' })).toBe('Aziza')
    expect(clientGreetingName({ full_name: '  Bobur  Mirzo ', name: null })).toBe('Bobur')
    // full_name wins over name; never greets a blank/absent name (caller uses a generic heading)
    expect(clientGreetingName({ full_name: 'Sardor', name: 'ignored' })).toBe('Sardor')
    // an empty-string full_name falls through to a populated name (|| not ??)
    expect(clientGreetingName({ full_name: '', name: 'Aziza' })).toBe('Aziza')
    expect(clientGreetingName({ full_name: '   ', name: 'Jasur' })).toBe('Jasur')
    expect(clientGreetingName({ full_name: '', name: '' })).toBeNull()
    expect(clientGreetingName(null)).toBeNull()
  })

  it('keys the dashboard subtitle off what most needs attention', () => {
    // ready-for-pickup wins; "qolgani yo'lda" only when other orders are still in flight
    expect(clientHomeSubtitle({ ready: 1, active: 3, drafts: 2 })).toBe(
      "1 buyurtmangiz olishga tayyor — qolgani yo'lda.",
    )
    expect(clientHomeSubtitle({ ready: 2, active: 2, drafts: 0 })).toBe(
      '2 buyurtmangiz olishga tayyor.',
    )
    // no ready order → in-flight orders, then drafts, then first-run
    expect(clientHomeSubtitle({ ready: 0, active: 2, drafts: 1 })).toBe(
      '2 ta faol buyurtmangiz bor.',
    )
    expect(clientHomeSubtitle({ ready: 0, active: 0, drafts: 3 })).toBe(
      'Saqlangan chizmalaringizdan davom eting.',
    )
    expect(clientHomeSubtitle({ ready: 0, active: 0, drafts: 0 })).toBe(
      'Birinchi kesim chizmangizdan boshlang.',
    )
  })

  it('formats optimizer waste ratios as percentages (0..1 fraction × 100)', () => {
    expect(formatPercent('0.1234')).toBe('12.34%')
    expect(formatPercent(0)).toBe('0.00%')
    expect(formatPercent(1)).toBe('100.00%')
    expect(formatPercent(null)).toBe('-')
    expect(formatPercent('')).toBe('-')
    expect(formatPercent('abc')).toBe('-')
  })

  it('uses stable numeric compact dates', () => {
    expect(formatRelativeDate(new Date(2026, 5, 2, 9, 4))).toBe('02.06 09:04')
  })

  it('maps client error codes to Uzbek copy, never leaking raw codes', () => {
    // known codes get specific Uzbek copy
    expect(clientErrorLabel('permission_denied')).toBe("Bu amal uchun ruxsat yo'q.")
    expect(clientErrorLabel('order_version_conflict')).toContain("o'zgardi")
    expect(clientErrorLabel('profile_update_failed')).toContain('Profilni')
    // unknown snake_case codes fall back to the generic Uzbek message, not the raw code
    expect(clientErrorLabel('some_unmapped_backend_code')).toBe(
      "Amal bajarilmadi. Qayta urinib ko'ring.",
    )
    expect(clientErrorLabel('some_unmapped_backend_code')).not.toContain('_')
    // null/empty → caller fallback (default or custom)
    expect(clientErrorLabel(null)).toBe("Amal bajarilmadi. Qayta urinib ko'ring.")
    expect(clientErrorLabel(undefined, 'Buyurtma yuborilmadi.')).toBe('Buyurtma yuborilmadi.')
    // an already-human sentence is returned unchanged
    expect(clientErrorLabel('Tarmoqqa ulanib bolmadi.')).toBe('Tarmoqqa ulanib bolmadi.')
  })

  it('presents order notifications with localized titles and an order-number body (CB-02)', () => {
    // event_code → Uzbek title; never the raw code
    expect(clientNotificationTitle(notification({ event_code: 'order.confirmed' }))).toBe(
      'Buyurtma tasdiqlandi',
    )
    expect(clientNotificationTitle(notification({ event_code: 'order.ready' }))).toBe(
      'Buyurtma tayyor',
    )
    expect(clientNotificationTitle(notification({ event_code: 'order.status_changed' }))).toBe(
      "Buyurtma holati o'zgardi",
    )
    // an unknown code never leaks; falls back to the generic title
    const unknown = clientNotificationTitle(notification({ event_code: 'order.weird_new_code' }))
    expect(unknown).toBe('Bildirishnoma')
    expect(unknown).not.toContain('_')
    // an explicit summary in the payload wins over the static map
    expect(
      clientNotificationTitle(
        notification({ event_code: 'order.confirmed', payload: { summary: 'Custom' } }),
      ),
    ).toBe('Custom')

    // body: denormalized order_number is surfaced when there is no prose body
    expect(clientNotificationBody(notification({ payload: { order_number: 'A-1023' } }))).toBe(
      'Buyurtma № A-1023',
    )
    // an explicit body wins over the order-number fallback
    expect(
      clientNotificationBody(
        notification({ payload: { order_number: 'A-1023', body: "Tayyor bo'ldi" } }),
      ),
    ).toBe("Tayyor bo'ldi")
    // inventory events name the material the balance belongs to (QAD-150)
    expect(
      clientNotificationBody(notification({ payload: { material_name: 'LDSP Egger H1145' } })),
    ).toBe('Material: LDSP Egger H1145')
    // no body, no order_number, no material → null (row shows title only)
    expect(clientNotificationBody(notification({ payload: {} }))).toBeNull()

    // a consume that drove the books below zero gets its own title, not a raw code
    expect(
      clientNotificationTitle(
        notification({ event_code: 'inventory.negative_stock', entity_type: 'stock_item' }),
      ),
    ).toBe("Ombor qoldig'i manfiy")

    // icon family resolves from the event code / entity
    expect(clientNotificationIconName(notification({ event_code: 'order.ready' }))).toBe('box')
    expect(
      clientNotificationIconName(
        notification({ event_code: 'inventory.negative_stock', entity_type: 'stock_item' }),
      ),
    ).toBe('alert')
  })
})
