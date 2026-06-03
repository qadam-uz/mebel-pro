<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import CuttingPanelSvg from '@/shared/components/CuttingPanelSvg.vue'
import {
  metres,
  useCuttingStore,
  type CuttingPanel,
  type CuttingPlacement,
  type CuttingResult,
} from '@/shared/stores/cutting'

const route = useRoute()
const cutting = useCuttingStore()
const resultId = computed(() => String(route.params.result_id))
const activePanelId = ref<string | null>(null)
const activePlacementId = ref<string | null>(null)

const plan = computed(() => cutting.currentWorkshopPlan)
const result = computed(() => plan.value?.result ?? null)
const activePanel = computed(() => {
  const current = result.value
  if (!current) return null
  return (
    current.panels.find((panel) => panel.id === activePanelId.value) ?? current.panels[0] ?? null
  )
})
const totalPanels = computed(() =>
  result.value
    ? Object.values(result.value.panels_used_by_material).reduce((sum, count) => sum + count, 0)
    : 0,
)

function panelTitle(current: CuttingResult, panel: CuttingPanel) {
  const snapshot = current.material_snapshots[panel.material_id]
  return `${String(snapshot?.name ?? 'Panel')} · ${panel.panel_index}`
}

function selectPlacement(placement: CuttingPlacement) {
  activePlacementId.value = placement.id
}

onMounted(async () => {
  await cutting.loadWorkshopPlan(resultId.value)
  activePanelId.value = result.value?.panels[0]?.id ?? null
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <RouterLink to="/workshop/cutting-plans" class="text-sm font-bold text-accent">
          Cutting plans
        </RouterLink>
        <h1 class="mt-2 font-serif text-3xl font-semibold text-ink">Read-only cutting plan</h1>
        <p v-if="plan" class="mt-2 text-base text-ink-soft">
          {{ plan.order_number }} · {{ plan.algorithm_name }}
        </p>
      </div>
      <button
        v-if="plan"
        type="button"
        class="mp-button mp-button-primary"
        @click="cutting.downloadWorkshopPdf(plan.id)"
      >
        Download PDF
      </button>
    </div>

    <section v-if="cutting.workshopLoading" class="mp-surface p-5" aria-live="polite">
      Loading cutting plan
    </section>
    <section v-else-if="cutting.error === 'permission_denied'" class="mp-surface p-5 text-warning">
      <div class="font-extrabold">Permission denied</div>
      <p class="mt-1 text-sm">This account cannot open workshop cutting plans.</p>
    </section>
    <section v-else-if="cutting.error" class="mp-surface p-5 text-danger">
      Cutting plan could not be loaded. trace {{ cutting.traceId ?? 'unavailable' }}
    </section>

    <template v-else-if="plan && result">
      <section class="grid gap-3 sm:grid-cols-4">
        <div class="rounded-md bg-sunk p-3">
          <div class="text-xs font-bold uppercase text-ink-muted">Waste</div>
          <div class="mt-1 text-xl font-extrabold text-ink">
            {{ (Number(result.waste_percentage) * 100).toFixed(2) }}%
          </div>
        </div>
        <div class="rounded-md bg-sunk p-3">
          <div class="text-xs font-bold uppercase text-ink-muted">Panels</div>
          <div class="mt-1 text-xl font-extrabold text-ink">{{ totalPanels }}</div>
        </div>
        <div class="rounded-md bg-sunk p-3">
          <div class="text-xs font-bold uppercase text-ink-muted">Edge</div>
          <div class="mt-1 text-xl font-extrabold text-ink">
            {{ metres(result.total_edge_length_mm) }}
          </div>
        </div>
        <div class="rounded-md bg-sunk p-3">
          <div class="text-xs font-bold uppercase text-ink-muted">Cut length</div>
          <div class="mt-1 text-xl font-extrabold text-ink">
            {{ metres(result.total_cut_length_mm) }}
          </div>
        </div>
      </section>

      <section class="mp-surface grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div class="min-w-0 space-y-4">
          <div class="flex flex-wrap gap-2">
            <button
              v-for="panel in result.panels"
              :key="panel.id"
              type="button"
              class="mp-chip"
              :class="panel.id === activePanel?.id ? 'bg-accent-soft text-accent' : ''"
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

        <aside v-if="activePanel" class="rounded-lg border border-hairline bg-sunk p-4">
          <h2 class="text-sm font-extrabold text-ink">Placements</h2>
          <div class="mt-3 grid gap-2">
            <button
              v-for="placement in activePanel.placements"
              :key="placement.id"
              type="button"
              class="rounded-md border border-hairline bg-elevated px-3 py-2 text-left text-sm"
              :class="placement.id === activePlacementId ? 'border-accent text-accent' : 'text-ink'"
              @click="selectPlacement(placement)"
            >
              {{ placement.part_ref }} #{{ placement.part_quantity_index }}
              <span v-if="placement.rotated" class="font-bold">R</span>
            </button>
          </div>
        </aside>
      </section>
    </template>
  </section>
</template>
