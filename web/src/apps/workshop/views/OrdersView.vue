<script setup lang="ts">
// Workshop orders — Board mode (columns by status, action menu per card, NO
// drag) + Table mode (filters: status chips / search / branch). Branch-scoped
// via the topbar picker. Mirrors prototype workshop/orders.html.
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtTiyin } from '@/shared/format'
import { useWorkshopAuth } from '../store'
import { useBranchesStore } from '../stores/branches'
import * as api from '../api'
import type { OrderCard, OrderStatus } from '../api/types'
import { BOARD_COLUMNS, groupByColumn, relativeAge } from '../lib/orders'

const auth = useWorkshopAuth()
const branchesStore = useBranchesStore()
const router = useRouter()

const mode = ref<'board' | 'table'>('board')
const stateFilter = ref<'all' | 'active' | OrderStatus>('all')
const search = ref('')
const branchFilter = ref<'all' | string>('all')

const loading = ref(true)
const error = ref<ApiError | null>(null)
const orders = ref<OrderCard[]>([])
const openMenu = ref<string | null>(null)

const STATE_FILTERS: { id: 'all' | 'active' | OrderStatus; key: string }[] = [
  { id: 'all', key: 'workshop.allStates' },
  { id: 'active', key: 'workshop.activeStates' },
  { id: 'new', key: 'orderState.new' },
  { id: 'confirmed', key: 'orderState.confirmed' },
  { id: 'cutting', key: 'orderState.cutting' },
  { id: 'edge_banding', key: 'orderState.edge_banding' },
  { id: 'ready', key: 'orderState.ready' },
  { id: 'completed', key: 'orderState.completed' },
]

let searchTimer: ReturnType<typeof setTimeout> | null = null

const filtered = computed(() => {
  let list = orders.value
  if (branchFilter.value !== 'all') list = list.filter((o) => o.branch_id === branchFilter.value)
  if (stateFilter.value === 'active') {
    list = list.filter((o) => BOARD_COLUMNS.includes(o.status))
  } else if (stateFilter.value !== 'all') {
    list = list.filter((o) => o.status === stateFilter.value)
  }
  return list
})

const columns = computed(() => groupByColumn(filtered.value))

function canActOn(branchId: string): boolean {
  return auth.can('manage_orders', branchId)
}

async function load() {
  loading.value = true
  error.value = null
  try {
    await branchesStore.load()
    const board = await api.listOrders({
      branchId: auth.branchScope,
      search: search.value.trim() || undefined,
    })
    orders.value = board.orders
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

watch(() => auth.branchScope, load)
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 350)
})

function go(id: string) {
  router.push(`/workshop/orders/${id}`)
}

function toggleMenu(id: string) {
  openMenu.value = openMenu.value === id ? null : id
}

onMounted(load)
</script>

<template>
  <div @click="openMenu = null">
    <div class="page-head">
      <div>
        <h1>{{ t('workshop.ordersTitle') }}</h1>
        <p class="sub">{{ t('workshop.ordersSub') }}</p>
      </div>
      <div class="tools">
        <button
          class="btn btn-outline btn-sm"
          :class="{ on: mode === 'board' }"
          type="button"
          @click="mode = 'board'"
        >
          {{ t('workshop.modeBoard') }}
        </button>
        <button
          class="btn btn-outline btn-sm"
          :class="{ on: mode === 'table' }"
          type="button"
          @click="mode = 'table'"
        >
          {{ t('workshop.modeTable') }}
        </button>
      </div>
    </div>

    <div class="filters">
      <div class="chips">
        <button
          v-for="f in STATE_FILTERS"
          :key="f.id"
          class="chip"
          :class="{ on: stateFilter === f.id }"
          type="button"
          @click="stateFilter = f.id"
        >
          {{ t(f.key) }}
        </button>
      </div>
      <div class="input">
        <input v-model="search" :placeholder="t('workshop.searchOrders')" />
      </div>
      <select v-model="branchFilter">
        <option value="all">{{ t('workshop.allBranchesOpt') }}</option>
        <option v-for="b in branchesStore.branches" :key="b.id" :value="b.id">{{ b.name }}</option>
      </select>
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />

    <div v-else-if="loading" class="board">
      <div v-for="n in 4" :key="n" class="board-col">
        <div class="sk sk-line" style="width: 40%" />
        <div class="board-card"><div class="sk sk-line" style="width: 90%" /></div>
        <div class="board-card"><div class="sk sk-line" style="width: 70%" /></div>
      </div>
    </div>

    <div v-else-if="filtered.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.ordersEmpty') }}</h3>
      <p>{{ t('workshop.ordersEmptyBody') }}</p>
    </div>

    <!-- BOARD -->
    <div v-else-if="mode === 'board'" class="board">
      <div v-for="col in BOARD_COLUMNS" :key="col" class="board-col">
        <h4>
          {{ t(`orderState.${col}`) }} <span class="ct">{{ columns[col].length }}</span>
        </h4>
        <article v-for="o in columns[col]" :key="o.id" class="board-card" @click="go(o.id)">
          <div class="top">
            <span class="id">{{ o.order_number }}</span>
            <span class="amt">{{ fmtTiyin(o.total_tiyin) }}</span>
          </div>
          <div class="who">{{ o.contact_name || '—' }}</div>
          <div class="meta">
            <span style="font-size: 10.5px; color: var(--ink-6)"
              >{{ o.item_count }} {{ t('workshop.partsCount') }}</span
            >
            <span style="font-size: 10.5px; color: var(--ink-6)">{{
              relativeAge(o.created_at)
            }}</span>
            <span v-if="o.assigned_cutter_user_id" class="pill p-cut" style="font-size: 9.5px"
              >✄</span
            >
            <span v-if="o.assigned_edger_user_id" class="pill p-eb" style="font-size: 9.5px"
              >▥</span
            >
          </div>
          <div class="meta" style="margin-top: 6px">
            <div class="menu-wrap" style="margin-left: auto" @click.stop>
              <button class="btn btn-outline btn-sm" type="button" @click="toggleMenu(o.id)">
                {{ t('workshop.statusMenu') }}
              </button>
              <div v-if="openMenu === o.id" class="menu">
                <button v-if="canActOn(o.branch_id)" class="mi" type="button" @click="go(o.id)">
                  {{ t('workshop.detailsLink') }}
                </button>
                <RouterLink v-else class="mi" :to="`/workshop/orders/${o.id}`">{{
                  t('workshop.detailsLink')
                }}</RouterLink>
              </div>
            </div>
          </div>
        </article>
        <div
          v-if="columns[col].length === 0"
          style="color: var(--ink-6); font-size: 11.5px; padding: 14px 6px; text-align: center"
        >
          {{ t('common.empty') }}
        </div>
      </div>
    </div>

    <!-- TABLE -->
    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.colId') }}</th>
            <th>{{ t('workshop.colClient') }}</th>
            <th>{{ t('workshop.colBranch') }}</th>
            <th>{{ t('workshop.colStatus') }}</th>
            <th class="right">{{ t('workshop.colAmount') }}</th>
            <th>{{ t('workshop.colTime') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in filtered" :key="o.id" class="clickable" @click="go(o.id)">
            <td class="id">{{ o.order_number }}</td>
            <td class="nm">{{ o.contact_name || '—' }}</td>
            <td>{{ branchesStore.nameOf(o.branch_id) }}</td>
            <td><StatusBadge :state="o.status" /></td>
            <td class="amt">{{ fmtTiyin(o.total_tiyin) }}</td>
            <td style="font-size: 11.5px; color: var(--ink-6)">{{ relativeAge(o.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
