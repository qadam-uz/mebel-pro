<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { adminInitials, adminNavMetrics, iconPath } from '@/shared/app/adminUi'
import { roleMessageKey, useRoleConfig } from '@/shared/app/roleConfig'
import { groupedNav, isChromelessLayout } from '@/shared/app/shellChrome'
import BrandMark from '@/shared/components/BrandMark.vue'
import NotificationsMenu from '@/shared/components/NotificationsMenu.vue'
import ToastHost from '@/shared/components/ToastHost.vue'
import { useMobileNav } from '@/shared/composables/useMobileNav'
import { useAdminStore } from '@/shared/stores/admin'
import { useAuthStore } from '@/shared/stores/auth'

const config = useRoleConfig()
const auth = useAuthStore()
const admin = useAdminStore()
const route = useRoute()
const { t } = useI18n()

/** Shorthand for the role-scoped messages the shell reads a dozen times. */
const roleText = (name: string) => t(roleMessageKey(config.role, name))

const docsMenuOpen = ref(false)
const {
  mobileNavOpen,
  mobileTriggerRef,
  drawerPanelRef,
  openMobileNav,
  closeMobileNav,
  onDrawerKeydown,
} = useMobileNav()

const isChromeless = computed(() => isChromelessLayout(route.meta.layout))
const tenantLabel = computed(() => roleText('tenant'))
const adminOperatorInitials = computed(() => adminInitials(auth.displayName, 'N'))
const navGroups = computed(() => groupedNav(config.nav))
const adminMetrics = computed(() =>
  adminNavMetrics({
    workshops: admin.workshops.length,
    manufacturers: admin.manufacturers.length,
    decors: admin.decors.length,
    failedJobs: admin.jobs.filter((job) => job.definition.last_result === 'failed').length,
    openErrors: admin.errors.filter((error) => error.status === 'open').length,
    operators: admin.platformUsers.filter((user) => user.status === 'active').length,
  }),
)
const adminDocsLinks = [
  { label: 'Docs', href: '/docs' },
  { label: 'API docs', href: '/api-docs' },
  { label: 'ReDoc', href: '/api-redoc' },
]
// Password-reset gate (access-management.md): a fresh operator is pinned to the
// profile until they change their temp password. Surface it loudly and lock the
// nav so clicks don't silently bounce.
const passwordResetRequired = computed(() => auth.me?.password_reset_required === true)

function onAdminNavClick(event: MouseEvent) {
  if (passwordResetRequired.value) {
    event.preventDefault()
    event.stopPropagation()
    return
  }
  closeMobileNav()
}

watch(
  () => route.fullPath,
  () => {
    closeMobileNav()
    docsMenuOpen.value = false
  },
)
</script>

