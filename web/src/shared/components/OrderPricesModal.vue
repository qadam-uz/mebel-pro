<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import AppModal from '@/shared/components/AppModal.vue'
import { parseSomToTiyin } from '@/shared/formatters'
import type { OrderPriceLine } from '@/shared/stores/orders'

// Per-unit prices for one placed order (orders.md → Pricing). Every row edits a
// *rate* — per sheet, per metre — never a quantity: how many sheets the layout
// needs is the optimiser's answer, and retyping it here would put the bill and
// the cutting plan out of step. The quantity is shown beside each field so the
// operator can see the multiplication they are changing.
const props = defineProps<{
  open: boolean
  priceLines: OrderPriceLine[]
  cuttingRateTiyin: number
  edgeBandingRateTiyin: number
  panelsUsed: number
  bandedMm: number
  busy: boolean
  submitError: string | null
}>()

const emit = defineEmits<{
  save: [
    payload: {
      cutting_rate_tiyin: number | null
      edge_banding_rate_tiyin: number | null
      material_prices: Record<string, number>
    },
  ]
  close: []
}>()

/** Rates are entered in so'm and stored in tiyin, like every other money field. */
function toSom(tiyin: number) {
  return tiyin ? String(tiyin / 100) : ''
}

const materialSom = ref<Record<string, string>>({})
const cuttingSom = ref('')
const edgeSom = ref('')
const error = ref<string | null>(null)

watch(
  () => [props.open, props.priceLines] as const,
  ([open]) => {
    if (!open) return
    error.value = null
    materialSom.value = Object.fromEntries(
      props.priceLines.map((line) => [line.material_id, toSom(line.unit_price_tiyin)]),
    )
    cuttingSom.value = toSom(props.cuttingRateTiyin)
    edgeSom.value = toSom(props.edgeBandingRateTiyin)
  },
  { immediate: true, deep: true },
)

// Type-time sanitization, same as the branch rate fields — invalid characters
// never stick, so the strict parser below only ever sees a plausible figure.
watch(
  [materialSom, cuttingSom, edgeSom],
  () => {
    for (const [id, value] of Object.entries(materialSom.value)) {
      const clean = sanitizeMoneyInput(value)
      if (clean !== value) materialSom.value[id] = clean
    }
    const cleanCutting = sanitizeMoneyInput(cuttingSom.value)
    if (cleanCutting !== cuttingSom.value) cuttingSom.value = cleanCutting
    const cleanEdge = sanitizeMoneyInput(edgeSom.value)
    if (cleanEdge !== edgeSom.value) edgeSom.value = cleanEdge
  },
  { deep: true },
)

const rows = computed(() =>
  props.priceLines.map((line) => ({
    materialId: line.material_id,
    materialName: line.material_name,
    kind: line.kind,
    quantity: line.kind === 'panel' ? (line.panels_used ?? 0) : (line.consumed_mm ?? 0),
  })),
)
const hasBanding = computed(() => props.bandedMm > 0)

/** `''` means "no agreement here" → the branch's price. */
function parseOptional(value: string): number | null | 'invalid' {
  if (!value.trim()) return null
  const tiyin = parseSomToTiyin(value)
  return tiyin === null || tiyin < 0 ? 'invalid' : tiyin
}

function save() {
  error.value = null
  const materialPrices: Record<string, number> = {}
  for (const [id, value] of Object.entries(materialSom.value)) {
    const parsed = parseOptional(value)
    if (parsed === 'invalid') {
      error.value = 'invalid'
      return
    }
    if (parsed !== null) materialPrices[id] = parsed
  }
  const cutting = parseOptional(cuttingSom.value)
  const edge = parseOptional(edgeSom.value)
  if (cutting === 'invalid' || edge === 'invalid') {
    error.value = 'invalid'
    return
  }
  emit('save', {
    cutting_rate_tiyin: cutting,
    edge_banding_rate_tiyin: edge,
    material_prices: materialPrices,
  })
}
</script>

<template>
  <AppModal :open="open" :title="$t('orders.prices.title')" @close="emit('close')">
    <div class="grid gap-4">
      <p class="text-sm text-ink-muted">{{ $t('orders.prices.body') }}</p>

      <div v-for="row in rows" :key="row.materialId" class="grid gap-1">
        <label class="field" :for="`order-price-${row.materialId}`">
          <span>{{ row.materialName }}</span>
          <input
            :id="`order-price-${row.materialId}`"
            v-model="materialSom[row.materialId]"
            class="mp-input"
            inputmode="numeric"
            :disabled="busy"
          />
          <small class="text-ink-muted">
            {{
              row.kind === 'panel'
                ? $t('orders.prices.perSheet', { n: row.quantity })
                : $t('orders.prices.perMetre', { m: (row.quantity / 1000).toFixed(2) })
            }}
          </small>
        </label>
      </div>

      <label class="field" for="order-price-cutting">
        <span>{{ $t('orders.prices.cutting') }}</span>
        <input
          id="order-price-cutting"
          v-model="cuttingSom"
          class="mp-input"
          inputmode="numeric"
          :disabled="busy"
        />
        <small class="text-ink-muted">{{ $t('orders.prices.perSheet', { n: panelsUsed }) }}</small>
      </label>

      <label v-if="hasBanding" class="field" for="order-price-edge">
        <span>{{ $t('orders.prices.banding') }}</span>
        <input
          id="order-price-edge"
          v-model="edgeSom"
          class="mp-input"
          inputmode="numeric"
          :disabled="busy"
        />
        <small class="text-ink-muted">{{
          $t('orders.prices.perMetre', { m: (bandedMm / 1000).toFixed(2) })
        }}</small>
      </label>

      <p class="text-xs text-ink-muted">{{ $t('orders.prices.blankHint') }}</p>

      <p v-if="error" class="mp-field-error" role="alert">{{ $t('orders.prices.invalid') }}</p>
      <p
        v-else-if="submitError"
        role="alert"
        class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
      >
        {{ submitError }}
      </p>

      <div class="grid gap-2">
        <button
          type="button"
          class="mp-button mp-button-primary w-full"
          :disabled="busy"
          @click="save"
        >
          {{ busy ? $t('orders.busy.saving') : $t('workshopAdmin.action.save') }}
        </button>
        <button type="button" class="mp-button w-full" :disabled="busy" @click="emit('close')">
          {{ $t('workshopAdmin.action.cancel') }}
        </button>
      </div>
    </div>
  </AppModal>
</template>
