<script setup lang="ts">
import { computed } from 'vue'

import { tapeThicknessList, type TapeDecor } from '@/shared/app/cuttingGroupTape'
import Icon from '@/shared/components/AppIcon.vue'

/**
 * «Kromka: Egger H1145 · 0.4 / 2 mm» — the group's tape, in the slot the edge
 * registry used to occupy (§7.1).
 *
 * **The line itself is the control**, with no «O'zgartirish» button beside it:
 * the material name one row up is already a dashed link, so kromka behaving the
 * same way is the rule the head sets rather than a new one (owner, 2026-09-04).
 * It replaces the registry line, and it says something different — one tape, not
 * a numbering.
 *
 * With no tape it turns into the request («rangi mos lentani tanlang») in the
 * warning colour, and `armed` raises that to a full warning tile — which is what
 * «Hisoblash» scrolls to when a group bands a side it has no tape for.
 */
const props = withDefaults(
  defineProps<{
    decor: TapeDecor | null
    /** The gate fired on this group: the missing-tape state gets a tile. */
    armed?: boolean
    /** Desktop table / docked card sizing. */
    dense?: boolean
  }>(),
  { armed: false, dense: false },
)

const emit = defineEmits<{ open: [] }>()

const thicknesses = computed(() => (props.decor ? tapeThicknessList(props.decor) : ''))
</script>

<template>
  <button
    type="button"
    class="flex w-full items-center gap-2 border-b border-hairline px-3 pb-2 pt-1.5 text-left transition"
    :class="[
      dense ? 'text-[13px]' : 'text-[12.5px]',
      decor ? 'hover:bg-sunk/60' : 'font-bold text-warning hover:bg-warning-soft',
      armed && !decor
        ? 'mx-2 mb-1 rounded-lg border border-warning-border bg-warning-soft px-3'
        : '',
    ]"
    @click.stop="emit('open')"
  >
    <span v-if="decor" class="min-w-0 flex-1 truncate font-semibold text-ink-muted">
      {{ $t('cutting.edge.groupLabel') }}
      <b class="border-b border-dashed border-hairline-strong font-bold text-ink">{{
        decor.label
      }}</b>
      · {{ thicknesses }} mm
    </span>
    <span v-else class="min-w-0 flex-1 truncate">{{ $t('cutting.edge.groupPick') }}</span>
    <Icon
      name="chevron-right"
      class="size-[15px] shrink-0"
      :class="decor ? 'text-ink-muted' : 'text-warning'"
    />
  </button>
</template>
