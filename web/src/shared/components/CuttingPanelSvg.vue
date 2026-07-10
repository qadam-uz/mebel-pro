<script setup lang="ts">
import { computed } from 'vue'

import { partDisplayName } from '@/shared/app/cuttingEditorDerived'
import type {
  CuttingOffcut,
  CuttingPanel,
  CuttingPart,
  CuttingPlacement,
  CuttingResult,
} from '@/shared/stores/cutting'

// The viewBox stays in raw panel mm, but a label only renders when its placement
// is large enough at a normalized 800-unit width: the font size and the
// visibility threshold are expressed against that scale so a 2800mm panel and a
// 900mm panel read the same on screen.
const NORM_WIDTH = 800
const LABEL_FONT = 11
const LABEL_MIN_W = 80
const LABEL_MIN_H = 30
// Edge-banding marks: a short, centred "tape" tick set just inside each banded
// side — not a full-length frame. Inset, length and thickness are on-screen
// constants (same normalization as labels), so a banded side reads the same on a
// 2800mm and a 900mm panel.
const BAND_STROKE = 3
const BAND_INSET = 3
const BAND_MARK = 30

const props = defineProps<{
  result: CuttingResult
  panel: CuttingPanel
  activePlacementId?: string | null
}>()

const emit = defineEmits<{
  'select-placement': [placement: CuttingPlacement]
}>()

const material = computed(() => props.result.material_snapshots[props.panel.material_id] ?? {})
const panelLength = computed(() => numberSnapshot(material.value.panel_length_mm, 1000))
const panelWidth = computed(() => numberSnapshot(material.value.panel_width_mm, 700))
const viewBox = computed(() => `0 0 ${panelLength.value} ${panelWidth.value}`)
const normScale = computed(() => NORM_WIDTH / panelLength.value)
const labelFontSize = computed(() => LABEL_FONT / normScale.value)
const bandStrokeWidth = computed(() => BAND_STROKE / normScale.value)

// A placement carries no edge data itself — its part (by part_ref) holds which
// sides are banded, so map them back here.
const partRowsByRef = computed(
  () =>
    new Map<string, { part: CuttingPart; index: number }>(
      (props.result.parts_snapshot ?? []).map((part, index) => [part.part_ref, { part, index }]),
    ),
)

type BandedSides = { top: boolean; bottom: boolean; left: boolean; right: boolean }

function numberSnapshot(value: unknown, fallback: number) {
  if (typeof value === 'number') return value
  if (typeof value === 'string' && value.trim()) return Number(value)
  return fallback
}

function svgY(placement: CuttingPlacement) {
  return panelWidth.value - placement.y_mm - placement.width_mm
}

function offcutY(offcut: CuttingOffcut) {
  return panelWidth.value - offcut.y_mm - offcut.width_mm
}

function labelFits(placement: CuttingPlacement) {
  return (
    placement.length_mm * normScale.value > LABEL_MIN_W &&
    placement.width_mm * normScale.value > LABEL_MIN_H
  )
}

function offcutLabelFits(offcut: CuttingOffcut) {
  return (
    offcut.length_mm * normScale.value > LABEL_MIN_W &&
    offcut.width_mm * normScale.value > LABEL_MIN_H
  )
}

function placementLabel(placement: CuttingPlacement) {
  const row = partRowsByRef.value.get(placement.part_ref)
  const name = row ? partDisplayName(row.part, row.index) : placement.part_ref
  return `${name} ${placement.length_mm}×${placement.width_mm}${placement.rotated ? ' ↻' : ''}`
}

function offcutLabel(offcut: CuttingOffcut) {
  if (!offcut.usable) return 'chiqit'
  return `Qoldiq ${offcut.length_mm}×${offcut.width_mm} — sizda qoladi`
}

// Which physical sides of the *placed* rectangle carry edge banding. Unrotated:
// top/bottom run along the length (horizontal), left/right along the width
// (vertical) — the optimizer's own convention (edge length = length for top/bottom,
// width for left/right). The only rotation the optimizer applies is 90°, swapping
// length↔width; it records no direction, so map clockwise (part top→right, …).
function bandedSides(placement: CuttingPlacement): BandedSides | null {
  const part = partRowsByRef.value.get(placement.part_ref)?.part
  if (!part) return null
  if (!placement.rotated) {
    return {
      top: Boolean(part.edge_top),
      bottom: Boolean(part.edge_bottom),
      left: Boolean(part.edge_left),
      right: Boolean(part.edge_right),
    }
  }
  return {
    top: Boolean(part.edge_left),
    right: Boolean(part.edge_top),
    bottom: Boolean(part.edge_right),
    left: Boolean(part.edge_bottom),
  }
}

