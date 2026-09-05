import type { InjectionKey } from 'vue'
import { inject } from 'vue'

export type RoleKey = 'client' | 'workshop' | 'admin'

/** Sidebar sections are grouped by this id, never by their rendered label.
 *  `groupedNav` used to key on the display string, so translating "Moliya"
 *  would have silently split or merged sections per locale. */
export type NavGroupId =
  | 'management'
  | 'production'
  | 'resources'
  | 'finance'
  | 'system'
  | 'platform'
  | 'catalog'
  | 'admin'

export interface NavItem {
  /** Catalog key under `nav.item`, resolved where the item is rendered — a
   *  label baked in here would freeze at whatever locale was active when this
   *  module was first evaluated. */
  labelKey: string
  to: string
  group?: NavGroupId
  icon?: string
}

export interface DropdownOption {
  value: string
  label: string
  // Secondary line + status dot — rendered by the rich dropdown skin only
  // (topbar, forms). Filter bars use the compact skin, which ignores both.
  meta?: string
  status?: 'active' | 'pending' | 'blocked'
  // Colored dot for the compact filter skin; set only on status filters
  // (mapped from the matching pill palette), omitted everywhere else.
  dot?: 'success' | 'warning' | 'danger' | 'info' | 'accent' | 'muted'
}

export interface RoleConfig {
  role: RoleKey
  /** The product name is a brand, not copy — it reads `Mebel Pro` in every
   *  locale, including the Cyrillic ones. */
  productLabel: string
  homePath: string
  loginPath: string
  profilePath: string
  primaryActionTo: string
  dropdownOptions: DropdownOption[]
  nav: NavItem[]
}

/** Every message the shell needs about a role, resolved from `nav.role.<role>`.
 *  Kept as a key prefix rather than a bag of strings so a new locale is a
 *  catalog edit and nothing else. */
export function roleMessageKey(role: RoleKey, name: string): string {
  return `nav.role.${role}.${name}`
}

export const roleConfigKey = Symbol('role-config') as InjectionKey<RoleConfig>

export function useRoleConfig(): RoleConfig {
  const config = inject(roleConfigKey)
  if (!config) {
    throw new Error('Role config was not provided')
  }
  return config
}

export const clientConfig: RoleConfig = {
  role: 'client',
  productLabel: 'Mebel Pro',
  homePath: '/c',
  loginPath: '/auth/login',
  profilePath: '/c/profile',
  primaryActionTo: '/c/cutting/drafts',
  dropdownOptions: [],
  nav: [
    { labelKey: 'nav.item.clientHome', to: '/c', icon: 'home' },
    { labelKey: 'nav.item.clientDrafts', to: '/c/cutting/drafts', icon: 'scissors' },
    { labelKey: 'nav.item.clientOrders', to: '/c/orders', icon: 'orders' },
    // Ustaxona: the client's own workshops, not a platform directory (spec §5).
    // Same label *and* same key as the phone tab — one entry point, named once.
    // This `to` is the fallback the config can state statically; ClientShell
    // re-points the item at `clientEntry.workshopPath`, which skips the
    // one-item list, so the nav and the phone's Ustaxona tab land together.
    { labelKey: 'nav.item.clientWorkshop', to: '/c/branches', icon: 'store' },
  ],
}

export const workshopConfig: RoleConfig = {
  role: 'workshop',
  productLabel: 'Mebel Pro',
  homePath: '/workshop',
  loginPath: '/auth/login',
  profilePath: '/workshop/profile',
  primaryActionTo: '/workshop/branches',
  dropdownOptions: [],
  // The live sidebar is built by `workshopNavItems`, which filters this
  // inventory by the operator's grants; this list is the unfiltered shape.
  nav: [
    { labelKey: 'nav.item.dashboard', to: '/workshop', group: 'management', icon: 'dashboard' },
    { labelKey: 'nav.item.orders', to: '/workshop/orders', group: 'management', icon: 'orders' },
    {
      labelKey: 'nav.item.cutting',
      to: '/workshop/cutting',
      group: 'production',
      icon: 'scissors',
    },
    { labelKey: 'nav.item.banding', to: '/workshop/banding', group: 'production', icon: 'layers' },
    { labelKey: 'nav.item.inventory', to: '/workshop/inventory', group: 'resources', icon: 'box' },
    { labelKey: 'nav.item.catalog', to: '/workshop/catalog', group: 'resources', icon: 'grid' },
    {
      labelKey: 'nav.item.financeExpenses',
      to: '/workshop/finance/expenses',
      group: 'finance',
      icon: 'wallet',
    },
    { labelKey: 'nav.item.branches', to: '/workshop/branches', group: 'system', icon: 'store' },
    { labelKey: 'nav.item.staff', to: '/workshop/settings/users', group: 'system', icon: 'users' },
    { labelKey: 'nav.item.settings', to: '/workshop/settings', group: 'system', icon: 'settings' },
  ],
}

export const adminConfig: RoleConfig = {
  role: 'admin',
  productLabel: 'Mebel Pro',
  homePath: '/admin',
  loginPath: '/auth/login',
  profilePath: '/admin/profile',
  primaryActionTo: '',
  dropdownOptions: [],
  nav: [
    { labelKey: 'nav.item.dashboard', to: '/admin', group: 'platform', icon: 'dashboard' },
    { labelKey: 'nav.item.workshops', to: '/admin/workshops', group: 'platform', icon: 'factory' },
    {
      labelKey: 'nav.item.manufacturers',
      to: '/admin/catalog/manufacturers',
      group: 'catalog',
      icon: 'factory',
    },
    {
      labelKey: 'nav.item.dekorlar',
      to: '/admin/catalog/decors',
      group: 'catalog',
      icon: 'package',
    },
    { labelKey: 'nav.item.jobs', to: '/admin/platform/jobs', group: 'admin', icon: 'activity' },
    { labelKey: 'nav.item.errors', to: '/admin/platform/errors', group: 'admin', icon: 'alert' },
    { labelKey: 'nav.item.audit', to: '/admin/audit', group: 'admin', icon: 'list' },
    { labelKey: 'nav.item.admins', to: '/admin/platform/users', group: 'system', icon: 'users' },
  ],
}
