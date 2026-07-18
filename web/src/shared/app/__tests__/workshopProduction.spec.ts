import { describe, expect, it } from 'vitest'

import {
  groupProductionJobsByAssignee,
  isProductionJobStarted,
  nextUncutPanelId,
  partitionProductionJobs,
  productionJobMetaLine,
  productionPartNames,
  workshopEdgeMaterialLabel,
  workshopProductionQueueCounts,
  workshopQueueEdgeLine,
  workshopQueuePartsLine,
  type ProductionStationJob,
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

  it('names job-sheet parts from detail names with the editor D-numbering fallback', () => {
    const names = productionPartNames([
      { part_ref: 'uuid-a', name: 'Shkaf yon devor' },
      { part_ref: 'uuid-b', name: null },
      { part_ref: 'uuid-c', name: '   ' },
    ])
    expect(names.get('uuid-a')).toBe('Shkaf yon devor')
    expect(names.get('uuid-b')).toBe('D2')
    expect(names.get('uuid-c')).toBe('D3')
    expect(names.get('uuid-missing')).toBeUndefined()
  })

  it('advances the drawing to the next uncut panel, wrapping around the order', () => {
    const panels = [{ id: 'p1' }, { id: 'p2' }, { id: 'p3' }, { id: 'p4' }]
    // Middle panel marked → the next uncut one after it.
    expect(nextUncutPanelId(panels, new Set(['p2']), 'p2')).toBe('p3')
    // Last panel marked → wrap to the first uncut.
    expect(nextUncutPanelId(panels, new Set(['p1', 'p4']), 'p4')).toBe('p2')
    // Everything marked → stay put.
    expect(nextUncutPanelId(panels, new Set(['p1', 'p2', 'p3', 'p4']), 'p1')).toBeNull()
    // A lone uncut panel is the target wherever the mark landed.
    expect(nextUncutPanelId(panels, new Set(['p1', 'p2', 'p4']), 'p1')).toBe('p3')
  })
})

function stationJob(overrides: Partial<ProductionStationJob> = {}): ProductionStationJob {
  return {
    status: 'confirmed',
    cutting_started_at: null,
    banding_started_at: null,
    assigned_cutter: { id: 'worker-1', full_name: 'Sardor' },
    assigned_edger: { id: 'worker-2', full_name: 'Jamshid' },
    material_labels: ['Premium Oq'],
    item_count: 6,
    planned_panels: 1,
    planned_edge_lines: [
      { material_label: 'PVX Oq', thickness_mm: '2', color: 'oq', consumed_mm: 3900 },
    ],
    ...overrides,
  }
}

describe('station workspace partitioning', () => {
  it('treats a cutting-status job as running even without a start stamp (legacy rows)', () => {
    expect(isProductionJobStarted(stationJob({ status: 'cutting' }), 'cutting')).toBe(true)
    expect(isProductionJobStarted(stationJob({ status: 'confirmed' }), 'cutting')).toBe(false)
  })

  it('treats a banding job as running only once the start stamp is set', () => {
    expect(isProductionJobStarted(stationJob({ status: 'edge_banding' }), 'banding')).toBe(false)
    expect(
      isProductionJobStarted(
        stationJob({ status: 'edge_banding', banding_started_at: '2026-07-11T09:00:00Z' }),
        'banding',
      ),
    ).toBe(true)
  })

  it('splits the queue into the running job and the waiting stack', () => {
    const running = stationJob({ status: 'cutting' })
    const queued = stationJob({ status: 'confirmed' })
    expect(partitionProductionJobs([queued, running], 'cutting')).toEqual({
      current: [running],
      queued: [queued],
    })
  })

  it('groups the manager view by assignee in queue order', () => {
    const a1 = stationJob()
    const b = stationJob({ assigned_cutter: { id: 'worker-9', full_name: 'Bek' } })
    const a2 = stationJob()
    const groups = groupProductionJobsByAssignee([a1, b, a2], 'cutting')
    expect(groups.map((group) => group.worker?.full_name)).toEqual(['Sardor', 'Bek'])
    expect(groups[0]?.jobs).toEqual([a1, a2])
  })

  it('sizes the job for the saw and for the edge bander differently', () => {
    expect(productionJobMetaLine(stationJob(), 'cutting')).toBe('Premium Oq · 6 qism · 1 panel')
    // The edge line already names the tape — no panel-material prefix.
    expect(productionJobMetaLine(stationJob(), 'banding')).toBe('PVX Oq · 2 mm · oq: 3.9 m')
    expect(productionJobMetaLine(stationJob({ planned_edge_lines: [] }), 'banding')).toBe(
      'Premium Oq',
    )
  })
})
