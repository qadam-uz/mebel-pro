<script setup lang="ts">
import { computed } from 'vue'

import { edgeFields, sideLabels, type EdgeField } from '@/shared/app/cuttingDisplay'
import { thicknessColorVar, type TapeDecor } from '@/shared/app/cuttingGroupTape'
import { formatMm } from '@/shared/app/materialLabel'
import type { CuttingPart } from '@/shared/stores/cutting'

/**
 * The client's whole per-part kromka control (§7.1): the four-side diagram and
 * the **Qalinlik** chips, and nothing else.
 *
 * What is deliberately absent, and why:
 *
 * - **No decor list.** The tape decor belongs to the material group; this block
 *   only names it and points at the group line that changes it.
 * - **No «4 tomon» / «Kromsiz» patterns** (owner, 2026-09-04): four taps on the
 *   diagram, or none, say the same thing, and two extra controls beside a
 *   diagram that already reads as the answer cost more than they save.
 * - **No registry numbers.** One material, one tape — there is no numbering
 *   left to show.
 *
 * The chips are exactly the thicknesses the group's decor is stocked in at this
 * branch, so a decor carried only in 0.4 and 2 mm simply has no 1 mm chip —
 * that absence is the message, which is why the group tape is named above it.
 *
 * Colour only appears when the part actually mixes thicknesses. With one
 * thickness everything stays ink: a colour that is always on carries no
 * information, and the `tur-*` ramp is worth spending only on the case it
 * answers ("which of these two is the thick one").
 */
const props = defineProps<{
  part: CuttingPart
  /** `D2` and `700 × 396` — the diagram's centre tile. */
  partLabel: string
  decor: TapeDecor | null
  /** The armed thickness; a side takes this one when it is tapped on. */
  selectedThicknessMm: number | null
  /** Names a tape that is not in the group's decor (legacy bands, §7.1). */
  foreignTapeLabel: (materialId: string) => string
  /** Compact geometry for the 340px docked desktop card. */
  dense?: boolean
}>()

const emit = defineEmits<{
  'update:selectedThicknessMm': [number]
  /** Band this side with `materialId`, or clear it with null. */
  'set-side': [side: EdgeField, materialId: string | null]
  /** A side was tapped while the group has no tape decor — open the picker. */
  'need-tape': []
}>()

function bandThickness(side: EdgeField): number | null {
  const materialId = props.part[side]?.material_id
  if (!materialId) return null
  const variant = props.decor?.variants.find((item) => item.material.id === materialId)
  return variant ? variant.thicknessMm : null
}

/** Sides carrying a tape outside the group decor — kept, shown, not editable. */
const foreignSides = computed(() =>
  edgeFields.filter((side) => {
    const materialId = props.part[side]?.material_id
    if (!materialId) return false
    return !props.decor?.variants.some((variant) => variant.material.id === materialId)
  }),
)

const foreignLabels = computed(() => [
  ...new Set(
    foreignSides.value.map((side) => props.foreignTapeLabel(props.part[side]!.material_id)),
  ),
])

/** More than one thickness on this part is what earns the colour. */
const mixedThickness = computed(
  () => new Set(edgeFields.map(bandThickness).filter((value) => value !== null)).size > 1,
)

const sides = computed(() =>
  edgeFields.map((field) => {
    const thicknessMm = bandThickness(field)
    const on = Boolean(props.part[field]?.material_id)
    const color =
      mixedThickness.value && thicknessMm != null ? thicknessColorVar(thicknessMm) : null
    return {
      field,
      label: sideLabels[field],
      on,
      thicknessMm,
      color,
      foreign: foreignSides.value.includes(field),
    }
  }),
)

const chips = computed(() =>
  (props.decor?.variants ?? []).map((variant) => ({
    thicknessMm: variant.thicknessMm,
    label: `${formatMm(variant.material.thickness_mm)} mm`,
    on: variant.thicknessMm === props.selectedThicknessMm,
    color: mixedThickness.value ? thicknessColorVar(variant.thicknessMm) : null,
  })),
)

function armedMaterialId(): string | null {
  const variants = props.decor?.variants ?? []
  if (variants.length === 0) return null
  const armed = variants.find((variant) => variant.thicknessMm === props.selectedThicknessMm)
  return (armed ?? variants[variants.length - 1]).material.id
}

/**
 * One tap does the obvious thing: a bare side takes the armed thickness, a side
 * already carrying it comes off, and a side carrying a *different* thickness is
 * re-banded to the armed one — which is what «Qalinlikni tanlab, tomonga
 * bosing» promises. Without that last case, changing 0.4 → 2 mm on one side
 * would be two taps that both look like mistakes.
 */
function onSide(side: EdgeField) {
  if (!props.decor) {
    emit('need-tape')
    return
  }
  const materialId = armedMaterialId()
  if (!materialId) {
    emit('need-tape')
    return
  }
  const current = props.part[side]?.material_id ?? null
  emit('set-side', side, current === materialId ? null : materialId)
}

function sideStyle(side: { on: boolean; color: string | null }) {
  if (!side.on) return undefined
  if (!side.color) return { borderColor: 'var(--color-ink)', borderWidth: '2px' }
  return {
    borderColor: side.color,
    borderWidth: '2px',
    color: side.color,
    background: `color-mix(in srgb, ${side.color} 12%, var(--color-elevated))`,
  }
}

