import { describe, expect, it } from 'vitest'
import { pickerBranchIds } from '../branches'
import type { Grant } from '@/shared/types'

const all = ['b1', 'b2', 'b3']

describe('pickerBranchIds', () => {
  it('gives the owner every branch regardless of grants', () => {
    expect(pickerBranchIds(true, all, [], null)).toEqual(all)
  })

  it('scopes staff to branches they hold a grant on', () => {
    const grants: Grant[] = [
      { permission: 'manage_orders', branch_id: 'b2' },
      { permission: 'view_dashboard', branch_id: 'b2' },
    ]
    expect(pickerBranchIds(false, all, grants, null)).toEqual(['b2'])
  })

  it('always includes the home branch even without a grant on it', () => {
    expect(pickerBranchIds(false, all, [], 'b3')).toEqual(['b3'])
  })

  it('returns nothing for a staff user with no grants and no home branch', () => {
    expect(pickerBranchIds(false, all, [], null)).toEqual([])
  })
})
