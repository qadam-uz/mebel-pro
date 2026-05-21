import { createAuthStore } from '@/shared/stores/auth'

export const useClientAuth = createAuthStore({ app: 'client' })
