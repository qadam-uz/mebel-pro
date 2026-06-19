export interface AssignmentChipOrder {
  branch_id: string
  assigned_cutter_user_id: string | null
  assigned_edger_user_id: string | null
}

export interface AssignmentChipWorker {
  id: string
  full_name: string
}

export interface AssignmentChip {
  key: 'cutter' | 'edger'
  userId: string
  className: 'p-cut' | 'p-eb'
  icon: 'scissors' | 'layers'
  label: string
  initials: string
}

function fallbackInitials(userId: string) {
  return userId.slice(0, 4).toUpperCase()
}

export function workerInitials(name: string) {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter((part) => part.length > 0)
  if (parts.length === 0) return '??'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
}

function chipForWorker(
  key: AssignmentChip['key'],
  userId: string | null,
  resolveWorker: (branchId: string, userId: string) => AssignmentChipWorker | null,
  branchId: string,
) {
  if (!userId) return null
  const worker = resolveWorker(branchId, userId)
  const roleLabel = key === 'cutter' ? 'Kesuvchi' : 'Kromchi'
  const fallback = `ID ${userId.slice(0, 8)}`
  return {
    key,
    userId,
    className: key === 'cutter' ? 'p-cut' : 'p-eb',
    icon: key === 'cutter' ? 'scissors' : 'layers',
    label: `${roleLabel}: ${worker?.full_name ?? fallback}`,
    initials: worker ? workerInitials(worker.full_name) : fallbackInitials(userId),
  } satisfies AssignmentChip
}

export function assignmentChipsForOrder(
  order: AssignmentChipOrder,
  resolveWorker: (branchId: string, userId: string) => AssignmentChipWorker | null,
) {
  return [
    chipForWorker('cutter', order.assigned_cutter_user_id, resolveWorker, order.branch_id),
    chipForWorker('edger', order.assigned_edger_user_id, resolveWorker, order.branch_id),
  ].filter((chip): chip is AssignmentChip => chip !== null)
}
