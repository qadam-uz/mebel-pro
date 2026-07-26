import type {} from 'vue-router'

/**
 * How a workshop route relates to the topbar branch picker.
 *
 * The picker writes `selectedBranchContext` (workshop store) and every view
 * decides for itself whether to read it. Nothing used to communicate that
 * choice, so on a workshop-wide page the picker sat there looking live and
 * silently did nothing. Each route now *declares* its scope and `AppShell`
 * renders the picker accordingly — a new route has to state where it stands.
 *
 * The scopes, and which pages fall into each, are documented in
 * `docs/ref/features/access-management.md` ("Branch context").
 */
export type BranchScope =
  /** Reads `selectedBranchContext` and reloads when it changes — picker enabled. */
  | 'branch'
  /** Workshop-wide by design (debts, settings, branches, notifications, profile). */
  | 'workshop'
  /** Takes its branch from the record being viewed; the topbar must never override it. */
  | 'entity'

declare module 'vue-router' {
  interface RouteMeta {
    branchScope?: BranchScope
  }
}

/** Topbar hint explaining why the picker is inert on a non-branch-scoped route. */
export const branchScopeHints: Record<Exclude<BranchScope, 'branch'>, string> = {
  workshop: "Bu sahifa butun ustaxona bo'yicha",
  entity: 'Filial ochilgan yozuvdan olinadi',
}

/** Routes default to `branch` so an undeclared route fails loud, not silent. */
export function branchScopeOf(scope: BranchScope | undefined): BranchScope {
  return scope ?? 'branch'
}
