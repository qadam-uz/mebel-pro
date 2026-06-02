import type { RoleKey } from '@/shared/app/roleConfig'

export const i18nSeed: Record<RoleKey, { appName: string; ready: string; error: string }> = {
  client: {
    appName: 'Client',
    ready: 'Ready',
    error: 'Error',
  },
  workshop: {
    appName: 'Workshop',
    ready: 'Ready',
    error: 'Error',
  },
  admin: {
    appName: 'Superadmin',
    ready: 'Ready',
    error: 'Error',
  },
}
