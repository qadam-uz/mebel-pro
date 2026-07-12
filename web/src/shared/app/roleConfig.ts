import type { InjectionKey } from 'vue'
import { inject } from 'vue'

export type RoleKey = 'client' | 'workshop' | 'admin'

export interface NavItem {
  label: string
  to: string
  group?: string
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
  productLabel: string
  roleLabel: string
  tenantLabel: string
  tenantMeta: string
  homePath: string
  loginPath: string
  profilePath: string
  notFoundHomeLabel: string
  dashboardTitle: string
  dashboardSubtitle: string
  primaryActionLabel: string
  primaryActionTo: string
  dropdownLabel: string
  dropdownOptions: DropdownOption[]
  nav: NavItem[]
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
  roleLabel: 'Mijoz',
  tenantLabel: 'Mijoz kabineti',
  tenantMeta: 'telefon orqali kirish',
  homePath: '/c',
  loginPath: '/auth/login',
  profilePath: '/c/profile',
  notFoundHomeLabel: 'Bosh sahifaga qaytish',
  dashboardTitle: 'Bosh sahifa',
  dashboardSubtitle: 'Chizmalar, buyurtmalar va ustaxonalar.',
  primaryActionLabel: 'Yangi kesim chizmasi',
  primaryActionTo: '/c/cutting/drafts',
  dropdownLabel: 'Chizma konteksti',
  dropdownOptions: [
    { value: 'drafts', label: 'Drafts', meta: 'first-run empty', status: 'active' },
    { value: 'orders', label: 'Orders', meta: 'no active orders', status: 'pending' },
  ],
  nav: [
    { label: 'Bosh sahifa', to: '/c', icon: 'home' },
    { label: 'Chizmalar', to: '/c/cutting/drafts', icon: 'scissors' },
    { label: 'Buyurtmalar', to: '/c/orders', icon: 'orders' },
    { label: 'Ustaxonalar', to: '/c/branches', icon: 'store' },
  ],
}

export const workshopConfig: RoleConfig = {
  role: 'workshop',
  productLabel: 'Mebel Pro',
  roleLabel: 'Boshqaruv',
  tenantLabel: 'Ustaxona kabineti',
  tenantMeta: 'filial ruxsatlari',
  homePath: '/workshop',
  loginPath: '/auth/login',
  profilePath: '/workshop/profile',
  notFoundHomeLabel: 'Asosiyga qaytish',
  dashboardTitle: 'Asosiy',
  dashboardSubtitle: 'Buyurtmalar, ishlab chiqarish, ombor va moliya holati.',
  primaryActionLabel: 'Filiallar',
  primaryActionTo: '/workshop/branches',
  dropdownLabel: 'Filial',
  dropdownOptions: [
    { value: 'yunusobod', label: 'Yunusobod', meta: 'open branch', status: 'active' },
    { value: 'chilonzor', label: 'Chilonzor', meta: 'no access grant', status: 'pending' },
    { value: 'archived', label: 'Archived branch', meta: 'inactive', status: 'blocked' },
  ],
  nav: [
    { label: 'Asosiy', to: '/workshop', group: 'Boshqaruv', icon: 'dashboard' },
    { label: 'Buyurtmalar', to: '/workshop/orders', group: 'Boshqaruv', icon: 'orders' },
    {
      label: 'Ishlarim',
      to: '/workshop/production',
      group: 'Ishlab chiqarish',
      icon: 'scissors',
    },
    { label: 'Ombor', to: '/workshop/inventory', group: 'Resurslar', icon: 'box' },
    { label: 'Material katalogi', to: '/workshop/catalog', group: 'Resurslar', icon: 'grid' },
    {
      label: 'Tushum va xarajat',
      to: '/workshop/finance/expenses',
      group: 'Moliya',
      icon: 'wallet',
    },
    { label: 'Filiallar', to: '/workshop/branches', group: 'Tizim', icon: 'store' },
    { label: 'Xodimlar', to: '/workshop/settings/users', group: 'Tizim', icon: 'users' },
    { label: 'Sozlamalar', to: '/workshop/settings', group: 'Tizim', icon: 'settings' },
  ],
}

export const adminConfig: RoleConfig = {
  role: 'admin',
  productLabel: 'Mebel Pro',
  roleLabel: 'Superadmin',
  tenantLabel: 'Platforma',
  tenantMeta: "admin · O'Z",
  homePath: '/admin',
  loginPath: '/auth/login',
  profilePath: '/admin/profile',
  notFoundHomeLabel: 'Asosiyga qaytish',
  dashboardTitle: 'Asosiy',
  dashboardSubtitle: "Platforma sog'ligi, insidentlar va ustaxona yaratish holati.",
  primaryActionLabel: '',
  primaryActionTo: '',
  dropdownLabel: 'Monitor',
  dropdownOptions: [
    { value: 'platform', label: "Platforma sog'ligi", meta: 'ready', status: 'active' },
    { value: 'jobs', label: 'Fon vazifalar', meta: 'muvaffaqiyatsiz kuzatuvi', status: 'pending' },
    { value: 'errors', label: 'Xatolik monitor', meta: 'ochiq kodlar', status: 'pending' },
  ],
  nav: [
    { label: 'Asosiy', to: '/admin', group: 'Platforma', icon: 'dashboard' },
    { label: 'Ustaxonalar', to: '/admin/workshops', group: 'Platforma', icon: 'factory' },
    {
      label: 'Ishlab chiqaruvchilar',
      to: '/admin/catalog/manufacturers',
      group: 'Katalog',
      icon: 'factory',
    },
    { label: 'Materiallar', to: '/admin/catalog/materials', group: 'Katalog', icon: 'package' },
    {
      label: 'Fon vazifalar',
      to: '/admin/platform/jobs',
      group: 'Admin',
      icon: 'activity',
    },
    {
      label: 'Xatolik monitor',
      to: '/admin/platform/errors',
      group: 'Admin',
      icon: 'alert',
    },
    { label: 'Audit log', to: '/admin/audit', group: 'Admin', icon: 'list' },
    { label: 'Adminlar', to: '/admin/platform/users', group: 'Tizim', icon: 'users' },
  ],
}
