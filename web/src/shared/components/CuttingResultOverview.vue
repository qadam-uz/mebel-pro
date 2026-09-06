<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { snapshotEdgeLabel, snapshotMaterialLabel } from '@/shared/app/cuttingDisplay'
import {
  clientResultFigures,
  deriveSnapshotEdgeRegistry,
  edgeRegistryEntryByMaterial,
  groupPanelPlacements,
  panelDisplayIndex,
  resultTotals,
  squareMetres,
} from '@/shared/app/cuttingResultsDisplay'
import { snapshotSheetSize } from '@/shared/app/materialLabel'
import CuttingPartsList from '@/shared/components/CuttingPartsList.vue'
import CuttingResultSheets from '@/shared/components/CuttingResultSheets.vue'
import {
  metres,
  useCuttingStore,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'

// The whole read-only face of a finished cutting result: the material and edge
// tally, the sheet strip, the active sheet's drawing, and the per-sheet parts
// rail — with the two-way selection between drawing and rails.
//
// It takes a `CuttingResult` and nothing else. Everything draft-shaped (price
// quote, checkout CTA, "this result is stale" banners) stays with the caller,
// which is what lets a placed order render the identical screen after its draft
// has been consumed.
const props = withDefaults(
  defineProps<{
    result: CuttingResult
    activePanelId: string | null
    /**
     * The result stage's price card repeats the four figures as its 2×2 grid
     * below `xl` (§7.7), where this rail has dropped under the drawing — so
     * that one caller asks for the rail's figures from `xl` up only. Every
     * other caller (order confirmation, the order detail's Chizma tab) has no
     * second copy and leaves this off.
     */
    figuresXlOnly?: boolean
  }>(),
  { figuresXlOnly: false },
)

// SPEC_CLIENT_UX_MVP decision 9 + §7.7. The client reads a shorter version of
// the same screen — four figures, and a materials list that is a name and a
// sheet count. Keyed on the store scope rather than a prop because every caller
// on the client path (result stage, order confirmation, the order detail's
// Chizma tab) wants the same answer, and a prop would be three chances to
// forget it. The workshop's copy is untouched.
const isClientView = computed(() => cutting.scope === 'client')

const emit = defineEmits<{
  'update:activePanelId': [string | null]
}>()

const { t } = useI18n()
const cutting = useCuttingStore()

const activePartRef = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)
// Carries a selection across a sheet switch: picking a row from another sheet
// in the narrow-viewport parts list changes the active panel, and the panel
// watcher below would otherwise wipe the selection it was made for.
const pendingPartRef = ref<string | null>(null)
const sheets = ref<{ revealDrawing: () => void } | null>(null)

const activePanel = computed(
  () =>
    props.result.panels.find((panel) => panel.id === props.activePanelId) ??
    props.result.panels[0] ??
    null,
)
const snapshotEdgeRegistry = computed(() =>
  deriveSnapshotEdgeRegistry(props.result.parts_snapshot ?? []),
)
const panelMaterials = computed(() =>
  Object.entries(props.result.panels_used_by_material)
    .filter(([, count]) => count > 0)
    .map(([id, count]) => ({
      id,
      count,
      label: snapshotMaterialLabel(props.result.material_snapshots[id], id.slice(0, 8)),
      // Any claim at all marks the row: a client who brought 2 of the 5 sheets
      // this layout needs still brought material, and the split itself is the
      // ownership dialog's and the quote's job to state — the chip only answers
      // "whose board is this", which `> 0` answers exactly.
      own: (props.result.own_panel_counts?.[id] ?? 0) > 0,
      // How much of this material's sheets the layout actually consumed —
      // averaged over its own panels, so a material is judged against itself
      // rather than against a result-wide figure two materials would share.
      fill: materialFillPercent(id),
    }))
    .sort((left, right) => left.label.localeCompare(right.label, 'uz')),
)

