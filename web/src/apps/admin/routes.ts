import type { RouteRecordRaw } from 'vue-router'

export const adminRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/admin',
  },
  {
    path: '/auth/login',
    name: 'admin-login',
    component: () => import('@/shared/views/AdminLoginView.vue'),
    meta: { layout: 'auth', titleKey: 'routes.login' },
  },
  {
    path: '/admin',
    name: 'admin-home',
    component: () => import('@/shared/views/AdminDashboardView.vue'),
    meta: { titleKey: 'routes.dashboard' },
  },
  {
    path: '/admin/profile',
    name: 'admin-profile',
    component: () => import('@/shared/views/AdminProfileView.vue'),
    meta: { titleKey: 'routes.myProfile' },
  },
  {
    path: '/admin/workshops',
    name: 'admin-workshops',
    component: () => import('@/shared/views/AdminWorkshopsView.vue'),
    meta: { titleKey: 'routes.workshops' },
  },
  {
    path: '/admin/catalog',
    name: 'admin-catalog',
    redirect: '/admin/catalog/decors',
    meta: { titleKey: 'routes.catalog' },
  },
  {
    path: '/admin/catalog/manufacturers',
    name: 'admin-catalog-manufacturers',
    component: () => import('@/shared/views/AdminManufacturersView.vue'),
    meta: { titleKey: 'routes.manufacturers' },
  },
  {
    path: '/admin/catalog/decors',
    name: 'admin-catalog-decors',
    component: () => import('@/shared/views/AdminDecorsView.vue'),
    meta: { titleKey: 'routes.dekorlar' },
  },
  {
    path: '/admin/catalog/decors/:decor_id',
    name: 'admin-catalog-decor-detail',
    component: () => import('@/shared/views/AdminDecorDetailView.vue'),
    meta: { titleKey: 'routes.dekorDetail' },
  },
  // The platform `materials` table was split into decors (identity) and branch
  // materials (format); the old admin path is bookmarked and linked from older
  // docs, so it redirects rather than 404s.
  {
    path: '/admin/catalog/materials',
    redirect: '/admin/catalog/decors',
  },
  // ...and the format reshape moved the path again, from `dekorlar` to
  // `decors`, when the schema vocabulary went English. Same reason: an
  // operator's bookmark must not 404.
  {
    path: '/admin/catalog/dekorlar',
    redirect: '/admin/catalog/decors',
  },
  {
    path: '/admin/catalog/dekorlar/:decor_id',
    redirect: (to) => `/admin/catalog/decors/${to.params.decor_id}`,
  },
  {
    path: '/admin/notifications',
    name: 'admin-notifications',
    component: () => import('@/shared/views/AdminNotificationsView.vue'),
    meta: { titleKey: 'routes.notifications' },
  },
  {
    path: '/admin/platform/jobs',
    name: 'admin-platform-jobs',
    component: () => import('@/shared/views/AdminPlatformJobsView.vue'),
    meta: { titleKey: 'routes.jobs' },
  },
  {
    path: '/admin/platform/errors',
    name: 'admin-platform-errors',
    component: () => import('@/shared/views/AdminPlatformErrorsView.vue'),
    meta: { titleKey: 'routes.errorMonitor' },
  },
  {
    path: '/admin/platform/users',
    name: 'admin-platform-users',
    component: () => import('@/shared/views/AdminPlatformUsersView.vue'),
    meta: { titleKey: 'routes.admins' },
  },
  {
    path: '/admin/audit',
    name: 'admin-audit',
    component: () => import('@/shared/views/AdminAuditView.vue'),
    meta: { titleKey: 'routes.audit' },
  },
  {
    path: '/admin/workshops/:workshop_id',
    name: 'admin-workshop-detail',
    component: () => import('@/shared/views/AdminWorkshopDetailView.vue'),
    meta: { titleKey: 'routes.workshopDetail' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'admin-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
    meta: { titleKey: 'routes.notFound' },
  },
]
