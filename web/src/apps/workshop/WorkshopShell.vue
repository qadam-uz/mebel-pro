<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { branchScopeHint, branchScopeOf } from '@/shared/app/branchScope'
import {
  persistStoredContext,
  readStoredContext,
  workshopContextStorageKey,
} from '@/shared/app/contextStorage'
import { decorTypeLabel } from '@/shared/app/materialLabel'
import { useRolePath } from '@/shared/app/paths'
import { roleMessageKey, useRoleConfig, type NavItem } from '@/shared/app/roleConfig'
import { groupedNav, iconPath, isChromelessLayout } from '@/shared/app/shellChrome'
import { workshopNavItems } from '@/shared/app/workshopNav'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import {
  grantSummary,
  initials,
  workshopStatusUz,
  workshopTenantName,
} from '@/shared/app/workshopUi'
import ActionMenu from '@/shared/components/ActionMenu.vue'
import BrandMark from '@/shared/components/BrandMark.vue'
import LocaleSwitcher from '@/shared/components/LocaleSwitcher.vue'
import NotificationsMenu from '@/shared/components/NotificationsMenu.vue'
import OnboardingSpotlight from '@/shared/components/OnboardingSpotlight.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import ToastHost from '@/shared/components/ToastHost.vue'
import { useMobileNav } from '@/shared/composables/useMobileNav'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { useAuthStore } from '@/shared/stores/auth'
import { useOnboardingStore } from '@/shared/stores/onboarding'
import { useOrdersStore } from '@/shared/stores/orders'
import { useProductionStore } from '@/shared/stores/production'
import { useWorkshopStore } from '@/shared/stores/workshop'
import { useWorkshopSearchStore } from '@/shared/stores/workshopSearch'

const config = useRoleConfig()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const onboarding = useOnboardingStore()
const orders = useOrdersStore()
const production = useProductionStore()
const workshopSearch = useWorkshopSearchStore()
const permissions = useWorkshopPermissions()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const { t } = useI18n()

/** Shorthand for the role-scoped messages the shell reads a dozen times. */
const roleText = (name: string) => t(roleMessageKey(config.role, name))

// Profile / sessions / log out — the three things an avatar is expected to
// offer. No confirm on the way out: logging out is not destructive, and
// DESIGN.md prefers undo over a nag (QAD-182).
const accountMenuItems = computed(() => [
  { label: t('shell.account.profile') },
  { label: t('shell.account.sessions') },
  { label: t('shell.account.logout'), danger: true },
])

