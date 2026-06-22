<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import { orderPillClass, permissionLabels, workshopStatusUz } from '@/shared/app/workshopUi'
import AppTabs from '@/shared/components/AppTabs.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useOrdersStore } from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'

const route = useRoute()
const rolePath = useRolePath()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const orders = useOrdersStore()
const toast = useToast()
type BranchDetailTab = 'overview' | 'materials' | 'inventory' | 'settings' | 'staff' | 'orders'

const activeTab = ref<BranchDetailTab>('overview')
const branchId = computed(() => String(route.params.branch_id ?? ''))
const loading = ref(false)
const pageError = ref<string | null>(null)
const pageTraceId = ref<string | null>(null)
const staffLoadError = ref<string | null>(null)
const ordersLoadError = ref<string | null>(null)
const settingsSaving = ref(false)
const statusCountRefreshing = ref(false)
const settingsError = ref<string | null>(null)
const settingsTraceId = ref<string | null>(null)
const settingsSuccess = ref<string | null>(null)
const statusCountRefreshedAt = ref<string | null>(null)
const branchForm = reactive({
  name: '',
  address: '',
  phone: '',
  latitude: '',
  longitude: '',
})
const pricingForm = reactive({
  cuttingRateTiyin: '',
  edgeBandingRateTiyin: '',
})
const statusForm = reactive({
  status: 'active',
  reason: '',
  confirmed: false,
})

const contextBranch = computed(() =>
  workshop.branches.find((branch) => branch.id === branchId.value),
)
const canManageCatalog = computed(
  () => auth.me?.is_owner || contextBranch.value?.permissions.includes('manage_catalog') === true,
)
const canManageInventory = computed(
  () => auth.me?.is_owner || contextBranch.value?.permissions.includes('manage_inventory') === true,
)
const canManageSettings = computed(() => auth.me?.is_owner === true)
const canManageOrders = computed(
  () => auth.me?.is_owner || contextBranch.value?.permissions.includes('manage_orders') === true,
)
const statusOptions = [
  { value: 'active', label: 'Faol', meta: "mijozlarga ko'rinadi" },
  { value: 'temporarily_closed', label: 'Vaqtincha yopiq', meta: 'sabab bilan ko`rinadi' },
  { value: 'inactive', label: 'Faol emas', meta: 'mijozlardan yashirilgan' },
]
const visibleTabs = computed<Array<{ key: BranchDetailTab; label: string }>>(() => {
  const tabs: Array<{ key: BranchDetailTab; label: string }> = []
  if (workshop.selectedBranch) tabs.push({ key: 'overview', label: 'Umumiy' })
  if (canManageCatalog.value) {
    tabs.push({
      key: 'materials',
      label: `Materiallar (${workshop.selectedBranch?.material_count ?? 0})`,
    })
  }
  if (canManageInventory.value) tabs.push({ key: 'inventory', label: 'Ombor' })
  if (canManageSettings.value) tabs.push({ key: 'settings', label: 'Sozlamalar' })
  if (canManageSettings.value) {
    tabs.push({
      key: 'staff',
      label: `Xodimlar (${workshop.selectedBranch?.staff_count ?? 0})`,
    })
  }
  if (canManageOrders.value) {
    tabs.push({
      key: 'orders',
      label: `Buyurtmalar (${workshop.selectedBranch?.active_orders_count ?? 0})`,
    })
  }
  return tabs
})
const visibleTabOptions = computed<ChoiceOption[]>(() =>
  visibleTabs.value.map((tab) => ({ value: tab.key, label: tab.label })),
)

function selectFirstVisibleTab() {
  if (visibleTabs.value.some((tab) => tab.key === activeTab.value)) return
  activeTab.value = visibleTabs.value[0]?.key ?? 'overview'
}