function chipStyle(chip: { on: boolean; color: string | null }) {
  if (!chip.on) return chip.color ? { borderColor: chip.color, color: chip.color } : undefined
  if (!chip.color) return undefined
  return { borderColor: chip.color, background: chip.color, color: 'var(--color-on-accent)' }
}
</script>

<template>
  <div>
    <!-- The diagram: 62 / 1fr / 62 columns over 44 / 92 / 44 rows, tightened on
         the docked card where the column is 340px wide. -->
    <div
      class="mx-auto grid gap-1.5"
      :class="
        dense
          ? 'grid-cols-[56px_minmax(0,1fr)_56px] grid-rows-[38px_82px_38px]'
          : 'max-w-[314px] grid-cols-[62px_minmax(0,1fr)_62px] grid-rows-[44px_92px_44px]'
      "
    >
      <span></span>
      <button
        type="button"
        class="mp-edge-side"
        :aria-pressed="sides[0].on"
        :style="sideStyle(sides[0])"
        @click="onSide(sides[0].field)"
      >
        {{ sides[0].label
        }}<template v-if="sides[0].on && sides[0].thicknessMm != null">
          · {{ formatMm(String(sides[0].thicknessMm)) }} mm</template
        >
      </button>
      <span></span>

      <button
        type="button"
        class="mp-edge-side"
        :aria-pressed="sides[2].on"
        :style="sideStyle(sides[2])"
        @click="onSide(sides[2].field)"
      >
        {{ sides[2].label
        }}<template v-if="sides[2].on && sides[2].thicknessMm != null">
          · {{ formatMm(String(sides[2].thicknessMm)) }} mm</template
        >
      </button>
      <span
        class="mp-edge-face flex flex-col items-center justify-center gap-1 rounded-[10px] border border-hairline text-ink-muted"
      >
        <span class="text-[12.5px] font-bold text-ink">{{ partLabel }}</span>
        <span class="text-[12.5px] font-bold text-ink-soft"
          >{{ part.length_mm || '—' }} × {{ part.width_mm || '—' }}</span
        >
      </span>
      <button
        type="button"
        class="mp-edge-side"
        :aria-pressed="sides[3].on"
        :style="sideStyle(sides[3])"
        @click="onSide(sides[3].field)"
      >
        {{ sides[3].label
        }}<template v-if="sides[3].on && sides[3].thicknessMm != null">
          · {{ formatMm(String(sides[3].thicknessMm)) }} mm</template
        >
      </button>

      <span></span>
      <button
        type="button"
        class="mp-edge-side"
        :aria-pressed="sides[1].on"
        :style="sideStyle(sides[1])"
        @click="onSide(sides[1].field)"
      >
        {{ sides[1].label
        }}<template v-if="sides[1].on && sides[1].thicknessMm != null">
          · {{ formatMm(String(sides[1].thicknessMm)) }} mm</template
        >
      </button>
      <span></span>
    </div>

    <template v-if="chips.length > 0">
      <span class="mt-3.5 block text-[12.5px] font-semibold text-ink">
        {{ $t('cutting.edge.thickness') }}
      </span>
      <div class="mt-1.5 flex gap-2" role="radiogroup" :aria-label="$t('cutting.edge.thickness')">
        <button
          v-for="chip in chips"
          :key="chip.thicknessMm"
          type="button"
          role="radio"
          :aria-checked="chip.on"
          class="inline-flex min-h-10 flex-1 items-center justify-center rounded-full border px-3 text-[12.5px] font-bold transition"
          :class="
            chip.on
              ? 'border-accent bg-accent text-on-accent'
              : 'border-hairline-strong bg-elevated text-ink-soft hover:border-accent-tint'
          "
          :style="chipStyle(chip)"
          @click="emit('update:selectedThicknessMm', chip.thicknessMm)"
        >
          {{ chip.label }}
        </button>
      </div>
      <p class="mt-1.5 text-[12.5px] leading-[1.4] text-ink-soft">
        {{ $t('cutting.edge.thicknessHint') }}
      </p>
    </template>

    <!-- A band the group's decor does not contain: kept exactly as saved, named
         so the client knows why the chips do not describe it, and replaced only
         if they tap that side again. -->
    <p v-if="foreignLabels.length > 0" class="mt-2.5 text-[12.5px] font-semibold text-warning">
      {{ $t('cutting.edge.legacyTape', { name: foreignLabels.join(', ') }) }}
    </p>
  </div>
</template>

<style scoped>
.mp-edge-side {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: 10px;
  border: 1px solid var(--color-hairline);
  background: var(--color-elevated);
  padding: 0 4px;
  color: var(--color-ink-soft);
  font-size: 12.5px;
  font-weight: 700;
  line-height: 1.15;
  text-align: center;
  transition: border-color 150ms ease;
}
.mp-edge-side:hover {
  border-color: var(--color-hairline-strong);
}
/* The face is the part itself: a hatched tile, so the four buttons around it
   read as its edges rather than as a 2×2 group of unrelated toggles. */
.mp-edge-face {
  background: repeating-linear-gradient(
    45deg,
    var(--color-sunk),
    var(--color-sunk) 7px,
    var(--color-elevated) 7px,
    var(--color-elevated) 14px
  );
}
</style>
