import { describe, expect, it } from 'vitest'

import {
  CLIENT_PHASE_STATUSES,
  clientErrorLabel,
  draftDisplayName,
  clientGreetingName,
  clientHomeSubtitle,
  clientNextPhaseLabel,
  clientNotificationBody,
  clientNotificationIconName,
  clientNotificationTitle,
  clientPhaseIndex,
  clientPhaseLabels,
  clientPhaseProgress,
  clientPhaseSubtitle,
  clientStatusLabel,
  clientStatusPillClass,
  formatPercent,
  formatFullDate,
  formatRelativeDate,
  isUzPhone,
  normalizeUzPhone,
} from '@/shared/app/clientUi'
import type { NotificationItem } from '@/shared/stores/notifications'
import type { OrderStatus } from '@/shared/stores/orders'
import type { CuttingDraft, CuttingPart, CuttingResult } from '@/shared/stores/cutting'

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

  // Four phases, mode-independent (orders.md): `confirmed`, `cutting` and
  // `edge_banding` are one client phase in BOTH production modes, so the client
  // reads the same track whichever way the workshop runs its floor.
  it('maps the three production statuses onto one client phase', () => {
    expect(clientPhaseIndex('new')).toBe(0)
    expect(clientPhaseIndex('confirmed')).toBe(1)
    expect(clientPhaseIndex('cutting')).toBe(1)
    expect(clientPhaseIndex('edge_banding')).toBe(1)
    expect(clientPhaseIndex('ready')).toBe(2)
    expect(clientPhaseIndex('completed')).toBe(3)
    expect(clientPhaseIndex('cancelled')).toBe(-1)
    expect(clientPhaseLabels()).toEqual(['Yangi', 'Tayyorlanmoqda', 'Tayyor', 'Olib ketildi'])
  })

  it('gives one label, one pill tone and one sub-line per client phase', () => {
    // one word for the whole production phase — and therefore one colour: two
    // tones under the same label would read as a defect, not as detail
    expect(clientStatusLabel('confirmed')).toBe('Tayyorlanmoqda')
    expect(clientStatusLabel('cutting')).toBe('Tayyorlanmoqda')
    expect(clientStatusLabel('edge_banding')).toBe('Tayyorlanmoqda')
    expect(clientStatusPillClass('cutting')).toBe(clientStatusPillClass('confirmed'))
    expect(clientStatusPillClass('edge_banding')).toBe(clientStatusPillClass('confirmed'))
    expect(clientStatusPillClass('ready')).toContain('client-pill-ready')
    expect(clientStatusPillClass('cancelled')).toContain('client-pill-danger')
    expect(clientPhaseSubtitle('new')).toBe('Ustaxona tasdiqlashi kutilmoqda')
    expect(clientPhaseSubtitle('edge_banding')).toBe('Ishlab chiqarish jarayonida')
    expect(clientPhaseSubtitle('ready')).toBe('Olib ketishingiz mumkin')
    // the final phase closes the track and off-track statuses have no sub-line
    expect(clientPhaseSubtitle('completed')).toBe('')
    expect(clientPhaseSubtitle('cancelled')).toBe('')
  })

  it('drives the dashboard progress bar and next-phase hint from the order phase', () => {
    // monotonic fill across the four phases; ready is near-complete, completed is full
    expect(clientPhaseProgress('new')).toBe(14)
    expect(clientPhaseProgress('confirmed')).toBe(45)
    // an order deeper in the workshop's own spine sits at the same client mark
    expect(clientPhaseProgress('cutting')).toBe(45)
    expect(clientPhaseProgress('ready')).toBe(80)
    expect(clientPhaseProgress('completed')).toBe(100)
    // off-track statuses read as empty rather than NaN
    expect(clientPhaseProgress('cancelled')).toBe(0)
    // next-phase label points one step ahead; the final phase has none
    expect(clientNextPhaseLabel('new')).toBe('Tayyorlanmoqda')
    expect(clientNextPhaseLabel('cutting')).toBe('Tayyor')
    expect(clientNextPhaseLabel('ready')).toBe('Olib ketildi')
    expect(clientNextPhaseLabel('completed')).toBeNull()
    expect(clientNextPhaseLabel('cancelled')).toBeNull()
  })

  // The dashboard count strip's second tile: the phase-2 bucket, which an order
  // enters at Approve — not when the saw starts.
  it('counts the whole production phase as one dashboard bucket', () => {
    const statuses: OrderStatus[] = [
      'new',
      'confirmed',
      'cutting',
      'edge_banding',
      'ready',
      'completed',
      'cancelled',
    ]
    expect(statuses.filter((status) => clientPhaseIndex(status) === 1)).toEqual([
      'confirmed',
      'cutting',
      'edge_banding',
    ])
    expect(CLIENT_PHASE_STATUSES[1]).toEqual(['confirmed', 'cutting', 'edge_banding'])
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

  // Same clock, plus the year — order history spans years, where `02.06` alone
  // does not say which one.
  it('spells the year out in full dates', () => {
    expect(formatFullDate(new Date(2026, 5, 2, 9, 4))).toBe('02.06.2026 09:04')
    expect(formatFullDate(new Date(2025, 11, 31, 23, 59))).toBe('31.12.2025 23:59')
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
    // event_code → Uzbek title; never the raw code. The `order.confirmed` title
    // names the phase the client's own pill will now be showing them
    // («Tayyorlanmoqda»), not the internal transition that fired it.
    expect(clientNotificationTitle(notification({ event_code: 'order.confirmed' }))).toBe(
      'Buyurtma tayyorlanmoqda',
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

    // body: denormalized order_number is surfaced when there is no prose body,
    // through the display formatter — the `№` is the formatter's, never copy's
    // (spec §1.3), and a legacy number renders exactly as it was minted.
    expect(clientNotificationBody(notification({ payload: { order_number: 'A-1023' } }))).toBe(
      'Buyurtma A-1023',
    )
    expect(clientNotificationBody(notification({ payload: { order_number: '482917' } }))).toBe(
      `Buyurtma №\u2009482\u2009917`,
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

// draftDisplayName had no coverage at all, which is exactly how it would have
// broken silently: with `.name` gone from post-reshape snapshots the material
// list would be empty and every saved draft would render as "Nomsiz", with a
// green suite. These cases pin the composed-label path in both vocabularies.
describe('draftDisplayName', () => {
  function draft(overrides: Partial<CuttingDraft> = {}): CuttingDraft {
    return {
      id: 'draft-1',
      client_id: 'client-1',
      name: null,
      preferred_branch_id: null,
      kerf_mm: 4,
      edge_trim_mm: 5,
      own_material_allowed: false,
      parts_snapshot: [],
      own_panel_counts: {},
      own_edge_material_ids: [],
      chosen_result_id: null,
      revision_of_order_id: null,
      created_at: '2026-08-01T00:00:00Z',
      updated_at: '2026-08-01T00:00:00Z',
      results: [],
      ...overrides,
    }
  }

  function part(materialId: string): CuttingPart {
    return {
      part_ref: `part-${materialId}`,
      name: null,
      material_id: materialId,
      material_source: 'shop',
      follow_grain: true,
      thickened: false,
      length_mm: 300,
      width_mm: 200,
      quantity: 1,
      edge_top: null,
      edge_bottom: null,
      edge_left: null,
      edge_right: null,
    }
  }

  function withSnapshots(snapshots: Record<string, Record<string, unknown>>): CuttingDraft {
    const result = {
      id: 'result-1',
      material_snapshots: snapshots,
    } as unknown as CuttingResult
    return draft({
      parts_snapshot: Object.keys(snapshots).map(part),
      chosen_result_id: 'result-1',
      results: [result],
    })
  }

  it('uses the draft name whenever there is one', () => {
    expect(draftDisplayName(draft({ name: 'Oshxona' }))).toBe('Oshxona')
  })

  it('names an untitled draft after its materials — new vocabulary', () => {
    expect(
      draftDisplayName(
        withSnapshots({
          'bm-1': {
            manufacturer_name: 'Egger',
            type: 'ldsp',
            code: 'H1334',
            name: 'Sanoma',
            thickness_mm: '18',
            length_mm: 2800,
            width_mm: 2070,
          },
        }),
      ),
    ).toBe('LDSP Egger H1334')
  })

  it('names an untitled draft after its materials — legacy snapshot', () => {
    expect(
      draftDisplayName(
        withSnapshots({
          'bm-1': {
            manufacturer_name: 'Egger',
            type: 'dsp',
            decor_code: 'H1334',
            color: 'Sanoma',
            thickness_mm: '18',
            panel_length_mm: 2800,
            panel_width_mm: 2070,
          },
        }),
      ),
    ).toBe('DSP Egger H1334')
  })

  it('joins two materials and counts the rest', () => {
    const name = draftDisplayName(
      withSnapshots({
        'bm-1': { manufacturer_name: 'Egger', type: 'ldsp', code: 'A' },
        'bm-2': { manufacturer_name: 'Egger', type: 'ldsp', code: 'B' },
        'bm-3': { manufacturer_name: 'Egger', type: 'ldsp', code: 'C' },
      }),
    )
    expect(name).toBe('LDSP Egger A + LDSP Egger B +1')
  })

  it('falls back to the untitled copy when no result names a material', () => {
    expect(draftDisplayName(draft())).toBe('Nomsiz chizma')
    // An empty snapshot resolves to the generic fallback label, which must be
    // filtered out rather than becoming the draft's name.
    expect(draftDisplayName(withSnapshots({ 'bm-1': {} }))).toBe('Nomsiz chizma')
  })
})
