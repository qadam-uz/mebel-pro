import type { InjectionKey } from 'vue'
import { inject } from 'vue'

export type RoleKey = 'client' | 'workshop' | 'admin'
export type ShellStateKind = 'loading' | 'empty' | 'error' | 'ready'

export interface NavItem {
  label: string
  to: string
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
  roleLabel: 'Client',
  tenantLabel: 'Client workspace',
  tenantMeta: 'phone sign-in',
  homePath: '/c',
  loginPath: '/auth/login',
  profilePath: '/c/profile',
  notFoundHomeLabel: 'Go to client home',
  dashboardTitle: 'Client workspace',
  dashboardSubtitle: 'Cutting drafts, profile, and order entry points for clients.',
  primaryActionLabel: 'Open drafts',
  primaryActionTo: '/c/cutting/drafts',
  dropdownLabel: 'Cutting context',
  dropdownOptions: [
    { value: 'drafts', label: 'Drafts', meta: 'first-run empty', status: 'active' },
    { value: 'orders', label: 'Orders', meta: 'no active orders', status: 'pending' },
  ],
  nav: [
    { label: 'Home', to: '/c' },
    { label: 'Cutting drafts', to: '/c/cutting/drafts' },
    { label: 'Profile', to: '/c/profile' },
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
  roleLabel: 'Workshop',
  tenantLabel: 'Demo Workshop',
  tenantMeta: 'owner and staff',
  homePath: '/workshop',
  loginPath: '/auth/login',
  profilePath: '/workshop/profile',
  notFoundHomeLabel: 'Go to workshop home',
  dashboardTitle: 'Workshop dashboard',
  dashboardSubtitle: 'Branch context, access states, and production entry points for operators.',
  primaryActionLabel: 'Manage users',
  primaryActionTo: '/workshop/settings/users',
  dropdownLabel: 'Branch',
  dropdownOptions: [
    { value: 'yunusobod', label: 'Yunusobod', meta: 'open branch', status: 'active' },
    { value: 'chilonzor', label: 'Chilonzor', meta: 'no access grant', status: 'pending' },
    { value: 'archived', label: 'Archived branch', meta: 'inactive', status: 'blocked' },
  ],
  nav: [
    { label: 'Dashboard', to: '/workshop' },
    { label: 'Users', to: '/workshop/settings/users' },
    { label: 'Profile', to: '/workshop/profile' },
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
  tenantLabel: 'Platform console',
  tenantMeta: 'operator',
  homePath: '/admin',
  loginPath: '/auth/login',
  profilePath: '/admin/profile',
  notFoundHomeLabel: 'Go to admin home',
  dashboardTitle: 'Platform console',
  dashboardSubtitle: 'Operations for workshops, jobs, errors, docs, and API surfaces.',
  primaryActionLabel: 'Manage workshops',
  primaryActionTo: '/admin/workshops',
  dropdownLabel: 'Monitor',
  dropdownOptions: [
    { value: 'platform', label: 'Platform health', meta: 'ready', status: 'active' },
    { value: 'jobs', label: 'Jobs', meta: 'no failed jobs', status: 'pending' },
    { value: 'errors', label: 'Errors', meta: 'no open errors', status: 'pending' },
  ],
  nav: [
    { label: 'Dashboard', to: '/admin' },
    { label: 'Workshops', to: '/admin/workshops' },
    { label: 'Profile', to: '/admin/profile' },
    { label: 'Docs', to: '/docs' },
    { label: 'API', to: '/api-docs' },
  ],
  states: [
    { kind: 'loading', label: 'Loading platform console', detail: 'Readiness check is in flight.' },
    { kind: 'empty', label: 'No workshops yet', detail: 'Provisioned workshops appear here.' },
    { kind: 'error', label: 'API error', detail: 'Trace ID is visible for support.' },
    { kind: 'ready', label: 'Ready', detail: 'Docs and API links are available.' },
  ],
}
