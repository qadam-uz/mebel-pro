<script setup lang="ts">
// Branch detail with tabs: Overview / Materials / Stock / Pricing / Staff /
// Orders. Owner-only route. Mirrors prototype workshop/branch-detail.html.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppTabs, ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtPhone } from '@/shared/format'
import { useBranchesStore } from '../../stores/branches'
import * as api from '../../api'
import type { BranchStatus, BranchSummary } from '../../api/types'
import BranchMaterialsTab from './BranchMaterialsTab.vue'
import BranchStockTab from './BranchStockTab.vue'
import BranchPricingTab from './BranchPricingTab.vue'
import BranchOrdersTab from './BranchOrdersTab.vue'

const route = useRoute()
const router = useRouter()
const branchesStore = useBranchesStore()

const branchId = computed(() => String(route.params.id))
const loading = ref(true)
const error = ref<ApiError | null>(null)
const branch = ref<BranchSummary | null>(null)
const activeTab = ref('overview')

const tabs = computed(() => [
  { id: 'overview', label: t('workshop.branchOverview') },
  { id: 'materials', label: t('workshop.branchMaterials') },
  { id: 'stock', label: t('workshop.branchStock') },
  { id: 'pricing', label: t('workshop.branchPricing') },
  { id: 'orders', label: t('workshop.branchOrders') },
])

const pillTone = (s: BranchStatus) =>
  s === 'active' ? 'ok' : s === 'temporarily_closed' ? 'warn' : 'bad'

async function load() {
  loading.value = true
  error.value = null
  try {
    await branchesStore.load()
    branch.value = await api.getBranch(branchId.value)
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

watch(branchId, load)
onMounted(load)
</script>

<template>
  <div>
    <button class="back" type="button" @click="router.push('/workshop/branches')">
      ← {{ t('workshop.branchesTitle') }}
    </button>

    <ErrorState v-if="error" :error="error" :retry="load" />

    <div v-else-if="loading" class="card" style="margin-top: 12px">
      <div class="card-b"><div class="sk sk-line" style="width: 50%" /></div>
    </div>

    <template v-else-if="branch">
      <div class="page-head" style="margin-top: 8px">
        <div>
          <h1>{{ branch.name }}</h1>
          <p class="sub">{{ branch.address }} · {{ fmtPhone(branch.phone) }}</p>
        </div>
        <div class="tools">
          <StatusBadge
            :tone="pillTone(branch.status)"
            :label="t(`branchStatus.${branch.status}`)"
          />
        </div>
      </div>

      <AppTabs v-model="activeTab" :tabs="tabs" />

      <div v-show="activeTab === 'overview'" style="margin-top: 16px">
        <div class="kpis">
          <div class="kpi">
            <div class="lbl">{{ t('workshop.colMaterials') }}</div>
            <div class="v num">{{ branch.materials_count }}</div>
          </div>
          <div class="kpi warn">
            <div class="lbl">{{ t('workshop.colLowStock') }}</div>
            <div class="v num" :style="branch.low_stock_count > 0 ? 'color:var(--warn)' : ''">
              {{ branch.low_stock_count }}
            </div>
          </div>
          <div class="kpi">
            <div class="lbl">{{ t('workshop.colActiveOrders') }}</div>
            <div class="v num">{{ branch.active_orders_count }}</div>
          </div>
        </div>
      </div>

      <BranchMaterialsTab v-if="activeTab === 'materials'" :branch-id="branchId" />
      <BranchStockTab v-if="activeTab === 'stock'" :branch-id="branchId" />
      <BranchPricingTab v-if="activeTab === 'pricing'" :branch-id="branchId" />
      <BranchOrdersTab v-if="activeTab === 'orders'" :branch-id="branchId" />
    </template>
  </div>
</template>
