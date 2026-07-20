<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import {
  productionJobMetaLine,
  resolveProductionCreditUser,
  type ProductionStationKey,
} from '@/shared/app/workshopProduction'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { useAuthStore } from '@/shared/stores/auth'
import type { CuttingPanel, CuttingPlacement, CuttingResult } from '@/shared/stores/cutting'
import { useOrdersStore } from '@/shared/stores/orders'
import { useProductionStore, type ProductionJobItem } from '@/shared/stores/production'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const orders = useOrdersStore()
const production = useProductionStore()
const toast = useToast()
const permissions = useWorkshopPermissions()

const orderId = computed(() => String(route.params.order_id ?? ''))
const job = computed(() => production.job)
const result = computed(() => job.value?.cutting_result ?? null)

const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const actionBusy = ref(false)
const completeOpen = ref(false)
const completedByDraft = ref('')
const workerOptions = ref<ChoiceOption[]>([])

// Which station this sheet belongs to right now — the same order visits both.
const station = computed<ProductionStationKey>(() =>
  job.value?.status === 'edge_banding' ? 'banding' : 'cutting',
)
const assignee = computed(() =>
  station.value === 'cutting' ? job.value?.assigned_cutter : job.value?.assigned_edger,
)
const isManager = computed(() => permissions.canOnBranch(p.manageOrders, job.value?.branch_id))
const canAct = computed(() => assignee.value?.id === auth.me?.principal_id || isManager.value)

// The single state-appropriate action for the sticky bar.
const primaryAction = computed<'start' | 'complete' | null>(() => {
  const current = job.value
  if (!current || !canAct.value) return null
  if (current.status === 'confirmed') return 'start'
  if (current.status === 'cutting') return 'complete'
  if (current.status === 'edge_banding') {
    return current.banding_started_at ? 'complete' : 'start'
  }
  return null
})
const primaryLabel = computed(() => {
  if (primaryAction.value === 'start') return 'Boshlash'
  if (primaryAction.value === 'complete') return '✓ Tugatdim'
  return ''
})

const statusNote = computed(() => {
  const current = job.value
  if (!current) return null
  if (current.status === 'ready') return 'Buyurtma tayyor — mijoz olib ketishini kutmoqda.'
  if (current.status === 'completed') return 'Buyurtma topshirilgan.'
  if (current.status === 'cancelled') return 'Buyurtma bekor qilingan.'
  return null
})

const activePanel = computed<CuttingPanel | null>(() => {
  const current = result.value
  if (!current) return null
  return (
    current.panels.find((panel) => panel.id === activePanelId.value) ?? current.panels[0] ?? null
  )
})

