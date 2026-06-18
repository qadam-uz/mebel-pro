import type { InjectionKey } from 'vue'
import { inject } from 'vue'

export type RoleKey = 'client' | 'workshop' | 'admin'
export type ShellStateKind = 'loading' | 'empty' | 'error' | 'ready'

export interface NavItem {
  label: string
  to: string
  group?: string
  icon?: string
}

export interface DropdownOption {
  value: string
  label: string
  meta: string
  status: 'active' | 'pending' | 'blocked'
}

export interface ShellState {
  kind: ShellStateKind
  label: string
  detail: string
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
  states: ShellState[]
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
    { label: 'Profil', to: '/c/profile', icon: 'users' },
  ],
  states: [
    { kind: 'loading', label: 'Loading client workspace', detail: 'Backend status is checked.' },
    {
      kind: 'empty',
      label: 'No drafts yet',
      detail: 'Saved cutting drafts appear here.',
    },
    { kind: 'error', label: 'API error', detail: 'Trace ID is shown when readiness fails.' },
    { kind: 'ready', label: 'Ready', detail: 'Workspace navigation is available.' },
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
      label: 'Kesish navbati',
      to: '/workshop/cutting',
      group: 'Ishlab chiqarish',
      icon: 'scissors',
    },
    { label: 'Krom navbati', to: '/workshop/banding', group: 'Ishlab chiqarish', icon: 'layers' },
    { label: 'Ombor', to: '/workshop/inventory', group: 'Resurslar', icon: 'box' },
    { label: 'Material katalogi', to: '/workshop/catalog', group: 'Resurslar', icon: 'grid' },
    { label: 'Hisobotlar', to: '/workshop/finance', group: 'Moliya', icon: 'chart' },
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
  states: [
    { kind: 'loading', label: 'Loading branch context', detail: 'Branch data is loading.' },
    {
      kind: 'empty',
      label: 'No accessible branch',
      detail: 'Staff without branch access see this.',
    },
    { kind: 'error', label: 'API error', detail: 'Trace ID is carried into the error panel.' },
    { kind: 'ready', label: 'Ready', detail: 'Branch picker and navigation are available.' },
  ],
}

export const adminConfig: RoleConfig = {
  role: 'admin',
  productLabel: 'Mebel Pro',
  roleLabel: 'Superadmin',
  tenantLabel: 'Platforma',
  tenantMeta: "operator · O'Z",
  homePath: '/admin',
  loginPath: '/auth/login',
  profilePath: '/admin/profile',
  notFoundHomeLabel: 'Asosiyga qaytish',
  dashboardTitle: 'Platforma asosiy',
  dashboardSubtitle: "Platforma sog'ligi, insidentlar va provisioning holati.",
  primaryActionLabel: 'Yangi ustaxona',
  primaryActionTo: '/admin/workshops',
  dropdownLabel: 'Monitor',
  dropdownOptions: [
    { value: 'platform', label: "Platforma sog'ligi", meta: 'ready', status: 'active' },
    { value: 'jobs', label: 'Background ish', meta: 'failed kuzatuv', status: 'pending' },
    { value: 'errors', label: 'Xatolik monitor', meta: 'ochiq kodlar', status: 'pending' },
  ],
  nav: [
    { label: 'Asosiy', to: '/admin', group: 'Platforma', icon: 'dashboard' },
    { label: 'Ustaxonalar', to: '/admin/workshops', group: 'Platforma', icon: 'factory' },
    {
      label: 'Manufacturerlar',
      to: '/admin/catalog/manufacturers',
      group: 'Katalog',
      icon: 'factory',
    },
    { label: 'Materiallar', to: '/admin/catalog/materials', group: 'Katalog', icon: 'package' },
    {
      label: 'Background ish',
      to: '/admin/platform/jobs',
      group: 'Operatorlik',
      icon: 'activity',
    },
    {
      label: 'Xatolik monitor',
      to: '/admin/platform/errors',
      group: 'Operatorlik',
      icon: 'alert',
    },
    { label: 'Audit log', to: '/admin/audit', group: 'Operatorlik', icon: 'list' },
    { label: 'Operatorlar', to: '/admin/platform/users', group: 'Tizim', icon: 'users' },
  ],
  states: [
    { kind: 'loading', label: 'Loading platform console', detail: 'Readiness check is in flight.' },
    { kind: 'empty', label: 'No workshops yet', detail: 'Provisioned workshops appear here.' },
    { kind: 'error', label: 'API error', detail: 'Trace ID is visible for support.' },
    { kind: 'ready', label: 'Ready', detail: 'Docs and API links are available.' },
  ],
}
