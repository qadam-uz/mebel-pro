<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import {
  persistStoredContext,
  readStoredContext,
  workshopContextStorageKey,
} from '@/shared/app/contextStorage'
import { useRoleConfig, type NavItem } from '@/shared/app/roleConfig'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

const config = useRoleConfig()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const route = useRoute()
const selectedContext = ref(config.dropdownOptions[0]?.value ?? '')
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
  auth.me?.password_reset_required ? 'password change required' : auth.displayName,
)
const dropdownOptions = computed(() => {
  if (config.role !== 'workshop') return config.dropdownOptions
  if (workshop.branches.length === 0) {
    return [
      {
        value: 'none',
        label: 'No accessible branch',
        meta: 'account controls only',
        status: 'pending' as const,
      },
    ]
  }
  return workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.status === 'temporarily_closed' ? 'temporarily closed' : branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  }))
})
const visibleNav = computed<NavItem[]>(() => {
  if (config.role !== 'workshop') return config.nav
  const nav: NavItem[] = [{ label: 'Dashboard', to: '/workshop' }]
  if (auth.me?.is_owner) {
    nav.push({ label: 'Branches', to: '/workshop/branches' })
    nav.push({ label: 'Users', to: '/workshop/settings/users' })
  } else {
    const selectedBranch = workshop.branches.find((branch) => branch.id === selectedContext.value)
    const branch = selectedBranch ?? workshop.branches[0]
    if (branch) nav.push({ label: 'Branch workspace', to: `/workshop/branches/${branch.id}` })
  }
  nav.push({ label: 'Profile', to: '/workshop/profile' })
  return nav
})

function isExternal(to: string) {
  return to.startsWith('/docs') || to.startsWith('/api-docs') || to.startsWith('/api-redoc')
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
</script>

<template>
  <div v-if="isAuthRoute" class="min-h-screen bg-bg text-ink">
    <RouterView />
  </div>

  <div v-else class="min-h-screen bg-bg text-ink lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
    <aside
      class="hidden border-r border-hairline bg-elevated bg-[radial-gradient(120%_60%_at_0%_0%,#e9f6f4,transparent_62%)] px-4 py-5 lg:flex lg:min-h-screen lg:flex-col"
      aria-label="Primary"
    >
      <RouterLink
        :to="config.homePath"
        class="flex items-center gap-3 border-b border-hairline pb-5 no-underline"
      >
        <img src="/favicon.svg" alt="" class="size-8" />
        <span>
          <span class="block font-serif text-lg font-semibold text-ink">{{
            config.productLabel
          }}</span>
          <span class="block text-[10px] font-extrabold uppercase tracking-[0.16em] text-ink-muted">
            {{ config.roleLabel }}
          </span>
        </span>
      </RouterLink>

      <div class="mt-5 rounded-lg border border-hairline bg-sunk p-3">
        <div class="flex items-center gap-3">
          <span
            class="grid size-8 place-items-center rounded-md bg-accent font-serif text-sm font-bold text-white"
            aria-hidden="true"
          >
            {{ config.roleLabel.slice(0, 1) }}
          </span>
          <span class="min-w-0">
            <span class="block truncate text-sm font-bold text-ink">{{ config.tenantLabel }}</span>
            <span class="block truncate font-mono text-[11px] text-ink-muted">
              {{ config.tenantMeta }}
            </span>
          </span>
        </div>
      </div>

      <nav class="mt-5 flex flex-1 flex-col gap-1">
        <template v-for="item in visibleNav" :key="item.to">
          <a
            v-if="isExternal(item.to)"
            :href="item.to"
            class="rounded-md px-3 py-2 text-sm font-bold text-ink-soft transition hover:bg-sunk hover:text-ink"
          >
            {{ item.label }}
          </a>
          <RouterLink
            v-else
            :to="item.to"
            class="rounded-md px-3 py-2 text-sm font-bold text-ink-soft transition hover:bg-sunk hover:text-ink"
            active-class="bg-accent text-white hover:bg-accent hover:text-white"
          >
            {{ item.label }}
          </RouterLink>
        </template>
      </nav>

      <RouterLink
        :to="config.profilePath"
        class="mt-5 rounded-lg border border-transparent bg-sunk px-3 py-3 no-underline transition hover:border-hairline-strong"
      >
        <span class="block text-sm font-bold text-ink">{{ config.roleLabel }} profile</span>
        <span class="block truncate font-mono text-[11px] text-ink-muted">
          {{ profileSubtitle }}
        </span>
      </RouterLink>
    </aside>

    <div class="flex min-w-0 flex-col">
      <header
        class="sticky top-0 z-30 border-b border-hairline bg-elevated/90 px-4 py-3 backdrop-blur lg:px-7"
      >
        <div class="flex flex-wrap items-center gap-3">
          <RouterLink :to="config.homePath" class="flex items-center gap-2 lg:hidden">
            <img src="/favicon.svg" alt="" class="size-8" />
            <span class="font-serif text-lg font-semibold">{{ config.productLabel }}</span>
          </RouterLink>

          <ProjectDropdown
            v-model="selectedContext"
            :label="config.dropdownLabel"
            :options="dropdownOptions"
          />

          <nav class="ml-auto flex flex-wrap items-center gap-2" aria-label="Top">
            <template v-for="item in visibleNav" :key="`top-${item.to}`">
              <a
                v-if="isExternal(item.to)"
                :href="item.to"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              >
                {{ item.label }}
              </a>
              <RouterLink
                v-else
                :to="item.to"
                class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              >
                {{ item.label }}
              </RouterLink>
            </template>
          </nav>
        </div>
      </header>

      <main class="min-w-0 flex-1 px-4 py-6 lg:px-7 lg:py-7">
        <RouterView />
      </main>
    </div>
  </div>
</template>
