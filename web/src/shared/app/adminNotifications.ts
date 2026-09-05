import type { NotificationItem } from '@/shared/stores/notifications'

/**
 * Platform notification copy and destinations, plus the two label helpers they
 * lean on.
 *
 * These live apart from `adminUi.ts` because `notificationPresenter.ts` — which
 * every role's notification bell renders through — needs exactly this much of
 * the platform's copy. Importing it from `adminUi` put that whole module (its
 * label tables, its error map, its formatters) into the chunk all three SPAs
 * share, so the client and workshop bundles carried the platform's vocabulary
 * to render a title they never reach.
 */
export function fallbackDisplayLabel(value: string) {
  return value.replace(/_/g, ' ').replace(/-/g, ' ')
}

const ADMIN_JOB_LABELS: Record<string, string> = {
  'cleanup-expired-sessions': "Muddati o'tgan sessiyalarni tozalash",
}

export function adminJobNameLabel(value: string | null | undefined) {
  if (!value) return '-'
  return ADMIN_JOB_LABELS[value] ?? fallbackDisplayLabel(value)
}

function notificationPayloadText(item: NotificationItem, key: string) {
  const value = item.payload[key]
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function adminNotificationTitle(item: NotificationItem) {
  const summary = item.payload.summary
  if (typeof summary === 'string' && summary.trim()) return summary
  const jobName = notificationPayloadText(item, 'job_name')
  const errorCode =
    notificationPayloadText(item, 'error_code') ?? notificationPayloadText(item, 'code')
  if (item.event_code.includes('job')) {
    return jobName
      ? `Fon vazifa muvaffaqiyatsiz: ${adminJobNameLabel(jobName)}`
      : `Fon vazifa muvaffaqiyatsiz: ${item.event_code}`
  }
  if (item.event_code.includes('error')) {
    return errorCode ? `Xato ko'payishi: ${errorCode}` : `Xato ko'payishi: ${item.event_code}`
  }
  return item.event_code
}

export function adminNotificationDestination(item: NotificationItem) {
  if (item.entity_type === 'workshop' && item.entity_id) return `/admin/workshops/${item.entity_id}`
  if (item.entity_type === 'error_record' && item.entity_id) {
    return `/admin/platform/errors?record=${encodeURIComponent(item.entity_id)}`
  }
  const jobName = notificationPayloadText(item, 'job_name')
  if (item.event_code.includes('job')) {
    return jobName
      ? `/admin/platform/jobs?job=${encodeURIComponent(jobName)}`
      : '/admin/platform/jobs'
  }
  const errorCode =
    notificationPayloadText(item, 'error_code') ?? notificationPayloadText(item, 'code')
  if (item.event_code.includes('error')) {
    return errorCode
      ? `/admin/platform/errors?code=${encodeURIComponent(errorCode)}`
      : '/admin/platform/errors'
  }
  return '/admin/notifications'
}
