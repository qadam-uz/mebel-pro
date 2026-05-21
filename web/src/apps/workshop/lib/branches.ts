// Pure helper for the branch-picker scoping: the branches a principal may
// select. Owners see every branch; staff see only branches they hold a grant
// on (or their home branch). Kept framework-free for testing.

import type { Grant } from '@/shared/types'

export function pickerBranchIds(
  isOwner: boolean,
  allBranchIds: string[],
  grants: Grant[],
  homeBranchId: string | null,
): string[] {
  if (isOwner) return allBranchIds
  const granted = new Set(grants.map((g) => g.branch_id))
  if (homeBranchId) granted.add(homeBranchId)
  return allBranchIds.filter((id) => granted.has(id))
}