function panelTitle(current: CuttingResult, panel: CuttingPanel) {
  const snapshot = current.material_snapshots[panel.material_id]
  return `${String(snapshot?.name ?? 'Panel')} · ${panel.panel_index}`
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

function bandedSides(item: ProductionJobItem) {
  return {
    t: item.edge_top !== null,
    b: item.edge_bottom !== null,
    l: item.edge_left !== null,
    r: item.edge_right !== null,
  }
}

function bandedSidesText(item: ProductionJobItem) {
  const names: string[] = []
  if (item.edge_top) names.push('yuqori')
  if (item.edge_bottom) names.push('pastki')
  if (item.edge_left) names.push('chap')
  if (item.edge_right) names.push("o'ng")
  return names.length > 0 ? `kromka: ${names.join(', ')}` : 'kromkasiz'
}

const metaLine = computed(() => (job.value ? productionJobMetaLine(job.value, station.value) : ''))

async function load() {
  await production.loadJob(orderId.value)
}

async function runStart() {
  const current = job.value
  if (!current || primaryAction.value !== 'start') return
  actionError.value = null
  actionBusy.value = true
  try {
    if (station.value === 'cutting') await orders.startCutting(current.id, current.version)
    else await orders.startBanding(current.id, current.version)
    toast.success(station.value === 'cutting' ? 'Kesish boshlandi.' : 'Kromka boshlandi.')
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
  } finally {
    actionBusy.value = false
    await load()
  }
}

async function openComplete() {
  const current = job.value
  if (!current) return
  actionError.value = null
  completedByDraft.value = assignee.value?.id ?? ''
  if (isManager.value && workerOptions.value.length === 0) {
    await orders.loadWorkers(current.branch_id).catch(() => undefined)
    workerOptions.value = orders.workerOptions.map((worker) => ({
      value: worker.id,
      label: worker.full_name,
      meta: worker.is_owner ? 'owner' : 'production',
    }))
  }
  completeOpen.value = true
}

const completeMessage = computed(() => {
  const current = job.value
  if (!current) return ''
  if (station.value === 'banding' || !current.has_banding) {
    return `${current.order_number} · ${metaLine.value}. Keyin buyurtma tayyor holatga o'tadi.`
  }
  const edger = current.assigned_edger ? ` (${current.assigned_edger.full_name} navbatiga)` : ''
  return `${current.order_number} · ${metaLine.value}. Keyin buyurtma kromka bosqichiga o'tadi${edger}.`
})

async function confirmComplete() {
  const current = job.value
  if (!current) return
  actionError.value = null
  const completedBy = resolveProductionCreditUser(
    assignee.value?.id,
    completedByDraft.value,
    isManager.value,
  )
  if (!completedBy) {
    actionError.value = 'Ishni bajargan xodimni tanlang.'
    return
  }
  try {
    const payload = { version: current.version, completed_by_user_id: completedBy }
    if (station.value === 'cutting') await orders.cuttingDone(current.id, payload)
    else await orders.bandingDone(current.id, payload)
    completeOpen.value = false
    toast.success(`${current.order_number} yakunlandi.`)
    void router.push({
      path: rolePath('/workshop/production'),
      query: { station: station.value },
    })
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
    await load()
  }
}

function onPrimary() {
  if (primaryAction.value === 'start') void runStart()
  else if (primaryAction.value === 'complete') void openComplete()
}

onMounted(load)
</script>

<template>
  <section>
    <RouterLink
      :to="{ path: rolePath('/workshop/production'), query: { station } }"
      class="mb-4 inline-flex items-center gap-1 text-sm font-bold text-accent no-underline"
    >
      ‹ Ishlarim
    </RouterLink>

    <section v-if="production.jobLoading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="production.jobError || !job" class="st-error" role="alert">
      <h3>Ish varag'ini yuklab bo'lmadi</h3>
      <p>Buyurtma topilmadi yoki sizga tayinlanmagan.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="production.jobLoading"
        @click="load"
      >
        Qayta urinish
      </button>
      <p v-if="production.jobTraceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ production.jobTraceId }}
      </p>
    </section>

    <template v-else>
      <div class="page-head">
        <div>
          <h1 class="!font-mono !text-[22px]">{{ job.order_number }}</h1>
          <p class="mt-1 text-sm text-ink-soft">
            {{ metaLine }} · {{ job.client_first_name }} uchun
          </p>
        </div>
      </div>

      <div v-if="actionError" class="banner danger" role="alert">
        <div class="grow">
          {{ actionError }}
          <span v-if="orders.actionTraceId"> · trace {{ orders.actionTraceId }}</span>
        </div>
      </div>

      <!-- The drawing first: it is what the master came for. -->
      <section v-if="result" class="card">
        <div class="card-b space-y-4">
          <div class="flex flex-wrap gap-2" role="group" aria-label="Panellar">
            <button
              v-for="panel in result.panels"
              :key="panel.id"
              type="button"
              class="pill"
              :class="panel.id === activePanel?.id ? 'p-cut' : 'p-dn'"
              :aria-pressed="panel.id === activePanel?.id"
              @click="activePanelId = panel.id"
            >
              {{ panelTitle(result, panel) }}
            </button>
          </div>
          <CuttingPanelSvg
            v-if="activePanel"
            :result="result"
            :panel="activePanel"
            :active-placement-id="activePlacementId"
            @select-placement="selectPlacement"
          />
        </div>
      </section>

      <!-- Parts with per-side banding: the glyph mirrors the text for eyes,
           the text carries it for screen readers. -->
      <section class="card mt-4">
        <div class="card-h"><h2>Qismlar</h2></div>
        <div class="card-b !p-0">
          <div
            v-for="item in job.items"
            :key="item.id"
            class="flex items-center gap-3 border-t border-hairline px-4 py-3 first:border-t-0"
          >
            <span class="w-28 truncate text-[13.5px] font-semibold text-ink-soft">
              {{ item.part_ref }}
            </span>
            <span class="grow font-mono text-[15px] font-bold text-ink">
              {{ item.length_mm }} × {{ item.width_mm }}
            </span>
            <span class="sr-only">{{ bandedSidesText(item) }}</span>
            <span
              class="edge-glyph"
              :class="{
                t: bandedSides(item).t,
                b: bandedSides(item).b,
                l: bandedSides(item).l,
                r: bandedSides(item).r,
              }"
              aria-hidden="true"
            ></span>
            <span class="w-10 text-right font-mono text-[13px] text-ink-soft">
              ×{{ item.quantity }}
            </span>
          </div>
        </div>
      </section>

      <p v-if="statusNote" class="mt-4 rounded-md bg-sunk p-3 text-sm text-ink-soft">
        {{ statusNote }}
      </p>

      <div class="prod-stickybar">
        <button
          v-if="primaryAction"
          type="button"
          class="mp-button mp-button-primary min-h-12 grow px-5 text-[15px]"
          :disabled="actionBusy || orders.actionLoading"
          @click="onPrimary"
        >
          {{ actionBusy ? 'Bajarilmoqda…' : primaryLabel }}
        </button>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-12 px-5 text-[15px]"
          :disabled="orders.downloadingId === job.id"
          @click="orders.downloadWorkshopPdf(job.id)"
        >
          {{ orders.downloadingId === job.id ? 'Yuklanmoqda…' : 'PDF' }}
        </button>
      </div>
      <div v-if="orders.downloadError" class="banner danger" role="alert">
        <div class="grow">
          {{ orders.downloadError }} · trace_id: {{ orders.downloadTraceId ?? 'unavailable' }}
        </div>
      </div>
    </template>

    <ConfirmDialog
      :open="completeOpen"
      :title="station === 'cutting' ? 'Kesish tugadimi?' : 'Kromka tugadimi?'"
      :message="completeMessage"
      confirm-label="✓ Ha, tugatdim"
      cancel-label="Bekor qilish"
      busy-label="Bajarilmoqda"
      :busy="orders.actionLoading"
      @cancel="completeOpen = false"
      @confirm="confirmComplete"
    >
      <FormSelect
        v-if="isManager"
        v-model="completedByDraft"
        label="Kim bajardi"
        :options="workerOptions"
        :disabled="workerOptions.length === 0"
      />
      <p class="mt-2 text-xs text-ink-muted">
        Xatolik bo'lsa, rahbar bir qadam orqaga qaytara oladi.
      </p>
      <p v-if="actionError" class="mt-2 text-sm font-bold text-danger">{{ actionError }}</p>
    </ConfirmDialog>
  </section>
</template>
