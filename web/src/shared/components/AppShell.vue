<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import {
  persistStoredContext,
  readStoredContext,
  workshopContextStorageKey,
} from '@/shared/app/contextStorage'
import { useRolePath } from '@/shared/app/paths'
import { useRoleConfig, type NavItem } from '@/shared/app/roleConfig'
import { lockBodyScroll, unlockBodyScroll } from '@/shared/app/scrollLock'
import { branchScopeHints, branchScopeOf } from '@/shared/app/branchScope'
import {
  adminInitials,
  adminNavMetrics,
  groupedNav,
  iconPath as adminIconPath,
} from '@/shared/app/adminUi'
import {
  grantSummary,
  initials,
  workshopStatusUz,
  workshopTenantName,
} from '@/shared/app/workshopUi'
import { workshopNavItems } from '@/shared/app/workshopNav'
import NotificationsMenu from '@/shared/components/NotificationsMenu.vue'
import OnboardingSpotlight from '@/shared/components/OnboardingSpotlight.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import ToastHost from '@/shared/components/ToastHost.vue'
import { useAdminStore } from '@/shared/stores/admin'
import { useAuthStore } from '@/shared/stores/auth'
import { useOnboardingStore } from '@/shared/stores/onboarding'
import { useOrdersStore } from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'
import { useWorkshopSearchStore } from '@/shared/stores/workshopSearch'

