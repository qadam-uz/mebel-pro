import { describe, expect, it } from 'vitest'

import {
  isProductionJobStarted,
  nextUncutPanelId,
  partitionProductionJobs,
  productionJobMetaLine,
  productionPartNames,
  workerShortName,
  workshopProductionQueueCounts,
  workshopQueuePartsLine,
  workshopStationLoad,
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
    ).toBe('6 detal · 2 list')
  })

  it('falls back to completion panel snapshot when planned panels are absent', () => {
    expect(
      workshopQueuePartsLine({
        item_count: 4,
        planned_panels: 0,
        panels_used_snapshot: 1,
      }),
    ).toBe('4 detal · 1 list')
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

  it('counts station load across every assignee, not just the caller', () => {
    // The same rows the personal count above reads. The dashboard's Stansiyalar
    // panel asks the other question — what is at each station, whoever holds it
    // — so nobody's id enters the calculation.
    const load = workshopStationLoad([
      { status: 'new', assigned_cutter_user_id: null, assigned_edger_user_id: null },
      { status: 'confirmed', assigned_cutter_user_id: 'user-1', assigned_edger_user_id: null },
      { status: 'confirmed', assigned_cutter_user_id: null, assigned_edger_user_id: null },
      { status: 'cutting', assigned_cutter_user_id: 'user-2', assigned_edger_user_id: 'user-3' },
      {
        status: 'edge_banding',
        assigned_cutter_user_id: 'user-1',
        assigned_edger_user_id: 'user-3',
      },
      {
        status: 'edge_banding',
        assigned_cutter_user_id: 'user-2',
        assigned_edger_user_id: 'user-3',
      },
      // Past both stations — neither queue holds it any more.
      { status: 'ready', assigned_cutter_user_id: 'user-1', assigned_edger_user_id: 'user-1' },
    ])

    expect(load.cutting).toBe(3)
    expect(load.banding).toBe(2)
    // Distinct, and an unassigned order contributes no name.
    expect(load.cutters).toEqual(['user-1', 'user-2'])
    expect(load.edgers).toEqual(['user-3'])
  })

  it('shortens a station assignee to a given name and a family initial', () => {
    expect(workerShortName('Aziz Tursunov')).toBe('Aziz T.')
    expect(workerShortName('  Rustam   Qodirov Ogli ')).toBe('Rustam Q.')
    expect(workerShortName('Doniyor')).toBe('Doniyor')
    expect(workerShortName('   ')).toBe('')
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

  it('sizes the job for the saw and for the edge bander differently', () => {
    expect(productionJobMetaLine(stationJob(), 'cutting')).toBe('6 detal · 1 list')
    // The bander sizes a job in metres of tape; material names live on the sheet.
    expect(productionJobMetaLine(stationJob(), 'banding')).toBe('3.9 m krom · 6 detal')
    expect(productionJobMetaLine(stationJob({ planned_edge_lines: [] }), 'banding')).toBe(
      '6 detal · 1 list',
    )
  })
})