async function onAccountMenuSelect(index: number) {
  if (index === 0) {
    void router.push(config.profilePath)
    return
  }
  if (index === 1) {
    void router.push({ path: config.profilePath, query: { tab: 'sessions' } })
    return
  }
  try {
    await auth.logoutCurrent()
    await router.replace(config.loginPath)
  } catch {
    toast.danger(t('shell.account.logoutFailed'))
  }
}
const rolePath = useRolePath()
const selectedContext = ref(config.dropdownOptions[0]?.value ?? '')
const workshopSearchRootRef = ref<HTMLElement | null>(null)
const workshopSearchInputRef = ref<HTMLInputElement | null>(null)
const workshopSearchQuery = ref('')
const workshopSearchOpen = ref(false)
let workshopSearchTimer: number | undefined
const {
  mobileNavOpen,
  mobileTriggerRef,
  drawerPanelRef,
  openMobileNav,
  closeMobileNav,
  onDrawerKeydown,
} = useMobileNav({
  // The search panel is a teleported overlay of the topbar the drawer covers;
  // leaving it open would float it over the scrim with nothing behind it.
  onBeforeOpen: () => closeWorkshopSearch(),
})
const isChromeless = computed(() => isChromelessLayout(route.meta.layout))
// The order-drawing flow builds one document start to finish; a topbar field
// offering to jump to a different order is the one thing those screens are not
// for. Declared per route so a new screen in the flow opts in where it is
// defined, not in a path list here.
const showWorkshopSearch = computed(() => route.meta.hideSearch !== true)
const canLoadWorkshopContext = computed(
  () => auth.isAllowedFor('workshop') && auth.me?.password_reset_required === false,
)
const contextStorageKey = computed(() =>
  auth.me ? workshopContextStorageKey(auth.me.principal_id, auth.me.session_id) : null,
)
// Settings first so an owner's rename shows without a reload; `me` is the
// source everyone else has, because `/workshop/settings` is owner-only and
// staff used to fall through to the generic label (QAD-168).
const tenantLabel = computed(
  () => workshopTenantName(workshop.settings?.name, auth.me?.workshop_name) ?? roleText('tenant'),
)
const tenantMeta = computed(() => {
  if (!auth.me) return roleText('tenantMeta')
  return auth.me.is_owner ? t('shell.tenant.ownerMeta') : grantSummary(false, auth.me.grants)
})
// The sidebar's user button reads the ROLE: the grant summary lost its own render
// site when the branch picker took the card above it, and a role is the more
// useful second line under a name. The password-reset warning still wins — it is
// the only place that state stays visible in the workshop chrome.
const workshopUserMeta = computed(() =>
  auth.me?.password_reset_required ? t('shell.tenant.passwordResetHint') : tenantMeta.value,
)
// `aria-label` on the trigger REPLACES its contents, so the meta line — the role,
// or the password-reset warning, which the workshop chrome shows nowhere else —
// dropped out of the accessible name the moment the plain RouterLink became an
// ActionMenu. Fold it back in rather than leaving a screen reader with the name
// alone.
const accountMenuLabel = computed(() =>
  workshopUserMeta.value
    ? t('shell.account.menuAriaWithMeta', {
        name: auth.displayName,
        meta: workshopUserMeta.value,
      })
    : t('shell.account.menuAria', { name: auth.displayName }),
)
const tenantInitial = computed(() =>
  (tenantLabel.value.trim().slice(0, 1) || roleText('label')[0]).toUpperCase(),
)
const workshopUserInitials = computed(() => initials(auth.displayName, 'MP'))
const dropdownOptions = computed(() => {
  if (workshop.branches.length === 0) {
    return [
      {
        value: 'none',
        label: t('shell.branch.none'),
        meta: t('shell.branch.noneMeta'),
        status: 'pending' as const,
      },
    ]
  }
  return workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta:
      branch.status === 'temporarily_closed' ? t('shell.branch.temporarilyClosed') : branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  }))
})
const visibleNav = computed<NavItem[]>(() =>
  workshopNavItems({
    isOwner: auth.me?.is_owner === true,
    branches: workshop.branches,
    selectedBranchId: selectedContext.value,
    path: rolePath,
  }),
)
const selectedWorkshopBranch = computed(() =>
  workshop.branches.find((branch) => branch.id === selectedContext.value),
)
// The branch switcher only earns a listbox when there's a real choice. With a
// single branch (or none) the context auto-pins to it, so the sidebar renders the
// same card as an inert block — same geometry, no chevron — rather than changing
// the column's shape between workshops.
const showBranchSwitcher = computed(() => workshop.branches.length > 1)
// The branch card's second line. Reads the option list, not `workshop.branches`,
// so the zero-branch case shows "Filial yo'q" instead of going blank.
const selectedBranchLabel = computed(
  () =>
    dropdownOptions.value.find((option) => option.value === selectedContext.value)?.label ??
    dropdownOptions.value[0]?.label ??
    '',
)
// Not every page reads the branch context: some are workshop-wide by design
// (debts, settings, branches, notifications, profile), others take their branch
// from the record being viewed. Each route declares which it is; on the two
// non-branch kinds the picker renders disabled with a hint rather than sitting
// there looking live and silently doing nothing.
const branchScope = computed(() => branchScopeOf(route.meta.branchScope))
const branchPickerDisabled = computed(() => branchScope.value !== 'branch')
const branchPickerHint = computed(() =>
  branchScope.value === 'branch' ? null : branchScopeHint(branchScope.value),
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
const navGroups = computed(() => groupedNav(visibleNav.value))
// Sidebar `+N` badge on Buyurtmalar (QAD-156): a live count of orders still in
// NEW for the selected branch, so staff notice an arrival without being on the
// board. Not an unread counter — it falls on its own as orders get confirmed.
const ordersNavPath = computed(() => rolePath('/workshop/orders'))
const canSeeOrdersNav = computed(() =>
  visibleNav.value.some((item) => item.to === ordersNavPath.value),
)
const newOrderBadge = computed(() => {
  if (!canSeeOrdersNav.value || orders.newOrderCount < 1) return null
  return orders.newOrderCount > 99 ? '99+' : String(orders.newOrderCount)
})
// Kesish / Krom carry a plain number: how many jobs wait in the signed-in user's
// OWN queue. The backend scopes `/production/queue` to the caller's assignments
// for everyone, owner included, so this is exactly the figure the station page
// shows — never a workshop-wide total the operator cannot act on.
const cuttingNavPath = computed(() => rolePath('/workshop/cutting'))
const bandingNavPath = computed(() => rolePath('/workshop/banding'))
const canSeeProductionNav = computed(() =>
  visibleNav.value.some((item) => item.to === cuttingNavPath.value),
)
const productionNavCounts = computed(() => {
  const counts = new Map<string, number>()
  if (!canSeeProductionNav.value) return counts
  const cutting = production.queues.cutting?.jobs.length ?? 0
  const banding = production.queues.banding?.jobs.length ?? 0
  if (cutting > 0) counts.set(cuttingNavPath.value, cutting)
  if (banding > 0) counts.set(bandingNavPath.value, banding)
  return counts
})
// The badge and the count are decorative; the figure belongs to the link's own
// name so a screen reader hears "Buyurtmalar — 4 ta yangi buyurtma" in one go.
function navAriaLabel(item: NavItem) {
  if (item.to === ordersNavPath.value && newOrderBadge.value) {
    return t(
      'shell.nav.newOrdersAria',
      { label: t(item.labelKey), n: orders.newOrderCount },
      orders.newOrderCount,
    )
  }
  const queued = productionNavCounts.value.get(item.to)
  if (queued === undefined) return undefined
  return t('shell.nav.queuedAria', { label: t(item.labelKey), n: queued }, queued)
}
// `+ Yangi buyurtma` lives in the sidebar now, so it carries the same gate the
// route does: the walk-in flow is fixed to the selected branch, which must be
// open and must be one the staffer may place orders on. When it fails the control
// renders as a disabled button with the reason — never a link, because a link
// that bounces off the route guard is a dead end that looks live.
const canCreateOrder = computed(() => {
  const branch = selectedWorkshopBranch.value
  return (
    !!branch && branch.status === 'active' && permissions.canOnBranch(p.manageOrders, branch.id)
  )
})

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
  if (isChromeless.value || !showWorkshopSearch.value) return
  // The search field lives in the topbar, which the drawer covers. Honouring ⌘K
  // there would move focus outside an `aria-modal` dialog — and the drawer's own
  // focus guard would immediately pull it back, leaving the keypress looking
  // broken. The drawer is modal: it owns the keyboard until it closes.
  if (mobileNavOpen.value) return
  workshopSearchOpen.value = true
  void nextTick(() => {
    workshopSearchInputRef.value?.focus()
    workshopSearchInputRef.value?.select()
  })
}

