import { describe, expect, it } from 'vitest'

import {
  adminDate,
  adminDateTime,
  adminEntityLabel,
  adminInitials,
  adminJobLogText,
  adminJobNameLabel,
  adminJobScheduleLabel,
  adminNavMetrics,
  adminNotificationDestination,
  adminNotificationTitle,
  adminStatusTransitionLabel,
  auditActionFields,
  auditStatusFields,
  groupedNav,
  matchesNeedle,
} from '@/shared/app/adminUi'
import type { NavItem } from '@/shared/app/roleConfig'
import type { ActionLog, StatusChangeLog } from '@/shared/stores/admin'
import type { NotificationItem } from '@/shared/stores/notifications'

function notification(
  partial: Pick<NotificationItem, 'entity_type' | 'entity_id' | 'event_code'>,
): NotificationItem {
  return {
    id: 'notification-1',
    recipient_type: 'platform_user',
    recipient_id: 'operator-1',
    event_code: partial.event_code,
    payload: {},
    entity_type: partial.entity_type,
    entity_id: partial.entity_id,
    read_at: null,
    created_at: '2026-06-08T00:00:00Z',
  }
}

describe('admin UI helpers', () => {
  it('derives compact initials for the admin shell avatar', () => {
    expect(adminInitials('Platform Operator')).toBe('PO')
    expect(adminInitials('ops')).toBe('OP')
    expect(adminInitials('')).toBe('PL')
  })

  it('formats dates without browser-locale month artifacts', () => {
    expect(adminDate('2026-06-08T00:00:00')).toBe('08.06.2026')
    expect(adminDateTime('2026-06-08T14:05:00')).toBe('08.06.2026 14:05')
    expect(adminDate('not-a-date')).toBe('-')
  })

  it('maps admin internals to operator-facing labels', () => {
    expect(adminEntityLabel('platform_user')).toBe('Platforma admini')
    expect(adminEntityLabel('manufacturer')).toBe('Ishlab chiqaruvchi')
    expect(adminStatusTransitionLabel('active', 'blocked')).toBe('Faol -> Bloklangan')
    expect(adminJobNameLabel('cleanup-expired-sessions')).toBe(
      "Muddati o'tgan sessiyalarni tozalash",
    )
    expect(adminJobScheduleLabel('hourly')).toBe('Har soatda')
    expect(adminJobLogText('Pruned 0 expired sessions')).toBe(
      "Muddati o'tgan 0 ta sessiya tozalandi",
    )
  })

  it('maps live admin metrics to route-level sidebar badges', () => {
    const metrics = adminNavMetrics({
      workshops: 12,
      manufacturers: 4,
      dekorlar: 37,
      failedJobs: 2,
      openErrors: 0,
      operators: 3,
    })

    expect(metrics.get('/admin/workshops')).toMatchObject({ key: 'workshops', value: 12 })
    expect(metrics.get('/admin/catalog/dekorlar')).toMatchObject({
      key: 'dekorlar',
      value: 37,
    })
    expect(metrics.get('/admin/platform/jobs')).toMatchObject({
      key: 'failedJobs',
      value: 2,
      danger: true,
    })
    expect(metrics.get('/admin/platform/errors')).toMatchObject({
      key: 'openErrors',
      value: 0,
      danger: false,
    })
  })

  it('keeps prototype navigation grouped in display order', () => {
    const items: NavItem[] = [
      { labelKey: 'nav.item.dashboard', to: '/admin', group: 'platform' },
      { labelKey: 'nav.item.workshops', to: '/admin/workshops', group: 'platform' },
      { labelKey: 'nav.item.dekorlar', to: '/admin/catalog/dekorlar', group: 'catalog' },
      { labelKey: 'nav.item.audit', to: '/admin/audit', group: 'admin' },
    ]

    expect(groupedNav(items)).toEqual([
      { id: 'platform', items: items.slice(0, 2) },
      { id: 'catalog', items: [items[2]] },
      { id: 'admin', items: [items[3]] },
    ])
  })

  it('matches the audit search predicate by action / entity / trace, blank returns all (AB-51)', () => {
    const action = {
      action: 'platform.workshop.block',
      entity_type: 'workshop',
      entity_id: 'ws-42',
      summary: 'Blocked Acme',
      trace_id: 'trace-abc',
    } as ActionLog
    expect(matchesNeedle(auditActionFields(action), '')).toBe(true)
    expect(matchesNeedle(auditActionFields(action), 'BLOCK')).toBe(true)
    expect(matchesNeedle(auditActionFields(action), 'ws-42')).toBe(true)
    expect(matchesNeedle(auditActionFields(action), 'trace-abc')).toBe(true)
    expect(matchesNeedle(auditActionFields(action), 'nope')).toBe(false)

    const status = {
      entity_type: 'order',
      entity_id: 'ord-7',
      from_status: 'new',
      to_status: 'confirmed',
      reason: null,
    } as StatusChangeLog
    expect(matchesNeedle(auditStatusFields(status), 'confirmed')).toBe(true)
    expect(matchesNeedle(auditStatusFields(status), '  ')).toBe(true)
    expect(matchesNeedle(auditStatusFields(status), 'cancelled')).toBe(false)
  })

  it('routes admin notifications to the matching operating surface', () => {
    expect(
      adminNotificationDestination(
        notification({
          entity_type: 'workshop',
          entity_id: 'workshop-1',
          event_code: 'workshop.created',
        }),
      ),
    ).toBe('/admin/workshops/workshop-1')
    expect(
      adminNotificationDestination(
        notification({
          entity_type: 'error_record',
          entity_id: 'err-1',
          event_code: 'error.spike',
        }),
      ),
    ).toBe('/admin/platform/errors?record=err-1')
    expect(
      adminNotificationDestination(
        notification({ entity_type: null, entity_id: null, event_code: 'job.failed' }),
      ),
    ).toBe('/admin/platform/jobs')
  })

  it('presents admin notifications without mixed-language spike/job labels', () => {
    expect(
      adminNotificationTitle({
        ...notification({ entity_type: null, entity_id: null, event_code: 'error.spike' }),
        payload: { error_code: 'platform.error' },
      }),
    ).toBe("Xato ko'payishi: platform.error")
    expect(
      adminNotificationTitle({
        ...notification({ entity_type: null, entity_id: null, event_code: 'job.failed' }),
        payload: { job_name: 'cleanup-expired-sessions' },
      }),
    ).toBe("Fon vazifa muvaffaqiyatsiz: Muddati o'tgan sessiyalarni tozalash")
  })
})
