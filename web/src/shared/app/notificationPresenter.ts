import { adminNotificationDestination, adminNotificationTitle } from '@/shared/app/adminUi'
import {
  clientNotificationBody,
  clientNotificationIconName,
  clientNotificationTitle,
} from '@/shared/app/clientUi'
import type { RoleKey } from '@/shared/app/roleConfig'
import type { NotificationItem } from '@/shared/stores/notifications'

/**
 * One role-aware presenter for notifications (CB-101). The bell
 * (`NotificationsMenu`) and the full page (`ClientNotificationsView`) both render
 * through these helpers, so the same notification presents identically in both
 * surfaces instead of each component re-deriving title/body/icon/destination with
 * slightly different coverage. Per-role copy still lives in `clientUi`/`adminUi`;
 * this module only routes by role.
 */
export function notificationTitle(item: NotificationItem, role: RoleKey): string {
  if (role === 'admin') return adminNotificationTitle(item)
  return clientNotificationTitle(item)
}

export function notificationBody(item: NotificationItem): string | null {
  return clientNotificationBody(item)
}

export function notificationIconName(item: NotificationItem): string {
  return clientNotificationIconName(item)
}

/**
 * Where tapping a notification should navigate, or `null` when there is no
 * viewable destination (entity gone / not visible to this principal). Callers
 * must treat `null` as a "not available" state rather than silently doing nothing
 * (CB-125). Behaviour matches the prior inline logic exactly.
 */
export function notificationDestination(item: NotificationItem, role: RoleKey): string | null {
  if (item.entity_type === 'order' && item.entity_id && role === 'client') {
    return `/c/orders/${item.entity_id}`
  }
  if (item.entity_type === 'order' && item.entity_id && role === 'workshop') {
    return `/workshop/orders/${item.entity_id}`
  }
  if (item.entity_type === 'branch' && item.entity_id && role === 'workshop') {
    return `/workshop/branches/${item.entity_id}`
  }
  if (role === 'workshop') {
    if (
      item.entity_type === 'stock_item' ||
      item.entity_type === 'stock_transaction' ||
      item.event_code.includes('stock') ||
      item.event_code.includes('inventory')
    ) {
      return '/workshop/inventory'
    }
    if (
      item.entity_type === 'income' ||
      item.entity_type === 'expense' ||
      item.event_code.includes('finance')
    ) {
      return '/workshop/finance/expenses'
    }
  }
  if (!item.entity_type || !item.entity_id) return null
  if (item.entity_type === 'workshop' && role === 'admin') {
    return `/admin/workshops/${item.entity_id}`
  }
  if (role === 'admin') return adminNotificationDestination(item)
  return null
}
