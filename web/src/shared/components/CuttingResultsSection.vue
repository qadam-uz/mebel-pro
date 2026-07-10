<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { formatPercent } from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import { useToast } from '@/shared/composables/useToast'
import Icon from '@/shared/components/AppIcon.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import CuttingSheetThumbnails from '@/shared/components/CuttingSheetThumbnails.vue'
import CuttingVariantTabs from '@/shared/components/CuttingVariantTabs.vue'
import {
  metres,
  useCuttingStore,
  type CuttingDraft,
  type CuttingPanel,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'

// CB-93 seam: the optimizer-results surface — KPI tiles, algorithm comparison,
// the per-material panel strip + SVG visualiser, the krom/placement aside, and
// the order/PDF actions. All of `chosenResult` and its derived state lived only
// here in the parent, so they move wholesale into this component; the editor
// keeps `activeResultId`/`activePanelId` (written by optimize/the draft watch)
// and binds them as v-models, plus passes the parent-owned `optimizeError`.
const props = defineProps<{
  draft: CuttingDraft
  optimizeError: string | null
  activeResultId: string | null
  activePanelId: string | null
  // Role-specific "place order" target (client vs workshop checkout), injected
  // by the editor from its adapter so this presentational component stays dumb.
  checkoutPath: string
}>()
const emit = defineEmits<{
  'update:activeResultId': [string | null]
  'update:activePanelId': [string | null]
}>()

const cutting = useCuttingStore()
const rolePath = useRolePath()
const toast = useToast()

const activePlacementId = ref<string | null>(null)
const hasVariantTabs = computed(() => props.draft.results.length > 1)

const chosenResult = computed(() => {
  const draft = props.draft
  return (
    draft.results.find((result) => result.id === props.activeResultId) ??
    draft.results.find((result) => result.id === draft.chosen_result_id) ??
    draft.results[0] ??
    null
  )
})
const footerResult = computed(
  () =>
    props.draft.results.find((result) => result.id === props.draft.chosen_result_id) ??
    chosenResult.value,
)
const activePanel = computed(() => {
  const result = chosenResult.value
  if (!result) return null
  return result.panels.find((panel) => panel.id === props.activePanelId) ?? result.panels[0] ?? null
})
const totalPanels = computed(() =>
  chosenResult.value
    ? Object.values(chosenResult.value.panels_used_by_material).reduce(
        (sum, count) => sum + count,
        0,
      )
    : 0,
)
const consumedShop = computed(() => sumRecord(chosenResult.value?.edge_consumed_shop_by_material))
const consumedOwn = computed(() => sumRecord(chosenResult.value?.edge_consumed_own_by_material))
const resultWaste = computed(() => formatPercent(chosenResult.value?.waste_percentage))
const activeResultIsChosen = computed(() => chosenResult.value?.id === props.draft.chosen_result_id)
const viewingNonChosen = computed(
  () => Boolean(chosenResult.value && footerResult.value) && !activeResultIsChosen.value,
)
const placedCount = computed(() =>
  chosenResult.value
    ? chosenResult.value.panels.reduce((sum, panel) => sum + panel.placements.length, 0)
    : 0,
)
const requestedCount = computed(() =>
  chosenResult.value
    ? chosenResult.value.parts_snapshot.reduce((sum, part) => sum + part.quantity, 0)
    : 0,
)
const allPlaced = computed(() => placedCount.value >= requestedCount.value)
const edgeByMaterial = computed(() => {
  const result = chosenResult.value
  if (!result) return []
  const ids = new Set([
    ...Object.keys(result.edge_consumed_shop_by_material),
    ...Object.keys(result.edge_consumed_own_by_material),
  ])
  return [...ids]
    .map((id) => {
      const shop = result.edge_consumed_shop_by_material[id] ?? 0
      const own = result.edge_consumed_own_by_material[id] ?? 0
      const snapshot = result.material_snapshots[id]
      const name = typeof snapshot?.name === 'string' ? snapshot.name : id.slice(0, 8)
      return { id, name, total: shop + own }
    })
    .filter((row) => row.total > 0)
    .sort((left, right) => right.total - left.total)
})
const materialBreakdown = computed(() => {
  const result = chosenResult.value
  if (!result) return []
  return Object.entries(result.panels_used_by_material).map(([materialId, count]) => ({
    materialId,
    count,
    name: panelMaterialName(result, materialId),
    dims: snapshotDims(result.material_snapshots[materialId]),
  }))
})
const savingsBanner = computed<string | null>(() => null)

function sumRecord(record: Record<string, number> | undefined) {
  return Object.values(record ?? {}).reduce((sum, value) => sum + value, 0)
}

function snapshotDims(snapshot: Record<string, unknown> | undefined): string {
  const length = Number(snapshot?.panel_length_mm)
  const width = Number(snapshot?.panel_width_mm)
  return Number.isFinite(length) && Number.isFinite(width) && length > 0 && width > 0
    ? `${length}×${width}`
    : ''
}

function panelMaterialName(result: CuttingResult, materialId: string) {
  const snapshot = result.material_snapshots[materialId]
  const decor = typeof snapshot?.decor_code === 'string' ? snapshot.decor_code : ''
  const name = typeof snapshot?.name === 'string' ? snapshot.name : ''
  return decor || name || materialId.slice(0, 8)
}

function panelDims(result: CuttingResult, panel: CuttingPanel) {
  return snapshotDims(result.material_snapshots[panel.material_id])
}

function panelFillPercent(result: CuttingResult, panel: CuttingPanel) {
  const snapshot = result.material_snapshots[panel.material_id]
  const length = Number(snapshot?.panel_length_mm)
  const width = Number(snapshot?.panel_width_mm)
  if (!Number.isFinite(length) || !Number.isFinite(width) || length <= 0 || width <= 0) return '-'
  return `${Math.max(0, 100 - (panel.waste_area_mm2 / (length * width)) * 100).toFixed(1)}%`
}

function panelCaption(result: CuttingResult, panel: CuttingPanel) {
  const material = panelMaterialName(result, panel.material_id)
  const dims = panelDims(result, panel)
  return `List ${panel.panel_index} · ${material}${dims ? ` · ${dims}` : ''} · KIM ${panelFillPercent(result, panel)}`
}

function resultPanelCount(result: CuttingResult) {
  return Object.values(result.panels_used_by_material).reduce((sum, count) => sum + count, 0)
}

function selectResult(resultId: string) {
  const result = props.draft.results.find((item) => item.id === resultId)
  emit('update:activeResultId', resultId)
  emit('update:activePanelId', result?.panels[0]?.id ?? null)
  activePlacementId.value = null
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

async function choose(result: CuttingResult) {
  // chooseResult can throw (stale/invalidated result, network) — surface it
  // rather than silently leaving the chosen result out of sync (CB-57).
  try {
    await cutting.chooseResult(props.draft.id, result.id)
  } catch {
    toast.danger("Natijani tanlab bo'lmadi. Qayta urinib ko'ring.")
    return
  }
  emit('update:activeResultId', result.id)
  emit('update:activePanelId', result.panels[0]?.id ?? null)
}
</script>

<template>
  <section id="cutting-results" class="client-card mt-6 scroll-mt-28 min-[860px]:scroll-mt-20">
    <div class="client-card-h">
      <div>
        <h2>Natija</h2>
        <p class="mt-1 text-sm text-ink-muted">PDF yuklab oling yoki natijadan buyurtma bering.</p>
      </div>
      <div v-if="chosenResult" class="flex flex-wrap items-center gap-2">
        <span
          v-if="chosenResult.source === 'imported_map'"
          class="client-pill bg-info-soft text-info"
        >
          Fayldan joylashuv
        </span>
        <span class="client-pill" :class="allPlaced ? 'client-pill-done' : 'client-pill-danger'">
          Joylashtirildi {{ placedCount }}/{{ requestedCount }}
        </span>
      </div>
      <span v-if="chosenResult?.status === 'invalidated'" class="client-pill client-pill-danger">
        eskirgan
      </span>
    </div>

    <div v-if="optimizeError" class="client-card-b">
      <div class="client-banner danger" role="alert">
        <span class="font-mono font-black">!</span>
        <span>
          {{ optimizeError }}
          <span v-if="cutting.traceId" class="mt-1 block text-xs font-normal opacity-80">
            trace {{ cutting.traceId }}
          </span>
        </span>
      </div>
    </div>

    <div v-if="!chosenResult && !optimizeError" class="client-card-b">
      <div class="client-empty">
        <div class="client-empty-icon"><Icon name="layers" /></div>
        <h3>Optimizer natijasi yo'q</h3>
        <p>Qismlar saqlangach optimallashtirishni ishga tushiring.</p>
      </div>
    </div>

    <div v-if="chosenResult" class="grid gap-5 p-5">
      <div v-if="savingsBanner" class="client-banner success">
        <span class="font-mono font-black">✓</span>
        <span>{{ savingsBanner }}</span>
      </div>

      <CuttingVariantTabs
        v-if="hasVariantTabs"
        :results="draft.results"
        :active-result-id="chosenResult.id"
        :chosen-result-id="draft.chosen_result_id"
        @select="selectResult"
      />

      <div class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div class="min-w-0 space-y-4">
          <div v-if="chosenResult.status === 'invalidated'" class="client-banner warn">
            <span class="font-mono font-black">!</span>
            <span
              >Qismlar o'zgargani uchun bu natija eskirgan. Yangi optimallashtirishni ishga
              tushiring.</span
            >
          </div>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="text-sm font-bold text-ink-muted">
              {{ chosenResult.algorithm_name }}
            </div>
            <button
              v-if="!activeResultIsChosen"
              type="button"
              class="mp-button mp-button-outline"
              @click="choose(chosenResult)"
            >
              Shu variantni tanlash
            </button>
            <span v-else class="mp-chip bg-success-soft text-success">Tanlangan ✓</span>
          </div>

          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div class="rounded-md border border-hairline bg-elevated p-4">
              <div class="text-xs font-bold uppercase text-ink-muted">Taxminiy narx</div>
              <div class="mt-1 text-lg font-extrabold text-ink">Filial tanlang</div>
            </div>
            <div class="rounded-md border border-hairline bg-elevated p-4">
              <div class="text-xs font-bold uppercase text-ink-muted">Listlar</div>
              <div class="mt-1 font-serif text-2xl font-semibold text-ink">{{ totalPanels }}</div>
              <p v-if="materialBreakdown.length" class="mt-1 truncate text-xs text-ink-muted">
                {{
                  materialBreakdown
                    .map((row) => `${row.name}${row.dims ? ` ${row.dims}` : ''}: ${row.count}`)
                    .join(' · ')
                }}
              </p>
            </div>
            <div class="rounded-md border border-hairline bg-elevated p-4">
              <div class="text-xs font-bold uppercase text-ink-muted">Chiqit</div>
              <div class="mt-1 font-serif text-2xl font-semibold text-success">
                {{ resultWaste }}
              </div>
            </div>
            <div class="rounded-md border border-hairline bg-elevated p-4">
              <div class="text-xs font-bold uppercase text-ink-muted">Krom</div>
              <div class="mt-1 font-serif text-2xl font-semibold text-ink">
                {{ metres(consumedShop + consumedOwn) }}
              </div>
            </div>
          </div>

          <div v-if="!allPlaced" class="client-banner danger" role="alert">
            <span class="font-mono font-black">!</span>
            <span>
              {{ requestedCount - placedCount }} ta qism panelga joylashmadi — qism o'lchamini
              kichraytiring yoki boshqa panel tanlang.
            </span>
          </div>

          <section class="rounded-lg border border-hairline bg-elevated p-4">
            <CuttingSheetThumbnails
              :result="chosenResult"
              :active-panel-id="activePanel?.id ?? null"
              @select="emit('update:activePanelId', $event)"
            />
          </section>

          <section class="rounded-lg border border-hairline bg-elevated p-4">
            <p v-if="activePanel" class="mb-3 text-sm font-extrabold text-ink">
              {{ panelCaption(chosenResult, activePanel) }}
            </p>
            <CuttingPanelSvg
              v-if="activePanel"
              :result="chosenResult"
              :panel="activePanel"
              :active-placement-id="activePlacementId"
              @select-placement="selectPlacement"
            />
          </section>
        </div>

        <aside class="space-y-4">
          <button
            type="button"
            class="mp-button mp-button-outline w-full"
            :disabled="cutting.downloadingId === chosenResult.id"
            @click="cutting.downloadClientPdf(chosenResult.id)"
          >
            {{ cutting.downloadingId === chosenResult.id ? 'Yuklanmoqda…' : 'PDF yuklab olish' }}
          </button>
          <p
            v-if="cutting.downloadError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
            role="alert"
          >
            {{ cutting.downloadError }}
            <span v-if="cutting.downloadTraceId" class="block text-xs font-normal opacity-80">
              trace {{ cutting.downloadTraceId }}
            </span>
          </p>
          <div class="rounded-lg border border-hairline bg-sunk p-4">
            <h3 class="text-sm font-extrabold text-ink">Krom (material bo'yicha)</h3>
            <template v-if="edgeByMaterial.length">
              <ul class="mt-2 space-y-1.5 text-sm">
                <li v-for="row in edgeByMaterial" :key="row.id" class="flex justify-between gap-3">
                  <span class="min-w-0 truncate text-ink-soft">{{ row.name }}</span>
                  <span class="shrink-0 font-mono text-ink">{{ metres(row.total) }}</span>
                </li>
              </ul>
            </template>
            <p v-else class="mt-2 text-sm text-ink-soft">Krom ishlatilmagan.</p>
          </div>
          <div v-if="activePanel" class="rounded-lg border border-hairline bg-sunk p-4">
            <h3 class="text-sm font-extrabold text-ink">Joylashuvlar</h3>
            <div class="mt-3 grid gap-2">
              <button
                v-for="placement in activePanel.placements"
                :key="placement.id"
                type="button"
                class="rounded-md border border-hairline bg-elevated px-3 py-2 text-left text-sm"
                :class="
                  placement.id === activePlacementId ? 'border-accent text-accent' : 'text-ink'
                "
                @click="selectPlacement(placement)"
              >
                <b class="font-semibold">{{ placement.length_mm }}×{{ placement.width_mm }} mm</b>
                <span class="text-ink-muted">#{{ placement.part_quantity_index }}</span>
                <span v-if="placement.rotated" class="font-bold text-accent">↻</span>
              </button>
            </div>
          </div>
        </aside>
      </div>

      <div
        v-if="footerResult"
        class="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-hairline-strong bg-elevated/95 px-4 py-3 shadow-[0_-6px_24px_-14px_rgb(15_27_45_/_30%)] backdrop-blur"
      >
        <div class="text-sm">
          <span class="font-mono font-bold text-ink">
            {{ resultPanelCount(footerResult) }} list ·
            {{ formatPercent(footerResult.waste_percentage) }} chiqit · Filial tanlang
          </span>
          <span v-if="viewingNonChosen" class="ml-2 text-ink-muted">Boshqa variant tanlangan</span>
        </div>
        <RouterLink
          v-if="draft.chosen_result_id"
          :to="rolePath(props.checkoutPath)"
          class="mp-button mp-button-primary"
        >
          Buyurtma berish
        </RouterLink>
      </div>
    </div>
  </section>
</template>
