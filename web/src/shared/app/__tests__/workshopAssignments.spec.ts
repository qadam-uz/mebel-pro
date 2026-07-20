import { describe, expect, it } from 'vitest'

import { assignmentChipsForOrder, workerInitials } from '@/shared/app/workshopAssignments'

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
