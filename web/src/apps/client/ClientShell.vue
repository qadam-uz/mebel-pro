<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { iconPath, isChromelessRoute } from '@/shared/app/shellChrome'
import BrandMark from '@/shared/components/BrandMark.vue'
import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import NotificationsMenu from '@/shared/components/NotificationsMenu.vue'
import ToastHost from '@/shared/components/ToastHost.vue'
import { useAuthStore } from '@/shared/stores/auth'
import { useClientEntryStore } from '@/shared/stores/clientEntry'

// The client chrome is a header and a page column — no sidebar, no drawer, no
// branch context. Nothing workshop- or platform-shaped may be imported here:
// this file is what the client SPA's entry chunk carries.
//
// Two modes, switched at the `md` utility breakpoint (spec §2). Above it the
// header is unchanged: brand, nav, locale, bell, user pill. Below it the header
// collapses to one 56px row that names the page, and navigation moves to a
// fixed bottom tab bar. One markup tree carries both — a second header would
// mount a second NotificationsMenu and double its polling.
const config = useRoleConfig()
const auth = useAuthStore()
const entry = useClientEntryStore()
const route = useRoute()
const rolePath = useRolePath()
const { t } = useI18n()

const isChromeless = computed(() => isChromelessRoute(route.meta))
const clientInitial = computed(() =>
  (auth.displayName.trim().slice(0, 1) || auth.me?.phone?.slice(-1) || 'M').toUpperCase(),
)

/** The phone header's one title. Pages drop their own H1 of the same words. */
const pageTitle = computed(() => {
  const key = route.meta.titleKey
  return typeof key === 'string' ? t(key) : config.productLabel
})

/**
 * The "Ustaxona" tab (§2, UX review 2026-09-05).
 *
 * One related workshop is the common case, and a one-item list is a hop with
 * nothing to choose — so the tab goes straight to that workshop's profile.
 * Two or more, or nothing loaded yet, and it opens Ustaxonalarim.
 */
const workshopTabTo = computed(() => {
  const only = entry.workshops.length === 1 ? entry.workshops[0] : null
  return only ? `/c/workshops/${only.workshop_id}` : '/c/branches'
})

interface ClientTab {
  labelKey: string
  icon: string
  to: string
  /** Path prefixes this tab owns. `/c` is a prefix of every client route, so
   *  `router-link-active` cannot be trusted to mark the home tab. */
  owns: string[]
  exact?: boolean
}

const tabs = computed<ClientTab[]>(() => [
  { labelKey: 'nav.item.clientHome', icon: 'home', to: '/c', owns: ['/c'], exact: true },
  {
    labelKey: 'nav.item.clientDrafts',
    icon: 'scissors',
    to: '/c/cutting/drafts',
    owns: ['/c/cutting'],
  },
  { labelKey: 'nav.item.clientOrders', icon: 'orders', to: '/c/orders', owns: ['/c/orders'] },
  {
    labelKey: 'nav.item.clientWorkshop',
    icon: 'store',
    to: workshopTabTo.value,
    owns: ['/c/branches', '/c/workshops'],
  },
  {
    labelKey: 'nav.item.clientProfile',
    icon: 'user',
    to: '/c/profile',
    owns: ['/c/profile', '/c/notifications'],
  },
])

function isCurrentTab(tab: ClientTab): boolean {
  return tab.owns.some((owned) => {
    const base = rolePath(owned)
    if (tab.exact) return route.path === base || route.path === `${base}/`
    return route.path === base || route.path.startsWith(`${base}/`)
  })
}

// Loaded once, for the tab's destination. Signed-out chromeless routes (the
// entry landing, login) must not fire an authenticated request.
function primeWorkshops() {
  if (isChromeless.value || !auth.isAllowedFor('client')) return
  void entry.ensureMyWorkshops()
}

onMounted(primeWorkshops)
watch(isChromeless, primeWorkshops)
</script>

<template>
  <div v-if="isChromeless" class="min-h-[var(--app-vh)] bg-bg text-ink">
    <RouterView />
  </div>

  <div v-else class="min-h-[var(--app-vh)] bg-bg text-ink">
    <header class="client-header">
      <div
        class="client-container grid h-14 grid-cols-[36px_minmax(0,1fr)_36px] items-center gap-2 md:flex md:h-auto md:flex-wrap md:gap-[14px] md:py-[14px]"
      >
        <RouterLink
          :to="config.homePath"
          class="client-brand justify-self-start"
          :aria-label="$t('shell.a11y.clientHome')"
        >
          <BrandMark :size="32" />
          <span class="client-brand-name hidden md:inline">{{ config.productLabel }}</span>
        </RouterLink>

        <!-- Phone: the page's one title. Below `md` no page renders an H1 of
             the same words, so this is the only place the screen is named. -->
        <h1
          class="min-w-0 truncate text-center font-display text-[15.5px] font-bold tracking-[-0.015em] text-ink md:hidden"
        >
          {{ pageTitle }}
        </h1>

        <nav class="client-nav hidden md:flex" :aria-label="$t('shell.a11y.mainNav')">
          <RouterLink v-for="item in config.nav" :key="item.to" :to="item.to">
            <span class="client-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
            </span>
            {{ t(item.labelKey) }}
          </RouterLink>
        </nav>

        <div class="client-actions justify-self-end">
          <!-- The locale switcher moves into Profil on phones (§5.3): the 56px
               row has no width for it, and it is a once-per-install choice. -->
          <LocaleSwitcher class="hidden md:block" />
          <NotificationsMenu />
          <RouterLink
            :to="config.profilePath"
            class="client-user-pill hidden md:flex"
            :aria-label="$t('shell.a11y.clientProfile', { name: auth.displayName })"
          >
            <span class="client-user-avatar" aria-hidden="true">{{ clientInitial }}</span>
            <span class="client-user-name text-sm font-bold text-ink">{{ auth.displayName }}</span>
          </RouterLink>
        </div>
      </div>
    </header>

    <!-- The bar is fixed, so the page column reserves its height plus the home
         indicator's inset — without this the last card sits under it. -->
    <main
      class="client-container client-page pb-[calc(56px+env(safe-area-inset-bottom)+16px)] md:pb-16"
    >
      <RouterView />
    </main>

    <nav
      class="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-hairline-soft bg-elevated pb-[env(safe-area-inset-bottom)] md:hidden"
      :aria-label="$t('shell.a11y.mainNav')"
    >
      <RouterLink
        v-for="tab in tabs"
        :key="tab.labelKey"
        :to="rolePath(tab.to)"
        class="flex h-14 min-w-11 flex-col items-center justify-center gap-[3px] no-underline"
        :class="isCurrentTab(tab) ? 'text-ink' : 'text-ink-muted'"
        :aria-current="isCurrentTab(tab) ? 'page' : undefined"
      >
        <span
          class="grid h-6 w-9 place-items-center rounded-lg"
          :class="isCurrentTab(tab) ? 'bg-accent-soft text-accent-strong' : ''"
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 24 24"
            width="18"
            height="18"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            v-html="iconPath(tab.icon)"
          ></svg>
        </span>
        <!-- 12.5px is DESIGN.md's type floor; nothing on the client goes under it. -->
        <span class="text-[12.5px] font-semibold leading-none">{{ t(tab.labelKey) }}</span>
      </RouterLink>
    </nav>
  </div>

  <ToastHost />
</template>
