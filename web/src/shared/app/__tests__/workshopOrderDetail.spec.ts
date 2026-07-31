import { describe, expect, it } from 'vitest'

import {
  isRevisionEvent,
  orderPhaseSteps,
  orderReworkCount,
  parseOrderAdjustmentDraft,
  productionTimelineDetails,
  revisionTimelineDetails,
  workshopOrderListActions,
  type WorkshopOrderActionAccess,
  type WorkshopOrderActionOrder,
} from '@/shared/app/workshopOrderDetail'

describe('workshop order detail helpers', () => {
  const manager: WorkshopOrderActionAccess = {
    canManageOrders: true,
    canCompleteCutting: true,
    canCompleteBanding: true,
  }
  const readOnly: WorkshopOrderActionAccess = {
    canManageOrders: false,
    canCompleteCutting: false,
    canCompleteBanding: false,
  }
  const baseOrder: WorkshopOrderActionOrder = {
    status: 'new',
    has_banding: true,
    assigned_cutter_user_id: null,
    assigned_edger_user_id: null,
    banding_started_at: null,
  }

  it('parses a percent adjustment as a whole percent', () => {
    expect(parseOrderAdjustmentDraft('percent', '10', 'Promo')).toEqual({
      ok: true,
      payload: { kind: 'percent', value: 10, reason: 'Promo' },
    })
  })

  it("converts a fixed adjustment from so'm to tiyin, grouping included", () => {
    // "25 000" so'm → 2 500 000 tiyin; the grouping space that sanitizeMoneyInput
    // allows must not break the parse (the old Number() path returned NaN here).
    expect(parseOrderAdjustmentDraft('fixed', '25 000', 'Round down')).toEqual({
      ok: true,
      payload: { kind: 'fixed', value: 2_500_000, reason: 'Round down' },
    })
    expect(parseOrderAdjustmentDraft('fixed', '50000', 'Rush')).toEqual({
      ok: true,
      payload: { kind: 'fixed', value: 5_000_000, reason: 'Rush' },
    })
  })

  it('rejects invalid adjustment drafts with localized copy', () => {
    expect(parseOrderAdjustmentDraft('fixed', '0', 'Reason')).toEqual({
      ok: false,
      message: "Qiymatni to'g'ri kiriting — masalan: 50 000.",
    })
    expect(parseOrderAdjustmentDraft('fixed', '', 'Reason')).toEqual({
      ok: false,
      message: "Qiymatni to'g'ri kiriting — masalan: 50 000.",
    })
    expect(parseOrderAdjustmentDraft('fixed', '1000', '   ')).toEqual({
      ok: false,
      message: 'Sababni kiriting.',
    })
    expect(parseOrderAdjustmentDraft('percent', '120', 'Promo')).toEqual({
      ok: false,
      message: 'Foizni 1 dan 100 gacha butun son qilib kiriting.',
    })
    expect(parseOrderAdjustmentDraft('percent', '0', 'Promo')).toEqual({
      ok: false,
      message: 'Foizni 1 dan 100 gacha butun son qilib kiriting.',
    })
  })

  it('keeps read-only list menus to the detail action', () => {
    expect(workshopOrderListActions({ ...baseOrder, status: 'ready' }, readOnly)).toEqual([
      { kind: 'detail', label: 'Tafsilotlar' },
    ])
  })

  it('offers manager status actions from the order list', () => {
    expect(workshopOrderListActions(baseOrder, manager).map((action) => action.kind)).toEqual([
      'approve',
      'cancel',
      'detail',
    ])

    expect(
      workshopOrderListActions({ ...baseOrder, status: 'ready' }, manager).map(
        (action) => action.kind,
      ),
    ).toEqual(['mark_collected', 'revert', 'cancel', 'detail'])
  })

  it('lets assigned production users complete only their current step', () => {
    expect(
      workshopOrderListActions(
        {
          ...baseOrder,
          status: 'cutting',
          assigned_cutter_user_id: 'worker-1',
        },
        { canManageOrders: false, canCompleteCutting: true, canCompleteBanding: false },
      ).map((action) => action.kind),
    ).toEqual(['complete_cutting', 'detail'])
  })

  it("offers start-cutting as the queued order's forward action, not assignment", () => {
    // Assignment is metadata: a confirmed+assigned order starts via the worker
    // (or on-behalf), and assignment alone must not promise "boshlash".
    const assigned = workshopOrderListActions(
      { ...baseOrder, status: 'confirmed', assigned_cutter_user_id: 'worker-1' },
      manager,
    )
    expect(assigned.map((action) => action.kind)).toEqual([
      'start_cutting',
      'assign',
      'cancel',
      'detail',
    ])
    expect(assigned.find((action) => action.kind === 'assign')?.label).toBe('Tayinlash')

    // Unassigned: nothing to start yet — assign leads.
    expect(
      workshopOrderListActions({ ...baseOrder, status: 'confirmed' }, manager).map(
        (action) => action.kind,
      ),
    ).toEqual(['assign', 'cancel', 'detail'])

    // A worker assigned to the job can start it without manage_orders.
    expect(
      workshopOrderListActions(
        { ...baseOrder, status: 'confirmed', assigned_cutter_user_id: 'worker-1' },
        { canManageOrders: false, canCompleteCutting: true, canCompleteBanding: false },
      ).map((action) => action.kind),
    ).toEqual(['start_cutting', 'detail'])
  })

  it('offers start-banding once and only until the stamp is set', () => {
    const access = { canManageOrders: false, canCompleteCutting: false, canCompleteBanding: true }
    expect(
      workshopOrderListActions(
        { ...baseOrder, status: 'edge_banding', assigned_edger_user_id: 'worker-2' },
        access,
      ).map((action) => action.kind),
    ).toEqual(['start_banding', 'complete_banding', 'detail'])
    expect(
      workshopOrderListActions(
        {
          ...baseOrder,
          status: 'edge_banding',
          assigned_edger_user_id: 'worker-2',
          banding_started_at: '2026-07-11T09:00:00Z',
        },
        access,
      ).map((action) => action.kind),
    ).toEqual(['complete_banding', 'detail'])
  })

  it('falls back to assignment/detail when a manager cannot safely complete without a worker', () => {
    expect(
      workshopOrderListActions(
        {
          ...baseOrder,
          status: 'cutting',
          assigned_cutter_user_id: null,
        },
        manager,
      ).map((action) => action.kind),
    ).toEqual(['assign', 'revert', 'cancel', 'detail'])
  })

  it('lays out the phase stepper with the current step marked', () => {
    expect(orderPhaseSteps({ status: 'cutting', has_banding: true })).toEqual([
      { status: 'new', state: 'done' },
      { status: 'confirmed', state: 'done' },
      { status: 'cutting', state: 'current' },
      { status: 'edge_banding', state: 'upcoming' },
      { status: 'ready', state: 'upcoming' },
      { status: 'completed', state: 'upcoming' },
    ])
  })

  it('drops the edge_banding step when the order has no banding', () => {
    expect(orderPhaseSteps({ status: 'ready', has_banding: false }).map((s) => s.status)).toEqual([
      'new',
      'confirmed',
      'cutting',
      'ready',
      'completed',
    ])
  })

  it('marks every step done for a completed order', () => {
    expect(
      orderPhaseSteps({ status: 'completed', has_banding: true }).every((s) => s.state === 'done'),
    ).toBe(true)
  })

  it('counts only backward transitions as rework, ignoring cancellation', () => {
    expect(
      orderReworkCount([
        { from_status: null, to_status: 'new' },
        { from_status: 'confirmed', to_status: 'cutting' },
        { from_status: 'edge_banding', to_status: 'cutting' },
        { from_status: 'cutting', to_status: 'edge_banding' },
        { from_status: 'edge_banding', to_status: 'cutting' },
        { from_status: 'cutting', to_status: 'cancelled' },
      ]),
    ).toBe(2)
  })

  it('summarizes production metadata for the order timeline', () => {
    expect(
      productionTimelineDetails(
        {
          from_status: 'cutting',
          to_status: 'edge_banding',
          metadata: {
            credited_user_id: 'worker-1',
            panel_demands: { panel_a: 2, panel_b: 1 },
          },
        },
        (id) => (id === 'worker-1' ? 'Ali Valiyev' : id),
      ),
    ).toEqual(['Bajardi: Ali Valiyev', 'List sarfi: 3 list'])

    expect(
      productionTimelineDetails(
        {
          from_status: 'edge_banding',
          to_status: 'ready',
          metadata: {
            credited_user_id: 'worker-2',
            edge_demands: { edge_a: 2500, edge_b: 500 },
          },
        },
        (id) => id,
      ),
    ).toEqual(['Bajardi: worker-2', 'Kromka sarfi: 3 m'])
  })

  it('names a same-status edited event and summarizes its metadata', () => {
    const formatMoney = (tiyin: number) => `${tiyin / 100} so'm`
    const edited = {
      from_status: 'confirmed' as const,
      to_status: 'confirmed' as const,
      metadata: {
        edited: true,
        previous_total_tiyin: 300_000,
        total_tiyin: 450_000,
        discount_cleared_tiyin: 10_000,
        edger_assignment_cleared: true,
      },
    }
    expect(isRevisionEvent(edited)).toBe(true)
    expect(revisionTimelineDetails(edited, formatMoney)).toEqual([
      "Narx: 3000 so'm → 4500 so'm",
      "Chegirma bekor qilindi: 100 so'm",
      'Krom tayinlovi olib tashlandi',
    ])

    // A plain transition is untouched — no revision label, no details.
    const transition = {
      from_status: 'new' as const,
      to_status: 'confirmed' as const,
      metadata: null,
    }
    expect(isRevisionEvent(transition)).toBe(false)
    expect(revisionTimelineDetails(transition, formatMoney)).toEqual([])

    // An unchanged total renders no price line.
    expect(
      revisionTimelineDetails(
        {
          from_status: 'new',
          to_status: 'new',
          metadata: { edited: true, previous_total_tiyin: 300_000, total_tiyin: 300_000 },
        },
        formatMoney,
      ),
    ).toEqual([])
  })
})
