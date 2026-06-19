import { describe, expect, it } from 'vitest'

import {
  resolveProductionCreditUser,
  workshopEdgeMaterialLabel,
  workshopProductionQueueCounts,
  workshopQueueEdgeLine,
  workshopQueuePartsLine,
} from '@/shared/app/workshopProduction'

describe('workshop production display helpers', () => {
  it('shows planned panel counts before completion snapshots exist', () => {
    expect(
      workshopQueuePartsLine({
        item_count: 6,
        planned_panels: 2,
        panels_used_snapshot: null,
      }),
    ).toBe('6 qism · 2 panel')
  })

  it('falls back to completion panel snapshot when planned panels are absent', () => {
    expect(
      workshopQueuePartsLine({
        item_count: 4,
        planned_panels: 0,
        panels_used_snapshot: 1,
      }),
    ).toBe('4 qism · 1 panel')
  })

  it('renders edge-material labels instead of raw material ids', () => {
    const line = {
      material_label: 'Egger White Edge',
      thickness_mm: '2',
      color: 'White',
      consumed_mm: 12500,
    }

    expect(workshopEdgeMaterialLabel(line)).toBe('Egger White Edge · 2 mm · White')
    expect(workshopQueueEdgeLine([line])).toContain('Egger White Edge · 2 mm · White')
    expect(workshopQueueEdgeLine([line])).toMatch(/12[,.]5/)
  })

  it('names an empty banding plan without leaking ids', () => {
    expect(workshopQueueEdgeLine([])).toBe('krom rejasi')
  })

  it('counts only production jobs assigned to the current worker', () => {
    expect(
      workshopProductionQueueCounts(
        [
          {
            status: 'confirmed',
            assigned_cutter_user_id: 'user-1',
            assigned_edger_user_id: null,
          },
          {
            status: 'cutting',
            assigned_cutter_user_id: 'user-1',
            assigned_edger_user_id: 'user-2',
          },
          {
            status: 'edge_banding',
            assigned_cutter_user_id: 'user-2',
            assigned_edger_user_id: 'user-1',
          },
          {
            status: 'edge_banding',
            assigned_cutter_user_id: 'user-1',
            assigned_edger_user_id: 'user-3',
          },
          {
            status: 'ready',
            assigned_cutter_user_id: 'user-1',
            assigned_edger_user_id: 'user-1',
          },
        ],
        'user-1',
      ),
    ).toEqual({ cutting: 2, banding: 1, total: 3 })
  })

  it('lets managers credit a selected worker while staff credit the assignee', () => {
    expect(resolveProductionCreditUser('assigned', 'selected', true)).toBe('selected')
    expect(resolveProductionCreditUser('assigned', 'selected', false)).toBe('assigned')
    expect(resolveProductionCreditUser('assigned', null, true)).toBe('assigned')
    expect(resolveProductionCreditUser(null, null, true)).toBeNull()
  })
})
