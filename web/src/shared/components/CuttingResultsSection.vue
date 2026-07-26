<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { clientErrorLabel } from '@/shared/app/clientUi'
import { snapshotEdgeLabel, snapshotMaterialLabel } from '@/shared/app/cuttingDisplay'
import {
  deriveSnapshotEdgeRegistry,
  edgeRegistryEntryByMaterial,
  groupPanelPlacements,
  panelDisplayIndex,
  panelFillPercent,
  resultPanelCount,
} from '@/shared/app/cuttingResultsDisplay'
import { formatTiyin } from '@/shared/formatters'
import { useRolePath } from '@/shared/app/paths'
import { useToast } from '@/shared/composables/useToast'
import Icon from '@/shared/components/AppIcon.vue'
import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import CuttingSheetThumbnails from '@/shared/components/CuttingSheetThumbnails.vue'
import {
  metres,
  useCuttingStore,
  type CuttingDraft,
  type CuttingPanel,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'
import type { OrderQuote } from '@/shared/stores/orders'

// CB-93 seam: the results surface — per-material panel strip + SVG visualiser,
// kromka/placement aside, and order/PDF actions. A draft has one orderable
// result; legacy drafts may carry older candidates, but they are never offered
// for comparison here.
const props = defineProps<{
  draft: CuttingDraft
  optimizeError: string | null
  activePanelId: string | null
  // Role-specific "place order" target (client vs workshop checkout), injected
  // by the editor from its adapter so this presentational component stays dumb.
  checkoutPath: string
  // CTA copy override — the revision flow says "save changes", not "place order".
  checkoutLabel?: string
  // The active branch pre-filter (null until one is picked) — drives the price
  // quote below; not the same as `draft.preferred_branch_id` while unsaved.
  branchId: string | null
  // Role-scoped quote call (client vs workshop endpoint), injected by the
  // editor from its adapter — same "stays dumb" reasoning as checkoutPath.
  quoteForDraft: (draftId: string, branchId: string) => Promise<OrderQuote>
}>()
const emit = defineEmits<{
  'update:activePanelId': [string | null]
}>()

const cutting = useCuttingStore()
const rolePath = useRolePath()
const toast = useToast()

const activePartRef = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)