function materialFillPercent(materialId: string) {
  const panels = props.result.panels.filter((panel) => panel.material_id === materialId)
  if (panels.length === 0) return null
  const { length, width } = snapshotSheetSize(props.result.material_snapshots[materialId])
  if (length <= 0 || width <= 0) return null
  const sheetArea = length * width * panels.length
  const waste = panels.reduce((sum, panel) => sum + panel.waste_area_mm2, 0)
  return Math.max(0, Math.min(100, 100 - (waste / sheetArea) * 100))
}
// Three literal keys, never an interpolated one: `pnpm i18n:check` only
// resolves keys it can read as literals, so a computed key would leave the
// chip's copy entirely outside the gate. The client branch exists because the
// same screen renders for the client reading their own order, where
// "Mijoz materiali" is the third person for the person looking at it.
function sourceLabel(own: boolean) {
  if (!own) return t('cutting.source.shop')
  return cutting.scope === 'client' ? t('cutting.source.ownClient') : t('cutting.source.own')
}
const edgeByMaterial = computed(() => {
  const result = props.result
  const registry = snapshotEdgeRegistry.value
  const ids = new Set([
    ...Object.keys(result.edge_consumed_shop_by_material),
    ...Object.keys(result.edge_consumed_own_by_material),
  ])
  return [...ids]
    .map((id) => {
      const shop = result.edge_consumed_shop_by_material[id] ?? 0
      const own = result.edge_consumed_own_by_material[id] ?? 0
      const label = snapshotEdgeLabel(result.material_snapshots[id], id.slice(0, 8))
      const entry =
        edgeRegistryEntryByMaterial(registry, id, 'shop') ??
        edgeRegistryEntryByMaterial(registry, id, 'own')
      return { id, label, total: shop + own, entry }
    })
    .filter((row) => row.total > 0)
    .sort((left, right) => (left.entry?.number ?? 999) - (right.entry?.number ?? 999))
})
const activePanelGroups = computed(() =>
  activePanel.value ? groupPanelPlacements(props.result, activePanel.value) : [],
)

// D3.2: the order-level figures, which until now only existed on the order
// detail screen — so reading a fresh result meant leaving it. Nothing here is a
// new API field; `resultTotals` derives all five from the payload the optimizer
// already returns.
const summaryRows = computed(() => {
  const totals = resultTotals(props.result)
  const missing = Math.max(0, totals.requestedParts - totals.placedParts)
  // §7.7: four figures on the client — Detallar, Listlar, Kromka, Foydali
  // qoldiq. «Arra yo'li» is a saw metric the shop plans around and «Chiqim» is
  // the shop's yield; a client who is quoted a fixed price cannot act on
  // either, so both stay in the workshop app.
  //
  // One composer for those four (`clientResultFigures`), shared with the result
  // stage's price card: they sit on the same screen at different widths, so two
  // copies meant «Detallar 2 / 2 · Kromka lentasi» beside «Detallar 2 ta ·
  // Kromka». The one thing the card has no room for is the shortage, which on
  // the client app is the only signal that a part did not fit — so it is spelled
  // out here in words as well as coloured (colour alone is never the signal,
  // DESIGN.md).
  if (isClientView.value) {
    return clientResultFigures(props.result).map((figure) =>
      figure.key === 'parts' && missing
        ? {
            ...figure,
            value: t('cutting.result.summaryPartsShort', {
              placed: totals.placedParts,
              requested: totals.requestedParts,
              n: missing,
            }),
            short: true,
          }
        : { ...figure, short: false },
    )
  }
  const rows = [
    {
      key: 'parts',
      label: t('cutting.result.summaryParts'),
      value: missing
        ? t('cutting.result.summaryPartsShort', {
            placed: totals.placedParts,
            requested: totals.requestedParts,
            n: missing,
          })
        : t('cutting.result.summaryPartsValue', {
            placed: totals.placedParts,
            requested: totals.requestedParts,
          }),
      short: missing > 0,
    },
    {
      key: 'sheets',
      label: t('cutting.result.summarySheets'),
      value: `${totals.sheets} ${t('cutting.unit.sheet', totals.sheets)}`,
      short: false,
    },
    {
      key: 'cut',
      label: t('cutting.result.summaryCutLength'),
      value: metres(totals.cutLengthMm),
      short: false,
    },
    {
      key: 'edge',
      label: t('cutting.result.summaryEdge'),
      // Em-dash rather than "0.00 m": a drawing with no banding at all has no
      // tape figure, and printing a zero invites the reader to look for one.
      value: totals.edgeConsumedMm > 0 ? metres(totals.edgeConsumedMm) : '—',
      short: false,
    },
    {
      key: 'offcuts',
      label: t('cutting.result.summaryOffcuts'),
      value: totals.usableOffcutCount
        ? t('cutting.result.summaryOffcutsValue', {
            n: totals.usableOffcutCount,
            area: squareMetres(totals.usableOffcutAreaMm2),
          })
        : '—',
      short: false,
    },
  ]
  return rows
})

