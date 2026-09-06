<script setup lang="ts">
import { computed } from 'vue'

import Icon from '@/shared/components/AppIcon.vue'
import CuttingEdgeSides from '@/shared/components/CuttingEdgeSides.vue'
import CuttingGroupTapeLine from '@/shared/components/CuttingGroupTapeLine.vue'
import type { TapeDecor } from '@/shared/app/cuttingGroupTape'
import type { CuttingPart } from '@/shared/stores/cutting'
import type { EdgeField } from '@/shared/app/cuttingDisplay'

/**
 * The editor's kromka card, docked beside the parts board — **one card for both
 * editors** since SPEC_CLIENT_UX_MVP §13 W2 moved the workshop onto the client's
 * model: the tape *decor* belongs to the material group, the *thickness* to the
 * side.
 *
 * So the body is §7.1's block and nothing else — the group's tape line, the
 * four-side diagram and the «Qalinlik» chips. What used to live here for staff
 * (a per-part tape catalog, the registry colours, the «4 tomon» / «Kromsiz»
 * patterns) went with the registry itself: a material group carries exactly one
 * tape decor now, so there is no per-part list to rank and nothing left to
 * number.
 *
 * Deliberately NOT carried over from the modal it replaced: the backdrop, the
 * focus trap, the body scroll-lock, `role="dialog"`/`aria-modal`, and the
 * Escape→close document listener. Every one of them is wrong for a surface that
 * is simply part of the page — the scroll-lock in particular would freeze the
 * very board this panel sits beside (`body.modal-open` pins the workshop
 * frame's inner scroller, not just `body`).
 *
 * The panel appears only while a row is selected. It has no empty state and no
 * placeholder: with nothing selected there is nothing to say, and a 300px column
 * of explanatory text beside the board is width spent on a sentence the operator
 * reads once.
 */
const props = withDefaults(
  defineProps<{
    part: CuttingPart
    partNumber: number
    /** The material group's tape decor (null → the line asks for one). */
    groupTapeDecor: TapeDecor | null
    /** The armed thickness for the next banded side. */
    selectedThicknessMm: number | null
    /** Names a band outside the group decor (legacy drawings, §7.1). */
    foreignTapeLabel?: (materialId: string) => string
    /**
     * The order wizard docks the card in a measured `flex-wrap` row, so it needs
     * a knowable width; everywhere else it is a grid track and must not fight it.
     */
    fixedWidth?: boolean
    /**
     * «Uta (obmanka)» — the panel edge is doubled, so the tape has twice the
     * thickness to cover. A production instruction the client never gives, so
     * the toggle is workshop-only; it rides here because thickening is a
     * property of the detal's *edge*, and this card is where that is set.
     */
    showThickening?: boolean
  }>(),
  {
    foreignTapeLabel: () => '',
    fixedWidth: false,
    showThickening: false,
  },
)

const emit = defineEmits<{
  close: []
  'update:selectedThicknessMm': [number]
  'set-side': [side: EdgeField, materialId: string | null]
  'need-tape': []
  'open-group-tape': []
  'update:thickened': [boolean]
}>()

/** `D3 · Yon panel · 1800×450` — number, name, size. The size is here because
 *  the head has no diagram of its own: without it nothing on this surface says
 *  which detal's edges these are. */
const subline = computed(() => {
  const name = props.part.name?.trim()
  const size = `${props.part.length_mm || '—'}×${props.part.width_mm || '—'}`
  return [`D${props.partNumber}`, name, size].filter(Boolean).join(' · ')
})
</script>

<template>
  <aside
    role="region"
    :aria-label="$t('cutting.edge.panelTitle')"
    class="flex flex-col overflow-hidden rounded-2xl bg-elevated shadow-card"
    :class="fixedWidth ? 'w-[300px] flex-none' : 'min-w-0'"
  >
    <div class="flex items-start gap-2.5 border-b border-divider px-[15px] py-3.5">
      <div class="min-w-0 flex-1">
        <h3 class="font-display text-[17px] font-bold tracking-[-0.02em] text-ink">
          {{ $t('cutting.edge.panelTitle') }}
        </h3>
        <p class="num mt-0.5 text-[12.5px] text-ink-soft">{{ subline }}</p>
      </div>
      <button
        type="button"
        class="grid size-[30px] flex-none place-items-center rounded-[9px] text-ink-nav transition hover:bg-neutral-soft"
        :title="$t('cutting.edge.panelClearHint')"
        :aria-label="$t('cutting.edge.panelClear')"
        @click="emit('close')"
      >
        <Icon name="x" class="size-[15px]" />
      </button>
    </div>

    <!-- §7.1: the tape belongs to the material group, so the card opens by
         naming it and pointing at where it changes. -->
    <CuttingGroupTapeLine
      class="bg-sunk/50"
      dense
      :decor="groupTapeDecor"
      @open="emit('open-group-tape')"
    />

    <div class="p-[15px]">
      <CuttingEdgeSides
        dense
        :part="part"
        :part-label="`D${partNumber}`"
        :decor="groupTapeDecor"
        :selected-thickness-mm="selectedThicknessMm"
        :foreign-tape-label="foreignTapeLabel"
        @update:selected-thickness-mm="emit('update:selectedThicknessMm', $event)"
        @set-side="(side, materialId) => emit('set-side', side, materialId)"
        @need-tape="emit('need-tape')"
      />

      <!-- Workshop only. Below the sides, because it changes what the tape has
           to cover rather than which sides carry it. -->
      <button
        v-if="showThickening"
        type="button"
        role="switch"
        :aria-checked="part.thickened === true"
        class="mt-3.5 flex w-full items-start gap-2.5 rounded-[10px] border px-2.5 py-2 text-left transition"
        :class="
          part.thickened
            ? 'border-accent-tint bg-accent-soft'
            : 'border-hairline bg-elevated hover:border-hairline-strong'
        "
        @click="emit('update:thickened', part.thickened !== true)"
      >
        <span
          aria-hidden="true"
          class="grid size-[22px] flex-none place-items-center rounded-md text-[10px] font-black"
          :class="part.thickened ? 'bg-accent text-on-accent' : 'bg-sunk text-ink-muted'"
          >{{ $t('cutting.thickening.mark') }}</span
        >
        <span class="min-w-0 flex-1">
          <span class="block text-[12.5px] font-bold text-ink">{{
            $t('cutting.thickening.label')
          }}</span>
          <span class="mt-0.5 block text-[12px] leading-[1.35] text-ink-muted">{{
            $t('cutting.thickening.hint')
          }}</span>
        </span>
      </button>
    </div>
  </aside>
</template>
