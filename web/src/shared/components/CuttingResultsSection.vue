<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { clientErrorLabel, formatPercent } from '@/shared/app/clientUi'
import { snapshotEdgeLabel, snapshotMaterialLabel } from '@/shared/app/cuttingDisplay'
import {
  deriveSnapshotEdgeRegistry,
  edgeRegistryEntryByMaterial,
  groupPanelPlacements,
  panelDisplayIndex,
  panelFillPercent,
  resultPanelCount,
  sheetsSavingsBanner,
  wasteToneClass,
} from '@/shared/app/cuttingResultsDisplay'
import { formatTiyinParts } from '@/shared/formatters'
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
import type { OrderQuote } from '@/shared/stores/orders'

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
  // The active branch pre-filter (null until one is picked) — drives the price
  // quote below; not the same as `draft.preferred_branch_id` while unsaved.
  branchId: string | null
  // Role-scoped quote call (client vs workshop endpoint), injected by the
  // editor from its adapter — same "stays dumb" reasoning as checkoutPath.
  quoteForDraft: (draftId: string, branchId: string) => Promise<OrderQuote>
}>()
const emit = defineEmits<{
  'update:activeResultId': [string | null]
  'update:activePanelId': [string | null]
}>()

const cutting = useCuttingStore()
const rolePath = useRolePath()
const toast = useToast()

const activePartRef = ref<string | null>(null)
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
  const registry = snapshotEdgeRegistry.value
  const ids = new Set([
    ...Object.keys(result.edge_consumed_shop_by_material),
    ...Object.keys(result.edge_consumed_own_by_material),
  ])
  return [...ids]
    .map((id) => {
      const shop = result.edge_consumed_shop_by_material[id] ?? 0
      const own = result.edge_consumed_own_by_material[id] ?? 0
      const snapshot = result.material_snapshots[id]
      const label = snapshotEdgeLabel(snapshot, id.slice(0, 8))
      const entry =
        edgeRegistryEntryByMaterial(registry, id, 'shop') ??
        edgeRegistryEntryByMaterial(registry, id, 'own')
      return {
        id,
        label,
        total: shop + own,
        entry,
      }
    })
    .filter((row) => row.total > 0)
    .sort((left, right) => (left.entry?.number ?? 999) - (right.entry?.number ?? 999))
})
const savingsBanner = computed<string | null>(() =>
  sheetsSavingsBanner(props.draft.results, chosenResult.value),
)
const snapshotEdgeRegistry = computed(() =>
  chosenResult.value ? deriveSnapshotEdgeRegistry(chosenResult.value.parts_snapshot ?? []) : [],
)
const activePanelGroups = computed(() =>
  chosenResult.value && activePanel.value
    ? groupPanelPlacements(chosenResult.value, activePanel.value, snapshotEdgeRegistry.value)
    : [],
)

// The price always reflects the officially CHOSEN result (what ordering right
// now would actually cost) — not whichever tab is being viewed — because the
// backend quote endpoint only ever prices `draft.chosen_result_id` (there is
// no per-variant preview quote). `viewingNonChosen` below annotates the card
// when the viewed tab differs, so the number never reads as "this variant".
const quote = ref<OrderQuote | null>(null)
const quoteLoading = ref(false)
const quoteError = ref<string | null>(null)
const priceParts = computed(() => (quote.value ? formatTiyinParts(quote.value.total_tiyin) : null))

watch(
  [
    () => props.draft.id,
    () => props.branchId,
    () => props.draft.chosen_result_id,
    () => footerResult.value?.status,
  ],
  async () => {
    const branchId = props.branchId
    const resultId = props.draft.chosen_result_id
    if (!branchId || !resultId || footerResult.value?.status === 'invalidated') {
      quote.value = null
      quoteError.value = null
      return
    }
    quoteLoading.value = true
    quoteError.value = null
    try {
      quote.value = await props.quoteForDraft(props.draft.id, branchId)
    } catch (errorValue) {
      quote.value = null
      quoteError.value = clientErrorLabel(apiErrorCode(errorValue), "Narxni hisoblab bo'lmadi")
    } finally {
      quoteLoading.value = false
    }
  },
  { immediate: true },
)

watch(
  () => activePanel.value?.id,
  () => {
    clearSelection()
  },
)

function sumRecord(record: Record<string, number> | undefined) {
  return Object.values(record ?? {}).reduce((sum, value) => sum + value, 0)
}

function panelCaption(result: CuttingResult, panel: CuttingPanel) {
  const material = snapshotMaterialLabel(
    result.material_snapshots[panel.material_id],
    panel.material_id.slice(0, 8),
  )
  return `List ${panelDisplayIndex(result, panel)} · ${material} · KIM ${panelFillPercent(result, panel)}`
}

