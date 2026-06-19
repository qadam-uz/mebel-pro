import { notificationDestination } from '@/shared/app/notificationPresenter'
import type { NotificationItem } from '@/shared/stores/notifications'

export function workshopNotificationDestination(item: NotificationItem) {
  return notificationDestination(item, 'workshop')
}

export function workshopNotificationMatchesFilter(item: NotificationItem, filter: string) {
  if (filter === 'unread') return item.read_at === null
  if (filter === 'all') return true
  if (filter === 'inventory') {
    return (
      item.entity_type === 'stock_item' ||
      item.entity_type === 'stock_transaction' ||
      item.event_code.includes('inventory') ||
      item.event_code.includes('stock')
    )
  }
  if (filter === 'finance') {
    return (
      item.entity_type === 'income' ||
      item.entity_type === 'expense' ||
      item.event_code.includes('finance')
    )
  }
  return item.event_code.includes(filter) || item.entity_type === filter
}
