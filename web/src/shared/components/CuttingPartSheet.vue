<script setup lang="ts">
import { computed } from 'vue'

import type { EdgeField } from '@/shared/app/cuttingDisplay'
import { partDisplayName } from '@/shared/app/cuttingEditorDerived'
import type { TapeDecor } from '@/shared/app/cuttingGroupTape'
import { sanitizeWholeNumberInput } from '@/shared/app/inputSanitizers'
import CuttingBottomSheet from '@/shared/components/CuttingBottomSheet.vue'
import CuttingEdgeSides from '@/shared/components/CuttingEdgeSides.vue'
import Icon from '@/shared/components/AppIcon.vue'
import type { CuttingPart } from '@/shared/stores/cutting'

/**
 * The phone editor's «Detal» sheet (§7.0) — where a part is actually entered.
 *
 * Three things it does that the desktop row cannot:
 *
 * - **Big numeric fields.** Uzunlik / Kenglik / Soni get a 48px row and 19px
 *   digits, because these three numbers are the whole job and they are typed
 *   with a thumb, against a numeric keypad.
 * - **A docked action row.** «Saqlash» / «Saqlash va yana» sit in the sheet's
 *   foot, which stays above the on-screen keyboard while a field is focused.
 *   In a plain scrolling dialog they end up under the keyboard exactly when
 *   they are needed, and «Saqlash va yana» — the whole point of rapid entry —
 *   becomes unreachable.
 * - **Delete out of the primaries.** «Detalni o'chirish» is the last thing in
 *   the form, a full scroll away from the foot's «Saqlash va yana» — not a ⋯
 *   menu in the head (decision 27c). The menu was the wrong control twice
 *   over: its teleported panel paints at z-60 under the sheet's own z-80
 *   layer, so on a phone the ⋯ opened onto nothing, and a one-item menu is a
 *   tap that only reveals another tap.
 *
 * The sheet edits the live part object (the editor owns `parts`, and autosave
 * is debounced anyway), so «Saqlash» closes rather than commits — there is no
 * second copy of the truth to reconcile.
 */
const props = defineProps<{
  open: boolean
  part: CuttingPart | null
  index: number
  displayIndex: number
  decor: TapeDecor | null
  selectedThicknessMm: number | null
  foreignTapeLabel: (materialId: string) => string
  /**
   * False for a part this sheet has just created («Saqlash va yana»): there is
   * nothing to delete yet, and closing the sheet discards it. An existing row —
   * one the list already shows — gets the button.
   */
  deletable: boolean
}>()

// Granular emits, never a write through `part`: this component renders the row
// and the editor stays the single owner of `parts` (the same contract
// CuttingPartRow keeps, and what `vue/no-mutating-props` enforces).
const emit = defineEmits<{
  close: []
  save: []
  'save-and-next': []
  delete: []
  'update:name': [string | null]
  'update:length': [number]
  'update:width': [number]
  'update:quantity': [number]
  'update:followGrain': [boolean]
  'update:selectedThicknessMm': [number]
  'set-side': [side: EdgeField, materialId: string | null]
  'need-tape': []
  'open-group-tape': []
}>()

const partLabel = computed(() => (props.part ? partDisplayName(props.part, props.index) : ''))

// A fresh part stores 0 for "not entered yet" — painting a literal 0 makes an
// untouched field look filled and forces the user to clear it before typing.
function numeric(value: number): number | string {
  return value > 0 ? value : ''
}

function toNumber(raw: string): number {
  const value = Number(raw)
  return Number.isFinite(value) ? value : 0
}

// The field is plain text (a numeric keypad without the spinner), so the
// alphabet is constrained at `beforeinput` — rewriting `value` afterwards would
// jump the caret to the end mid-word.
function onWholeNumberBeforeInput(event: Event) {
  const input = event as InputEvent
  if (typeof input.data !== 'string' || input.data === '') return
  if (sanitizeWholeNumberInput(input.data) !== input.data) event.preventDefault()
}

const rotationAllowed = computed(() => props.part?.follow_grain === false)
</script>

