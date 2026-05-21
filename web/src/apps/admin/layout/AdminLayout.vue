<script setup lang="ts">
// Superadmin app shell — sidebar (.sb-*) + top bar (.tb-*). Mirrors the
// prototype's admin-shell.js: platform nav groups, the operator notification
// bell, and a "new workshop" action.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NotificationBell, ToastHost } from '@/shared/ui'
import { initialsOf } from '@/shared/format'
import { t } from '@/shared/i18n'
import { useAdminAuth } from '../store'

const auth = useAdminAuth()
const router = useRouter()
const drawerOpen = ref(false)

interface NavItem {
  to: string
  ic: string
  label: string
}
const NAV: { label: string; items: NavItem[] }[] = [
  {
    label: t('nav.grpPlatform'),
    items: [
      { to: '/admin', ic: '◐', label: t('nav.dashboard') },
      { to: '/admin/workshops', ic: '▥', label: t('nav.workshops') },
    ],
  },
  {
    label: t('nav.grpCatalog'),
    items: [{ to: '/admin/materials', ic: '⊞', label: t('nav.materials') }],
  },
  {
    label: t('nav.grpOps'),
    items: [
      { to: '/admin/platform/jobs', ic: '⌥', label: t('nav.jobs') },
      { to: '/admin/platform/errors', ic: '!', label: t('nav.errors') },
      { to: '/admin/audit', ic: '≡', label: t('nav.audit') },
    ],
  },
  {
    label: t('nav.grpSystem'),
    items: [{ to: '/admin/platform/users', ic: '◆', label: t('nav.operators') }],
  },
]

const meName = computed(() => auth.me?.full_name ?? '—')
const meInitials = computed(() => initialsOf(auth.me?.full_name))

async function onSignOut() {
  await auth.logout()
  router.push('/auth/login')
}
</script>

<template>
  <div class="app">
    <aside class="sb">
      <RouterLink class="sb-brand" to="/admin">
        <span class="mk">M</span>
        <span class="nm">{{ t('common.appName') }}<small>superadmin</small></span>
      </RouterLink>
      <div class="sb-tenant">
        <span class="av" style="background: linear-gradient(135deg, #2a4d6b, #1f3a50)">PL</span>
        <div class="info">
          <div class="nm">Platforma</div>
          <div class="role">Platforma operatori</div>
        </div>
      </div>
      <nav class="sb-nav">
        <div v-for="group in NAV" :key="group.label" class="sb-grp">
          <div class="lbl">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            class="sb-it"
            :to="item.to"
            active-class="on"
          >
            <span class="ic">{{ item.ic }}</span> {{ item.label }}
          </RouterLink>
        </div>
        <div class="sb-grp">
          <div class="lbl">{{ t('nav.grpReference') }}</div>
          <a class="sb-it" href="/docs" target="_blank" rel="noopener">
            <span class="ic">¶</span> {{ t('nav.docs') }} <span class="ct">↗</span>
          </a>
        </div>
      </nav>
      <div class="sb-foot">
        <RouterLink class="sb-user" to="/admin/profile">
          <span class="av">{{ meInitials }}</span>
          <div class="info">
            <div class="nm">{{ meName }}</div>
            <div class="rl">Platforma operatori</div>
          </div>
        </RouterLink>
      </div>
    </aside>

    <main class="shell-main">
      <div class="tb">
        <button
          class="mobile-nav-btn"
          type="button"
          aria-label="Menu"
          @click="drawerOpen = !drawerOpen"
        >
          ☰ Menu
        </button>
        <div class="tb-search">
          <svg
            width="14"
            height="14"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          >
            <circle cx="7" cy="7" r="5" />
            <path d="m11 11 3 3" />
          </svg>
          <input :placeholder="t('common.search') + '...'" />
          <span class="kbd">⌘ K</span>
        </div>
        <div class="tb-actions">
          <NotificationBell variant="app" all-route="/admin/notifications" />
          <button class="btn btn-ghost btn-sm" type="button" @click="onSignOut">
            {{ t('auth.signOut') }}
          </button>
        </div>
      </div>

      <div class="page">
        <RouterView />
      </div>
    </main>

    <ToastHost />
  </div>
</template>
