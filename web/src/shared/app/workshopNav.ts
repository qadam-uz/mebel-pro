import type { NavGroupId, NavItem } from '@/shared/app/roleConfig'
import type { ProductionMode } from '@/shared/stores/workshop'

export interface WorkshopNavBranch {
  id: string
  permissions: string[]
  /** Absent on callers that predate the mode (tests, older payloads); only an
   *  explicit `simple` hides the stations, so an unknown mode stays full. */
  production_mode?: ProductionMode
}

export interface WorkshopNavInput {
  isOwner: boolean
  branches: WorkshopNavBranch[]
  selectedBranchId: string
  path: (to: string) => string
}

function hasAny(branch: WorkshopNavBranch, permissions: string[]) {
  return permissions.some((permission) => branch.permissions.includes(permission))
}

function item(labelKey: string, to: string, group: NavGroupId, icon: string): NavItem {
  return { labelKey, to, group, icon }
}

export function workshopNavItems(input: WorkshopNavInput): NavItem[] {
  const nav: NavItem[] = [
    item('nav.item.dashboard', input.path('/workshop'), 'management', 'dashboard'),
  ]

  const selectedBranch =
    input.branches.find((branch) => branch.id === input.selectedBranchId) ?? input.branches[0]
  // The station pages are fed by assignments, and a simple-mode branch never
  // writes one — so on such a branch Kesish and Krom are permanently empty
  // screens. Hiding them takes their sidebar counters with them: the shell
  // derives those from this very list (orders.md, workshop UX).
  const showStations = selectedBranch?.production_mode !== 'simple'

  if (input.isOwner) {
    nav.push(item('nav.item.orders', input.path('/workshop/orders'), 'management', 'orders'))
    if (showStations) {
      nav.push(item('nav.item.cutting', input.path('/workshop/cutting'), 'production', 'scissors'))
      nav.push(item('nav.item.banding', input.path('/workshop/banding'), 'production', 'layers'))
    }
    nav.push(item('nav.item.inventory', input.path('/workshop/inventory'), 'resources', 'box'))
    nav.push(item('nav.item.catalog', input.path('/workshop/catalog'), 'resources', 'grid'))
    nav.push(
      item(
        'nav.item.financeExpenses',
        input.path('/workshop/finance/expenses'),
        'finance',
        'wallet',
      ),
    )
    nav.push(
      item('nav.item.financeDebts', input.path('/workshop/finance/debts'), 'finance', 'scale'),
    )
    nav.push(
      item(
        'nav.item.financeProduction',
        input.path('/workshop/finance/production'),
        'finance',
        'users',
      ),
    )
    nav.push(item('nav.item.branches', input.path('/workshop/branches'), 'system', 'store'))
    nav.push(
      // «Xodimlar ro'yxati», not «Xodimlar»: «Xodimlar mehnati» sits two groups
      // above it and the two labels were indistinguishable at a glance (QAD-182).
      item('nav.item.staff', input.path('/workshop/settings/users'), 'system', 'users'),
    )
    nav.push(item('nav.item.settings', input.path('/workshop/settings'), 'system', 'settings'))
    return nav
  }

  if (!selectedBranch) {
    return nav
  }

  if (hasAny(selectedBranch, ['manage_orders'])) {
    nav.push(item('nav.item.orders', input.path('/workshop/orders'), 'management', 'orders'))
  }
  if (showStations && hasAny(selectedBranch, ['process_production'])) {
    nav.push(item('nav.item.cutting', input.path('/workshop/cutting'), 'production', 'scissors'))
    nav.push(item('nav.item.banding', input.path('/workshop/banding'), 'production', 'layers'))
  }
  if (hasAny(selectedBranch, ['manage_inventory'])) {
    nav.push(item('nav.item.inventory', input.path('/workshop/inventory'), 'resources', 'box'))
  }
  if (hasAny(selectedBranch, ['manage_catalog'])) {
    nav.push(item('nav.item.catalog', input.path('/workshop/catalog'), 'resources', 'grid'))
  }
  if (hasAny(selectedBranch, ['manage_finance'])) {
    nav.push(
      item(
        'nav.item.financeExpenses',
        input.path('/workshop/finance/expenses'),
        'finance',
        'wallet',
      ),
    )
    nav.push(
      item('nav.item.financeDebts', input.path('/workshop/finance/debts'), 'finance', 'scale'),
    )
  }
  if (hasAny(selectedBranch, ['manage_finance', 'view_finance_reports'])) {
    nav.push(
      item(
        'nav.item.financeProduction',
        input.path('/workshop/finance/production'),
        'finance',
        'users',
      ),
    )
  }
  return nav
}