<template>
  <CuttingBottomSheet
    v-if="part"
    :open="open"
    :title="$t('cutting.part.sheetTitle', { n: displayIndex + 1 })"
    max-width="sm:max-w-[480px]"
    @close="emit('close')"
  >
    <div class="grid gap-3.5">
      <div class="grid grid-cols-3 gap-2">
        <label class="block min-w-0">
          <span class="mb-1.5 block text-[12.5px] font-semibold text-ink">
            {{ $t('cutting.column.length') }}
          </span>
          <input
            :value="numeric(part.length_mm)"
            type="text"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input min-h-12 justify-center text-center text-[19px] font-bold"
            :aria-label="$t('cutting.parts.lengthAria')"
            @beforeinput="onWholeNumberBeforeInput"
            @input="emit('update:length', toNumber(($event.target as HTMLInputElement).value))"
          />
          <span class="mt-1 block text-center text-[12.5px] text-ink-muted">
            {{ $t('cutting.unit.mm') }}
          </span>
        </label>
        <label class="block min-w-0">
          <span class="mb-1.5 block text-[12.5px] font-semibold text-ink">
            {{ $t('cutting.column.width') }}
          </span>
          <input
            :value="numeric(part.width_mm)"
            type="text"
            inputmode="numeric"
            enterkeyhint="next"
            class="mp-input min-h-12 justify-center text-center text-[19px] font-bold"
            :aria-label="$t('cutting.parts.widthAria')"
            @beforeinput="onWholeNumberBeforeInput"
            @input="emit('update:width', toNumber(($event.target as HTMLInputElement).value))"
          />
          <span class="mt-1 block text-center text-[12.5px] text-ink-muted">
            {{ $t('cutting.unit.mm') }}
          </span>
        </label>
        <label class="block min-w-0">
          <span class="mb-1.5 block text-[12.5px] font-semibold text-ink">
            {{ $t('cutting.column.quantity') }}
          </span>
          <input
            :value="numeric(part.quantity)"
            type="text"
            inputmode="numeric"
            enterkeyhint="done"
            class="mp-input min-h-12 justify-center text-center text-[19px] font-bold"
            :aria-label="$t('cutting.column.quantity')"
            @beforeinput="onWholeNumberBeforeInput"
            @input="emit('update:quantity', toNumber(($event.target as HTMLInputElement).value))"
          />
          <span class="mt-1 block text-center text-[12.5px] text-ink-muted">
            {{ $t('cutting.unit.piece', part.quantity) }}
          </span>
        </label>
      </div>

      <label class="block">
        <span class="mb-1.5 block text-[12.5px] font-semibold text-ink">
          {{ $t('cutting.column.name') }}
        </span>
        <input
          :value="part.name ?? ''"
          class="mp-input"
          maxlength="80"
          :placeholder="partLabel"
          :aria-label="$t('cutting.column.name')"
          @input="emit('update:name', ($event.target as HTMLInputElement).value.trim() || null)"
        />
      </label>

      <div>
        <span class="mb-1.5 block text-[12.5px] font-semibold text-ink">
          {{ $t('cutting.column.rotation') }}
        </span>
        <div class="flex items-center gap-2.5">
          <button
            type="button"
            role="switch"
            :aria-checked="rotationAllowed"
            class="grid size-11 shrink-0 place-items-center rounded-[10px] border border-hairline bg-elevated transition"
            :class="rotationAllowed ? 'text-ink-muted' : 'text-accent'"
            @click="emit('update:followGrain', rotationAllowed)"
          >
            <Icon :name="rotationAllowed ? 'rotate' : 'grain'" class="size-[18px]" />
          </button>
          <span class="min-w-0 text-[13px] leading-[1.4] text-ink-soft">
            {{
              rotationAllowed
                ? $t('cutting.parts.rotationAllowed')
                : $t('cutting.parts.rotationLocked')
            }}
          </span>
        </div>
      </div>

      <div>
        <span class="mb-1 block text-[12.5px] font-semibold text-ink">
          {{ $t('cutting.edge.label') }}
        </span>
        <!-- The tape is the group's, so this block only names it and says where
             it changes — the thickness below is the part's own choice. -->
        <p class="mb-2.5 text-[12.5px] leading-[1.35] text-ink-muted">
          <template v-if="decor">
            {{ $t('cutting.edge.groupLabel') }}
            <b class="font-bold text-ink">{{ decor.label }}</b> ·
          </template>
          <button
            type="button"
            class="font-semibold text-ink-soft underline underline-offset-2"
            @click="emit('open-group-tape')"
          >
            {{ decor ? $t('cutting.edge.changeForGroup') : $t('cutting.edge.groupPick') }}
          </button>
        </p>
        <CuttingEdgeSides
          :part="part"
          :part-label="partLabel"
          :decor="decor"
          :selected-thickness-mm="selectedThicknessMm"
          :foreign-tape-label="foreignTapeLabel"
          @update:selected-thickness-mm="emit('update:selectedThicknessMm', $event)"
          @set-side="(side, materialId) => emit('set-side', side, materialId)"
          @need-tape="emit('need-tape')"
        />
      </div>

      <!-- Last in the form, ghost-danger: the destructive action is reachable
           without hunting for a menu, and still sits a whole scroll away from
           the foot's two primaries. Undo is the safety net (the editor raises
           the toast), so there is no confirmation nag. -->
      <button
        v-if="deletable"
        type="button"
        class="mp-button w-full gap-2 border-transparent bg-transparent text-danger hover:bg-danger-soft max-md:text-[13.5px]"
        @click="emit('delete')"
      >
        <Icon name="trash" class="size-4" />
        {{ $t('cutting.part.delete') }}
      </button>
    </div>

    <template #foot>
      <div class="grid grid-cols-2 gap-2.5">
        <button
          type="button"
          class="mp-button mp-button-outline max-md:text-[13.5px]"
          @click="emit('save')"
        >
          {{ $t('cutting.part.save') }}
        </button>
        <button
          type="button"
          class="mp-button mp-button-primary max-md:text-[13.5px]"
          @click="emit('save-and-next')"
        >
          {{ $t('cutting.part.saveAndNext') }}
        </button>
      </div>
    </template>
  </CuttingBottomSheet>
</template>