const config = useRoleConfig()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const onboarding = useOnboardingStore()
const orders = useOrdersStore()
const workshopSearch = useWorkshopSearchStore()
const admin = useAdminStore()
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const selectedContext = ref(config.dropdownOptions[0]?.value ?? '')
const mobileNavOpen = ref(false)
// Desktop icon-rail collapse: production workers mostly live in Kesish/Krom,
// so the sidebar can shrink to icons for a wider workspace. Device-level
// preference (floor tablets); mobile keeps the drawer instead.
const SIDEBAR_COLLAPSED_KEY = 'mp-workshop-sidebar-collapsed'
const sidebarCollapsed = ref(browserStorage()?.getItem(SIDEBAR_COLLAPSED_KEY) === '1')
const mobileTriggerRef = ref<HTMLButtonElement | null>(null)
const drawerPanelRef = ref<HTMLElement | null>(null)
const workshopSearchRootRef = ref<HTMLElement | null>(null)
const workshopSearchInputRef = ref<HTMLInputElement | null>(null)
const workshopSearchQuery = ref('')
const workshopSearchOpen = ref(false)
const docsMenuOpen = ref(false)
let previousMobileFocus: HTMLElement | null = null
let workshopSearchTimer: number | undefined
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
  // Settings first so an owner's rename shows without a reload; `me` is the
  // source everyone else has, because `/workshop/settings` is owner-only and
  // staff used to fall through to the generic label (QAD-168).
  if (config.role === 'workshop') {
    return workshopTenantName(workshop.settings?.name, auth.me?.workshop_name) ?? config.tenantLabel
  }
  if (config.role === 'client' && auth.isAllowedFor('client')) return auth.displayName
  return config.tenantLabel
})
const tenantMeta = computed(() => {
  if (!auth.me) return config.tenantMeta
  if (config.role === 'workshop') {
    return auth.me.is_owner ? 'Rahbar · barcha ruxsatlar' : grantSummary(false, auth.me.grants)
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
const selectedWorkshopBranch = computed(() =>
  workshop.branches.find((branch) => branch.id === selectedContext.value),
)
// The topbar branch switcher only earns its space when there's a real choice.
// With a single branch (or none) the context auto-pins to it, so hide the
// selector on every screen and let the pages use that one branch silently.
const showBranchSwitcher = computed(
  () => config.role === 'workshop' && workshop.branches.length > 1,
)
// Not every page reads the branch context: some are workshop-wide by design
// (debts, settings, branches, notifications, profile), others take their branch
// from the record being viewed. Each route declares which it is; on the two
// non-branch kinds the picker renders disabled with a hint rather than sitting
// there looking live and silently doing nothing.
const branchScope = computed(() => branchScopeOf(route.meta.branchScope))
const branchPickerDisabled = computed(() => branchScope.value !== 'branch')
const branchPickerHint = computed(() =>
  branchScope.value === 'branch' ? null : branchScopeHints[branchScope.value],
)
const normalizedSearchBranchId = computed(() => selectedWorkshopBranch.value?.id ?? null)
const searchPermissions = computed(() => new Set(selectedWorkshopBranch.value?.permissions ?? []))
const canSearchOrders = computed(
  () =>
    auth.me?.is_owner === true ||
    searchPermissions.value.has('view_orders') ||
    searchPermissions.value.has('manage_orders'),
)
const canSearchCatalog = computed(
  () => auth.me?.is_owner === true || searchPermissions.value.has('manage_catalog'),
)
const canSearchInventory = computed(
  () => auth.me?.is_owner === true || searchPermissions.value.has('manage_inventory'),
)
const canSearchUsers = computed(() => auth.me?.is_owner === true)
const canSearchWorkshop = computed(
  () =>
    canSearchOrders.value ||
    canSearchCatalog.value ||
    canSearchInventory.value ||
    canSearchUsers.value,
)
const workshopSearchResultCount = computed(
  () =>
    workshopSearch.results.orders.length +
    workshopSearch.results.users.length +
    workshopSearch.results.materials.length +
    workshopSearch.results.stock.length,
)
const hasWorkshopSearchQuery = computed(() => workshopSearchQuery.value.trim().length >= 2)
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
// Sidebar `+N` badge on Buyurtmalar (QAD-156): a live count of orders still in
// NEW for the selected branch, so staff notice an arrival without being on the
// board. Not an unread counter — it falls on its own as orders get confirmed.
const ordersNavPath = computed(() => rolePath('/workshop/orders'))
const canSeeOrdersNav = computed(() =>
  visibleNav.value.some((item) => item.to === ordersNavPath.value),
)
const newOrderBadge = computed(() => {
  if (config.role !== 'workshop' || !canSeeOrdersNav.value || orders.newOrderCount < 1) return null
  return orders.newOrderCount > 99 ? '99+' : String(orders.newOrderCount)
})
// The badge itself is decorative; the count belongs to the link's own name so a
// screen reader hears "Buyurtmalar — 4 ta yangi buyurtma" in one go.
function navAriaLabel(item: NavItem) {
  if (item.to !== ordersNavPath.value || !newOrderBadge.value) return undefined
  return `${item.label} — ${orders.newOrderCount} ta yangi buyurtma`
}
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
    scale:
      '<path d="M12 3v18"/><path d="M8 21h8"/><path d="M5 7h14"/><path d="m5 7-2.5 5a2.9 2.9 0 0 0 5 0L5 7Z"/><path d="m19 7-2.5 5a2.9 2.9 0 0 0 5 0L19 7Z"/>',
    store: '<path d="M4 10h16l-1-5H5l-1 5Z"/><path d="M6 10v10h12V10"/><path d="M9 20v-6h6v6"/>',
    users:
      '<path d="M16 20v-2a4 4 0 0 0-8 0v2"/><circle cx="12" cy="8" r="4"/><path d="M20 20v-2a3 3 0 0 0-3-3"/><path d="M4 20v-2a3 3 0 0 1 3-3"/>',
    settings:
      '<path d="M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z"/><path d="M4 12h2m12 0h2M12 4v2m0 12v2m-5.7-3.7 1.4-1.4m8.6-8.6 1.4-1.4m0 11.4-1.4-1.4M7.7 7.7 6.3 6.3"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
  }
  return paths[name ?? 'dashboard'] ?? paths.dashboard
}

function drawerFocusable() {
  return Array.from(
    drawerPanelRef.value?.querySelectorAll<HTMLElement>(
      'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
    ) ?? [],
  ).filter((element) => !element.hasAttribute('disabled') && element.tabIndex >= 0)
}

function openMobileNav() {
  previousMobileFocus =
    document.activeElement instanceof HTMLElement ? document.activeElement : mobileTriggerRef.value
  mobileNavOpen.value = true
}

function closeMobileNav() {
  if (!mobileNavOpen.value) return
  mobileNavOpen.value = false
}

// One trigger for both worlds: on desktop it toggles the sidebar between full
// and icon-rail; on mobile it opens the drawer.
function onNavTrigger() {
  const isDesktop = window.matchMedia('(min-width: 921px)').matches
  if (config.role === 'workshop' && isDesktop) {
    sidebarCollapsed.value = !sidebarCollapsed.value
    browserStorage()?.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed.value ? '1' : '0')
    return
  }
  openMobileNav()
}

function onDrawerKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeMobileNav()
    return
  }
  if (event.key !== 'Tab') return

  const focusable = drawerFocusable()
  if (focusable.length === 0) {
    event.preventDefault()
    drawerPanelRef.value?.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

function searchDestination(path: string, query = workshopSearchQuery.value) {
  const trimmed = query.trim()
  const target = rolePath(path)
  if (!trimmed) return target
  return `${target}?search=${encodeURIComponent(trimmed)}`
}

function closeWorkshopSearch() {
  workshopSearchOpen.value = false
}

function focusWorkshopSearch() {
  if (config.role !== 'workshop' || isAuthRoute.value) return
  workshopSearchOpen.value = true
  void nextTick(() => {
    workshopSearchInputRef.value?.focus()
    workshopSearchInputRef.value?.select()
  })
}

function runWorkshopSearchNow() {
  window.clearTimeout(workshopSearchTimer)
  if (!canSearchWorkshop.value || !hasWorkshopSearchQuery.value) {
    workshopSearch.reset()
    return
  }
  void workshopSearch.search({
    query: workshopSearchQuery.value,
    branchId: normalizedSearchBranchId.value,
    includeOrders: canSearchOrders.value,
    includeUsers: canSearchUsers.value,
    includeCatalog: canSearchCatalog.value,
    includeInventory: canSearchInventory.value,
  })
}

function queueWorkshopSearch() {
  window.clearTimeout(workshopSearchTimer)
  if (!canSearchWorkshop.value || !hasWorkshopSearchQuery.value) {
    workshopSearch.reset()
    return
  }
  workshopSearchTimer = window.setTimeout(runWorkshopSearchNow, 220)
}

function submitWorkshopSearch() {
  workshopSearchOpen.value = true
  runWorkshopSearchNow()
  const results = workshopSearch.results
  if (workshopSearchResultCount.value !== 1) return
  const order = results.orders[0]
  const user = results.users[0]
  if (order) {
    void router.push(rolePath(`/workshop/orders/${order.id}`))
    closeWorkshopSearch()
  } else if (user) {
    void router.push(rolePath(`/workshop/settings/users/${user.id}`))
    closeWorkshopSearch()
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  if (config.role !== 'workshop' || !workshopSearchOpen.value) return
  const target = event.target
  if (target instanceof Node && workshopSearchRootRef.value?.contains(target)) return
  closeWorkshopSearch()
}

function onGlobalKeydown(event: KeyboardEvent) {
  if (config.role !== 'workshop' || isAuthRoute.value) return
  if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'k') return
  event.preventDefault()
  focusWorkshopSearch()
}

function browserStorage() {
  return typeof window === 'undefined' ? null : window.localStorage
}

// No polling: the count refreshes on the moments it can actually change for this
// user — shell mount, a branch switch, the tab coming back into view, and every
// order mutation (that last one lives in the orders store).
function reloadNewOrderCount() {
  if (config.role !== 'workshop' || !canLoadWorkshopContext.value || !canSeeOrdersNav.value) return
  void orders.loadNewOrderCount(selectedWorkshopBranch.value?.id ?? null)
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') reloadNewOrderCount()
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

watch(
  selectedContext,
  (value) => {
    if (config.role === 'workshop') workshop.setSelectedBranchContext(value)
    const storage = browserStorage()
    if (!storage || !contextStorageKey.value) return
    persistStoredContext(storage, contextStorageKey.value, value, dropdownOptions.value)
  },
  { immediate: true },
)

watch(
  () => workshop.selectedBranchContext,
  (value) => {
    if (config.role !== 'workshop' || !value || selectedContext.value === value) return
    if (!dropdownOptions.value.some((option) => option.value === value)) return
    selectedContext.value = value
  },
)

watch(
  canLoadWorkshopContext,
  (canLoad) => {
    if (canLoad) {
      void workshop.loadBranchContext().catch(() => undefined)
      // Guided first-run setup — owner-only; the store no-ops for staff.
      void onboarding.ensureLoaded()
    }
  },
  { immediate: true },
)

watch(
  () => route.fullPath,
  () => {
    closeMobileNav()
    docsMenuOpen.value = false
    closeWorkshopSearch()
  },
)

watch(
  [
    workshopSearchQuery,
    normalizedSearchBranchId,
    canSearchOrders,
    canSearchCatalog,
    canSearchInventory,
    canSearchUsers,
  ],
  () => {
    if (config.role !== 'workshop') return
    queueWorkshopSearch()
  },
)

watch(
  mobileNavOpen,
  async (open) => {
    if (open) {
      lockBodyScroll()
      await nextTick()
      const first = drawerFocusable()[0]
      if (first) first.focus()
      else drawerPanelRef.value?.focus()
      return
    }
    unlockBodyScroll()
    previousMobileFocus?.focus()
    previousMobileFocus = null
  },
  { flush: 'post' },
)

// The branch (or the right to see orders at all) only settles once the branch
// context has loaded, so drive the count off that instead of a bare onMounted.
watch([() => selectedWorkshopBranch.value?.id, canSeeOrdersNav], reloadNewOrderCount, {
  immediate: true,
})

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  window.addEventListener('keydown', onGlobalKeydown)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  window.clearTimeout(workshopSearchTimer)
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('keydown', onGlobalKeydown)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  if (mobileNavOpen.value) unlockBodyScroll()
  previousMobileFocus = null
})
</script>