// A short, centred "tape" tick just inside each banded side. The inset is capped
// at 30% of the shorter side so it never inverts on a thin sliver; each tick is
// capped at 60% of its side so it stays a mark, not a full edge.
function bandLines(placement: CuttingPlacement) {
  const sides = bandedSides(placement)
  if (!sides) return []
  const length = placement.length_mm
  const width = placement.width_mm
  const inset = Math.min(BAND_INSET / normScale.value, Math.min(length, width) * 0.3)
  const x0 = placement.x_mm
  const y0 = svgY(placement)
  const cx = x0 + length / 2
  const cy = y0 + width / 2
  const halfH = Math.min(BAND_MARK / normScale.value, length * 0.6) / 2
  const halfV = Math.min(BAND_MARK / normScale.value, width * 0.6) / 2
  const lines: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  if (sides.top) lines.push({ x1: cx - halfH, y1: y0 + inset, x2: cx + halfH, y2: y0 + inset })
  if (sides.bottom)
    lines.push({ x1: cx - halfH, y1: y0 + width - inset, x2: cx + halfH, y2: y0 + width - inset })
  if (sides.left) lines.push({ x1: x0 + inset, y1: cy - halfV, x2: x0 + inset, y2: cy + halfV })
  if (sides.right)
    lines.push({ x1: x0 + length - inset, y1: cy - halfV, x2: x0 + length - inset, y2: cy + halfV })
  return lines
}
</script>

<template>
  <svg
    class="block h-auto w-full rounded-md border border-hairline-strong bg-elevated"
    :viewBox="viewBox"
    style="touch-action: pinch-zoom"
    role="img"
    :aria-label="`Panel ${panel.panel_index} layout`"
  >
    <rect
      x="0"
      y="0"
      :width="panelLength"
      :height="panelWidth"
      fill="var(--color-elevated)"
      stroke="var(--color-accent)"
      stroke-width="2"
    />
    <g
      v-for="(offcut, index) in panel.offcuts"
      :key="`offcut-${index}`"
      class="offcut"
      aria-hidden="true"
    >
      <rect
        :x="offcut.x_mm"
        :y="offcutY(offcut)"
        :width="offcut.length_mm"
        :height="offcut.width_mm"
        fill="transparent"
        :stroke="offcut.usable ? 'var(--color-success)' : 'var(--color-danger)'"
        :stroke-width="1.5"
        stroke-dasharray="12 8"
      />
      <text
        v-if="offcutLabelFits(offcut)"
        :x="offcut.x_mm + offcut.length_mm / 2"
        :y="offcutY(offcut) + offcut.width_mm / 2"
        :fill="offcut.usable ? 'var(--color-success)' : 'var(--color-ink-muted)'"
        :font-size="labelFontSize"
        font-family="sans-serif"
        text-anchor="middle"
        dominant-baseline="middle"
        aria-hidden="true"
      >
        {{ offcutLabel(offcut) }}
      </text>
    </g>
    <g
      v-for="placement in panel.placements"
      :key="placement.id"
      class="placement"
      aria-hidden="true"
      @click="emit('select-placement', placement)"
    >
      <rect
        :x="placement.x_mm"
        :y="svgY(placement)"
        :width="placement.length_mm"
        :height="placement.width_mm"
        :fill="
          placement.id === activePlacementId
            ? 'var(--color-accent-tint)'
            : 'var(--color-accent-soft)'
        "
        stroke="var(--color-accent)"
        stroke-width="1.5"
      />
      <line
        v-for="(line, index) in bandLines(placement)"
        :key="`${placement.id}-band-${index}`"
        :x1="line.x1"
        :y1="line.y1"
        :x2="line.x2"
        :y2="line.y2"
        stroke="var(--color-accent)"
        :stroke-width="bandStrokeWidth"
        stroke-linecap="round"
        aria-hidden="true"
      />
      <template v-if="labelFits(placement)">
        <text
          :x="placement.x_mm + placement.length_mm / 2"
          :y="svgY(placement) + placement.width_mm / 2"
          fill="var(--color-ink-soft)"
          :font-size="labelFontSize"
          font-family="sans-serif"
          text-anchor="middle"
          dominant-baseline="middle"
          aria-hidden="true"
        >
          {{ placementLabel(placement) }}
        </text>
      </template>
    </g>
  </svg>
</template>

<style scoped>
.placement {
  cursor: pointer;
}
</style>
