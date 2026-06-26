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
    meta: { layout: 'auth', title: 'Kirish' },
  },
  {
    path: '/admin',
    name: 'admin-home',
    component: () => import('@/shared/views/AdminDashboardView.vue'),
    meta: { title: 'Asosiy' },
  },
  {
    path: '/admin/profile',
    name: 'admin-profile',
    component: () => import('@/shared/views/AdminProfileView.vue'),
    meta: { title: 'Mening profilim' },
  },
  {
    path: '/admin/workshops',
    name: 'admin-workshops',
    component: () => import('@/shared/views/AdminWorkshopsView.vue'),
    meta: { title: 'Ustaxonalar' },
  },
  {
    path: '/admin/catalog',
    name: 'admin-catalog',
    redirect: '/admin/catalog/materials',
    meta: { title: 'Katalog' },
  },
  {
    path: '/admin/catalog/manufacturers',
    name: 'admin-catalog-manufacturers',
    component: () => import('@/shared/views/AdminManufacturersView.vue'),
    meta: { title: 'Ishlab chiqaruvchilar' },
  },
  {
    path: '/admin/catalog/materials',
    name: 'admin-catalog-materials',
    component: () => import('@/shared/views/AdminMaterialsView.vue'),
    meta: { title: 'Materiallar' },
  },
  {
    path: '/admin/notifications',
    name: 'admin-notifications',
    component: () => import('@/shared/views/AdminNotificationsView.vue'),
    meta: { title: 'Bildirishnomalar' },
  },
  {
    path: '/admin/platform/jobs',
    name: 'admin-platform-jobs',
    component: () => import('@/shared/views/AdminPlatformJobsView.vue'),
    meta: { title: 'Fon vazifalar' },
  },
  {
    path: '/admin/platform/errors',
    name: 'admin-platform-errors',
    component: () => import('@/shared/views/AdminPlatformErrorsView.vue'),
    meta: { title: 'Xatolik monitor' },
  },
  {
    path: '/admin/platform/users',
    name: 'admin-platform-users',
    component: () => import('@/shared/views/AdminPlatformUsersView.vue'),
    meta: { title: 'Adminlar' },
  },
  {
    path: '/admin/audit',
    name: 'admin-audit',
    component: () => import('@/shared/views/AdminAuditView.vue'),
    meta: { title: 'Audit log' },
  },
  {
    path: '/admin/workshops/:workshop_id',
    name: 'admin-workshop-detail',
    component: () => import('@/shared/views/AdminWorkshopDetailView.vue'),
    meta: { title: 'Ustaxona tafsilotlari' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'admin-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
    meta: { title: 'Sahifa topilmadi' },
  },
]