<template>
  <div v-if="isAuthRoute" class="min-h-[var(--app-vh)] bg-bg text-ink">
    <RouterView />
  </div>

  <div v-else-if="config.role === 'client'" class="min-h-[var(--app-vh)] bg-bg text-ink">
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

  <div
    v-else-if="config.role === 'workshop'"
    class="workshop-app"
    :class="{ 'nav-collapsed': sidebarCollapsed }"
  >
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
            :title="item.label"
            :aria-label="navAriaLabel(item)"
          >
            <span class="workshop-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
            </span>
            <span>{{ item.label }}</span>
            <span
              v-if="newOrderBadge && item.to === ordersNavPath"
              class="workshop-nav-badge"
              aria-hidden="true"
              >{{ newOrderBadge }}</span
            >
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

    <div
      v-if="mobileNavOpen"
      class="workshop-drawer"
      role="dialog"
      aria-modal="true"
      @keydown="onDrawerKeydown"
    >
      <button
        class="workshop-drawer-scrim"
        type="button"
        aria-label="Menyuni yopish"
        @click="closeMobileNav"
      ></button>
      <div ref="drawerPanelRef" class="workshop-drawer-panel" tabindex="-1">
        <div class="workshop-drawer-head">
          <span class="font-serif text-lg font-semibold">Mebel Pro</span>
          <button
            class="workshop-icon-button"
            type="button"
            aria-label="Menyuni yopish"
            @click="closeMobileNav"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('close')"></svg>
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
              :aria-label="navAriaLabel(item)"
            >
              <span class="workshop-nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
              </span>
              <span>{{ item.label }}</span>
              <span
                v-if="newOrderBadge && item.to === ordersNavPath"
                class="workshop-nav-badge"
                aria-hidden="true"
                >{{ newOrderBadge }}</span
              >
            </RouterLink>
          </section>
        </nav>
      </div>
    </div>

    <main class="workshop-main">
      <header class="workshop-topbar">
        <button
          ref="mobileTriggerRef"
          class="workshop-mobile-button"
          type="button"
          aria-label="Menyu"
          @click="onNavTrigger"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('menu')"></svg>
        </button>

        <ProjectDropdown
          v-if="showBranchSwitcher"
          v-model="selectedContext"
          class="workshop-branch-dd"
          :label="config.dropdownLabel"
          :options="dropdownOptions"
          :disabled="branchPickerDisabled"
          :hint="branchPickerHint"
          hide-label
        />

        <div ref="workshopSearchRootRef" class="workshop-search-wrap">
          <label class="workshop-search" for="workshop-global-search">
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle cx="8.5" cy="8.5" r="5.5"></circle>
              <path d="m13 13 4 4"></path>
            </svg>
            <span class="sr-only">Global qidiruv</span>
            <input
              id="workshop-global-search"
              ref="workshopSearchInputRef"
              v-model="workshopSearchQuery"
              placeholder="Buyurtma, mijoz, xodim yoki material..."
              autocomplete="off"
              :aria-expanded="workshopSearchOpen"
              aria-controls="workshop-global-search-panel"
              @focus="workshopSearchOpen = true"
              @keydown.enter.prevent="submitWorkshopSearch"
              @keydown.escape.prevent="closeWorkshopSearch"
            />
            <span class="workshop-kbd">⌘ K</span>
          </label>

          <div
            v-if="workshopSearchOpen && (workshopSearchQuery || workshopSearch.loading)"
            id="workshop-global-search-panel"
            class="workshop-search-panel"
            role="dialog"
            aria-label="Qidiruv natijalari"
          >
            <div v-if="!canSearchWorkshop" class="workshop-search-empty">
              Bu filial bo'yicha qidiruv uchun ruxsat yo'q.
            </div>
            <div v-else-if="!hasWorkshopSearchQuery" class="workshop-search-empty">
              Kamida 2 ta belgi kiriting.
            </div>
            <div v-else-if="workshopSearch.loading" class="workshop-search-empty">
              Qidirilmoqda...
            </div>
            <template v-else>
              <p v-if="workshopSearch.error" class="workshop-search-error">
                Qidiruvning bir qismi yuklanmadi.
                <span v-if="workshopSearch.traceId">Trace: {{ workshopSearch.traceId }}</span>
              </p>

              <div v-if="workshopSearch.results.orders.length" class="workshop-search-section">
                <div class="workshop-search-section-title">Buyurtmalar</div>
                <RouterLink
                  v-for="order in workshopSearch.results.orders"
                  :key="order.id"
                  class="workshop-search-result"
                  :to="rolePath(`/workshop/orders/${order.id}`)"
                  @click="closeWorkshopSearch"
                >
                  <span>
                    <strong>{{ order.order_number }}</strong>
                    <small>{{ order.client_name }} · {{ order.branch_name }}</small>
                  </span>
                  <em>{{ workshopStatusUz[order.status] }}</em>
                </RouterLink>
              </div>

              <div v-if="workshopSearch.results.users.length" class="workshop-search-section">
                <div class="workshop-search-section-title">Xodimlar</div>
                <RouterLink
                  v-for="user in workshopSearch.results.users"
                  :key="user.id"
                  class="workshop-search-result"
                  :to="rolePath(`/workshop/settings/users/${user.id}`)"
                  @click="closeWorkshopSearch"
                >
                  <span>
                    <strong>{{ user.full_name }}</strong>
                    <small>{{ user.login }} · {{ user.phone }}</small>
                  </span>
                  <em>{{ user.status === 'active' ? 'Faol' : 'Bloklangan' }}</em>
                </RouterLink>
              </div>

              <div v-if="workshopSearch.results.materials.length" class="workshop-search-section">
                <div class="workshop-search-section-title">Material katalogi</div>
                <RouterLink
                  v-for="row in workshopSearch.results.materials"
                  :key="row.id"
                  class="workshop-search-result"
                  :to="searchDestination('/workshop/catalog', row.material.name)"
                  @click="closeWorkshopSearch"
                >
                  <span>
                    <strong>{{ row.material.name }}</strong>
                    <small>{{ row.material.manufacturer_name }} · {{ row.material.kind }}</small>
                  </span>
                  <em>{{ row.status === 'active' ? 'Faol' : 'Yashirilgan' }}</em>
                </RouterLink>
              </div>

              <div v-if="workshopSearch.results.stock.length" class="workshop-search-section">
                <div class="workshop-search-section-title">Ombor</div>
                <RouterLink
                  v-for="item in workshopSearch.results.stock"
                  :key="item.id"
                  class="workshop-search-result"
                  :to="searchDestination('/workshop/inventory', item.material.name)"
                  @click="closeWorkshopSearch"
                >
                  <span>
                    <strong>{{ item.material.name }}</strong>
                    <small>{{ item.material.manufacturer_name }} · {{ item.display_unit }}</small>
                  </span>
                  <em :class="{ danger: item.is_low_stock }">
                    {{ item.is_low_stock ? 'Kam qoldi' : 'Omborda' }}
                  </em>
                </RouterLink>
              </div>

              <div v-if="workshopSearchResultCount === 0" class="workshop-search-empty">
                Natija topilmadi.
              </div>

              <div class="workshop-search-shortcuts">
                <RouterLink
                  v-if="canSearchOrders"
                  :to="searchDestination('/workshop/orders')"
                  @click="closeWorkshopSearch"
                >
                  Buyurtmalar ro'yxatida ochish
                </RouterLink>
                <RouterLink
                  v-if="canSearchCatalog"
                  :to="searchDestination('/workshop/catalog')"
                  @click="closeWorkshopSearch"
                >
                  Katalogda ochish
                </RouterLink>
                <RouterLink
                  v-if="canSearchInventory"
                  :to="searchDestination('/workshop/inventory')"
                  @click="closeWorkshopSearch"
                >
                  Omborda ochish
                </RouterLink>
                <RouterLink
                  v-if="canSearchUsers"
                  :to="searchDestination('/workshop/settings/users')"
                  @click="closeWorkshopSearch"
                >
                  Xodimlarda ochish
                </RouterLink>
              </div>
            </template>
          </div>
        </div>

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
      <OnboardingSpotlight />
    </main>
  </div>

  <div v-else class="admin-app">
    <a class="admin-skip-link" href="#admin-content">Kontentga o'tish</a>
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

      <nav
        class="admin-nav"
        :class="{ 'is-locked': passwordResetRequired }"
        aria-label="Asosiy navigatsiya"
      >
        <section v-for="group in groupedAdminNav" :key="group.label" class="admin-nav-group">
          <div class="admin-nav-label">{{ group.label }}</div>
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
            :disabled="passwordResetRequired"
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
        </section>
      </nav>

      <RouterLink :to="config.profilePath" class="admin-user-card" @click="closeMobileNav">
        <span class="admin-user-avatar" aria-hidden="true">{{ adminOperatorInitials }}</span>
        <span class="min-w-0">
          <span class="admin-user-name">{{ auth.displayName }}</span>
          <span class="admin-user-meta">Platforma admini</span>
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
        aria-label="Menyuni yopish"
        @click="closeMobileNav"
      ></button>
      <div ref="drawerPanelRef" class="admin-drawer-panel" tabindex="-1">
        <div class="admin-drawer-head">
          <span id="admin-mobile-drawer-title" class="font-serif text-lg font-semibold">
            Mebel Pro
          </span>
          <button
            class="admin-icon-button"
            type="button"
            aria-label="Menyuni yopish"
            @click="closeMobileNav"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="adminIconPath('close')"></svg>
          </button>
        </div>
        <nav
          class="admin-nav"
          :class="{ 'is-locked': passwordResetRequired }"
          aria-label="Mobil navigatsiya"
        >
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
              :tabindex="passwordResetRequired ? -1 : undefined"
              :aria-disabled="passwordResetRequired ? 'true' : undefined"
              @click="onAdminNavClick"
            >
              <span class="admin-nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" v-html="adminIconPath(item.icon)"></svg>
              </span>
              <span>{{ item.label }}</span>
            </RouterLink>
          </section>
          <section class="admin-nav-group">
            <div class="admin-nav-label">Ma'lumotnoma</div>
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
                <svg viewBox="0 0 24 24" v-html="adminIconPath('book')"></svg>
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
          v-html="adminIconPath('lock')"
        ></svg>
        <div class="admin-reset-gate-body">
          <strong>Parolni o'zgartiring</strong>
          <span>
            Platformaning boshqa bo'limlari vaqtinchalik parol almashtirilmaguncha bloklangan.
          </span>
        </div>
        <RouterLink :to="config.profilePath" class="admin-reset-gate-cta">
          Parolni almashtirish
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
          <svg viewBox="0 0 24 24" aria-hidden="true" v-html="adminIconPath('menu')"></svg>
          Menu
        </button>

        <div class="admin-top-actions">
          <NotificationsMenu v-if="!passwordResetRequired" />
          <RouterLink
            v-if="config.primaryActionLabel && config.primaryActionTo"
            :to="config.primaryActionTo"
            class="admin-primary-action"
            :tabindex="passwordResetRequired ? -1 : undefined"
            :aria-disabled="passwordResetRequired ? 'true' : undefined"
            @click="onAdminNavClick"
          >
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