watch(
  () => activePanel.value?.id,
  () => {
    if (pendingPartRef.value) {
      activePartRef.value = pendingPartRef.value
      activePlacementId.value = null
      pendingPartRef.value = null
      return
    }
    clearSelection()
  },
)

function clearSelection() {
  activePartRef.value = null
  activePlacementId.value = null
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
  activePartRef.value = placement.part_ref
  const panelId = activePanel.value?.id
  void nextTick(() => {
    // Both rails carry the part: the desktop per-sheet rail and the narrow
    // parts list. Only one of them is displayed at a time — scrollIntoView on
    // the hidden one is a no-op, so scrolling both keeps this breakpoint-free.
    // The desktop rail scrolls inside the page beside the drawing, so
    // 'nearest' is right there; the narrow list scrolls the page itself, where
    // 'nearest' would leave the row pinned to the very bottom edge.
    document
      .querySelector<HTMLElement>(`[data-panel-part-ref="${placement.part_ref}"]`)
      ?.scrollIntoView({ block: 'nearest' })
    if (panelId) {
      document
        .querySelector<HTMLElement>(`[data-parts-row="${panelId}:${placement.part_ref}"]`)
        ?.scrollIntoView({ block: 'center' })
    }
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

// A parts-list row can point at a sheet the drawing isn't showing: switch the
// sheet first, then let the panel watcher apply the pending selection.
function selectListPart(target: { panelId: string; partRef: string }) {
  if (target.panelId === activePanel.value?.id) {
    selectPartGroup(target.partRef)
  } else {
    pendingPartRef.value = target.partRef
    emit('update:activePanelId', target.panelId)
  }
  revealDrawing()
}

// The list sits below the drawing, so a row tapped near the bottom of a long
// result would highlight a sheet that is off-screen — the tap would look like
// it did nothing. Centring is deliberate over `block: 'start'`: both shells
// stack a tall sticky header on narrow viewports, which would swallow a
// top-aligned card.
function revealDrawing() {
  void nextTick(() => sheets.value?.revealDrawing())
}
</script>

<template>
  <div
    class="grid gap-5 xl:grid-cols-[minmax(190px,220px)_minmax(0,1fr)] 2xl:grid-cols-[minmax(220px,280px)_minmax(0,1fr)]"
  >
    <div class="order-1 min-w-0 space-y-4 xl:col-start-2 xl:row-start-1">
      <slot name="banners" />

      <CuttingResultSheets
        ref="sheets"
        :result="result"
        :active-panel-id="activePanel?.id ?? null"
        :active-part-ref="activePartRef"
        :active-placement-id="activePlacementId"
        @update:active-panel-id="emit('update:activePanelId', $event)"
        @select-placement="selectPlacement"
        @clear-selection="clearSelection"
      />

      <!-- QAD-177: below `md` the drawing is an overview only — a 2800 mm sheet
           renders ~7× reduced and its labels cannot be read. The numbers move
           into this text list; at `md` and up the drawing is legible and the
           per-sheet rail in the aside carries the detail. -->
      <CuttingPartsList
        class="md:hidden"
        :result="result"
        :active-panel-id="activePanel?.id ?? null"
        :active-part-ref="activePartRef"
        @select="selectListPart"
      />
    </div>

    <aside class="order-2 space-y-4 xl:col-start-1 xl:row-start-1">
      <div class="rounded-lg border border-hairline p-4">
        <h3 class="text-sm font-extrabold text-ink">{{ $t('cutting.result.materialsTitle') }}</h3>
        <ul class="mt-2 space-y-1.5 text-sm">
          <li
            v-for="material in panelMaterials"
            :key="material.id"
            class="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-2"
          >
            <!-- Deliberately NOT the decor's colour, though the gap spec asks
                 for it here too. `colorForMaterial` is a pastel ramp built for
                 the 26-30px swatches; at 6px on white it lands near 1.5:1, under
                 DESIGN.md's 3:1 floor for a UI mark, and the ink dot it would
                 replace reads at 5.2:1. The bar outranks the handoff, and the
                 recognition the spec is after is carried by the two real
                 swatches on the order result. -->
            <span class="mt-1.5 size-1.5 rounded-full bg-ink-muted" aria-hidden="true"></span>
            <!-- The chip nests inside the label column rather than taking a
                 fourth grid track: the tape list below shares this template,
                 and a track it never fills would pull its counts out of line. -->
            <span class="min-w-0">
              <span class="block font-bold leading-tight text-ink-soft">{{ material.label }}</span>
              <!-- Decision 9: no «Ombordan» chip on the client. Own material is
                   hidden in the MVP (§7.7), so every board is the workshop's —
                   a chip that says the same thing on every row is noise. -->
              <span
                v-if="!isClientView"
                class="mt-1 inline-block rounded px-1.5 py-0.5 text-[11px] font-bold"
                :class="
                  material.own
                    ? 'bg-accent-soft text-accent-strong'
                    : 'bg-neutral-soft text-ink-nav'
                "
                >{{ sourceLabel(material.own) }}</span
              >
            </span>
            <span class="shrink-0 text-right">
              <span class="block text-ink"
                >{{ material.count }} {{ $t('cutting.unit.sheet', material.count) }}</span
              >
              <!-- The bar is a second reading of the number beside it, never
                   the only one: the percentage is written out, so a bar that
                   fails to paint costs nothing.
                   Decision 9: gone on the client — per-material utilisation is
                   a yield question the shop answers, and the per-sheet figure
                   on the sheet's own label already covers what a client asks. -->
              <template v-if="!isClientView && material.fill !== null">
                <span class="num block text-[11.5px] text-ink-soft">
                  {{ $t('cutting.result.fillUsed', { fill: `${material.fill.toFixed(0)}%` }) }}
                </span>
                <span
                  class="mt-1 block h-[5px] w-full min-w-[72px] overflow-hidden rounded-full bg-track"
                  aria-hidden="true"
                >
                  <span
                    class="block h-full rounded-full bg-accent"
                    :style="{ width: `${material.fill}%` }"
                  ></span>
                </span>
              </template>
            </span>
          </li>
        </ul>

        <div class="my-4 border-t border-hairline"></div>

        <h3 class="text-sm font-extrabold text-ink">{{ $t('cutting.result.edgeTitle') }}</h3>
        <ul v-if="edgeByMaterial.length" class="mt-2 space-y-1.5 text-sm">
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
              <span class="block whitespace-normal text-sm font-bold leading-tight text-ink-soft">
                {{ row.label }}
              </span>
            </span>
            <span class="shrink-0 text-ink">{{ metres(row.total) }}</span>
          </li>
        </ul>
        <p v-else class="mt-2 text-sm text-ink-soft">{{ $t('cutting.result.noEdgeUsed') }}</p>

        <div class="my-4 border-t border-hairline"></div>

        <!-- No heading: the two lists above earn theirs by naming what their
             rows are, and every row here already names itself. A third heading
             would also give the page two more `Kromka`/`Materiallar` accessible
             names to collide with. -->
        <dl class="text-[13px]" :class="figuresXlOnly ? 'max-xl:hidden' : ''">
          <div
            v-for="row in summaryRows"
            :key="row.key"
            class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-1.5"
          >
            <dt class="text-ink-soft">{{ row.label }}</dt>
            <dd
              class="shrink-0 text-right text-[13.5px] font-semibold"
              :class="row.short ? 'text-danger' : 'text-ink'"
            >
              {{ row.value }}
            </dd>
          </div>
        </dl>
      </div>

      <!-- Superseded below `md` by CuttingPartsList, which covers every sheet
           instead of only the active one. Two rails doing the same job on one
           screen is exactly what the design system forbids. -->
      <div v-if="activePanel" class="rounded-lg border border-hairline p-4 max-md:hidden">
        <h3 class="text-sm font-extrabold text-ink">
          {{ $t('cutting.result.partsOnSheet', { n: panelDisplayIndex(result, activePanel) }) }}
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
                ? 'border-accent-tint bg-accent-soft text-accent-strong'
                : 'border-hairline bg-elevated text-ink hover:border-accent-tint'
            "
            @click="selectPartGroup(group.partRef)"
          >
            <span class="flex min-w-0 flex-wrap items-center gap-1.5">
              <b class="min-w-0 truncate font-semibold"
                >{{ group.name }} · {{ group.length_mm }}×{{ group.width_mm }}</b
              >
              <span class="rounded bg-sunk px-1.5 py-0.5 text-[11px] font-bold text-ink-muted">
                × {{ group.count }}
              </span>
              <span
                v-if="group.rotatedCount > 0"
                class="rounded bg-accent-soft px-1.5 py-0.5 text-[11px] font-bold text-accent-strong"
              >
                ↻ {{ group.rotatedCount }}
              </span>
            </span>
          </button>
        </div>
      </div>
    </aside>
  </div>
</template>
