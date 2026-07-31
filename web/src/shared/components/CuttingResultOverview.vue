<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { snapshotEdgeLabel, snapshotMaterialLabel } from '@/shared/app/cuttingDisplay'
import {
  deriveSnapshotEdgeRegistry,
  edgeRegistryEntryByMaterial,
  groupPanelPlacements,
  panelDisplayIndex,
} from '@/shared/app/cuttingResultsDisplay'
import CuttingPartsList from '@/shared/components/CuttingPartsList.vue'
import CuttingResultSheets from '@/shared/components/CuttingResultSheets.vue'
import { metres, type CuttingPlacement, type CuttingResult } from '@/shared/stores/cutting'

// The whole read-only face of a finished cutting result: the material and edge
// tally, the sheet strip, the active sheet's drawing, and the per-sheet parts
// rail — with the two-way selection between drawing and rails.
//
// It takes a `CuttingResult` and nothing else. Everything draft-shaped (price
// quote, checkout CTA, "this result is stale" banners) stays with the caller,
// which is what lets a placed order render the identical screen after its draft
// has been consumed.
const props = defineProps<{
  result: CuttingResult
  activePanelId: string | null
}>()

const emit = defineEmits<{
  'update:activePanelId': [string | null]
}>()

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
    }))
    .sort((left, right) => left.label.localeCompare(right.label, 'uz')),
)
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
        <h3 class="text-sm font-extrabold text-ink">Materiallar</h3>
        <ul class="mt-2 space-y-1.5 text-sm">
          <li
            v-for="material in panelMaterials"
            :key="material.id"
            class="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-2"
          >
            <span class="mt-1.5 size-1.5 rounded-full bg-ink-muted" aria-hidden="true"></span>
            <span class="min-w-0 font-bold leading-tight text-ink-soft">{{ material.label }}</span>
            <span class="shrink-0 font-mono text-ink">{{ material.count }} list</span>
          </li>
        </ul>

        <div class="my-4 border-t border-hairline"></div>

        <h3 class="text-sm font-extrabold text-ink">Kromka</h3>
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
            <span class="shrink-0 font-mono text-ink">{{ metres(row.total) }}</span>
          </li>
        </ul>
        <p v-else class="mt-2 text-sm text-ink-soft">Kromka ishlatilmagan.</p>
      </div>

      <!-- Superseded below `md` by CuttingPartsList, which covers every sheet
           instead of only the active one. Two rails doing the same job on one
           screen is exactly what the design system forbids. -->
      <div v-if="activePanel" class="rounded-lg border border-hairline p-4 max-md:hidden">
        <h3 class="text-sm font-extrabold text-ink">
          Detallar — List {{ panelDisplayIndex(result, activePanel) }}
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
  </div>
</template>
