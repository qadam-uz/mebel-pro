<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { snapshotMaterialLabel } from '@/shared/app/materialLabel'
import { useRolePath } from '@/shared/app/paths'
import {
  clearPanelMarks,
  loadPanelMarks,
  prunePanelMarks,
  savePanelMarks,
} from '@/shared/app/productionCheckpoints'
import {
  nextUncutPanelId,
  productionJobMetaLine,
  productionPartNames,
  type ProductionStationKey,
} from '@/shared/app/workshopProduction'
import {
  deriveSnapshotEdgeRegistry,
  edgeRegistryEntryByMaterial,
} from '@/shared/app/cuttingResultsDisplay'
import { stockShortfallMessage, workshopErrorMessage } from '@/shared/app/workshopUi'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatStockQuantity } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import type { CuttingPanel, CuttingPlacement, CuttingResult } from '@/shared/stores/cutting'
import { useOrdersStore } from '@/shared/stores/orders'
import { useProductionStore, type ProductionJobItem } from '@/shared/stores/production'

const POLL_INTERVAL_MS = 15_000

const { t } = useI18n()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const orders = useOrdersStore()
const production = useProductionStore()
const toast = useToast()

const orderId = computed(() => String(route.params.order_id ?? ''))
const job = computed(() => production.job)
const result = computed(() => job.value?.cutting_result ?? null)

const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
const markedPanelIds = ref<Set<string>>(new Set())
const actionError = ref<string | null>(null)
const actionBusy = ref(false)
const completeOpen = ref(false)

// Which station this sheet belongs to right now — the same order visits both.
const station = computed<ProductionStationKey>(() =>
  job.value?.status === 'edge_banding' ? 'banding' : 'cutting',
)
const stationTitle = computed(() =>
  station.value === 'cutting' ? t('finance.station.cutting') : t('finance.station.banding'),
)
const stationListPath = computed(() =>
  rolePath(station.value === 'cutting' ? '/workshop/cutting' : '/workshop/banding'),
)
const assignee = computed(() =>
  station.value === 'cutting' ? job.value?.assigned_cutter : job.value?.assigned_edger,
)
// The sheet is the worker's page: only the assignee acts here. Owners and
// operators manage statuses on-behalf from the office order page.
const canAct = computed(() => assignee.value?.id === auth.me?.principal_id)
// The cut checkpoints are a saw-station aid; the banding station just reads
// the drawing, so the marks (and their auto-advance) exist for cutting only.
const marksEnabled = computed(() => station.value === 'cutting')

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
  if (primaryAction.value === 'start') return t('finance.action.start')
  if (primaryAction.value === 'complete') return t('finance.action.finish')
  return ''
})

const statusNote = computed(() => {
  const current = job.value
  if (!current) return null
  if (current.status === 'ready') return t('finance.job.statusReady')
  if (current.status === 'completed') return t('finance.job.statusCompleted')
  if (current.status === 'cancelled') return t('finance.job.statusCancelled')
  return null
})

const activePanel = computed<CuttingPanel | null>(() => {
  const current = result.value
  if (!current) return null
  return (
    current.panels.find((panel) => panel.id === activePanelId.value) ?? current.panels[0] ?? null
  )
})

const markedCount = computed(() => {
  const current = result.value
  if (!current) return 0
  return current.panels.filter((panel) => markedPanelIds.value.has(panel.id)).length
})

function panelTitle(current: CuttingResult, panel: CuttingPanel) {
  // New snapshots carry no `name` column; compose the label from the same fields
  // the server uses, reading the legacy keys for frozen history.
  const snapshot = current.material_snapshots[panel.branch_material_id]
  const name = snapshotMaterialLabel(snapshot, t('finance.job.panelFallback'))
  return `${name} · ${panel.panel_index}`
}

function isPanelMarked(panel: CuttingPanel) {
  return markedPanelIds.value.has(panel.id)
}