// Returns the run so a caller that needs the results (Enter) can await it.
// Fire-and-forget is still correct for the debounce path.
function runWorkshopSearchNow(): Promise<void> {
  window.clearTimeout(workshopSearchTimer)
  if (!canSearchWorkshop.value || !hasWorkshopSearchQuery.value) {
    workshopSearch.reset()
    return Promise.resolve()
  }
  return workshopSearch.search({
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

async function submitWorkshopSearch() {
  workshopSearchOpen.value = true
  // Awaited, not fired and forgotten: reading the store on the next line used to
  // see the *previous* query's results, because the debounce (220 ms) plus the
  // request had not finished. Pressing Enter right after typing therefore did
  // nothing, or opened the order matching what you typed a moment earlier.
  await runWorkshopSearchNow()
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
  if (!workshopSearchOpen.value) return
  const target = event.target
  if (target instanceof Node && workshopSearchRootRef.value?.contains(target)) return
  closeWorkshopSearch()
}

function onGlobalKeydown(event: KeyboardEvent) {
  if (isChromeless.value) return
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
  if (!canLoadWorkshopContext.value || !canSeeOrdersNav.value) return
  void orders.loadNewOrderCount(selectedWorkshopBranch.value?.id ?? null)
}

// Same rhythm for the two station counts, and only for a user who actually has
// the stations in their nav — nobody else may read the queue.
//
// Two things this must NOT do, both learned the hard way. It must not skip while
// `production.loading`: the first run fires before the branch context resolves,
// so it asks for every branch, and a skip then dropped the branch-scoped refetch
// that followed and left the badge counting the wrong workshop. And it must not
// run at all while the user is standing on a station page — that page owns the
// same store, so a shell refresh that fails would swap its loaded queue for a
// full-page error the operator never asked for. `requestedProductionBranch`
// replaces the loading skip: it collapses a repeat of the same question without
// swallowing a different one. `undefined` means "not asked yet", distinct from a
// null (all-branches) context.
let requestedProductionBranch: string | undefined
const onStationPage = computed(
  () =>
    route.path === rolePath('/workshop/cutting') || route.path === rolePath('/workshop/banding'),
)

function reloadProductionCounts(force = false) {
  if (!canLoadWorkshopContext.value || !canSeeProductionNav.value) {
    return
  }
  if (onStationPage.value) {
    // Forget what we asked for while the page owns the store, so stepping back
    // onto Asosiy always re-asks. Skipping without clearing the key left the
    // badge frozen at whatever the station page happened to leave behind.
    requestedProductionBranch = undefined
    return
  }
  // Keyed by principal as well as branch: `WorkshopShell` is never remounted
  // across a logout, so a plain branch key would tell the next user's identical
  // branch that the question had already been asked.
  const key = `${auth.me?.principal_id ?? ''}:${selectedWorkshopBranch.value?.id ?? ''}`
  if (!force && requestedProductionBranch === key) return
  requestedProductionBranch = key
  void production.loadQueues(['cutting', 'banding'], selectedWorkshopBranch.value?.id ?? null)
}

function onVisibilityChange() {
  if (document.visibilityState !== 'visible') return
  reloadNewOrderCount()
  // Coming back to the tab is the one moment the counts are worth re-asking for
  // even when the branch has not moved.
  reloadProductionCounts(true)
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
    workshop.setSelectedBranchContext(value)
    const storage = browserStorage()
    if (!storage || !contextStorageKey.value) return
    persistStoredContext(storage, contextStorageKey.value, value, dropdownOptions.value)
  },
  { immediate: true },
)

watch(
  () => workshop.selectedBranchContext,
  (value) => {
    if (!value || selectedContext.value === value) return
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
    queueWorkshopSearch()
  },
)

// The branch (or the right to see orders at all) only settles once the branch
// context has loaded, so drive the count off that instead of a bare onMounted.
watch([() => selectedWorkshopBranch.value?.id, canSeeOrdersNav], reloadNewOrderCount, {
  immediate: true,
})

// Wrapped, not passed by reference: a watcher hands its new value to the
// callback, which would land in `force` and turn every branch tick into an
// unconditional refetch.
watch(
  [() => selectedWorkshopBranch.value?.id, canSeeProductionNav],
  () => reloadProductionCounts(),
  {
    immediate: true,
  },
)

// The order-mutation half of the rhythm. The orders store owns that hook for the
// new-order badge; the station counts have to read it from outside, so watch the
// open order's version: a bump on the SAME order is a mutation (assign, start,
// finish — all of which move a queue), while a different id is just another order
// being opened and must not cost a request.
watch(
  () => (orders.currentOrder ? `${orders.currentOrder.id}:${orders.currentOrder.version}` : ''),
  (stamp, previous) => {
    if (!stamp || !previous) return
    if (stamp.split(':')[0] !== previous.split(':')[0]) return
    // The branch has not moved, the queue has — this one has to bypass the
    // same-branch dedupe.
    reloadProductionCounts(true)
  },
)

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
})
</script>