async function loadActiveTab() {
  if (!branchId.value) return
  if (activeTab.value === 'staff' && canManageSettings.value) {
    staffLoadError.value = null
    try {
      await workshop.loadUsers({ filters: { branch_id: branchId.value } })
      staffLoadError.value = workshop.error
    } catch {
      staffLoadError.value = 'staff_load_failed'
    }
  }
  if (activeTab.value === 'orders' && canManageOrders.value) {
    ordersLoadError.value = null
    try {
      await orders.loadWorkshopOrders({
        branch_id: branchId.value,
        status: 'all',
        limit: 6,
        offset: 0,
      })
      ordersLoadError.value = orders.error
    } catch {
      ordersLoadError.value = 'orders_load_failed'
    }
  }
}

async function refreshBranch() {
  if (!branchId.value) return
  loading.value = true
  pageError.value = null
  pageTraceId.value = null
  try {
    await workshop.loadBranchContext()
    workshop.setSelectedBranchContext(branchId.value)
    await workshop.loadBranch(branchId.value)
    syncBranchForms()
    selectFirstVisibleTab()
    await loadActiveTab()
  } catch {
    pageError.value = 'branch_detail_load_failed'
    pageTraceId.value = workshop.traceId ?? workshop.setupTraceId
  } finally {
    loading.value = false
  }
}

function workingHoursSummary(hours: Record<string, unknown>) {
  const labels: Record<string, string> = {
    monday: 'Du',
    tuesday: 'Se',
    wednesday: 'Chor',
    thursday: 'Pay',
    friday: 'Ju',
    saturday: 'Sh',
    sunday: 'Yak',
  }
  const rows = Object.entries(labels).map(([key, label]) => {
    const value = hours[key]
    const day = value && typeof value === 'object' ? (value as Record<string, unknown>) : null
    const open = typeof day?.open === 'string' ? day.open : null
    const close = typeof day?.close === 'string' ? day.close : null
    return `${label}: ${open && close ? `${open}-${close}` : 'yopiq'}`
  })
  return rows.join(' · ')
}

function branchPermissionSummary(user: (typeof workshop.users)[number]) {
  if (user.is_owner) return 'Egasi · barcha ruxsatlar'
  const branchGrants = user.grants.filter((grant) => grant.branch_id === branchId.value)
  if (branchGrants.length === 0 && user.home_branch_id === branchId.value) return 'Asosiy filial'
  if (branchGrants.length === 0) return '—'
  return branchGrants
    .map((grant) => permissionLabels[grant.permission] ?? grant.permission)
    .join(', ')
}

async function saveBranchSettings() {
  settingsSaving.value = true
  settingsError.value = null
  settingsTraceId.value = null
  settingsSuccess.value = null
  try {
    await workshop.updateBranch(branchId.value, {
      name: branchForm.name,
      address: branchForm.address,
      phone: branchForm.phone,
      latitude: branchForm.latitude,
      longitude: branchForm.longitude,
    })
    await workshop.updateBranchPricing(branchId.value, {
      cutting_rate_tiyin: pricingForm.cuttingRateTiyin
        ? Number(pricingForm.cuttingRateTiyin)
        : null,
      edge_banding_rate_tiyin: pricingForm.edgeBandingRateTiyin
        ? Number(pricingForm.edgeBandingRateTiyin)
        : null,
    })
    settingsSuccess.value = 'Filial sozlamalari saqlandi.'
    toast.success('Filial sozlamalari saqlandi.')
  } catch (caught) {
    settingsError.value = 'branch_settings_save_failed'
    settingsTraceId.value = apiTraceId(caught)
  } finally {
    settingsSaving.value = false
  }
}

async function refreshBranchStatusCount() {
  statusCountRefreshing.value = true
  try {
    await workshop.loadBranch(branchId.value)
    statusCountRefreshedAt.value = new Date().toISOString()
    return true
  } catch (caught) {
    settingsError.value = 'branch_load_failed'
    settingsTraceId.value = apiTraceId(caught)
    return false
  } finally {
    statusCountRefreshing.value = false
  }
}

