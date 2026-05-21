<script setup lang="ts">
// Workshop app shell — sidebar (.sb-*) + top bar (.tb-*) with the branch
// picker, search and the notification bell. Nav items are gated by the auth
// store's can()/isOwner, mirroring the prototype's workshop-shell.js NAV.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NotificationBell, ToastHost } from '@/shared/ui'
import { initialsOf } from '@/shared/format'
import { t } from '@/shared/i18n'
import type { Permission } from '@/shared/types'
import { useWorkshopAuth } from '../store'
import { useBranchesStore } from '../stores/branches'
import { pickerBranchIds as computePickerBranchIds } from '../lib/branches'

const auth = useWorkshopAuth()
const branchesStore = useBranchesStore()
const router = useRouter()
const drawerOpen = ref(false)
const branchPopOpen = ref(false)

// The branches the principal may scope to. Owner sees all loaded branches;
// staff see only the branches they hold any grant on (or their home branch).
const pickerBranchIds = computed(() =>
  computePickerBranchIds(
    auth.isOwner,
    branchesStore.branches.map((b) => b.id),
    auth.grants,
    auth.me?.home_branch_id ?? null,
  ),
)

onMounted(() => branchesStore.load())

interface NavItem {
  to: string
  ic: string
  label: string
  gate: 'owner' | Permission[] | null
}
interface NavGroup {
  label: string
  items: NavItem[]
}

const NAV: NavGroup[] = [
  {
    label: t('nav.grpManagement'),
    items: [
      { to: '/workshop', ic: '◐', label: t('nav.dashboard'), gate: null },
      {
        to: '/workshop/orders',
        ic: '▣',
        label: t('nav.orders'),
        gate: ['manage_orders', 'view_dashboard'],
      },
    ],
  },
  {
    label: t('nav.grpProduction'),
    items: [
      {
        to: '/workshop/cutting',
        ic: '⌥',
        label: t('nav.cuttingQueue'),
        gate: ['process_production'],
      },
      {
        to: '/workshop/banding',
        ic: '▥',
        label: t('nav.bandingQueue'),
        gate: ['process_production'],
      },
    ],
  },
  {
    label: t('nav.grpResources'),
    items: [
      { to: '/workshop/branches', ic: '◫', label: t('nav.workshopBranches'), gate: 'owner' },
      { to: '/workshop/settings/users', ic: '◆', label: t('nav.users'), gate: 'owner' },
    ],
  },
  {
    label: t('nav.grpFinance'),
    items: [
      {
        to: '/workshop/finance',
        ic: '∑',
        label: t('nav.financeReports'),
        gate: ['manage_finance', 'view_finance_reports'],
      },
      {
        to: '/workshop/finance/expenses',
        ic: '↕',
        label: t('nav.expenses'),
        gate: ['manage_finance', 'view_finance_reports'],
      },
    ],
  },
  {
    label: t('nav.grpSystem'),
    items: [{ to: '/workshop/settings', ic: '⚙', label: t('nav.settings'), gate: 'owner' }],
  },
]

function visible(item: NavItem): boolean {
  if (item.gate == null) return true
  if (item.gate === 'owner') return auth.isOwner
  return item.gate.some((p) => auth.can(p))
}

const groups = computed(() =>
  NAV.map((g) => ({ label: g.label, items: g.items.filter(visible) })).filter(
    (g) => g.items.length,
  ),
)

const meName = computed(() => auth.me?.full_name ?? '—')
const meInitials = computed(() => initialsOf(auth.me?.full_name))
const meSummary = computed(() =>
  auth.isOwner ? 'Egasi · barcha ruxsatlar' : `${auth.grants.length} grant`,
)

function selectBranch(selection: string) {
  auth.selectBranch(selection)
  branchPopOpen.value = false
}

const branchLabel = computed(() =>
  auth.selectedBranch === 'all'
    ? t('branchPicker.allBranches')
    : branchesStore.nameOf(auth.selectedBranch),
)

async function onSignOut() {
  await auth.logout()
  router.push('/auth/login')
}
</script>

<template>
  <div class="app">
    <aside class="sb">
      <RouterLink class="sb-brand" to="/workshop">
        <span class="mk">M</span>
        <span class="nm">{{ t('common.appName') }}<small>boshqaruv</small></span>
      </RouterLink>
      <div class="sb-tenant">
        <span class="av">{{ meInitials }}</span>
        <div class="info">
          <div class="nm">{{ meName }}</div>
          <div class="role">{{ meSummary }}</div>
        </div>
      </div>
      <nav class="sb-nav">
        <div v-for="group in groups" :key="group.label" class="sb-grp">
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
      </nav>
      <div class="sb-foot">
        <RouterLink class="sb-user" to="/workshop/profile">
          <span class="av">{{ meInitials }}</span>
          <div class="info" style="min-width: 0; flex: 1">
            <div class="nm">{{ meName }}</div>
            <div class="rl">{{ meSummary }}</div>
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

        <div class="br-picker" @click.stop="branchPopOpen = !branchPopOpen">
          <span class="ic" />
          <div>
            <div class="nm">{{ branchLabel }}</div>
            <div class="sub">{{ pickerBranchIds.length }} filial</div>
          </div>
          <div v-if="branchPopOpen" class="br-pop">
            <div
              class="it"
              :class="{ on: auth.selectedBranch === 'all' }"
              @click.stop="selectBranch('all')"
            >
              <span class="pin" />
              <div class="nm">
                {{ t('branchPicker.allBranches')
                }}<small>{{ pickerBranchIds.length }} filial</small>
              </div>
              <span class="ck">✓</span>
            </div>
            <div
              v-for="id in pickerBranchIds"
              :key="id"
              class="it"
              :class="{ on: auth.selectedBranch === id }"
              @click.stop="selectBranch(id)"
            >
              <span class="pin" />
              <div class="nm">{{ branchesStore.nameOf(id) }}</div>
              <span class="ck">✓</span>
            </div>
          </div>
        </div>

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
          <NotificationBell variant="app" all-route="/workshop/notifications" />
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
