// Notification inbox API — shared by all three apps' NotificationBell.

import type { Notification, UnreadCount } from '@/shared/types'
import { api } from './client'

export function fetchUnreadCount(): Promise<UnreadCount> {
  return api.get<UnreadCount>('/notifications/unread-count')
}

export function fetchNotifications(): Promise<Notification[]> {
  return api.get<Notification[]>('/notifications')
}

export function markAllRead(): Promise<UnreadCount> {
  return api.post<UnreadCount>('/notifications/mark-all-read')
}

export function markRead(id: string): Promise<void> {
  return api.post<void>(`/notifications/${id}/mark-read`)
}
