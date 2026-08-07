<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { registryColorStyle } from '@/shared/app/cuttingEditorDerived'
import AppModal from '@/shared/components/AppModal.vue'
import { formatTiyin } from '@/shared/formatters'
import { metres } from '@/shared/stores/cutting'
import type { MaterialPriceLine, EdgePriceLine } from '@/shared/stores/orders'

// Ownership is chosen here rather than in the parts editor because the two
// numbers it needs — how many sheets this layout uses and how many metres of
// each tape it consumes — do not exist until the optimiser has run. Before
// that the client can only guess; here they answer a question they can
// actually answer.
const props = defineProps<{
  open: boolean
  saving: boolean
  sheetLines: MaterialPriceLine[]
  edgeLines: { line: EdgePriceLine; number: number | null }[]
  ownPanelCounts: Record<string, number>
  ownEdgeMaterialIds: string[]
}>()

const emit = defineEmits<{
  close: []
  save: [payload: { own_panel_counts: Record<string, number>; own_edge_material_ids: string[] }]
}>()

const counts = ref<Record<string, number>>({})
const tapes = ref<string[]>([])

watch(
  () => props.open,
  (open) => {
    if (!open) return
    counts.value = { ...props.ownPanelCounts }
    tapes.value = [...props.ownEdgeMaterialIds]
  },
  { immediate: true },
)

function countFor(materialId: string) {
  return counts.value[materialId] ?? 0
}

// The `/ N` beside the stepper is information, not a ceiling. A client who owns
// seven sheets must be able to say so while today's layout needs five — the
// clamp happens per result, and capping here would throw the claim away right
// before the edit that needs it.
function adjust(materialId: string, delta: number) {
  counts.value = { ...counts.value, [materialId]: Math.max(0, countFor(materialId) + delta) }
}

function toggleTape(materialId: string) {
  tapes.value = tapes.value.includes(materialId)
    ? tapes.value.filter((id) => id !== materialId)
    : [...tapes.value, materialId]
}

// The only feedback the controls have: without it the steppers feel inert,
// because nothing else on this screen moves as they change.
const savingTiyin = computed(() => {
  const sheets = props.sheetLines.reduce((sum, line) => {
    const owned = Math.min(countFor(line.material_id), line.panels_used)
    return sum + owned * line.unit_price_tiyin
  }, 0)
  const tape = props.edgeLines.reduce((sum, row) => {
    if (!tapes.value.includes(row.line.material_id)) return sum
    return sum + row.line.material_cost_tiyin
  }, 0)
  return sheets + tape
})

function badgeStyle(number: number) {
  const style = registryColorStyle(number)
  return { background: style.bg, color: style.fg }
}

function submit() {
  emit('save', {
    own_panel_counts: Object.fromEntries(
      Object.entries(counts.value).filter(([, count]) => count > 0),
    ),
    own_edge_material_ids: [...tapes.value],
  })
}
</script>

<template>
  <AppModal
    :open="open"
    :title="$t('cutting.own.title')"
    max-width="max-w-md"
    @close="emit('close')"
  >
    <div class="grid gap-4">
      <section v-if="sheetLines.length" class="grid gap-3">
        <h3 class="text-[11px] font-extrabold uppercase tracking-wide text-ink-muted">
          {{ $t('cutting.result.sectionSheets') }}
        </h3>
        <div
          v-for="line in sheetLines"
          :key="line.material_id"
          class="flex flex-wrap items-center gap-3"
        >
          <span class="min-w-0 flex-1 text-sm font-extrabold text-ink">
            {{ line.material_name }}
          </span>
          <div
            class="flex shrink-0 items-stretch overflow-hidden rounded-md border border-hairline-strong"
          >
            <button
              type="button"
              class="min-h-10 w-9 bg-elevated font-extrabold text-ink hover:bg-sunk"
              :aria-label="$t('cutting.own.decrease')"
              @click="adjust(line.material_id, -1)"
            >
              −
            </button>
            <span
              class="grid min-w-11 place-items-center border-x border-hairline bg-elevated font-mono text-sm font-extrabold"
              :class="countFor(line.material_id) ? 'text-ink' : 'text-ink-muted'"
              aria-live="polite"
            >
              {{ countFor(line.material_id) }}
            </span>
            <button
              type="button"
              class="min-h-10 w-9 bg-elevated font-extrabold text-ink hover:bg-sunk"
              :aria-label="$t('cutting.own.increase')"
              @click="adjust(line.material_id, 1)"
            >
              +
            </button>
          </div>
          <span class="w-12 shrink-0 font-mono text-xs text-ink-muted">
            / {{ line.panels_used }}
          </span>
        </div>
      </section>

      <section v-if="edgeLines.length" class="grid gap-2.5 border-t border-hairline pt-4">
        <h3 class="text-[11px] font-extrabold uppercase tracking-wide text-ink-muted">
          {{ $t('cutting.result.sectionEdges') }}
        </h3>
        <label
          v-for="row in edgeLines"
          :key="row.line.material_id"
          class="flex items-center gap-2.5"
        >
          <input
            type="checkbox"
            class="size-4 shrink-0"
            :checked="tapes.includes(row.line.material_id)"
            @change="toggleTape(row.line.material_id)"
          />
          <span
            v-if="row.number"
            class="grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-extrabold"
            :style="badgeStyle(row.number)"
            aria-hidden="true"
            >{{ row.number }}</span
          >
          <span class="min-w-0 flex-1 truncate text-sm font-extrabold text-ink">
            {{ row.line.material_name }}
          </span>
          <span class="shrink-0 font-mono text-xs text-ink-muted">
            {{ $t('cutting.own.needed', { metres: metres(row.line.consumed_mm) }) }}
          </span>
        </label>
      </section>

      <!-- Three facts in one place: what is free, what is not, and when the
           work starts. The third is the one clients get wrong. -->
      <p class="import-chip import-chip-warn block">{{ $t('cutting.own.terms') }}</p>

      <div class="flex flex-wrap items-center gap-3 border-t border-hairline pt-3">
        <span v-if="savingTiyin > 0" class="min-w-0 text-sm font-extrabold text-success">
          {{ $t('cutting.own.saves', { amount: formatTiyin(savingTiyin) }) }}
        </span>
        <button
          type="button"
          class="mp-button mp-button-outline ml-auto"
          :disabled="saving"
          @click="emit('close')"
        >
          {{ $t('common.action.cancel') }}
        </button>
        <button
          type="button"
          class="mp-button mp-button-primary"
          :disabled="saving"
          @click="submit"
        >
          {{ saving ? $t('cutting.own.title') : $t('common.action.save') }}
        </button>
      </div>
    </div>
  </AppModal>
</template>
