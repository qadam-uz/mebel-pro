import { describe, expect, it } from 'vitest'
import {
  BOARD_COLUMNS,
  diffGrants,
  grantKey,
  grantsFromSet,
  groupByColumn,
  relativeAge,
} from '../orders'
import type { GrantIn, OrderCard } from '../../api/types'

function card(id: string, status: OrderCard['status']): OrderCard {
  return {
    id,
    order_number: `ORD-${id}`,
    branch_id: 'b1',
    status,
    total_tiyin: 0,
    item_count: 1,
    created_at: new Date().toISOString(),
    contact_name: null,
    contact_phone: null,
    assigned_cutter_user_id: null,
    assigned_edger_user_id: null,
  }
}

describe('groupByColumn', () => {
  it('groups cards into the five board columns by status', () => {
    const groups = groupByColumn([
      card('1', 'new'),
      card('2', 'new'),
      card('3', 'cutting'),
      card('4', 'ready'),
    ])
    expect(groups.new.map((o) => o.id)).toEqual(['1', '2'])
    expect(groups.cutting.map((o) => o.id)).toEqual(['3'])
    expect(groups.ready.map((o) => o.id)).toEqual(['4'])
    expect(groups.confirmed).toEqual([])
  })

  it('drops completed and cancelled orders (not board states)', () => {
    const groups = groupByColumn([card('1', 'completed'), card('2', 'cancelled'), card('3', 'new')])
    const total = BOARD_COLUMNS.reduce((a, c) => a + groups[c].length, 0)
    expect(total).toBe(1)
    expect(groups.new).toHaveLength(1)
  })
})

describe('relativeAge', () => {
  const now = new Date('2026-05-20T12:00:00Z')

  it('renders minutes, hours and days in Uzbek', () => {
    expect(relativeAge('2026-05-20T11:55:00Z', now)).toBe('5 daqiqa')
    expect(relativeAge('2026-05-20T10:00:00Z', now)).toBe('2 soat')
    expect(relativeAge('2026-05-17T12:00:00Z', now)).toBe('3 kun')
  })

  it('shows "hozir" for sub-minute ages and clamps the future to 0', () => {
    expect(relativeAge('2026-05-20T11:59:40Z', now)).toBe('hozir')
    expect(relativeAge('2026-05-20T13:00:00Z', now)).toBe('hozir')
  })

  it('returns empty string for an invalid date', () => {
    expect(relativeAge('not-a-date', now)).toBe('')
  })
})

describe('grants matrix diff', () => {
  const current: GrantIn[] = [
    { permission: 'manage_orders', branch_id: 'b1' },
    { permission: 'view_dashboard', branch_id: 'b1' },
  ]

  it('detects no change when sets are equal', () => {
    const desired = new Set([grantKey('manage_orders', 'b1'), grantKey('view_dashboard', 'b1')])
    const d = diffGrants(current, desired)
    expect(d.changed).toBe(false)
    expect(d.added).toEqual([])
    expect(d.removed).toEqual([])
  })

  it('detects an added grant', () => {
    const desired = new Set([
      grantKey('manage_orders', 'b1'),
      grantKey('view_dashboard', 'b1'),
      grantKey('manage_finance', 'b2'),
    ])
    const d = diffGrants(current, desired)
    expect(d.changed).toBe(true)
    expect(d.added).toEqual([grantKey('manage_finance', 'b2')])
    expect(d.removed).toEqual([])
  })

  it('detects a removed grant', () => {
    const desired = new Set([grantKey('manage_orders', 'b1')])
    const d = diffGrants(current, desired)
    expect(d.changed).toBe(true)
    expect(d.removed).toEqual([grantKey('view_dashboard', 'b1')])
  })

  it('round-trips a key set back into the grant list', () => {
    const keys = new Set([grantKey('manage_finance', 'b9')])
    expect(grantsFromSet(keys)).toEqual([{ permission: 'manage_finance', branch_id: 'b9' }])
  })
})
