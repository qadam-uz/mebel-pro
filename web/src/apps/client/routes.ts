import type { RouteRecordRaw } from 'vue-router'

export const clientRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/c',
  },
  {
    path: '/auth/login',
    name: 'client-login',
    component: () => import('@/apps/client/views/ClientLoginView.vue'),
    meta: { layout: 'auth', titleKey: 'routes.login' },
  },
  // The workshop link a QR opens. `meta.public` is what keeps the auth guard
  // off it: `layout: 'auth'` alone would bounce an already-signed-in client to
  // home, which is exactly the fast path this route has to own (spec §3.1).
  // The two-segment form is the branch QR (`/w/{code}/{branch_no}`); it must
  // precede nothing else, since `/w` has no other shapes.
  {
    path: '/w/:code',
    name: 'client-entry',
    component: () => import('@/apps/client/views/ClientEntryView.vue'),
    meta: { layout: 'auth', public: true, titleKey: 'routes.entry' },
  },
  {
    path: '/w/:code/:branchNo',
    name: 'client-entry-branch',
    component: () => import('@/apps/client/views/ClientEntryView.vue'),
    meta: { layout: 'auth', public: true, titleKey: 'routes.entry' },
  },
  {
    path: '/c',
    name: 'client-home',
    component: () => import('@/apps/client/views/ClientHomeView.vue'),
    meta: { titleKey: 'routes.clientHome' },
  },
  {
    path: '/c/profile',
    name: 'client-profile',
    component: () => import('@/apps/client/views/ClientProfileView.vue'),
    meta: { titleKey: 'routes.profile' },
  },
  {
    path: '/c/orders',
    name: 'client-orders',
    component: () => import('@/apps/client/views/ClientOrdersView.vue'),
    meta: { titleKey: 'routes.orders' },
  },
  {
    path: '/c/orders/new/:draft_id',
    name: 'client-order-new',
    component: () => import('@/apps/client/views/ClientOrderNewView.vue'),
    meta: { titleKey: 'routes.placeOrder', chromeless: true },
  },
  {
    path: '/c/orders/:order_id',
    name: 'client-order-detail',
    component: () => import('@/apps/client/views/ClientOrderDetailView.vue'),
    meta: { titleKey: 'routes.orderDetail' },
  },
  {
    path: '/c/cutting/drafts',
    name: 'client-cutting-drafts',
    component: () => import('@/shared/views/DraftsView.vue'),
    meta: { titleKey: 'routes.clientDrafts' },
  },
  {
    // New-editor entry; the first complete detail creates and autosaves the draft.
    // Must precede the `:id` route so "new" isn't matched as a draft id.
    path: '/c/cutting/new',
    name: 'client-cutting-new',
    component: () => import('@/shared/views/CuttingEditorView.vue'),
    meta: { titleKey: 'routes.newDraft', chromeless: true },
    // A drawing only ever starts from a workshop (spec §2.2): the pin, or the
    // branch whose «Yangi chizma» was tapped. Without a pin the editor has no
    // branch and no way to ask for one, so the URL is answered by Ustaxonalarim
    // instead — the guard runs before any editor screen renders.
    beforeEnter: async () => {
      const [{ useAuthStore }, { isClientPinned }] = await Promise.all([
        import('@/shared/stores/auth'),
        import('@/shared/app/clientUi'),
      ])
      const auth = useAuthStore()
      // `auth.restore()` has already run in the global guard, so `me` is in
      // hand; a principal that somehow is not lets the editor decide.
      if (auth.me && !isClientPinned(auth.me)) return '/c/branches'
      return true
    },
  },
  {
    path: '/c/cutting/:id',
    name: 'client-cutting-editor',
    component: () => import('@/shared/views/CuttingEditorView.vue'),
    meta: { titleKey: 'routes.draft', chromeless: true },
  },
  {
    path: '/c/cutting/:id/result',
    name: 'client-cutting-result',
    component: () => import('@/shared/views/CuttingResultView.vue'),
    meta: { titleKey: 'routes.cuttingResult', chromeless: true },
  },
  {
    // Ustaxonalarim — the client's own workshops (spec §5). The route name and
    // path stay; the platform-wide directory that used to live here is gone.
    path: '/c/branches',
    name: 'client-branches',
    component: () => import('@/apps/client/views/ClientBranchesView.vue'),
    meta: { titleKey: 'routes.workshops' },
  },
  {
    // A related workshop's own profile — its branches, their contacts, the pin
    // star and the two per-branch actions (spec §6.1). "Related" is what
    // `/client/my-workshops` returns; anything else renders not-found.
    path: '/c/workshops/:workshopId',
    name: 'client-workshop',
    component: () => import('@/apps/client/views/ClientWorkshopView.vue'),
    meta: { titleKey: 'routes.workshop' },
  },
  {
    // Read-only price list of one branch (spec §6.2). No add-to-draft, no
    // drawing CTA — that lives one tap back on the profile.
    path: '/c/workshops/:workshopId/catalog',
    name: 'client-workshop-catalog',
    component: () => import('@/apps/client/views/ClientWorkshopCatalogView.vue'),
    meta: { titleKey: 'routes.catalog' },
  },
  {
    path: '/c/notifications',
    name: 'client-notifications',
    component: () => import('@/apps/client/views/ClientNotificationsView.vue'),
    meta: { titleKey: 'routes.notifications' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'client-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
    meta: { titleKey: 'routes.notFound' },
  },
]