async function changeBranchStatus() {
  const nextStatus = statusForm.status
  const nextReason = statusForm.reason
  settingsSaving.value = true
  settingsError.value = null
  settingsTraceId.value = null
  settingsSuccess.value = null
  try {
    if (nextStatus !== 'active') {
      const refreshed = await refreshBranchStatusCount()
      if (!refreshed) return
    }
    await workshop.setBranchStatus(branchId.value, {
      status: nextStatus,
      reason: nextStatus === 'active' ? null : nextReason,
    })
    statusForm.confirmed = false
    syncBranchForms()
    settingsSuccess.value = "Filial holati o'zgartirildi."
    toast.success("Filial holati o'zgartirildi.")
  } catch (caught) {
    settingsError.value = 'branch_status_failed'
    settingsTraceId.value = apiTraceId(caught)
  } finally {
    settingsSaving.value = false
  }
}

function syncBranchForms() {
  const branch = workshop.selectedBranch
  if (branch) {
    branchForm.name = branch.name
    branchForm.address = branch.address
    branchForm.phone = branch.phone
    branchForm.latitude = String(branch.latitude)
    branchForm.longitude = String(branch.longitude)
    statusForm.status = branch.status
    statusForm.reason = branch.closed_reason ?? ''
  }
  const pricing = workshop.selectedBranchPricing
  if (pricing) {
    pricingForm.cuttingRateTiyin = String(pricing.cutting_rate_tiyin ?? '')
    pricingForm.edgeBandingRateTiyin = String(pricing.edge_banding_rate_tiyin ?? '')
  }
}

function statusClass(status: string) {
  return {
    'bg-success-soft text-success': status === 'active',
    'bg-warning-soft text-warning': status === 'temporarily_closed',
    'bg-danger-soft text-danger': status === 'inactive',
  }
}

