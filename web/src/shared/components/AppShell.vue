<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import {
  persistStoredContext,
  readStoredContext,
  workshopContextStorageKey,
} from '@/shared/app/contextStorage'
import { useRolePath } from '@/shared/app/paths'
import { useRoleConfig, type NavItem } from '@/shared/app/roleConfig'
import {
  adminInitials,
  adminNavMetrics,
  groupedNav,
  iconPath as adminIconPath,
} from '@/shared/app/adminUi'
import { grantSummary, initials } from '@/shared/app/workshopUi'
import { workshopNavItems } from '@/shared/app/workshopNav'
import NotificationsMenu from '@/shared/components/NotificationsMenu.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import ToastHost from '@/shared/components/ToastHost.vue'
import { useAdminStore } from '@/shared/stores/admin'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

const config = useRoleConfig()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const admin = useAdminStore()
const route = useRoute()
const rolePath = useRolePath()
const selectedContext = ref(config.dropdownOptions[0]?.value ?? '')
const mobileNavOpen = ref(false)
const docsMenuOpen = ref(false)
const isAuthRoute = computed(() => route.meta.layout === 'auth')
const canLoadWorkshopContext = computed(
  () =>
    config.role === 'workshop' &&
    auth.isAllowedFor('workshop') &&
    auth.me?.password_reset_required === false,
)
const contextStorageKey = computed(() =>
  config.role === 'workshop' && auth.me
    ? workshopContextStorageKey(auth.me.principal_id, auth.me.session_id)
    : null,
)
const profileSubtitle = computed(() =>
  auth.me?.password_reset_required ? "parolni o'zgartirish kerak" : auth.displayName,
)
const tenantLabel = computed(() => {
  if (config.role === 'workshop') return workshop.settings?.name ?? config.tenantLabel
  if (config.role === 'client' && auth.isAllowedFor('client')) return auth.displayName
  return config.tenantLabel
})
const tenantMeta = computed(() => {
  if (!auth.me) return config.tenantMeta
  if (config.role === 'workshop') {
    return auth.me.is_owner ? 'Egasi · barcha ruxsatlar' : grantSummary(false, auth.me.grants)
  }
  if (config.role === 'client') return auth.me.phone ?? auth.displayName
  if (config.role === 'admin') return auth.displayName
  return config.tenantMeta
})
const tenantInitial = computed(() =>
  (tenantLabel.value.trim().slice(0, 1) || config.roleLabel[0]).toUpperCase(),
)
const workshopUserInitials = computed(() => initials(auth.displayName, 'MP'))
const adminOperatorInitials = computed(() => adminInitials(auth.displayName, 'N'))
const clientInitial = computed(() =>
  (auth.displayName.trim().slice(0, 1) || auth.me?.phone?.slice(-1) || 'M').toUpperCase(),
)
const dropdownOptions = computed(() => {
  if (config.role !== 'workshop') return config.dropdownOptions
  if (workshop.branches.length === 0) {
    return [
      {
        value: 'none',
        label: "Filial yo'q",
        meta: 'biriktirilmagan',
        status: 'pending' as const,
      },
    ]
  }
  return workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.status === 'temporarily_closed' ? 'vaqtincha yopiq' : branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  }))
})
const visibleNav = computed<NavItem[]>(() => {
  if (config.role !== 'workshop') return config.nav
  return workshopNavItems({
    isOwner: auth.me?.is_owner === true,
    branches: workshop.branches,
    selectedBranchId: selectedContext.value,
    path: rolePath,
  })
})
const groupedWorkshopNav = computed(() => {
  const groups: Array<{ label: string; items: NavItem[] }> = []
  for (const item of visibleNav.value) {
    const label = item.group ?? 'Boshqaruv'
    let group = groups.find((current) => current.label === label)
    if (!group) {
      group = { label, items: [] }
      groups.push(group)
    }
    group.items.push(item)
  }
  return groups
})
const groupedAdminNav = computed(() => groupedNav(visibleNav.value))
const adminMetrics = computed(() =>
  adminNavMetrics({
    workshops: admin.workshops.length,
    manufacturers: admin.manufacturers.length,
    materials: admin.materials.length,
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

function iconPath(name: string | undefined) {
  const paths: Record<string, string> = {
    dashboard: '<path d="M4 13h6V4H4v9Zm10 7h6V4h-6v16ZM4 20h6v-5H4v5Z"/>',
    home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/>',
    orders: '<path d="M6 3h9l3 3v15H6V3Z"/><path d="M14 3v4h4"/><path d="M9 11h6M9 15h6"/>',
    scissors:
      '<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M8 8l10 10M8 16 18 6"/>',
    layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
    box: '<path d="m3 7 9-4 9 4-9 4-9-4Z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>',
    grid: '<path d="M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm9 0h7v7h-7v-7Z"/>',
    chart: '<path d="M4 19V5"/><path d="M4 19h17"/><path d="M8 16v-5M13 16V8M18 16v-9"/>',
    wallet:
      '<path d="M4 7h15a2 2 0 0 1 2 2v9H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h13"/><path d="M17 12h4v4h-4a2 2 0 0 1 0-4Z"/>',
    store: '<path d="M4 10h16l-1-5H5l-1 5Z"/><path d="M6 10v10h12V10"/><path d="M9 20v-6h6v6"/>',
    users:
      '<path d="M16 20v-2a4 4 0 0 0-8 0v2"/><circle cx="12" cy="8" r="4"/><path d="M20 20v-2a3 3 0 0 0-3-3"/><path d="M4 20v-2a3 3 0 0 1 3-3"/>',
    settings:
      '<path d="M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z"/><path d="M4 12h2m12 0h2M12 4v2m0 12v2m-5.7-3.7 1.4-1.4m8.6-8.6 1.4-1.4m0 11.4-1.4-1.4M7.7 7.7 6.3 6.3"/>',
  }
  return paths[name ?? 'dashboard'] ?? paths.dashboard
}

function closeMobileNav() {
  mobileNavOpen.value = false
}

function browserStorage() {
  return typeof window === 'undefined' ? null : window.localStorage
}

watch(
  [dropdownOptions, contextStorageKey],
  ([options, storageKey], oldValue) => {
    const previousStorageKey = oldValue?.[1] ?? null
    const storage = browserStorage()
    if (storage && previousStorageKey && !storageKey) {
      storage.removeItem(previousStorageKey)
    }

    const stored = storage && storageKey ? readStoredContext(storage, storageKey, options) : null
    const nextValue = stored ?? selectedContext.value
    if (options.some((option) => option.value === nextValue)) {
      selectedContext.value = nextValue
      return
    }
    selectedContext.value = options[0]?.value ?? ''
  },
  { immediate: true },
)

watch(selectedContext, (value) => {
  const storage = browserStorage()
  if (!storage || !contextStorageKey.value) return
  persistStoredContext(storage, contextStorageKey.value, value, dropdownOptions.value)
})

watch(
  canLoadWorkshopContext,
  (canLoad) => {
    if (canLoad) void workshop.loadBranchContext().catch(() => undefined)
  },
  { immediate: true },
)

watch(
  () => route.fullPath,
  () => {
    closeMobileNav()
    docsMenuOpen.value = false
  },
)
</script>

<template>
  <div v-if="isAuthRoute" class="min-h-screen bg-bg text-ink">
    <RouterView />
  </div>

  <div v-else-if="config.role === 'client'" class="min-h-screen bg-bg text-ink">
    <header class="client-header">
      <div class="client-container client-header-row">
        <RouterLink :to="config.homePath" class="client-brand" aria-label="Bosh sahifa">
          <img src="/favicon.svg" alt="" class="size-8" />
          <span class="client-brand-name">{{ config.productLabel }}</span>
        </RouterLink>

        <nav class="client-nav" aria-label="Asosiy navigatsiya">
          <RouterLink v-for="item in visibleNav" :key="item.to" :to="item.to">
            <span class="client-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
            </span>
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="client-actions">
          <NotificationsMenu />
          <RouterLink
            :to="config.profilePath"
            class="client-user-pill"
            :aria-label="`Profil — ${auth.displayName}`"
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

  <div v-else-if="config.role === 'workshop'" class="workshop-app">
    <aside class="workshop-sidebar" aria-label="Workshop navigation">
      <RouterLink :to="config.homePath" class="workshop-brand" @click="closeMobileNav">
        <img src="/favicon.svg" alt="" class="workshop-brand-mark" />
        <span class="workshop-brand-copy">
          <span class="workshop-brand-name">{{ config.productLabel }}</span>
          <span class="workshop-brand-role">{{ config.roleLabel }}</span>
        </span>
      </RouterLink>

      <div class="workshop-tenant">
        <span class="workshop-tenant-avatar" aria-hidden="true">{{ tenantInitial }}</span>
        <span class="min-w-0">
          <span class="workshop-tenant-name">{{ tenantLabel }}</span>
          <span class="workshop-tenant-meta">{{ tenantMeta }}</span>
        </span>
      </div>

      <nav class="workshop-nav" aria-label="Asosiy navigatsiya">
        <section v-for="group in groupedWorkshopNav" :key="group.label" class="workshop-nav-group">
          <div class="workshop-nav-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="workshop-nav-item"
            active-class="on"
          >
            <span class="workshop-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
            </span>
            <span>{{ item.label }}</span>
          </RouterLink>
        </section>
      </nav>

      <RouterLink :to="config.profilePath" class="workshop-user-card" @click="closeMobileNav">
        <span class="workshop-user-avatar" aria-hidden="true">{{ workshopUserInitials }}</span>
        <span class="min-w-0">
          <span class="workshop-user-name">{{ auth.displayName }}</span>
          <span class="workshop-user-meta">{{ profileSubtitle }}</span>
        </span>
      </RouterLink>
    </aside>

    <div v-if="mobileNavOpen" class="workshop-drawer" role="dialog" aria-modal="true">
      <button
        class="workshop-drawer-scrim"
        type="button"
        aria-label="Menyuni yopish"
        @click="closeMobileNav"
      ></button>
      <div class="workshop-drawer-panel">
        <div class="workshop-drawer-head">
          <span class="font-serif text-lg font-semibold">Mebel Pro</span>
          <button
            class="workshop-icon-button"
            type="button"
            aria-label="Menyuni yopish"
            @click="closeMobileNav"
          >
            ×
          </button>
        </div>
        <nav class="workshop-nav" aria-label="Mobil navigatsiya">
          <section
            v-for="group in groupedWorkshopNav"
            :key="`m-${group.label}`"
            class="workshop-nav-group"
          >
            <div class="workshop-nav-label">{{ group.label }}</div>
            <RouterLink
              v-for="item in group.items"
              :key="`m-${item.to}`"
              :to="item.to"
              class="workshop-nav-item"
              active-class="on"
            >
              <span class="workshop-nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
              </span>
              <span>{{ item.label }}</span>
            </RouterLink>
          </section>
        </nav>
      </div>
    </div>

    <main class="workshop-main">
      <header class="workshop-topbar">
        <button class="workshop-mobile-button" type="button" @click="mobileNavOpen = true">
          <span aria-hidden="true">☰</span>
          Menu
        </button>

        <ProjectDropdown
          v-model="selectedContext"
          :label="config.dropdownLabel"
          :options="dropdownOptions"
        />

        <label class="workshop-search">
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <circle cx="8.5" cy="8.5" r="5.5"></circle>
            <path d="m13 13 4 4"></path>
          </svg>
          <span class="sr-only">Global qidiruv</span>
          <input placeholder="Buyurtma, mijoz, xodim yoki material..." />
          <span class="workshop-kbd">⌘ K</span>
        </label>

        <div class="workshop-top-actions">
          <NotificationsMenu />
          <RouterLink :to="config.profilePath" class="workshop-top-user">
            <span class="workshop-user-avatar" aria-hidden="true">{{ workshopUserInitials }}</span>
            <span class="workshop-top-user-text">{{ auth.displayName }}</span>
          </RouterLink>
        </div>
      </header>

      <section class="workshop-page">
        <RouterView />
      </section>
    </main>
  </div>

  <div v-else class="admin-app">
    <aside class="admin-sidebar" aria-label="Superadmin navigation">
      <RouterLink :to="config.homePath" class="admin-brand" @click="closeMobileNav">
        <img src="/favicon.svg" alt="" class="admin-brand-mark" />
        <span class="admin-brand-copy">
          <span class="admin-brand-name">{{ config.productLabel }}</span>
          <span class="admin-brand-role">{{ config.roleLabel }}</span>
        </span>
      </RouterLink>

      <div class="admin-tenant">
        <span class="admin-tenant-avatar" aria-hidden="true">PL</span>
        <span class="min-w-0">
          <span class="admin-tenant-name">{{ tenantLabel }}</span>
          <span class="admin-tenant-meta">{{ admin.workshops.length }} ta ustaxona · O'Z</span>
        </span>
      </div>

      <nav class="admin-nav" aria-label="Asosiy navigatsiya">
        <section v-for="group in groupedAdminNav" :key="group.label" class="admin-nav-group">
          <div class="admin-nav-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="admin-nav-item"
            active-class="on"
            @click="closeMobileNav"
          >
            <span class="admin-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="adminIconPath(item.icon)"></svg>
            </span>
            <span>{{ item.label }}</span>
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
          <div class="admin-nav-label">Ma'lumotnoma</div>
          <button
            type="button"
            class="admin-nav-item"
            :aria-expanded="docsMenuOpen"
            @click="docsMenuOpen = !docsMenuOpen"
          >
            <span class="admin-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="adminIconPath('book')"></svg>
            </span>
            <span>Hujjatlar &amp; API</span>
            <span class="admin-nav-count">
              <svg viewBox="0 0 24 24" aria-hidden="true" v-html="adminIconPath('external')"></svg>
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
          <p class="admin-doc-note">Alohida kirish: chetda HTTP-Basic, yangi oynada.</p>
        </section>
      </nav>

      <RouterLink :to="config.profilePath" class="admin-user-card" @click="closeMobileNav">
        <span class="admin-user-avatar" aria-hidden="true">{{ adminOperatorInitials }}</span>
        <span class="min-w-0">
          <span class="admin-user-name">{{ auth.displayName }}</span>
          <span class="admin-user-meta">Platforma operatori</span>
        </span>
      </RouterLink>
    </aside>

    <div v-if="mobileNavOpen" class="admin-drawer" role="dialog" aria-modal="true">
      <button
        class="admin-drawer-scrim"
        type="button"
        aria-label="Menyuni yopish"
        @click="closeMobileNav"
      ></button>
      <div class="admin-drawer-panel">
        <div class="admin-drawer-head">
          <span class="font-serif text-lg font-semibold">Mebel Pro</span>
          <button
            class="admin-icon-button"
            type="button"
            aria-label="Menyuni yopish"
            @click="closeMobileNav"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="adminIconPath('close')"></svg>
          </button>
        </div>
        <nav class="admin-nav" aria-label="Mobil navigatsiya">
          <section
            v-for="group in groupedAdminNav"
            :key="`m-${group.label}`"
            class="admin-nav-group"
          >
            <div class="admin-nav-label">{{ group.label }}</div>
            <RouterLink
              v-for="item in group.items"
              :key="`m-${item.to}`"
              :to="item.to"
              class="admin-nav-item"
              active-class="on"
            >
              <span class="admin-nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" v-html="adminIconPath(item.icon)"></svg>
              </span>
              <span>{{ item.label }}</span>
            </RouterLink>
          </section>
        </nav>
      </div>
    </div>

    <main class="admin-main">
      <header class="admin-topbar">
        <button class="admin-mobile-button" type="button" @click="mobileNavOpen = true">
          <svg viewBox="0 0 24 24" aria-hidden="true" v-html="adminIconPath('menu')"></svg>
          Menu
        </button>

        <label class="admin-search">
          <svg viewBox="0 0 24 24" aria-hidden="true" v-html="adminIconPath('search')"></svg>
          <span class="sr-only">Global qidiruv</span>
          <input placeholder="Ustaxona, mijoz, buyurtma yoki xatolik kodi..." />
          <span class="admin-kbd">⌘ K</span>
        </label>

        <div class="admin-top-actions">
          <NotificationsMenu />
          <RouterLink :to="config.primaryActionTo" class="admin-primary-action">
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="adminIconPath('plus')"></svg>
            {{ config.primaryActionLabel }}
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
