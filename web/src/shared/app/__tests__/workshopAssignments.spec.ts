import { describe, expect, it } from 'vitest'

import {
  assignmentChipsForOrder,
  edgerMissingForOrder,
  workerInitials,
} from '@/shared/app/workshopAssignments'

describe('workshop assignment chips', () => {
  it('builds cutter and edger chips with role labels and initials', () => {
    const chips = assignmentChipsForOrder(
      {
        branch_id: 'branch-1',
        assigned_cutter_user_id: 'user-cutter',
        assigned_edger_user_id: 'user-edger',
      },
      (_branchId, userId) =>
        userId === 'user-cutter'
          ? { id: userId, full_name: 'Ali Valiyev' }
          : { id: userId, full_name: 'Madina Sobirova' },
    )

    expect(chips).toEqual([
      expect.objectContaining({
        key: 'cutter',
        className: 'p-cut',
        icon: 'scissors',
        label: 'Kesuvchi: Ali Valiyev',
        initials: 'AV',
      }),
      expect.objectContaining({
        key: 'edger',
        className: 'p-eb',
        icon: 'layers',
        label: 'Kromka ustasi: Madina Sobirova',
        initials: 'MS',
      }),
    ])
  })

  it('falls back to a short id when worker details are unavailable', () => {
    const chips = assignmentChipsForOrder(
      {
        branch_id: 'branch-1',
        assigned_cutter_user_id: 'abcdef012345',
        assigned_edger_user_id: null,
      },
      () => null,
    )

    expect(chips).toHaveLength(1)
    expect(chips[0]?.label).toBe('Kesuvchi: ID abcdef01')
    expect(chips[0]?.initials).toBe('ABCD')
  })

  it('handles one-part names without dropping the chip text', () => {
    expect(workerInitials('Dilshod')).toBe('DI')
  })
})

describe('edger gap warning', () => {
  const banded = { has_banding: true, assigned_edger_user_id: null }

  it('flags a banded order without an edger once production is running', () => {
    expect(edgerMissingForOrder({ ...banded, status: 'cutting' })).toBe(true)
    expect(edgerMissingForOrder({ ...banded, status: 'edge_banding' })).toBe(true)
  })

  it('stays quiet before the saw starts and after the slot is filled', () => {
    expect(edgerMissingForOrder({ ...banded, status: 'confirmed' })).toBe(false)
    expect(
      edgerMissingForOrder({ ...banded, status: 'cutting', assigned_edger_user_id: 'user-1' }),
    ).toBe(false)
  })

  it('never fires on an order with no banding at all', () => {
    expect(
      edgerMissingForOrder({ has_banding: false, assigned_edger_user_id: null, status: 'cutting' }),
    ).toBe(false)
  })
})
