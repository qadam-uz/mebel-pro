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

function item(label: string, to: string, group: string, icon: string): NavItem {
  return { label, to, group, icon }
}

export function workshopNavItems(input: WorkshopNavInput): NavItem[] {
  const nav: NavItem[] = [item('Asosiy', input.path('/workshop'), 'Boshqaruv', 'dashboard')]

  if (input.isOwner) {
    nav.push(item('Buyurtmalar', input.path('/workshop/orders'), 'Boshqaruv', 'orders'))
    nav.push(
      item('Kesish navbati', input.path('/workshop/cutting'), 'Ishlab chiqarish', 'scissors'),
    )
    nav.push(item('Krom navbati', input.path('/workshop/banding'), 'Ishlab chiqarish', 'layers'))
    nav.push(item('Ombor', input.path('/workshop/inventory'), 'Resurslar', 'box'))
    nav.push(item('Material katalogi', input.path('/workshop/catalog'), 'Resurslar', 'grid'))
    nav.push(item('Hisobotlar', input.path('/workshop/finance'), 'Moliya', 'chart'))
    nav.push(
      item('Tushum va xarajat', input.path('/workshop/finance/expenses'), 'Moliya', 'wallet'),
    )
    nav.push(item('Filiallar', input.path('/workshop/branches'), 'Tizim', 'store'))
    nav.push(item('Xodimlar', input.path('/workshop/settings/users'), 'Tizim', 'users'))
    nav.push(item('Sozlamalar', input.path('/workshop/settings'), 'Tizim', 'settings'))
    return nav
  }

  const selectedBranch =
    input.branches.find((branch) => branch.id === input.selectedBranchId) ?? input.branches[0]
  if (!selectedBranch) {
    return nav
  }

  if (hasAny(selectedBranch, ['view_dashboard', 'manage_orders'])) {
    nav.push(item('Buyurtmalar', input.path('/workshop/orders'), 'Boshqaruv', 'orders'))
  }
  if (hasAny(selectedBranch, ['process_production'])) {
    nav.push(
      item('Kesish navbati', input.path('/workshop/cutting'), 'Ishlab chiqarish', 'scissors'),
    )
    nav.push(item('Krom navbati', input.path('/workshop/banding'), 'Ishlab chiqarish', 'layers'))
  }
  if (hasAny(selectedBranch, ['manage_inventory'])) {
    nav.push(item('Ombor', input.path('/workshop/inventory'), 'Resurslar', 'box'))
  }
  if (hasAny(selectedBranch, ['manage_catalog'])) {
    nav.push(item('Material katalogi', input.path('/workshop/catalog'), 'Resurslar', 'grid'))
  }
  if (hasAny(selectedBranch, ['manage_finance', 'view_finance_reports'])) {
    nav.push(item('Hisobotlar', input.path('/workshop/finance'), 'Moliya', 'chart'))
    nav.push(
      item('Tushum va xarajat', input.path('/workshop/finance/expenses'), 'Moliya', 'wallet'),
    )
  }
  return nav
}