const chosenResult = computed(() => {
  const draft = props.draft
  return (
    draft.results.find((result) => result.id === draft.chosen_result_id) ?? draft.results[0] ?? null
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
const activeResultIsChosen = computed(() => chosenResult.value?.id === props.draft.chosen_result_id)
const orderPanelCount = computed(() =>
  footerResult.value ? resultPanelCount(footerResult.value) : 0,
)
const orderEdgeLength = computed(() =>
  metres(
    sumRecord(footerResult.value?.edge_consumed_shop_by_material) +
      sumRecord(footerResult.value?.edge_consumed_own_by_material),
  ),
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
const panelMaterials = computed(() => {
  const result = chosenResult.value
  if (!result) return []
  return Object.entries(result.panels_used_by_material)
    .filter(([, count]) => count > 0)
    .map(([id, count]) => ({
      id,
      count,
      label: snapshotMaterialLabel(result.material_snapshots[id], id.slice(0, 8)),
    }))
    .sort((left, right) => left.label.localeCompare(right.label, 'uz'))
})
const snapshotEdgeRegistry = computed(() =>
  chosenResult.value ? deriveSnapshotEdgeRegistry(chosenResult.value.parts_snapshot ?? []) : [],
)
const activePanelGroups = computed(() =>
  chosenResult.value && activePanel.value
    ? groupPanelPlacements(chosenResult.value, activePanel.value)
    : [],
)

// The price always reflects the officially chosen result (what ordering now
// would cost) because the backend quote endpoint only prices that result.
const quote = ref<OrderQuote | null>(null)
const quoteLoading = ref(false)
const quoteError = ref<string | null>(null)

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

async function choose(result: CuttingResult) {
  // chooseResult can throw (stale/invalidated result, network) — surface it
  // rather than silently leaving the chosen result out of sync (CB-57).
  try {
    await cutting.chooseResult(props.draft.id, result.id)
  } catch {
    toast.danger("Natijani tanlab bo'lmadi. Qayta urinib ko'ring.")
    return
  }
  emit('update:activePanelId', result.panels[0]?.id ?? null)
}
</script>

<template>
  <section id="cutting-results" class="client-card mt-6 scroll-mt-28 min-[860px]:scroll-mt-20">
    <div class="client-card-h">
      <div>
        <h2>Kesish natijasi</h2>
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
      <div
        class="grid gap-5 xl:grid-cols-[minmax(190px,220px)_minmax(0,1fr)_250px] 2xl:grid-cols-[minmax(220px,280px)_minmax(0,1fr)_300px]"
      >
        <div
          class="order-1 min-w-0 space-y-4 xl:col-start-2 xl:row-start-1 2xl:col-start-2 2xl:row-start-1"
        >
          <div v-if="chosenResult.status === 'invalidated'" class="client-banner warn">
            <span class="font-mono font-black">!</span>
            <span
              >Qismlar o'zgargani uchun bu natija eskirgan. Yangi optimallashtirishni ishga
              tushiring.</span
            >
          </div>

          <div v-if="!activeResultIsChosen" class="flex justify-end">
            <button type="button" class="mp-button mp-button-outline" @click="choose(chosenResult)">
              Shu variantni tanlash
            </button>
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
              fit="viewport"
              @select-placement="selectPlacement"
              @clear-selection="clearSelection"
            />
            <p class="mt-2 text-right text-xs text-ink-muted">
              Arra kesigi {{ chosenResult.kerf_mm }} mm · Chetki qirqim
              {{ chosenResult.edge_trim_mm }} mm
            </p>
          </section>
        </div>

        <aside
          class="order-2 space-y-4 xl:col-start-1 xl:row-start-1 2xl:col-start-1 2xl:row-start-1"
        >
          <div class="rounded-lg border border-hairline p-4">
            <h3 class="text-sm font-extrabold text-ink">Materiallar</h3>
            <ul class="mt-2 space-y-1.5 text-sm">
              <li
                v-for="material in panelMaterials"
                :key="material.id"
                class="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-2"
              >
                <span class="mt-1.5 size-1.5 rounded-full bg-ink-muted" aria-hidden="true"></span>
                <span class="min-w-0 font-bold leading-tight text-ink-soft">{{
                  material.label
                }}</span>
                <span class="shrink-0 font-mono text-ink">{{ material.count }} list</span>
              </li>
            </ul>

            <div class="my-4 border-t border-hairline"></div>

            <h3 class="text-sm font-extrabold text-ink">Kromka</h3>
            <template v-if="edgeByMaterial.length">
              <ul class="mt-2 space-y-1.5 text-sm">
                <li
                  v-for="row in edgeByMaterial"
                  :key="row.id"
                  class="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-2"
                  :title="row.label"
                >
                  <span
                    class="mt-1.5 size-1.5 rounded-full bg-ink-muted"
                    :style="row.entry ? { background: row.entry.colorStyle.bg } : undefined"
                    aria-hidden="true"
                  ></span>
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
            <p v-else class="mt-2 text-sm text-ink-soft">Kromka ishlatilmagan.</p>
          </div>
          <div v-if="activePanel" class="rounded-lg border border-hairline p-4">
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
                </span>
              </button>
            </div>
          </div>
        </aside>

        <aside class="order-3 xl:col-start-3 xl:row-start-1 2xl:col-start-3 2xl:row-start-1">
          <section class="rounded-lg border border-hairline bg-sunk p-4">
            <h3 class="font-serif text-xl font-semibold text-ink">Buyurtmangiz</h3>

            <dl class="mt-4 grid grid-cols-2 gap-4 border-b border-hairline pb-4">
              <div>
                <dt class="text-xs font-bold uppercase text-ink-muted">Listlar</dt>
                <dd class="mt-1 font-serif text-xl font-semibold text-ink">
                  {{ orderPanelCount }} dona
                </dd>
              </div>
              <div>
                <dt class="text-xs font-bold uppercase text-ink-muted">Kromka</dt>
                <dd class="mt-1 font-serif text-xl font-semibold text-ink">
                  {{ orderEdgeLength }}
                </dd>
              </div>
            </dl>

            <div v-if="!branchId" class="py-4 text-sm text-ink-muted">
              Narxni ko'rish uchun filialni tanlang.
            </div>
            <div v-else-if="quoteLoading" class="py-4 text-sm font-bold text-ink-muted">
              Hisoblanmoqda…
            </div>
            <div v-else-if="quoteError" class="py-4 text-sm font-bold text-danger" role="alert">
              {{ quoteError }}
            </div>
            <dl v-else-if="quote" class="divide-y divide-hairline py-2">
              <div class="flex items-center justify-between gap-4 py-3 text-sm">
                <dt class="text-ink-soft">Kesish</dt>
                <dd class="font-mono font-bold text-ink">
                  {{ formatTiyin(quote.subtotal_cutting_tiyin) }}
                </dd>
              </div>
              <div class="flex items-center justify-between gap-4 py-3 text-sm">
                <dt class="text-ink-soft">Materiallar</dt>
                <dd class="font-mono font-bold text-ink">
                  {{ formatTiyin(quote.subtotal_materials_tiyin) }}
                </dd>
              </div>
              <div class="flex items-center justify-between gap-4 py-3 text-sm">
                <dt class="text-ink-soft">Kromka</dt>
                <dd class="font-mono font-bold text-ink">
                  {{ formatTiyin(quote.subtotal_edge_banding_tiyin) }}
                </dd>
              </div>
              <div class="flex items-center justify-between gap-4 py-4">
                <dt class="text-lg font-extrabold text-ink">Jami</dt>
                <dd class="font-mono text-lg font-extrabold text-ink">
                  {{ formatTiyin(quote.total_tiyin) }}
                </dd>
              </div>
            </dl>
            <p v-else class="py-4 text-sm text-ink-muted">Narx hozircha mavjud emas.</p>

            <div class="mt-3 grid gap-2">
              <button
                type="button"
                class="mp-button mp-button-outline w-full"
                :disabled="cutting.downloadingId === chosenResult.id"
                @click="cutting.downloadClientPdf(chosenResult.id)"
              >
                {{
                  cutting.downloadingId === chosenResult.id ? 'Yuklanmoqda…' : 'PDF yuklab olish'
                }}
              </button>
              <RouterLink
                v-if="draft.chosen_result_id"
                :to="rolePath(props.checkoutPath)"
                class="mp-button mp-button-primary w-full"
              >
                {{ props.checkoutLabel ?? 'Buyurtmaga davom etish' }}
              </RouterLink>
            </div>
            <p
              v-if="cutting.downloadError"
              class="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
              role="alert"
            >
              {{ cutting.downloadError }}
              <span v-if="cutting.downloadTraceId" class="block text-xs font-normal opacity-80">
                trace {{ cutting.downloadTraceId }}
              </span>
            </p>
          </section>
        </aside>
      </div>
    </div>
  </section>
</template>
