import { createRouter, createWebHistory } from 'vue-router'
import { installAuthGuard } from '@/shared/guards'
import ClientLayout from './layout/ClientLayout.vue'
import HomeView from './views/HomeView.vue'
import { useClientAuth } from './store'

const router = createRouter({
  history: createWebHistory('/client.html'),
  routes: [
    {
      path: '/auth/telegram',
      name: 'telegram-login',
      component: () => import('./views/TelegramLoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: ClientLayout,
      children: [
        { path: '', name: 'home', component: HomeView },
        {
          path: 'c/cutting/drafts',
          name: 'cutting-drafts',
          component: () => import('./views/DraftsView.vue'),
        },
        {
          path: 'c/cutting/:id',
          name: 'cutting',
          component: () => import('./views/CuttingView.vue'),
        },
        {
          path: 'c/orders/new/:draftId',
          name: 'order-new',
          component: () => import('./views/OrderNewView.vue'),
        },
        { path: 'c/orders', name: 'orders', component: () => import('./views/OrdersView.vue') },
        {
          path: 'c/orders/:id',
          name: 'order-detail',
          component: () => import('./views/OrderDetailView.vue'),
        },
        {
          path: 'c/branches',
          name: 'branches',
          component: () => import('./views/BranchesView.vue'),
        },
        { path: 'c/profile', name: 'profile', component: () => import('./views/ProfileView.vue') },
        {
          path: 'c/notifications',
          name: 'notifications',
          component: () => import('./views/NotificationsView.vue'),
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/shared/ui/NotFoundView.vue'),
    },
  ],
})

installAuthGuard(router, {
  loginRoute: '/auth/telegram',
  homeRoute: '/',
  useAuth: () => useClientAuth(),
})

export default router