watch(branchId, refreshBranch)
watch(activeTab, () => {
  void loadActiveTab()
})
watch(
  () => statusForm.status,
  (status) => {
    if (status !== 'active') void refreshBranchStatusCount()
  },
)
onMounted(refreshBranch)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">
          {{ workshop.selectedBranch?.name ?? 'Filial' }}
        </h1>
        <p class="mt-2 text-base text-ink-soft">
          Filial holati, xodimlar, buyurtmalar va boshqaruv sahifalariga tez o'tish.
        </p>
      </div>
      <span
        v-if="workshop.selectedBranch"
        class="mp-chip"
        :class="statusClass(workshop.selectedBranch.status)"
      >
        <span class="mp-dot" aria-hidden="true"></span>
        {{
          workshop.selectedBranch.status === 'active'
            ? 'Faol'
            : workshop.selectedBranch.status === 'temporarily_closed'
              ? 'Vaqtincha yopiq'
              : 'Faol emas'
        }}
      </span>
    </div>

    <div v-if="loading" class="rounded-lg bg-info-soft p-4 font-bold text-info" aria-live="polite">
      Filial sahifasi yuklanmoqda
    </div>
    <div v-else-if="pageError" class="rounded-lg bg-danger-soft p-4 font-bold text-danger">
      Filial sahifasini yuklab bo'lmadi. trace {{ pageTraceId ?? 'unavailable' }}
    </div>

    <div
      v-if="workshop.selectedBranch?.status === 'temporarily_closed'"
      class="banner warn"
      role="status"
    >
      <div class="grow">
        <b>Vaqtincha yopiq</b>
        <span v-if="workshop.selectedBranch.closed_reason">
          · {{ workshop.selectedBranch.closed_reason }}
        </span>
      </div>
    </div>
    <div v-else-if="workshop.selectedBranch?.status === 'inactive'" class="banner danger">
      <div class="grow">
        <b>Faol emas</b> · bu filial yangi buyurtma qabul qilmaydi. Ochiq buyurtmalar odatdagi
        tartibda yakunlanadi.
      </div>
    </div>

    <div v-if="workshop.selectedBranch" class="kpis">
      <div class="kpi">
        <div class="lbl">Faol buyurtma</div>
        <div class="v num">{{ workshop.selectedBranch.active_orders_count }}</div>
      </div>
      <div class="kpi">
        <div class="lbl">Materiallar</div>
        <div class="v num">{{ workshop.selectedBranch.material_count }}</div>
      </div>
      <div class="kpi warn">
        <div class="lbl">Past zaxira</div>
        <div class="v num">{{ workshop.selectedBranch.low_stock_count }}</div>
        <div v-if="workshop.selectedBranch.low_stock_count > 0" class="d">Tez tekshirish kerak</div>
      </div>
      <div class="kpi">
        <div class="lbl">Xodim</div>
        <div class="v num">{{ workshop.selectedBranch.staff_count }}</div>
      </div>
    </div>

    <AppTabs
      v-if="visibleTabs.length > 0"
      v-model="activeTab"
      id-prefix="workshop-branch"
      label="Filial bo'limlari"
      :tabs="visibleTabOptions"
    />
    <div
      v-else-if="!loading && !pageError"
      class="rounded-lg bg-warning-soft p-4 font-bold text-warning"
    >
      Bu akkauntda filial bo'yicha ruxsat yo'q.
    </div>

    <section
      v-if="activeTab === 'overview' && workshop.selectedBranch"
      id="workshop-branch-overview-panel"
      class="space-y-5"
      role="tabpanel"
      aria-labelledby="workshop-branch-overview-tab"
      tabindex="0"
    >
      <section class="card">
        <div class="card-h">
          <h2>Filial haqida</h2>
        </div>
        <div class="card-b pt-0">
          <div class="row-item">
            <div>
              <div class="nm">Manzil</div>
            </div>
            <div class="meta">{{ workshop.selectedBranch.address }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">Telefon</div>
            </div>
            <div class="meta">{{ workshop.selectedBranch.phone }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">Ish vaqti</div>
            </div>
            <div class="meta">{{ workingHoursSummary(workshop.selectedBranch.working_hours) }}</div>
          </div>
          <div class="row-item">
            <div>
              <div class="nm">Geo (lat, lng)</div>
            </div>
            <div class="meta">
              {{ workshop.selectedBranch.latitude }}, {{ workshop.selectedBranch.longitude }}
            </div>
          </div>
        </div>
      </section>
    </section>

    <section
      v-if="activeTab === 'staff' && canManageSettings"
      id="workshop-branch-staff-panel"
      class="space-y-5"
      role="tabpanel"
      aria-labelledby="workshop-branch-staff-tab"
      tabindex="0"
    >
      <section class="card">
        <div class="card-h">
          <h2>Bu filialdagi xodimlar</h2>
          <RouterLink class="more" :to="rolePath('/workshop/settings/users')">
            hammasi →
          </RouterLink>
        </div>
        <div v-if="workshop.loading" class="card-b" aria-live="polite">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
        <div v-else-if="staffLoadError" class="st-error">
          <h3>Xodimlarni yuklab bo'lmadi</h3>
          <p>trace_id: {{ workshop.traceId ?? 'unavailable' }}</p>
        </div>
        <div v-else-if="workshop.users.length === 0" class="st-empty">
          <h3>Bu filialda xodim yo'q</h3>
          <p>Xodim qo'shib, filial ruxsatlarini belgilang.</p>
        </div>
        <div v-else class="card-b p-0">
          <table class="tbl">
            <thead>
              <tr>
                <th>Xodim</th>
                <th>Ruxsatlar</th>
                <th>Holat</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in workshop.users" :key="user.id" class="clickable">
                <td class="nm">
                  <RouterLink :to="rolePath(`/workshop/settings/users/${user.id}`)">
                    {{ user.full_name }}
                  </RouterLink>
                  <small>{{ user.login }} · {{ user.phone }}</small>
                </td>
                <td>
                  <small class="text-ink">{{ branchPermissionSummary(user) }}</small>
                </td>
                <td>
                  <span :class="user.status === 'active' ? 'pill p-ok' : 'pill p-bad'">
                    <span class="pd"></span>{{ user.status === 'active' ? 'Faol' : 'Bloklangan' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section
      v-if="activeTab === 'orders' && canManageOrders"
      id="workshop-branch-orders-panel"
      class="space-y-5"
      role="tabpanel"
      aria-labelledby="workshop-branch-orders-tab"
      tabindex="0"
    >
      <section class="card">
        <div class="card-h">
          <h2>Bu filialdagi buyurtmalar</h2>
          <RouterLink
            class="more"
            :to="rolePath(`/workshop/orders?branch=${workshop.selectedBranch?.id ?? branchId}`)"
          >
            hammasi →
          </RouterLink>
        </div>
        <div v-if="orders.loading" class="card-b" aria-live="polite">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
        <div v-else-if="ordersLoadError" class="st-error">
          <h3>Buyurtmalarni yuklab bo'lmadi</h3>
          <p>trace_id: {{ orders.traceId ?? 'unavailable' }}</p>
        </div>
        <div v-else-if="orders.workshopOrders.length === 0" class="st-empty">
          <h3>Bu filialda buyurtma yo'q</h3>
          <p>Filial tanlangach yangi buyurtmalar shu yerda ko'rinadi.</p>
        </div>
        <div v-else class="card-b p-0">
          <table class="tbl">
            <thead>
              <tr>
                <th>ID</th>
                <th>Mijoz</th>
                <th>Holat</th>
                <th class="right">Summa</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="order in orders.workshopOrders.slice(0, 6)"
                :key="order.id"
                class="clickable"
              >
                <td class="id">
                  <RouterLink :to="rolePath(`/workshop/orders/${order.id}`)">
                    {{ order.order_number }}
                  </RouterLink>
                </td>
                <td class="nm">
                  {{ order.client_name }}
                  <small>{{ order.client_phone }}</small>
                </td>
                <td>
                  <span :class="orderPillClass(order.status)">
                    <span class="pd"></span>{{ workshopStatusUz[order.status] }}
                  </span>
                </td>
                <td class="amt">{{ formatTiyin(order.total_tiyin) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section
      v-if="activeTab === 'materials' && canManageCatalog"
      id="workshop-branch-materials-panel"
      class="space-y-5"
      role="tabpanel"
      aria-labelledby="workshop-branch-materials-tab"
      tabindex="0"
    >
      <section class="card p-5">
        <h2 class="font-serif text-xl font-semibold text-ink">Material katalogi</h2>
        <p class="mt-2 text-sm text-ink-soft">
          Material qo'shish, narx/min zaxira va mijozga ko'rinish katalog sahifasida boshqariladi.
        </p>
        <RouterLink class="mp-button mp-button-primary mt-4" :to="rolePath('/workshop/catalog')">
          Katalogni ochish
        </RouterLink>
      </section>
    </section>

    <section
      v-if="activeTab === 'inventory' && canManageInventory"
      id="workshop-branch-inventory-panel"
      class="space-y-5"
      role="tabpanel"
      aria-labelledby="workshop-branch-inventory-tab"
      tabindex="0"
    >
      <section class="card p-5">
        <h2 class="font-serif text-xl font-semibold text-ink">Ombor</h2>
        <p class="mt-2 text-sm text-ink-soft">
          Kirim, tuzatish, tranzaksiyalar va yetkazib beruvchilar ombor sahifasida boshqariladi.
        </p>
        <RouterLink class="mp-button mp-button-primary mt-4" :to="rolePath('/workshop/inventory')">
          Omborni ochish
        </RouterLink>
      </section>
    </section>

    <section
      v-if="activeTab === 'settings' && canManageSettings"
      id="workshop-branch-settings-panel"
      class="grid gap-5 xl:grid-cols-2"
      role="tabpanel"
      aria-labelledby="workshop-branch-settings-tab"
      tabindex="0"
    >
      <section class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold text-ink">Filial ma'lumotlari va narxlar</h2>
        <form class="mt-4 grid gap-3" @submit.prevent="saveBranchSettings">
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-name"
              >Nom</label
            >
            <input
              id="detail-branch-name"
              v-model="branchForm.name"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-address"
              >Manzil</label
            >
            <input
              id="detail-branch-address"
              v-model="branchForm.address"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <div class="grid gap-3 md:grid-cols-3">
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-phone"
                >Telefon</label
              >
              <input
                id="detail-branch-phone"
                v-model="branchForm.phone"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                required
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-lat"
                >Latitude</label
              >
              <input
                id="detail-branch-lat"
                v-model="branchForm.latitude"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="decimal"
                required
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="detail-branch-lng"
                >Longitude</label
              >
              <input
                id="detail-branch-lng"
                v-model="branchForm.longitude"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="decimal"
                required
              />
            </div>
          </div>
          <div class="grid gap-3 md:grid-cols-2">
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="cutting-rate"
                >Kesish narxi (tiyin)</label
              >
              <input
                id="cutting-rate"
                v-model="pricingForm.cuttingRateTiyin"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="numeric"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-bold text-ink" for="edge-rate"
                >Krom narxi (tiyin)</label
              >
              <input
                id="edge-rate"
                v-model="pricingForm.edgeBandingRateTiyin"
                class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
                inputmode="numeric"
              />
            </div>
          </div>
          <button class="mp-button mp-button-primary" type="submit" :disabled="settingsSaving">
            {{ settingsSaving ? 'Saqlanmoqda' : 'Filial sozlamalarini saqlash' }}
          </button>
          <p
            v-if="settingsError === 'branch_settings_save_failed'"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            Filial sozlamalari saqlanmadi · trace_id:
            {{ settingsTraceId ?? 'unavailable' }}
          </p>
          <p
            v-else-if="settingsSuccess === 'Filial sozlamalari saqlandi.'"
            class="rounded-md bg-success-soft px-3 py-2 text-sm font-bold text-success"
          >
            {{ settingsSuccess }}
          </p>
        </form>
      </section>

      <section class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold text-ink">Mijozlarga ko'rinish</h2>
        <form class="mt-4 grid gap-3" @submit.prevent="changeBranchStatus">
          <FormSelect v-model="statusForm.status" label="Holat" :options="statusOptions" />
          <div v-if="statusForm.status !== 'active'">
            <label class="mb-1 block text-sm font-bold text-ink" for="branch-status-reason"
              >Sabab</label
            >
            <input
              id="branch-status-reason"
              v-model="statusForm.reason"
              class="min-h-11 w-full rounded-md border border-hairline-strong px-3"
              required
            />
          </div>
          <label
            class="flex items-start gap-3 rounded-md border border-warning bg-warning-soft p-3 text-sm font-bold text-warning"
          >
            <input
              v-model="statusForm.confirmed"
              type="checkbox"
              class="mt-1 size-4 accent-warning"
            />
            <span>
              Mijozlarga ko'rinish o'zgarishini tasdiqlayman. Ochiq buyurtmalar soni:
              {{
                statusCountRefreshing
                  ? 'yangilanmoqda...'
                  : (workshop.selectedBranch?.active_orders_count ?? 0)
              }}.
              <span v-if="statusCountRefreshedAt">Hisob submit oldidan yangilanadi.</span>
            </span>
          </label>
          <button
            class="mp-button mp-button-primary"
            type="submit"
            :disabled="settingsSaving || !statusForm.confirmed"
          >
            {{ settingsSaving ? "O'zgartirilmoqda" : "Holatni o'zgartirish" }}
          </button>
          <p
            v-if="settingsError === 'branch_status_failed'"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            Filial holati o'zgartirilmadi · trace_id:
            {{ settingsTraceId ?? 'unavailable' }}
          </p>
          <p
            v-else-if="settingsSuccess === `Filial holati o'zgartirildi.`"
            class="rounded-md bg-success-soft px-3 py-2 text-sm font-bold text-success"
          >
            {{ settingsSuccess }}
          </p>
        </form>
      </section>
    </section>
  </section>
</template>
