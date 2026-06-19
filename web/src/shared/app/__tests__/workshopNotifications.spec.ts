import { describe, expect, it } from 'vitest'

import {
  workshopNotificationDestination,
  workshopNotificationMatchesFilter,
} from '@/shared/app/workshopNotifications'
import type { NotificationItem } from '@/shared/stores/notifications'

function notification(overrides: Partial<NotificationItem>): NotificationItem {
  return {
    id: 'notification-1',
    recipient_type: 'workshop_user',
    recipient_id: 'user-1',
    event_code: 'inventory.low_stock',
    entity_type: 'stock_item',
    entity_id: 'stock-1',
    payload: {},
    created_at: '2026-06-19T00:00:00Z',
    read_at: null,
    ...overrides,
  }
}

describe('workshop notifications', () => {
  it('matches inventory notifications for both inventory and stock event families', () => {
    expect(
      workshopNotificationMatchesFilter(
        notification({ event_code: 'stock.low', entity_type: null, entity_id: null }),
        'inventory',
      ),
    ).toBe(true)
    expect(
      workshopNotificationMatchesFilter(
        notification({ event_code: 'inventory.low_stock', entity_type: 'stock_item' }),
        'inventory',
      ),
    ).toBe(true)
  })

  it('routes workshop notifications to the relevant operating surface', () => {
    expect(workshopNotificationDestination(notification({ entity_type: 'stock_item' }))).toBe(
      '/workshop/inventory',
    )
    expect(
      workshopNotificationDestination(
        notification({
          event_code: 'finance.income.create',
          entity_type: 'income',
          entity_id: 'income-1',
        }),
      ),
    ).toBe('/workshop/finance/expenses')
    expect(
      workshopNotificationDestination(
        notification({
          event_code: 'order.ready',
          entity_type: 'order',
          entity_id: 'order-1',
        }),
      ),
    ).toBe('/workshop/orders/order-1')
  })
})
