import { createAuthStore } from '@/shared/stores/auth'

export const useWorkshopAuth = createAuthStore({ app: 'workshop' })
