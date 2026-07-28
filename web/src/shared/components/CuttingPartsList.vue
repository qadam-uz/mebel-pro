<script setup lang="ts">
import { computed } from 'vue'

import { resultSheetPartGroups } from '@/shared/app/cuttingResultsDisplay'
import type { CuttingResult } from '@/shared/stores/cutting'

// QAD-177: the authoritative text reading of a cutting result, sheet by sheet.
// A 2800 mm sheet inside a 390 px viewport renders at ~7× reduction, where no
// label or dimension in the drawing survives — so on narrow screens the drawing
// stays a navigational overview and the numbers live here, as selectable text a
// screen reader reads in sheet order. Rendered by CuttingResultsSection below
// the `md` breakpoint only; the desktop layout keeps its per-sheet rail.
const props = defineProps<{
  result: CuttingResult
  activePanelId: string | null
  activePartRef: string | null
}>()

const emit = defineEmits<{
  select: [target: { panelId: string; partRef: string }]
}>()

// The material label repeats verbatim for every sheet cut from the same board,
// and at 390px it costs two lines each. Print it only when it changes, so the
// header stays a sheet number and the material reads as a run heading.
const sheets = computed(() => {
  let previousMaterial: string | null = null
  return resultSheetPartGroups(props.result)
    .filter((sheet) => sheet.groups.length > 0)
    .map((sheet) => {
      const repeatsMaterial = sheet.materialLabel === previousMaterial
      previousMaterial = sheet.materialLabel
      return { ...sheet, repeatsMaterial }
    })
})

function isSelected(panelId: string, partRef: string) {
  return panelId === props.activePanelId && partRef === props.activePartRef
}
</script>

<template>
  <section
    class="rounded-lg border border-hairline bg-elevated p-4"
    aria-labelledby="cutting-parts-list-heading"
  >
    <h3 id="cutting-parts-list-heading" class="text-sm font-extrabold text-ink">Detallar</h3>
    <p class="mt-1 text-xs text-ink-muted">Chizmada ko'rish uchun qatorni bosing.</p>

    <p v-if="!sheets.length" class="mt-3 text-sm text-ink-soft">
      Bu natijada joylashtirilgan detal yo'q.
    </p>

    <div v-else class="mt-3 grid gap-4">
      <section v-for="sheet in sheets" :key="sheet.panelId" class="grid gap-2">
        <h4 class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 leading-tight">
          <span class="text-sm font-extrabold text-ink">{{ sheet.sheetLabel }}</span>
          <span v-if="!sheet.repeatsMaterial" class="min-w-0 text-xs font-bold text-ink-muted">
            {{ sheet.materialLabel }}
          </span>
        </h4>
        <ul class="grid gap-1.5">
          <li v-for="group in sheet.groups" :key="`${sheet.panelId}-${group.partRef}`">
            <button
              type="button"
              :data-parts-row="`${sheet.panelId}:${group.partRef}`"
              class="grid w-full select-text grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border px-3 py-2.5 text-left transition"
              :class="
                isSelected(sheet.panelId, group.partRef)
                  ? 'border-accent bg-accent-soft'
                  : 'border-hairline bg-elevated hover:border-accent-tint'
              "
              :aria-pressed="isSelected(sheet.panelId, group.partRef)"
              @click="emit('select', { panelId: sheet.panelId, partRef: group.partRef })"
            >
              <span class="min-w-0">
                <span class="block break-words text-sm font-bold leading-snug text-ink">
                  {{ group.name }}
                </span>
                <span class="mt-0.5 block font-mono text-xs text-ink-soft">
                  {{ group.length_mm }} × {{ group.width_mm }} mm
                </span>
              </span>
              <span class="shrink-0 text-right">
                <span class="block font-mono text-sm font-bold text-ink">
                  {{ group.count }} dona
                </span>
                <span
                  v-if="group.rotatedCount > 0"
                  class="mt-0.5 block font-mono text-[11px] font-bold text-accent"
                >
                  <span aria-hidden="true">↻ {{ group.rotatedCount }}</span>
                  <span class="sr-only">{{ group.rotatedCount }} ta burilgan</span>
                </span>
              </span>
            </button>
          </li>
        </ul>
      </section>
    </div>
  </section>
</template>
