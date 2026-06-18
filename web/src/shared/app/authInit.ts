import { useAuthStore } from '@/shared/stores/auth'

// Single source of truth for injecting the access token into API calls (CB-97).
// Reads the token at call time (not at import) so a silent refresh (CB-08) is
// always picked up. Replaces a per-store `function authInit()` copy in every
// non-auth store; the auth store keeps its own to avoid importing itself.
export function authInit() {
  return { accessToken: useAuthStore().accessToken }
}
