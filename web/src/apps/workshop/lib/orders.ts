// Pure helpers for the workshop orders screens — board grouping, relative
// age, and the worker-grants matrix diff. Kept framework-free so they're
// easy to unit-test.

import type { GrantIn, OrderCard, OrderStatus } from '../api/types'
import type { Permission } from '@/shared/types'

// Board columns, left → right, in state-machine order (no completed/cancelled).
export const BOARD_COLUMNS: OrderStatus[] = ['new', 'confirmed', 'cutting', 'edge_banding', 'ready']

// The catalog of staff permissions, in display order, for the grants matrix.
export const PERMISSIONS: Permission[] = [
  'view_dashboard',
  'manage_orders',
  'process_production',
  'manage_catalog',
  'manage_inventory',
  'manage_finance',
  'view_finance_reports',
]

// Group order cards into the board columns. Orders outside the board states
// (completed/cancelled) are dropped — the board only shows in-flight work.
export function groupByColumn(orders: OrderCard[]): Record<OrderStatus, OrderCard[]> {
  const groups = Object.fromEntries(BOARD_COLUMNS.map((c) => [c, [] as OrderCard[]])) as Record<
    OrderStatus,
    OrderCard[]
  >
  for (const o of orders) {
    if (o.status in groups) groups[o.status].push(o)
  }
  return groups
}

// Relative age in Uzbek, e.g. "5 daqiqa", "2 soat", "3 kun".
export function relativeAge(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const mins = Math.max(0, Math.floor((now.getTime() - then) / 60000))
  if (mins < 1) return 'hozir'
  if (mins < 60) return `${mins} daqiqa`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} soat`
  const days = Math.floor(hours / 24)
  return `${days} kun`
}

// A grant key — uniquely identifies a (permission, branch) pair.
export function grantKey(permission: Permission, branchId: string): string {
  return `${permission}::${branchId}`
}

// Diff a desired grant set against the current one. Returns whether anything
// changed plus the added/removed keys (handy for the unsaved-changes guard and
// for previewing the change to the user).
export function diffGrants(
  current: GrantIn[],
  desired: Set<string>,
): { changed: boolean; added: string[]; removed: string[] } {
  const currentKeys = new Set(current.map((g) => grantKey(g.permission, g.branch_id)))
  const added = [...desired].filter((k) => !currentKeys.has(k))
  const removed = [...currentKeys].filter((k) => !desired.has(k))
  return { changed: added.length > 0 || removed.length > 0, added, removed }
}

// Serialise a grant key set back into the API's grant list.
export function grantsFromSet(keys: Set<string>): GrantIn[] {
  return [...keys].map((k) => {
    const [permission, branch_id] = k.split('::') as [Permission, string]
    return { permission, branch_id }
  })
}