<template>
  <div v-if="isChromeless" class="min-h-[var(--app-vh)] bg-bg text-ink">
    <RouterView />
  </div>

  <div v-else class="workshop-app">
    <aside class="workshop-sidebar" :aria-label="$t('shell.a11y.workshopNav')">
      <RouterLink :to="config.homePath" class="workshop-brand" @click="closeMobileNav">
        <!-- The mark is markup, not the favicon: a graphite tile with two Display
             800 letters around a 2px orange cut (DESIGN.md → Brand). -->
        <BrandMark :size="32" />
        <span class="workshop-brand-copy">
          <span class="workshop-brand-name">{{ config.productLabel }}</span>
          <span class="workshop-brand-role">{{ roleText('label') }}</span>
        </span>
      </RouterLink>

      <ProjectDropdown
        v-if="showBranchSwitcher"
        v-model="selectedContext"
        class="workshop-branch-card"
        :label="roleText('dropdown')"
        :options="dropdownOptions"
        :disabled="branchPickerDisabled"
        :hint="branchPickerHint"
        trigger-class="workshop-branch"
        hint-class="workshop-branch-hint"
      >
        <!-- The slot replaces the primitive's own one-line trigger, so the label
             comes along as screen-reader text or the button's name would read as
             two bare proper nouns. -->
        <template #trigger="{ selected }">
          <span class="sr-only">{{ roleText('dropdown') }}</span>
          <span class="workshop-branch-avatar" aria-hidden="true">{{ tenantInitial }}</span>
          <span class="workshop-branch-copy">
            <span class="workshop-branch-name">{{ tenantLabel }}</span>
            <span class="workshop-branch-meta">{{ selected.label }}</span>
          </span>
          <svg
            class="workshop-branch-chevron"
            viewBox="0 0 24 24"
            aria-hidden="true"
            v-html="iconPath('chevron-right')"
          ></svg>
        </template>
      </ProjectDropdown>
      <!-- One branch (or none): the same card, inert. Keeping its geometry means
           the sidebar does not change shape between workshops. -->
      <div v-else class="workshop-branch-card">
        <div class="workshop-branch is-static">
          <span class="workshop-branch-avatar" aria-hidden="true">{{ tenantInitial }}</span>
          <span class="workshop-branch-copy">
            <span class="workshop-branch-name">{{ tenantLabel }}</span>
            <span class="workshop-branch-meta">{{ selectedBranchLabel }}</span>
          </span>
        </div>
      </div>

      <!-- Outside the <nav> on purpose: it is an action, not a destination, and
           the nav's link list is asserted item-for-item against the grant set. -->
      <RouterLink
        v-if="canCreateOrder"
        :to="rolePath('/workshop/orders/new')"
        class="workshop-create"
        @click="closeMobileNav"
      >
        {{ $t('orders.list.create') }}
      </RouterLink>
      <button
        v-else
        class="workshop-create"
        type="button"
        disabled
        :title="$t('orders.list.createBlocked')"
      >
        {{ $t('orders.list.create') }}
      </button>

      <nav class="workshop-nav" :aria-label="$t('shell.a11y.mainNav')">
        <section v-for="group in navGroups" :key="group.id" class="workshop-nav-group">
          <div class="workshop-nav-label">{{ t(`nav.group.${group.id}`) }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="workshop-nav-item"
            active-class="on"
            :aria-label="navAriaLabel(item)"
          >
            <span class="workshop-nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" v-html="iconPath(item.icon)"></svg>
            </span>
            <span>{{ t(item.labelKey) }}</span>
            <span
              v-if="newOrderBadge && item.to === ordersNavPath"
              class="workshop-nav-badge"
              aria-hidden="true"
              >{{ newOrderBadge }}</span
            >
            <span
              v-else-if="productionNavCounts.get(item.to)"
              class="workshop-nav-count"
              aria-hidden="true"
              >{{ productionNavCounts.get(item.to) }}</span
            >
          </RouterLink>
        </section>
      </nav>

      <!-- The class goes on the component so it lands on ActionMenu's root
           wrapper: the sidebar's last row is this block, and the frame test
           measures it as a direct child of `.workshop-sidebar`. -->
      <ActionMenu
        class="workshop-user-card"
        :items="accountMenuItems"
        :label="accountMenuLabel"
        trigger-class="workshop-user-trigger"
        @select="onAccountMenuSelect"
      >
        <template #trigger>
          <span class="workshop-user-avatar" aria-hidden="true">{{ workshopUserInitials }}</span>
          <span class="workshop-user-copy">
            <span class="workshop-user-name">{{ auth.displayName }}</span>
            <span class="workshop-user-meta">{{ workshopUserMeta }}</span>
          </span>
          <svg
            class="workshop-user-chevron"
            viewBox="0 0 24 24"
            aria-hidden="true"
            v-html="iconPath('chevron-down')"
          ></svg>
        </template>
      </ActionMenu>
    </aside>

    <div
      v-if="mobileNavOpen"
      class="workshop-drawer"
      role="dialog"
      aria-modal="true"
      aria-labelledby="workshop-mobile-drawer-title"
      @keydown="onDrawerKeydown"
    >
      <button
        class="workshop-drawer-scrim"
        type="button"
        :aria-label="$t('shell.a11y.closeMenu')"
        @click="closeMobileNav"
      ></button>
      <!-- Below 921px the sidebar IS this drawer, so it carries the sidebar's
           whole content. Branch switching, order creation and logging out live
           nowhere else on a phone. -->
      <div ref="drawerPanelRef" class="workshop-drawer-panel" tabindex="-1">
        <div class="workshop-drawer-head">
          <span class="workshop-brand">
            <BrandMark :size="32" />
            <span class="workshop-brand-copy">
              <span id="workshop-mobile-drawer-title" class="workshop-brand-name">
                {{ config.productLabel }}
              </span>
              <span class="workshop-brand-role">{{ roleText('label') }}</span>
            </span>
          </span>
          <button
            class="workshop-icon-button"
            type="button"
            :aria-label="$t('shell.a11y.closeMenu')"
            @click="closeMobileNav"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('close')"></svg>
          </button>
        </div>

        <ProjectDropdown
          v-if="showBranchSwitcher"
          v-model="selectedContext"
          class="workshop-branch-card"
          :label="roleText('dropdown')"
          :options="dropdownOptions"
          :disabled="branchPickerDisabled"
          :hint="branchPickerHint"
          trigger-class="workshop-branch"
          hint-class="workshop-branch-hint"
        >
          <template #trigger="{ selected }">
            <span class="sr-only">{{ roleText('dropdown') }}</span>
            <span class="workshop-branch-avatar" aria-hidden="true">{{ tenantInitial }}</span>
            <span class="workshop-branch-copy">
              <span class="workshop-branch-name">{{ tenantLabel }}</span>
              <span class="workshop-branch-meta">{{ selected.label }}</span>
            </span>
            <svg
              class="workshop-branch-chevron"
              viewBox="0 0 24 24"
              aria-hidden="true"
              v-html="iconPath('chevron-right')"
            ></svg>
          </template>
        </ProjectDropdown>
        <div v-else class="workshop-branch-card">
          <div class="workshop-branch is-static">
            <span class="workshop-branch-avatar" aria-hidden="true">{{ tenantInitial }}</span>
            <span class="workshop-branch-copy">
              <span class="workshop-branch-name">{{ tenantLabel }}</span>
              <span class="workshop-branch-meta">{{ selectedBranchLabel }}</span>
            </span>
          </div>
        </div>

        <RouterLink
          v-if="canCreateOrder"
          :to="rolePath('/workshop/orders/new')"
          class="workshop-create"
          @click="closeMobileNav"
        >
          {{ $t('orders.list.create') }}
        </RouterLink>
        <button
          v-else
          class="workshop-create"
          type="button"
          disabled
          :title="$t('orders.list.createBlocked')"
        >
          {{ $t('orders.list.create') }}
        </button>

        <nav class="workshop-nav" :aria-label="$t('shell.a11y.mobileNav')">
          <section v-for="group in navGroups" :key="`m-${group.id}`" class="workshop-nav-group">
            <div class="workshop-nav-label">{{ t(`nav.group.${group.id}`) }}</div>
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
              <span>{{ t(item.labelKey) }}</span>
              <span
                v-if="newOrderBadge && item.to === ordersNavPath"
                class="workshop-nav-badge"
                aria-hidden="true"
                >{{ newOrderBadge }}</span
              >
              <span
                v-else-if="productionNavCounts.get(item.to)"
                class="workshop-nav-count"
                aria-hidden="true"
                >{{ productionNavCounts.get(item.to) }}</span
              >
            </RouterLink>
          </section>
        </nav>

        <ActionMenu
          class="workshop-user-card"
          :items="accountMenuItems"
          :label="accountMenuLabel"
          trigger-class="workshop-user-trigger"
          @select="onAccountMenuSelect"
        >
          <template #trigger>
            <span class="workshop-user-avatar" aria-hidden="true">{{ workshopUserInitials }}</span>
            <span class="workshop-user-copy">
              <span class="workshop-user-name">{{ auth.displayName }}</span>
              <span class="workshop-user-meta">{{ workshopUserMeta }}</span>
            </span>
            <svg
              class="workshop-user-chevron"
              viewBox="0 0 24 24"
              aria-hidden="true"
              v-html="iconPath('chevron-down')"
            ></svg>
          </template>
        </ActionMenu>
      </div>
    </div>

    <main class="workshop-main">
      <header class="workshop-topbar">
        <button
          ref="mobileTriggerRef"
          class="workshop-mobile-button"
          type="button"
          :aria-label="$t('shell.a11y.menu')"
          @click="openMobileNav"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" v-html="iconPath('menu')"></svg>
        </button>

        <div v-if="showWorkshopSearch" ref="workshopSearchRootRef" class="workshop-search-wrap">
          <label class="workshop-search" for="workshop-global-search">
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle cx="8.5" cy="8.5" r="5.5"></circle>
              <path d="m13 13 4 4"></path>
            </svg>
            <span class="sr-only">{{ $t('shell.search.label') }}</span>
            <input
              id="workshop-global-search"
              ref="workshopSearchInputRef"
              v-model="workshopSearchQuery"
              :placeholder="$t('shell.search.placeholder')"
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
            :aria-label="$t('shell.search.resultsAria')"
            :aria-busy="workshopSearch.loading"
          >
            <div v-if="!canSearchWorkshop" class="workshop-search-empty">
              {{ $t('shell.search.noPermission') }}
            </div>
            <div v-else-if="!hasWorkshopSearchQuery" class="workshop-search-empty">
              {{ $t('shell.search.minChars') }}
            </div>
            <!-- Only blank on the FIRST search. Once there are results, keep them
                 on screen while the next query loads: `loading` stays true until
                 the slowest of four requests lands, so tearing them out meant the
                 panel went empty on every typing pause. -->
            <div
              v-else-if="workshopSearch.loading && workshopSearchResultCount === 0"
              class="workshop-search-empty"
            >
              {{ $t('shell.search.searching') }}
            </div>
            <template v-else>
              <p v-if="workshopSearch.error" class="workshop-search-error">
                {{ $t('shell.search.partialError') }}
                <span v-if="workshopSearch.traceId">Trace: {{ workshopSearch.traceId }}</span>
              </p>

              <div v-if="workshopSearch.results.orders.length" class="workshop-search-section">
                <div class="workshop-search-section-title">
                  {{ $t('shell.search.sectionOrders') }}
                </div>
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
                  <em>{{ workshopStatusUz(order.status) }}</em>
                </RouterLink>
              </div>

              <div v-if="workshopSearch.results.users.length" class="workshop-search-section">
                <div class="workshop-search-section-title">
                  {{ $t('shell.search.sectionUsers') }}
                </div>
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
                  <em>{{
                    user.status === 'active'
                      ? $t('shell.search.userActive')
                      : $t('shell.search.userBlocked')
                  }}</em>
                </RouterLink>
              </div>

              <div v-if="workshopSearch.results.materials.length" class="workshop-search-section">
                <div class="workshop-search-section-title">
                  {{ $t('shell.search.sectionMaterials') }}
                </div>
                <RouterLink
                  v-for="row in workshopSearch.results.materials"
                  :key="row.id"
                  class="workshop-search-result"
                  :to="searchDestination('/workshop/catalog', row.decor.name)"
                  @click="closeWorkshopSearch"
                >
                  <span>
                    <strong>{{ row.label }}</strong>
                    <small>
                      {{ row.decor.manufacturer_name }} ·
                      {{ decorTypeLabel(row.decor_format.type) }}
                    </small>
                  </span>
                  <em>{{
                    row.status === 'active'
                      ? $t('shell.search.materialActive')
                      : $t('shell.search.materialHidden')
                  }}</em>
                </RouterLink>
              </div>

              <div v-if="workshopSearch.results.stock.length" class="workshop-search-section">
                <div class="workshop-search-section-title">
                  {{ $t('shell.search.sectionStock') }}
                </div>
                <RouterLink
                  v-for="item in workshopSearch.results.stock"
                  :key="item.id"
                  class="workshop-search-result"
                  :to="searchDestination('/workshop/inventory', item.material.decor.name)"
                  @click="closeWorkshopSearch"
                >
                  <span>
                    <strong>{{ item.material.label }}</strong>
                    <small>
                      {{ item.material.decor.manufacturer_name }} · {{ item.display_unit }}
                    </small>
                  </span>
                  <em :class="{ danger: item.is_low_stock }">
                    {{
                      item.is_low_stock ? $t('shell.search.stockLow') : $t('shell.search.stockOk')
                    }}
                  </em>
                </RouterLink>
              </div>

              <div v-if="workshopSearchResultCount === 0" class="workshop-search-empty">
                {{ $t('shell.search.empty') }}
              </div>

              <div class="workshop-search-shortcuts">
                <RouterLink
                  v-if="canSearchOrders"
                  :to="searchDestination('/workshop/orders')"
                  @click="closeWorkshopSearch"
                >
                  {{ $t('shell.search.openInOrders') }}
                </RouterLink>
                <RouterLink
                  v-if="canSearchCatalog"
                  :to="searchDestination('/workshop/catalog')"
                  @click="closeWorkshopSearch"
                >
                  {{ $t('shell.search.openInCatalog') }}
                </RouterLink>
                <RouterLink
                  v-if="canSearchInventory"
                  :to="searchDestination('/workshop/inventory')"
                  @click="closeWorkshopSearch"
                >
                  {{ $t('shell.search.openInInventory') }}
                </RouterLink>
                <RouterLink
                  v-if="canSearchUsers"
                  :to="searchDestination('/workshop/settings/users')"
                  @click="closeWorkshopSearch"
                >
                  {{ $t('shell.search.openInUsers') }}
                </RouterLink>
              </div>
            </template>
          </div>
        </div>

        <!-- Locale and notifications, and nothing else. The account menu moved
             down to the sidebar's user button, where the name it belongs to is
             already on screen (QAD-182 kept it one click from the avatar). -->
        <div class="workshop-top-actions">
          <LocaleSwitcher />
          <NotificationsMenu />
        </div>
      </header>

      <section class="workshop-page">
        <RouterView />
      </section>
      <OnboardingSpotlight />
    </main>
  </div>

  <ToastHost />
</template>
