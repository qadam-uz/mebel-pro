import { createAuthStore } from '@/shared/stores/auth'

export const useAdminAuth = createAuthStore({ app: 'admin' })
