<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { clientErrorLabel } from '@/shared/app/clientUi'
import {
  deriveSnapshotEdgeRegistry,
  edgeRegistryEntryByMaterial,
} from '@/shared/app/cuttingResultsDisplay'
import { formatSom, formatTiyin } from '@/shared/formatters'
import { useRolePath } from '@/shared/app/paths'
import { useToast } from '@/shared/composables/useToast'
import Icon from '@/shared/components/AppIcon.vue'
import CuttingOwnMaterialDialog from '@/shared/components/CuttingOwnMaterialDialog.vue'
import CuttingResultOverview from '@/shared/components/CuttingResultOverview.vue'
import {
  metres,
  useCuttingStore,
  type CuttingDraft,
  type CuttingResult,
} from '@/shared/stores/cutting'
import type { OrderQuote } from '@/shared/stores/orders'

// CB-93 seam: the draft-side wrapper around a cutting result — the shared
// read-only view of the result itself lives in CuttingResultOverview, which a
// placed order renders too. What stays here is everything draft-shaped: the
// stale/unplaced banners, the "choose this variant" action, and the price quote
// with its checkout CTA.
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
const { t } = useI18n()

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
const activeResultIsChosen = computed(() => chosenResult.value?.id === props.draft.chosen_result_id)
// The receipt shows its own arithmetic — `2 × 300 000 = 600 000` — because a
// rolled-up subtotal asks to be trusted while a visible multiplication can be
// checked. Everything below comes from the quote as it already ships (CB-117);
// nothing is recomputed here beyond joining the edge lines to their registry
// number so the card, the drawing and the PDF all call a tape by ①②.
const receiptSheetLines = computed(() => quote.value?.material_lines ?? [])
const receiptEdgeRegistry = computed(() =>
  deriveSnapshotEdgeRegistry(footerResult.value?.parts_snapshot ?? []),
)
const receiptEdgeLines = computed(() =>
  (quote.value?.edge_lines ?? [])
    .map((line) => {
      const entry =
        edgeRegistryEntryByMaterial(receiptEdgeRegistry.value, line.material_id, 'shop') ??
        edgeRegistryEntryByMaterial(receiptEdgeRegistry.value, line.material_id, 'own')
      return { line, number: entry?.number ?? null }
    })
    .sort((left, right) => (left.number ?? 999) - (right.number ?? 999)),
)
// Client-supplied material. The claim lives on the draft so it survives a
// re-optimise; what a given layout charges is `min(claim, panels_used)`, which
// the quote already applied — the card only renders the split.
const ownDialogOpen = ref(false)
const ownPanelCounts = computed(() => props.draft.own_panel_counts ?? {})
const ownEdgeMaterialIds = computed(() => props.draft.own_edge_material_ids ?? [])

function ownSheets(line: { material_id: string; own_panels?: number }) {
  return line.own_panels ?? 0
}

function chargedSheets(line: { panels_used: number; own_panels?: number }) {
  return Math.max(0, line.panels_used - (line.own_panels ?? 0))
}

const ownSavingTiyin = computed(() => {
  const sheets = receiptSheetLines.value.reduce(
    (sum, line) => sum + ownSheets(line) * line.unit_price_tiyin,
    0,
  )
  // An own tape carries no material cost in the quote, so its saving is what the
  // shop rate would have charged for the same length.
  const tape = receiptEdgeLines.value.reduce((sum, row) => {
    if (!row.line.own) return sum
    const paid = receiptEdgeLines.value.find((other) => !other.line.own)
    const rate =
      paid && paid.line.consumed_mm > 0 ? paid.line.material_cost_tiyin / paid.line.consumed_mm : 0
    return sum + Math.round(rate * row.line.consumed_mm)
  }, 0)
  return sheets + tape
})

async function saveOwnMaterial(payload: {
  own_panel_counts: Record<string, number>
  own_edge_material_ids: string[]
}) {
  try {
    await cutting.updateDraft(props.draft.id, payload)
  } catch {
    toast.danger(t('cutting.error.saveFailed'))
    return
  }
  ownDialogOpen.value = false
  // Ownership never moves a part, so the layout stands; only what it costs
  // changed, which means the quote — not the optimiser — has to re-run.
  await reloadQuote()
}

// Edge labour is one figure across every tape; the per-tape split the quote
// carries is the material share, which already sits on its own row above.
const receiptEdgeServiceTiyin = computed(() =>
  (quote.value?.edge_lines ?? []).reduce((sum, line) => sum + line.service_cost_tiyin, 0),
)
const receiptEdgeServiceMm = computed(() =>
  (quote.value?.edge_lines ?? []).reduce((sum, line) => sum + line.consumed_mm, 0),
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
  () => void reloadQuote(),
  { immediate: true },
)

async function reloadQuote() {
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
    quoteError.value = clientErrorLabel(apiErrorCode(errorValue), t('cutting.error.quoteFailed'))
  } finally {
    quoteLoading.value = false
  }
}

