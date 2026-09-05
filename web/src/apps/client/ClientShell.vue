<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { useRoleConfig } from '@/shared/app/roleConfig'
import { iconPath, isChromelessLayout } from '@/shared/app/shellChrome'
import BrandMark from '@/shared/components/BrandMark.vue'
import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import NotificationsMenu from '@/shared/components/NotificationsMenu.vue'
import ToastHost from '@/shared/components/ToastHost.vue'
import { useAuthStore } from '@/shared/stores/auth'

// The client chrome is a header and a page column — no sidebar, no drawer, no
// branch context. Nothing workshop- or platform-shaped may be imported here:
// this file is what the client SPA's entry chunk carries.
const config = useRoleConfig()
const auth = useAuthStore()
const route = useRoute()
const { t } = useI18n()

const isChromeless = computed(() => isChromelessLayout(route.meta.layout))
const clientInitial = computed(() =>
  (auth.displayName.trim().slice(0, 1) || auth.me?.phone?.slice(-1) || 'M').toUpperCase(),
)
</script>

<template>
  <div v-if="isChromeless" class="min-h-[var(--app-vh)] bg-bg text-ink">
    <RouterView />
  </div>

  <div v-else class="min-h-[var(--app-vh)] bg-bg text-ink">
    <header class="client-header">
      <div class="client-container client-header-row">
        <RouterLink
          :to="config.homePath"
          class="client-brand"
          :aria-label="$t('shell.a11y.clientHome')"
        >
          <BrandMark :size="32" />
          <span class="client-brand-name">{{ config.productLabel }}</span>
        </RouterLink>

        <nav class="client-nav" :aria-label="$t('shell.a11y.mainNav')">
          <RouterLink v-for="item in config.nav" :key="item.to" :to="item.to">
            <span class="client-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
            </span>
            {{ t(item.labelKey) }}
          </RouterLink>
        </nav>

        <div class="client-actions">
          <LocaleSwitcher />
          <NotificationsMenu />
          <RouterLink
            :to="config.profilePath"
            class="client-user-pill"
            :aria-label="$t('shell.a11y.clientProfile', { name: auth.displayName })"
          >
            <span class="client-user-avatar" aria-hidden="true">{{ clientInitial }}</span>
            <span class="client-user-name text-sm font-bold text-ink">{{ auth.displayName }}</span>
          </RouterLink>
        </div>
      </div>
    </header>

    <main class="client-container client-page">
      <RouterView />
    </main>
  </div>

  <ToastHost />
</template>