<template>
  <div v-if="isChromeless" class="min-h-[var(--app-vh)] bg-bg text-ink">
    <RouterView />
  </div>

  <div v-else class="admin-app">
    <a class="admin-skip-link" href="#admin-content">{{ $t('shell.admin.skipLink') }}</a>
    <aside class="admin-sidebar" :aria-label="$t('shell.a11y.platformNav')">
      <RouterLink :to="config.homePath" class="admin-brand" @click="closeMobileNav">
        <BrandMark :size="30" />
        <span class="admin-brand-copy">
          <span class="admin-brand-name">{{ config.productLabel }}</span>
          <span class="admin-brand-role">{{ roleText('label') }}</span>
        </span>
      </RouterLink>

      <div class="admin-tenant">
        <span class="admin-tenant-avatar" aria-hidden="true">PL</span>
        <span class="min-w-0">
          <span class="admin-tenant-name">{{ tenantLabel }}</span>
          <span class="admin-tenant-meta">{{
            $t('shell.admin.tenantMeta', { n: admin.workshops.length }, admin.workshops.length)
          }}</span>
        </span>
      </div>

      <nav
        class="admin-nav"
        :class="{ 'is-locked': passwordResetRequired }"
        :aria-label="$t('shell.a11y.mainNav')"
      >
        <section v-for="group in navGroups" :key="group.id" class="admin-nav-group">
          <div class="admin-nav-label">{{ t(`nav.group.${group.id}`) }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="admin-nav-item"
            active-class="on"
            :tabindex="passwordResetRequired ? -1 : undefined"
            :aria-disabled="passwordResetRequired ? 'true' : undefined"
            @click="onAdminNavClick"
          >
            <span class="admin-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
            </span>
            <span>{{ t(item.labelKey) }}</span>
            <span
              v-if="adminMetrics.get(item.to)"
              class="admin-nav-count"
              :class="{ danger: adminMetrics.get(item.to)?.danger }"
            >
              {{ adminMetrics.get(item.to)?.value }}
            </span>
          </RouterLink>
        </section>

        <section class="admin-nav-group">
          <div class="admin-nav-label">{{ $t('shell.admin.reference') }}</div>
          <button
            type="button"
            class="admin-nav-item"
            :disabled="passwordResetRequired"
            :aria-expanded="docsMenuOpen"
            @click="docsMenuOpen = !docsMenuOpen"
          >
            <span class="admin-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="iconPath('book')"></svg>
            </span>
            <span>{{ $t('shell.admin.docsAndApi') }}</span>
            <span class="admin-nav-count">
              <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('external')"></svg>
            </span>
          </button>
          <div v-if="docsMenuOpen" class="admin-doc-menu">
            <a
              v-for="link in adminDocsLinks"
              :key="link.href"
              :href="link.href"
              target="_blank"
              rel="noopener"
            >
              {{ link.label }}
            </a>
          </div>
        </section>
      </nav>

      <RouterLink :to="config.profilePath" class="admin-user-card" @click="closeMobileNav">
        <span class="admin-user-avatar" aria-hidden="true">{{ adminOperatorInitials }}</span>
        <span class="min-w-0">
          <span class="admin-user-name">{{ auth.displayName }}</span>
          <span class="admin-user-meta">{{ $t('shell.admin.operatorRole') }}</span>
        </span>
      </RouterLink>
    </aside>

    <div
      v-if="mobileNavOpen"
      class="admin-drawer"
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-mobile-drawer-title"
      @keydown="onDrawerKeydown"
    >
      <button
        class="admin-drawer-scrim"
        type="button"
        :aria-label="$t('shell.a11y.closeMenu')"
        @click="closeMobileNav"
      ></button>
      <div ref="drawerPanelRef" class="admin-drawer-panel" tabindex="-1">
        <div class="admin-drawer-head">
          <!-- Was a hardcoded, untranslated literal in a face the system no longer
               has. The platform sidebar's own brand block instead. -->
          <span class="admin-brand">
            <BrandMark :size="30" />
            <span class="admin-brand-copy">
              <span id="admin-mobile-drawer-title" class="admin-brand-name">
                {{ config.productLabel }}
              </span>
              <span class="admin-brand-role">{{ roleText('label') }}</span>
            </span>
          </span>
          <button
            class="admin-icon-button"
            type="button"
            :aria-label="$t('shell.a11y.closeMenu')"
            @click="closeMobileNav"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('close')"></svg>
          </button>
        </div>
        <nav
          class="admin-nav"
          :class="{ 'is-locked': passwordResetRequired }"
          :aria-label="$t('shell.a11y.mobileNav')"
        >
          <section v-for="group in navGroups" :key="`m-${group.id}`" class="admin-nav-group">
            <div class="admin-nav-label">{{ t(`nav.group.${group.id}`) }}</div>
            <RouterLink
              v-for="item in group.items"
              :key="`m-${item.to}`"
              :to="item.to"
              class="admin-nav-item"
              active-class="on"
              :tabindex="passwordResetRequired ? -1 : undefined"
              :aria-disabled="passwordResetRequired ? 'true' : undefined"
              @click="onAdminNavClick"
            >
              <span class="admin-nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
              </span>
              <span>{{ t(item.labelKey) }}</span>
            </RouterLink>
          </section>
          <section class="admin-nav-group">
            <div class="admin-nav-label">{{ $t('shell.admin.reference') }}</div>
            <a
              v-for="link in adminDocsLinks"
              :key="`m-doc-${link.href}`"
              class="admin-nav-item"
              :href="link.href"
              target="_blank"
              rel="noopener"
              :tabindex="passwordResetRequired ? -1 : undefined"
              :aria-disabled="passwordResetRequired ? 'true' : undefined"
              @click="onAdminNavClick"
            >
              <span class="admin-nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" v-html="iconPath('book')"></svg>
              </span>
              <span>{{ link.label }}</span>
            </a>
          </section>
        </nav>
      </div>
    </div>

    <main id="admin-content" class="admin-main" tabindex="-1">
      <div v-if="passwordResetRequired" class="admin-reset-gate" role="alert">
        <svg
          class="admin-reset-gate-ic"
          viewBox="0 0 24 24"
          aria-hidden="true"
          v-html="iconPath('lock')"
        ></svg>
        <div class="admin-reset-gate-body">
          <strong>{{ $t('shell.admin.resetTitle') }}</strong>
          <span>{{ $t('shell.admin.resetBody') }}</span>
        </div>
        <RouterLink :to="config.profilePath" class="admin-reset-gate-cta">
          {{ $t('shell.admin.resetCta') }}
        </RouterLink>
      </div>

      <header class="admin-topbar">
        <button
          ref="mobileTriggerRef"
          class="admin-mobile-button"
          type="button"
          :disabled="passwordResetRequired"
          @click="openMobileNav"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('menu')"></svg>
          {{ $t('shell.a11y.menu') }}
        </button>

        <div class="admin-top-actions">
          <NotificationsMenu v-if="!passwordResetRequired" />
          <RouterLink
            v-if="config.primaryActionTo"
            :to="config.primaryActionTo"
            class="admin-primary-action"
            :tabindex="passwordResetRequired ? -1 : undefined"
            :aria-disabled="passwordResetRequired ? 'true' : undefined"
            @click="onAdminNavClick"
          >
            {{ roleText('primaryAction') }}
          </RouterLink>
        </div>
      </header>

      <section class="admin-page">
        <RouterView />
      </section>
    </main>
  </div>

  <ToastHost />
</template>