function selectResult(resultId: string) {
  const result = props.draft.results.find((item) => item.id === resultId)
  emit('update:activeResultId', resultId)
  emit('update:activePanelId', result?.panels[0]?.id ?? null)
  activePlacementId.value = null
  activePartRef.value = null
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
  activePartRef.value = placement.part_ref
  void nextTick(() => {
    document
      .querySelector<HTMLElement>(`[data-panel-part-ref="${placement.part_ref}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  })
}

function selectPartGroup(partRef: string) {
  if (activePartRef.value === partRef && activePlacementId.value === null) {
    clearSelection()
    return
  }
  activePartRef.value = partRef
  activePlacementId.value = null
}

function clearSelection() {
  activePartRef.value = null
  activePlacementId.value = null
}

function tapeBadgeStyle(number: number) {
  const entry = snapshotEdgeRegistry.value.find((item) => item.number === number)
  if (!entry) return {}
  return {
    background: entry.colorStyle.bg,
    color: entry.colorStyle.fg,
  }
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
        <h2>Kesish natijasi</h2>
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
              <div v-if="!branchId" class="mt-1 text-lg font-extrabold text-ink">
                Filial tanlang
              </div>
              <div v-else-if="quoteLoading" class="mt-1 text-lg font-extrabold text-ink-muted">
                Hisoblanmoqda…
              </div>
              <div v-else-if="quoteError" class="mt-1 text-sm font-bold text-danger">
                {{ quoteError }}
              </div>
              <div v-else-if="priceParts" class="mt-1 flex items-baseline gap-1">
                <span class="font-serif text-2xl font-semibold text-ink">{{
                  priceParts.amount
                }}</span>
                <span class="text-xs font-bold text-ink-muted">{{ priceParts.unit }}</span>
              </div>
              <div v-else class="mt-1 text-lg font-extrabold text-ink">—</div>
              <p v-if="priceParts && viewingNonChosen" class="mt-1 text-xs text-ink-muted">
                tanlangan variant narxi
              </p>
            </div>
            <div class="rounded-md border border-hairline bg-elevated p-4">
              <div class="text-xs font-bold uppercase text-ink-muted">Listlar</div>
              <div class="mt-1 font-serif text-2xl font-semibold text-ink">{{ totalPanels }}</div>
            </div>
            <div class="rounded-md border border-hairline bg-elevated p-4">
              <div class="text-xs font-bold uppercase text-ink-muted">Chiqit</div>
              <div
                class="mt-1 font-serif text-2xl font-semibold"
                :class="wasteToneClass(chosenResult.waste_percentage)"
              >
                {{ resultWaste }}
              </div>
            </div>
            <div class="rounded-md border border-hairline bg-elevated p-4">
              <div class="text-xs font-bold uppercase text-ink-muted">Krom</div>
              <div class="mt-1 font-serif text-2xl font-semibold text-ink">
                {{ metres(consumedShop + consumedOwn) }}
              </div>
              <p v-if="edgeByMaterial.length" class="mt-1 text-xs text-ink-muted">
                {{ edgeByMaterial.length }} xil tasma
              </p>
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
              :active-part-ref="activePartRef"
              :active-placement-id="activePlacementId"
              @select-placement="selectPlacement"
              @clear-selection="clearSelection"
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
                <li
                  v-for="row in edgeByMaterial"
                  :key="row.id"
                  class="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2"
                  :title="row.label"
                >
                  <span
                    v-if="row.entry"
                    class="grid size-6 place-items-center rounded-full text-[11px] font-black"
                    :style="{
                      background: row.entry.colorStyle.bg,
                      color: row.entry.colorStyle.fg,
                    }"
                  >
                    {{ row.entry.number }}
                  </span>
                  <span v-else class="size-6"></span>
                  <span class="min-w-0">
                    <span
                      class="block whitespace-normal text-sm font-bold leading-tight text-ink-soft"
                    >
                      {{ row.label }}
                    </span>
                  </span>
                  <span class="shrink-0 font-mono text-ink">{{ metres(row.total) }}</span>
                </li>
              </ul>
            </template>
            <p v-else class="mt-2 text-sm text-ink-soft">Krom ishlatilmagan.</p>
          </div>
          <div v-if="activePanel" class="rounded-lg border border-hairline bg-sunk p-4">
            <h3 class="text-sm font-extrabold text-ink">
              Detallar — List {{ panelDisplayIndex(chosenResult, activePanel) }}
            </h3>
            <div class="mt-3 grid gap-2">
              <button
                v-for="group in activePanelGroups"
                :key="group.partRef"
                type="button"
                :data-panel-part-ref="group.partRef"
                class="rounded-md border px-3 py-2 text-left text-sm transition"
                :class="
                  group.partRef === activePartRef
                    ? 'border-accent bg-accent-soft text-accent'
                    : 'border-hairline bg-elevated text-ink hover:border-accent-tint'
                "
                @click="selectPartGroup(group.partRef)"
              >
                <span class="flex min-w-0 flex-wrap items-center gap-1.5">
                  <b class="min-w-0 truncate font-semibold"
                    >{{ group.name }} · {{ group.length_mm }}×{{ group.width_mm }}</b
                  >
                  <span
                    class="rounded bg-sunk px-1.5 py-0.5 font-mono text-[11px] font-bold text-ink-muted"
                  >
                    × {{ group.count }}
                  </span>
                  <span
                    v-if="group.rotatedCount > 0"
                    class="rounded bg-accent-soft px-1.5 py-0.5 font-mono text-[11px] font-bold text-accent"
                  >
                    ↻ {{ group.rotatedCount }}
                  </span>
                  <span
                    v-for="number in group.tapeNumbers"
                    :key="number"
                    class="grid size-5 place-items-center rounded-full text-[10px] font-black"
                    :style="tapeBadgeStyle(number)"
                  >
                    {{ number }}
                  </span>
                </span>
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
            {{ formatPercent(footerResult.waste_percentage) }} chiqit ·
            {{ !branchId ? 'Filial tanlang' : priceParts ? priceParts.full : '—' }}
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
