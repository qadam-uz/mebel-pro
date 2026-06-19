import { describe, expect, it } from 'vitest'

import {
  adminDate,
  adminDateTime,
  adminInitials,
  adminNavMetrics,
  adminNotificationDestination,
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

  it('maps live admin metrics to route-level sidebar badges', () => {
    const metrics = adminNavMetrics({
      workshops: 12,
      manufacturers: 4,
      materials: 37,
      failedJobs: 2,
      openErrors: 0,
      operators: 3,
    })

    expect(metrics.get('/admin/workshops')).toMatchObject({ key: 'workshops', value: 12 })
    expect(metrics.get('/admin/catalog/materials')).toMatchObject({
      key: 'materials',
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
      { label: 'Asosiy', to: '/admin', group: 'Platforma' },
      { label: 'Ustaxonalar', to: '/admin/workshops', group: 'Platforma' },
      { label: 'Materiallar', to: '/admin/catalog/materials', group: 'Katalog' },
      { label: 'Audit log', to: '/admin/audit', group: 'Operatorlik' },
    ]

    expect(groupedNav(items)).toEqual([
      { label: 'Platforma', items: items.slice(0, 2) },
      { label: 'Katalog', items: [items[2]] },
      { label: 'Operatorlik', items: [items[3]] },
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
    ).toBe('/admin/platform/errors')
    expect(
      adminNotificationDestination(
        notification({ entity_type: null, entity_id: null, event_code: 'job.failed' }),
      ),
    ).toBe('/admin/platform/jobs')
  })
})
