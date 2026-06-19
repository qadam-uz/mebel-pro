import type { RouteRecordRaw } from 'vue-router'

export const clientRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/c',
  },
  {
    path: '/auth/login',
    name: 'client-login',
    component: () => import('@/shared/views/ClientLoginView.vue'),
    meta: { layout: 'auth', title: 'Kirish' },
  },
  {
    path: '/c',
    name: 'client-home',
    component: () => import('@/shared/views/ClientHomeView.vue'),
    meta: { title: 'Bosh sahifa' },
  },
  {
    path: '/c/profile',
    name: 'client-profile',
    component: () => import('@/shared/views/ClientProfileView.vue'),
    meta: { title: 'Profil' },
  },
  {
    path: '/c/orders',
    name: 'client-orders',
    component: () => import('@/shared/views/ClientOrdersView.vue'),
    meta: { title: 'Buyurtmalar' },
  },
  {
    path: '/c/orders/new/:draft_id',
    name: 'client-order-new',
    component: () => import('@/shared/views/ClientOrderNewView.vue'),
    meta: { title: 'Buyurtma berish' },
  },
  {
    path: '/c/orders/:order_id',
    name: 'client-order-detail',
    component: () => import('@/shared/views/ClientOrderDetailView.vue'),
    meta: { title: 'Buyurtma tafsilotlari' },
  },
  {
    path: '/c/cutting/drafts',
    name: 'client-cutting-drafts',
    component: () => import('@/shared/views/DraftsView.vue'),
    meta: { title: 'Kesim chizmalari' },
  },
  {
    path: '/c/cutting/:id',
    name: 'client-cutting-editor',
    component: () => import('@/shared/views/ClientCuttingEditorView.vue'),
    meta: { title: 'Kesim chizmasi' },
  },
  {
    path: '/c/branches',
    name: 'client-branches',
    component: () => import('@/shared/views/ClientBranchesView.vue'),
    meta: { title: 'Ustaxonalar' },
  },
  {
    path: '/c/notifications',
    name: 'client-notifications',
    component: () => import('@/shared/views/ClientNotificationsView.vue'),
    meta: { title: 'Bildirishnomalar' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'client-not-found',
    component: () => import('@/shared/views/RoleNotFoundView.vue'),
    meta: { title: 'Sahifa topilmadi' },
  },
]
