<script setup lang="ts">
import { computed } from 'vue'

import { edgeFields } from '@/shared/app/cuttingDisplay'
import { partDisplayName } from '@/shared/app/cuttingEditorDerived'
import type { CuttingPart } from '@/shared/stores/cutting'

/**
 * One part, as the phone editor draws it (§7.0): a **read-only card** — number,
 * name, size, count and the sides glyph — that opens the «Detal» sheet.
 *
 * The desktop table stays the table (`CuttingPartRow`): eight columns of live
 * inputs is the right shape for a mouse and a keyboard, and the wrong one for a
 * thumb. Typing four numbers into 44px-wide cells with the keyboard covering
 * half the screen is what the sheet exists to replace, and a card that is not
 * itself editable is what lets the sheet own the whole job.
 *
 * The glyph says **which sides are banded and nothing else** — no tape colour,
 * no registry fill. On the client there is one tape per material group, so a
 * colour here would be the same colour on every row of the group: ink is the
 * honest mark (and it matches the canvas, which draws the client row bare).
 */
const props = defineProps<{
  part: CuttingPart
  index: number
  displayIndex?: number
  hasError: boolean
}>()

const emit = defineEmits<{ open: [] }>()

const name = computed(() => partDisplayName(props.part, props.index))
const number = computed(() => (props.displayIndex ?? props.index) + 1)

const glyphStyle = computed(() => {
  const sideBorders = {
    edge_top: 'borderTop',
    edge_bottom: 'borderBottom',
    edge_left: 'borderLeft',
    edge_right: 'borderRight',
  } as const
  return Object.fromEntries(
    edgeFields.map((side) => [
      sideBorders[side],
      props.part[side]?.material_id
        ? '2.5px solid var(--color-ink)'
        : '1.5px solid var(--color-hairline)',
    ]),
  )
})

const bandedCount = computed(
  () => edgeFields.filter((side) => props.part[side]?.material_id).length,
)
</script>

<template>
  <button
    :id="`part-row-${part.part_ref}`"
    type="button"
    class="grid min-h-14 grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2.5 rounded-[10px] border px-3 py-2 text-left transition"
    :class="
      hasError
        ? 'border-danger bg-danger-soft/60'
        : 'border-hairline bg-elevated hover:border-accent-tint'
    "
    @click="emit('open')"
  >
    <span class="min-w-0 truncate">
      <span class="text-[12.5px] font-bold text-ink-muted">#{{ number }} · </span>
      <span class="text-[15px] font-semibold text-ink">{{ name }}</span>
    </span>
    <span class="whitespace-nowrap text-sm text-ink-soft">
      {{ part.length_mm || '—' }} × {{ part.width_mm || '—' }}
    </span>
    <span class="inline-flex items-center gap-2">
      <span class="text-[12.5px] font-bold text-ink-muted">×{{ part.quantity || 0 }}</span>
      <span
        class="block h-[15px] w-5 rounded-[3px] bg-elevated"
        :style="glyphStyle"
        :aria-label="
          bandedCount > 0
            ? $t('cutting.parts.edgeSideCount', { n: bandedCount })
            : $t('cutting.parts.noEdge')
        "
        role="img"
      ></span>
    </span>
  </button>
</template>
