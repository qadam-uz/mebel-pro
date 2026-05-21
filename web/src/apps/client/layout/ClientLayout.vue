<script setup lang="ts">
// Client app shell — sticky header (.hdr) with brand, nav, the notification
// bell and a user button. Mobile-first; the design system handles the
// responsive nav reflow. Mirrors the prototype's client-shell.js header.
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { NotificationBell, ToastHost } from '@/shared/ui'
import { initialsOf } from '@/shared/format'
import { t } from '@/shared/i18n'
import { useClientAuth } from '../store'

const auth = useClientAuth()
const router = useRouter()

const meName = computed(() => auth.me?.first_name ?? auth.me?.full_name ?? '—')
const meInitials = computed(() => initialsOf(auth.me?.first_name ?? auth.me?.full_name))

const NAV = [
  { to: '/', label: t('nav.home') },
  { to: '/c/cutting/drafts', label: t('nav.drafts') },
  { to: '/c/orders', label: t('nav.orders') },
  { to: '/c/branches', label: t('nav.branches') },
]

async function onSignOut() {
  await auth.logout()
  router.push('/auth/telegram')
}
</script>

<template>
  <div>
    <header class="hdr">
      <div class="container hdr-row">
        <RouterLink class="brand" to="/" aria-label="Bosh sahifa">
          <span class="mk">M</span><span class="nm">{{ t('common.appName') }}</span>
        </RouterLink>
        <nav class="hdr-nav" aria-label="Asosiy navigatsiya">
          <RouterLink
            v-for="item in NAV"
            :key="item.to"
            :to="item.to"
            active-class="on"
            :exact-active-class="item.to === '/' ? 'on' : undefined"
          >
            {{ item.label }}
          </RouterLink>
        </nav>
        <div class="hdr-actions">
          <NotificationBell variant="client" all-route="/c/notifications" />
          <RouterLink class="user-btn" to="/c/profile">
            <span class="av">{{ meInitials }}</span>
            <span class="nm">{{ meName }}</span>
          </RouterLink>
          <button class="btn btn-ghost btn-sm" type="button" @click="onSignOut">
            {{ t('auth.signOut') }}
          </button>
        </div>
      </div>
    </header>

    <main class="container" style="padding: 24px 0 48px">
      <RouterView />
    </main>

    <ToastHost />
  </div>
</template>
