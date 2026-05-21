// Router guard factory shared by the three apps. Wires a per-app auth store
// into vue-router beforeEach:
//   - public routes (meta.public) pass through;
//   - unauthenticated → the app's login route;
//   - force_password_change → the app's change-password route (and nowhere
//     else until resolved);
//   - meta.ownerOnly routes (workshop) → home unless the principal is owner.

import type { Router, RouteLocationNormalized } from 'vue-router'

interface AuthLike {
  isAuthenticated: boolean
  forcePasswordChange: boolean
  isOwner: boolean
  ensureLoaded: () => Promise<void>
}

export interface GuardConfig {
  loginRoute: string
  changePasswordRoute?: string
  homeRoute: string
  // Returns the (already-instantiated) auth store for the current pinia.
  useAuth: () => AuthLike
}

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    ownerOnly?: boolean
  }
}

export function installAuthGuard(router: Router, config: GuardConfig): void {
  router.beforeEach(async (to: RouteLocationNormalized) => {
    const auth = config.useAuth()
    await auth.ensureLoaded()

    if (to.meta.public) {
      // Already signed in? Bounce off the login screen to home.
      if (auth.isAuthenticated && to.path === config.loginRoute) return config.homeRoute
      return true
    }

    if (!auth.isAuthenticated) {
      return { path: config.loginRoute, query: { redirect: to.fullPath } }
    }

    if (auth.forcePasswordChange && config.changePasswordRoute) {
      if (to.path !== config.changePasswordRoute) return config.changePasswordRoute
      return true
    }

    if (to.meta.ownerOnly && !auth.isOwner) {
      return config.homeRoute
    }

    return true
  })
}
