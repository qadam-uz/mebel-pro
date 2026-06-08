import type { NavItem } from '@/shared/app/roleConfig'

export interface WorkshopNavBranch {
  id: string
  permissions: string[]
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

export function workshopNavItems(input: WorkshopNavInput): NavItem[] {
  const nav: NavItem[] = [{ label: 'Dashboard', to: input.path('/workshop') }]

  if (input.isOwner) {
    nav.push({ label: 'Orders', to: input.path('/workshop/orders') })
    nav.push({ label: 'Cutting queue', to: input.path('/workshop/cutting') })
    nav.push({ label: 'Banding queue', to: input.path('/workshop/banding') })
    nav.push({ label: 'Branches', to: input.path('/workshop/branches') })
    nav.push({ label: 'Cutting plans', to: input.path('/workshop/cutting-plans') })
    nav.push({ label: 'Finance', to: input.path('/workshop/finance') })
    nav.push({ label: 'Users', to: input.path('/workshop/settings/users') })
    nav.push({ label: 'Profile', to: input.path('/workshop/profile') })
    return nav
  }

  const selectedBranch =
    input.branches.find((branch) => branch.id === input.selectedBranchId) ?? input.branches[0]
  if (!selectedBranch) {
    nav.push({ label: 'Profile', to: input.path('/workshop/profile') })
    return nav
  }

  nav.push({
    label: 'Branch workspace',
    to: input.path(`/workshop/branches/${selectedBranch.id}`),
  })
  if (hasAny(selectedBranch, ['view_dashboard', 'manage_orders'])) {
    nav.push({ label: 'Orders', to: input.path('/workshop/orders') })
  }
  if (hasAny(selectedBranch, ['process_production'])) {
    nav.push({ label: 'Cutting queue', to: input.path('/workshop/cutting') })
    nav.push({ label: 'Banding queue', to: input.path('/workshop/banding') })
    nav.push({ label: 'Cutting plans', to: input.path('/workshop/cutting-plans') })
  }
  if (hasAny(selectedBranch, ['manage_finance', 'view_finance_reports'])) {
    nav.push({ label: 'Finance', to: input.path('/workshop/finance') })
  }
  nav.push({ label: 'Profile', to: input.path('/workshop/profile') })
  return nav
}