// The worker's own cut checkpoints: one tap per panel, kept on this tablet.
// Marking the panel on screen advances the drawing to the next uncut one, so
// a long order is a sequence of taps, not scrolling.
function togglePanelMark(panel: CuttingPanel) {
  if (!marksEnabled.value) return
  const next = new Set(markedPanelIds.value)
  if (next.has(panel.id)) next.delete(panel.id)
  else next.add(panel.id)
  markedPanelIds.value = next
  savePanelMarks(orderId.value, next)
  if (!next.has(panel.id) || panel.id !== activePanel.value?.id) return
  const targetId = nextUncutPanelId(result.value?.panels ?? [], next, panel.id)
  if (targetId) activePanelId.value = targetId
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

// Part rows are named from the cutting result's detail names (the editor's
// D-numbering as fallback) — the raw part_ref uuid never reaches the screen.
const partNames = computed(() => productionPartNames(result.value?.parts_snapshot ?? []))

function itemName(item: ProductionJobItem, index: number) {
  return partNames.value.get(item.part_ref) ?? `D${index + 1}`
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
  if (item.edge_top) names.push(t('finance.job.sideTop'))
  if (item.edge_bottom) names.push(t('finance.job.sideBottom'))
  if (item.edge_left) names.push(t('finance.job.sideLeft'))
  if (item.edge_right) names.push(t('finance.job.sideRight'))
  return names.length > 0
    ? t('finance.job.bandedSides', { sides: names.join(', ') })
    : t('finance.job.noBanding')
}

const metaLine = computed(() => (job.value ? productionJobMetaLine(job.value, station.value) : ''))

// Head chips size the job in glanceable numbers; material names live in the
// panels rail and the parts list, so the head stays one line tall.
const kromTotal = computed(() => {
  const total = (job.value?.planned_edge_lines ?? []).reduce(
    (sum, line) => sum + line.consumed_mm,
    0,
  )
  return total > 0 ? formatStockQuantity(total, 'm') : null
})

// Krom legend: one row per tape, swatch-matched to the drawing's edge ticks,
// so the bander sees which roll to load and how much it will consume.
const edgeLegend = computed(() => {
  if (station.value !== 'banding') return []
  const registry = deriveSnapshotEdgeRegistry(result.value?.parts_snapshot ?? [])
  return (job.value?.planned_edge_lines ?? []).map((line) => ({
    key: line.material_id,
    swatch:
      (
        edgeRegistryEntryByMaterial(registry, line.material_id, 'shop') ??
        edgeRegistryEntryByMaterial(registry, line.material_id, 'own')
      )?.colorStyle.bg ?? 'var(--color-accent)',
    // A compact "which roll to load" legend: color + thickness when known.
    // `material_label` (already the full canonical shape, thickness and all)
    // is only the fallback when color is missing — don't re-append thickness
    // on top of a label that already carries it.
    label: line.color
      ? [line.color, line.thickness_mm ? `${line.thickness_mm} mm` : null]
          .filter(Boolean)
          .join(' · ')
      : line.material_label,
    metres: formatStockQuantity(line.consumed_mm, 'm'),
  }))
})

async function load() {
  await production.loadJob(orderId.value)
}

// The sheet stays fresh on its own, same cadence as the station queues; a
// worker keeps it open for the whole cut.
let pollTimer: ReturnType<typeof setInterval> | null = null

function onVisibilityChange() {
  if (!document.hidden) void load()
}

async function runStart() {
  if (primaryAction.value !== 'start') return
  actionError.value = null
  // Fetch the latest state before stamping the start — a stale version is a
  // conflict, and someone may have moved the order while the sheet was open.
  await load()
  const current = job.value
  if (!current || primaryAction.value !== 'start') return
  actionBusy.value = true
  try {
    if (station.value === 'cutting') await orders.startCutting(current.id, current.version)
    else await orders.startBanding(current.id, current.version)
    toast.success(
      station.value === 'cutting'
        ? t('finance.toast.cuttingStarted')
        : t('finance.toast.bandingStartedSheet'),
    )
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
  } finally {
    actionBusy.value = false
    await load()
  }
}

async function openComplete() {
  actionError.value = null
  await load()
  if (primaryAction.value !== 'complete') return
  completeOpen.value = true
}

const completeMessage = computed(() => {
  const current = job.value
  if (!current) return ''
  const intro = `${current.order_number} · ${metaLine.value}`
  if (station.value === 'banding' || !current.has_banding) {
    return t('finance.complete.toReady', { job: intro })
  }
  if (!current.assigned_edger) return t('finance.complete.toBanding', { job: intro })
  return t('finance.complete.toBandingWithEdger', {
    job: intro,
    edger: current.assigned_edger.full_name,
  })
})

async function confirmComplete() {
  const current = job.value
  if (!current) return
  actionError.value = null
  // Completion always credits the assignee; a manager who needs a different
  // credit uses the office order page, which keeps its own "who did this" flow.
  const completedBy = assignee.value?.id ?? null
  if (!completedBy) {
    actionError.value = t('finance.error.noAssignee')
    return
  }
  try {
    const payload = { version: current.version, completed_by_user_id: completedBy }
    const updated =
      station.value === 'cutting'
        ? await orders.cuttingDone(current.id, payload)
        : await orders.bandingDone(current.id, payload)
    completeOpen.value = false
    clearPanelMarks(current.id)
    toast.success(t('finance.toast.jobFinished', { order: current.order_number }))
    // The books went negative — say so, but only after the job is marked done.
    if (updated.stock_shortfall) toast.warn(stockShortfallMessage())
    void router.push(stationListPath.value)
  } catch {
    actionError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
    await load()
  }
}

function onPrimary() {
  if (primaryAction.value === 'start') void runStart()
  else if (primaryAction.value === 'complete') void openComplete()
}

onMounted(async () => {
  prunePanelMarks()
  await load()
  // Checkpoints belong to the saw: the station is known only after the job
  // loads, and the banding view must not resurrect marks stored while cutting.
  if (marksEnabled.value) {
    markedPanelIds.value = loadPanelMarks(orderId.value)
    // A resuming worker lands on the first uncut panel, not on panel one.
    const panels = result.value?.panels ?? []
    const firstUncut = panels.find((panel) => !markedPanelIds.value.has(panel.id))
    if (firstUncut) activePanelId.value = firstUncut.id
  }
  pollTimer = setInterval(() => {
    if (!document.hidden && !orders.actionLoading && !actionBusy.value) void load()
  }, POLL_INTERVAL_MS)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <section>
    <RouterLink :to="stationListPath" class="back">{{
      $t('finance.job.back', { station: stationTitle })
    }}</RouterLink>

    <section v-if="production.jobLoading && !job" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="production.jobError || !job" class="st-error" role="alert">
      <h3>{{ $t('finance.job.loadFailed') }}</h3>
      <p>{{ $t('finance.job.loadFailedBody') }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="production.jobLoading"
        @click="load"
      >
        {{ $t('common.action.retry') }}
      </button>
      <p v-if="production.jobTraceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ production.jobTraceId }}
      </p>
    </section>

    <template v-else>
      <div class="page-head">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h1 class="!font-mono !text-[22px]">{{ job.order_number }}</h1>
          <!-- The job's size in numbers, on the number's own row; material
               names stay in the panels rail and the parts list. -->
          <div class="prod-stats">
            <span class="prod-stat">
              <svg viewBox="0 0 24 24" class="prod-stat-ico" aria-hidden="true">
                <circle cx="12" cy="8" r="4" />
                <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
              </svg>
              <b>{{ job.client_first_name }}</b>
            </span>
            <span class="prod-stat"
              >{{ $t('finance.job.parts') }} <b class="font-mono">{{ job.item_count }}</b></span
            >
            <span v-if="job.planned_panels > 0" class="prod-stat">
              {{ $t('finance.job.panels') }} <b class="font-mono">{{ job.planned_panels }}</b>
            </span>
            <span v-if="kromTotal" class="prod-stat">
              {{ $t('finance.station.banding') }} <b class="font-mono">{{ kromTotal }}</b>
            </span>
          </div>
        </div>
      </div>

      <div v-if="actionError" class="banner danger" role="alert">
        <div class="grow">
          {{ actionError }}
          <span v-if="orders.actionTraceId"> · trace {{ orders.actionTraceId }}</span>
        </div>
      </div>

      <!-- The drawing first: it is what the master came for. The rail beside
           it holds the panels with the worker's own cut checkpoints (✓) —
           they live on this tablet only. -->
      <section v-if="result" class="card">
        <!-- card-b's zero top padding expects a card-h above; this card has
             none, so pad the top to keep the plan off the wrapper's edge. -->
        <div class="card-b !pt-[22px]">
          <div class="prod-sheet">
            <div class="min-w-0">
              <CuttingPanelSvg
                v-if="activePanel"
                :result="result"
                :panel="activePanel"
                :active-placement-id="activePlacementId"
                fit="viewport"
                @select-placement="selectPlacement"
              />
              <!-- Which tape rolls this order needs: swatches match the
                   drawing's edge ticks. -->
              <div v-if="edgeLegend.length" class="prod-legend">
                <span v-for="line in edgeLegend" :key="line.key" class="prod-legend-item">
                  <span class="prod-legend-swatch" :style="{ background: line.swatch }"></span>
                  {{ line.label }} · <b class="font-mono">{{ line.metres }}</b>
                </span>
              </div>
            </div>
            <div class="prod-rail">
              <div class="prod-rail-h">
                <span>{{ $t('finance.job.panels') }}</span>
                <span v-if="marksEnabled">{{ markedCount }}/{{ result.panels.length }}</span>
                <span v-else>{{ $t('finance.unit.count', { n: result.panels.length }) }}</span>
              </div>
              <div
                v-for="panel in result.panels"
                :key="panel.id"
                class="prod-rail-row"
                :class="{
                  active: panel.id === activePanel?.id,
                  marked: isPanelMarked(panel),
                }"
              >
                <button
                  type="button"
                  class="prod-rail-select"
                  :aria-pressed="panel.id === activePanel?.id"
                  @click="activePanelId = panel.id"
                >
                  {{ panelTitle(result, panel) }}
                </button>
                <button
                  v-if="marksEnabled"
                  type="button"
                  class="prod-rail-mark"
                  :aria-pressed="isPanelMarked(panel)"
                  :aria-label="
                    $t('finance.job.panelCutAction', { panel: panelTitle(result, panel) })
                  "
                  @click="togglePanelMark(panel)"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="m5 12.5 4.5 4.5L19 7.5" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Parts with per-side banding: the glyph mirrors the text for eyes,
           the text carries it for screen readers. -->
      <section class="card mt-4">
        <div class="card-h">
          <h2>{{ $t('finance.job.parts') }}</h2>
        </div>
        <div class="card-b !p-0">
          <div
            v-for="(item, index) in job.items"
            :key="item.id"
            class="flex items-center gap-3 border-t border-hairline px-4 py-3 first:border-t-0"
          >
            <span class="w-32 truncate text-[13.5px] font-semibold text-ink-soft">
              {{ itemName(item, index) }}
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

      <div v-if="primaryAction" class="prod-stickybar">
        <button
          type="button"
          class="mp-button mp-button-primary min-h-12 grow px-5 text-[15px]"
          :disabled="actionBusy || orders.actionLoading"
          @click="onPrimary"
        >
          {{ actionBusy ? $t('finance.action.busyProgress') : primaryLabel }}
        </button>
      </div>
    </template>

    <ConfirmDialog
      :open="completeOpen"
      :title="
        station === 'cutting'
          ? $t('finance.complete.titleCutting')
          : $t('finance.complete.titleBanding')
      "
      :message="completeMessage"
      :confirm-label="$t('finance.action.finishConfirm')"
      :cancel-label="$t('common.action.cancel')"
      :busy-label="$t('finance.action.busy')"
      :busy="orders.actionLoading"
      @cancel="completeOpen = false"
      @confirm="confirmComplete"
    >
      <p class="mt-2 text-xs text-ink-muted">{{ $t('finance.complete.revertNote') }}</p>
      <p v-if="actionError" class="mt-2 text-sm font-bold text-danger">{{ actionError }}</p>
    </ConfirmDialog>
  </section>
</template>