async function choose(result: CuttingResult) {
  // chooseResult can throw (stale/invalidated result, network) — surface it
  // rather than silently leaving the chosen result out of sync (CB-57).
  try {
    await cutting.chooseResult(props.draft.id, result.id)
  } catch {
    toast.danger(t('cutting.error.resultChooseFailed'))
    return
  }
  emit('update:activePanelId', result.panels[0]?.id ?? null)
}
</script>

<template>
  <section id="cutting-results" class="client-card mt-6 scroll-mt-28 min-[860px]:scroll-mt-20">
    <div class="client-card-h">
      <div>
        <h2>{{ $t('cutting.result.title') }}</h2>
      </div>
      <div v-if="chosenResult" class="flex flex-wrap items-center gap-2">
        <span
          v-if="chosenResult.source === 'imported_map'"
          class="client-pill bg-info-soft text-info"
        >
          {{ $t('cutting.result.fromFile') }}
        </span>
        <span class="client-pill" :class="allPlaced ? 'client-pill-done' : 'client-pill-danger'">
          {{ $t('cutting.result.placed', { placed: placedCount, requested: requestedCount }) }}
        </span>
      </div>
      <span v-if="chosenResult?.status === 'invalidated'" class="client-pill client-pill-danger">
        {{ $t('cutting.result.stale') }}
      </span>
    </div>

    <div v-if="optimizeError" class="client-card-b">
      <div class="client-banner danger" role="alert">
        <span class="font-black">!</span>
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
        <h3>{{ $t('cutting.result.emptyTitle') }}</h3>
        <p>{{ $t('cutting.result.emptyBody') }}</p>
      </div>
    </div>

    <div v-if="chosenResult" class="grid gap-5 p-5">
      <div
        class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_312px] 2xl:grid-cols-[minmax(0,1fr)_352px]"
      >
        <CuttingResultOverview
          class="order-1 min-w-0 xl:col-start-1 xl:row-start-1"
          :result="chosenResult"
          :active-panel-id="activePanelId"
          @update:active-panel-id="emit('update:activePanelId', $event)"
        >
          <template #banners>
            <div v-if="chosenResult.status === 'invalidated'" class="client-banner warn">
              <span class="font-black">!</span>
              <span>{{ $t('cutting.result.invalidatedBanner') }}</span>
            </div>

            <div v-if="!activeResultIsChosen" class="flex justify-end">
              <button
                type="button"
                class="mp-button mp-button-outline"
                @click="choose(chosenResult)"
              >
                {{ $t('cutting.result.chooseVariant') }}
              </button>
            </div>

            <div v-if="!allPlaced" class="client-banner danger" role="alert">
              <span class="font-black">!</span>
              <span>
                {{
                  $t(
                    'cutting.result.notPlaced',
                    { n: requestedCount - placedCount },
                    requestedCount - placedCount,
                  )
                }}
              </span>
            </div>
          </template>
        </CuttingResultOverview>

        <aside class="order-2 xl:col-start-2 xl:row-start-1">
          <section class="rounded-lg border border-hairline bg-sunk p-4">
            <h3 class="font-display text-xl font-semibold text-ink">
              {{ $t('cutting.result.orderTitle') }}
            </h3>

            <div v-if="!branchId" class="py-4 text-sm text-ink-muted">
              {{ $t('cutting.result.priceNeedsBranch') }}
            </div>
            <div v-else-if="quoteLoading" class="py-4 text-sm font-bold text-ink-muted">
              {{ $t('cutting.result.priceLoading') }}
            </div>
            <div v-else-if="quoteError" class="py-4 text-sm font-bold text-danger" role="alert">
              {{ quoteError }}
            </div>

            <!-- A receipt, not a summary: each row carries the multiplication
                 behind it, so the client can check the price instead of taking
                 it on faith. Services sit in their own section because cutting
                 and banding are charged on every sheet and metre. -->
            <div v-else-if="quote" class="mt-4 grid gap-4">
              <section v-if="receiptSheetLines.length">
                <h4 class="pb-1.5 text-[12.5px] font-semibold text-ink-muted">
                  {{ $t('cutting.result.sectionSheets') }}
                </h4>
                <div
                  v-for="(line, index) in receiptSheetLines"
                  :key="line.material_id"
                  class="grid gap-0.5 border-t py-2.5"
                  :class="index === 0 ? 'border-hairline-strong' : 'border-hairline'"
                >
                  <p class="text-sm font-extrabold text-ink">
                    <span class="text-ink-muted">{{ index + 1 }}.</span> {{ line.material_name }}
                    <span class="whitespace-nowrap"
                      >— {{ line.panels_used }} {{ $t('cutting.unit.sheet') }}</span
                    >
                  </p>
                  <span v-if="ownSheets(line)" class="text-xs font-extrabold text-success">
                    {{
                      $t('cutting.own.sheetsSplit', {
                        own: ownSheets(line),
                        shop: chargedSheets(line),
                      })
                    }}
                  </span>
                  <span class="pt-0.5 text-right text-xs text-ink">
                    {{ chargedSheets(line) }} {{ $t('cutting.unit.sheet') }} ×
                    {{ formatSom(line.unit_price_tiyin) }} =
                    <b class="font-extrabold">{{ formatSom(line.line_total_tiyin) }}</b>
                  </span>
                </div>
              </section>

              <section v-if="receiptEdgeLines.length">
                <h4 class="pb-1.5 text-[12.5px] font-semibold text-ink-muted">
                  {{ $t('cutting.result.sectionEdges') }}
                </h4>
                <div
                  v-for="(row, index) in receiptEdgeLines"
                  :key="row.line.material_id"
                  class="grid gap-0.5 border-t py-2.5"
                  :class="index === 0 ? 'border-hairline-strong' : 'border-hairline'"
                >
                  <p class="text-sm font-extrabold text-ink">
                    <span class="text-ink-muted">{{ row.number ?? index + 1 }}.</span>
                    {{ row.line.material_name }}
                    <span class="whitespace-nowrap">— {{ metres(row.line.consumed_mm) }}</span>
                  </p>
                  <span v-if="row.line.own" class="text-xs font-extrabold text-success">
                    {{ $t('cutting.own.tapeFree') }}
                  </span>
                  <span v-else class="pt-0.5 text-right text-xs text-ink">
                    {{ metres(row.line.consumed_mm) }} ×
                    {{ formatSom(row.line.metre_price_tiyin) }} =
                    <b class="font-extrabold">{{ formatSom(row.line.material_cost_tiyin) }}</b>
                  </span>
                </div>
              </section>

              <section>
                <h4 class="pb-1.5 text-[12.5px] font-semibold text-ink-muted">
                  {{ $t('cutting.result.sectionServices') }}
                </h4>
                <div class="grid gap-2 border-t border-hairline-strong py-2.5">
                  <div class="grid gap-0.5">
                    <span class="text-sm text-ink">
                      {{ $t('cutting.result.serviceCutting') }}
                    </span>
                    <span class="text-right text-xs text-ink">
                      {{ quote.panels_used }} {{ $t('cutting.unit.sheet') }} ×
                      {{ formatSom(quote.cutting_rate_tiyin) }} =
                      <b class="font-extrabold">{{ formatSom(quote.subtotal_cutting_tiyin) }}</b>
                    </span>
                  </div>
                  <div v-if="receiptEdgeServiceTiyin > 0" class="grid gap-0.5">
                    <span class="text-sm text-ink">
                      {{ $t('cutting.result.serviceEdgeBanding') }}
                    </span>
                    <span class="text-right text-xs text-ink">
                      {{ metres(receiptEdgeServiceMm) }} ×
                      {{ formatSom(quote.edge_banding_rate_tiyin) }} =
                      <b class="font-extrabold">{{ formatSom(receiptEdgeServiceTiyin) }}</b>
                    </span>
                  </div>
                </div>
              </section>

              <div class="flex items-baseline justify-between gap-2.5 border-t border-ink pt-3">
                <span class="text-base font-extrabold text-ink">
                  {{ $t('cutting.result.total') }}
                </span>
                <span class="text-xl font-extrabold text-ink">
                  {{ formatTiyin(quote.total_tiyin) }}
                </span>
              </div>
              <p v-if="ownSavingTiyin > 0" class="text-right text-xs font-extrabold text-success">
                {{ $t('cutting.own.saved', { amount: formatTiyin(ownSavingTiyin) }) }}
              </p>

              <button
                type="button"
                class="mp-button w-full border-accent-tint bg-accent-soft text-accent-strong"
                @click="ownDialogOpen = true"
              >
                {{ $t('cutting.own.open') }}
              </button>
            </div>
            <p v-else class="py-4 text-sm text-ink-muted">
              {{ $t('cutting.result.priceUnavailable') }}
            </p>

            <div class="mt-3 grid gap-2">
              <button
                type="button"
                class="mp-button mp-button-outline w-full"
                :disabled="cutting.downloadingId === chosenResult.id"
                @click="cutting.openClientPdf(chosenResult.id)"
              >
                {{
                  cutting.downloadingId === chosenResult.id
                    ? $t('cutting.result.pdfOpening')
                    : $t('cutting.result.pdfOpen')
                }}
              </button>
              <RouterLink
                v-if="draft.chosen_result_id"
                :to="rolePath(props.checkoutPath)"
                class="mp-button mp-button-primary w-full"
              >
                {{ props.checkoutLabel ?? $t('cutting.result.checkout') }}
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

          <CuttingOwnMaterialDialog
            :open="ownDialogOpen"
            :saving="cutting.saving"
            :sheet-lines="receiptSheetLines"
            :edge-lines="receiptEdgeLines"
            :own-panel-counts="ownPanelCounts"
            :own-edge-material-ids="ownEdgeMaterialIds"
            @close="ownDialogOpen = false"
            @save="saveOwnMaterial"
          />
        </aside>
      </div>
    </div>
  </section>
</template>
