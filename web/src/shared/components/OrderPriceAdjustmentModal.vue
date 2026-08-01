<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import {
  parseOrderAdjustmentDraft,
  type WorkshopAdjustmentKind,
} from '@/shared/app/workshopOrderDetail'
import AppModal from '@/shared/components/AppModal.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { formatTiyin } from '@/shared/formatters'

// The shared "apply a discount / surcharge" modal (orders.md → Pricing). One
// instance per adjustment; the parent wires @apply / @remove to the matching
// store action. The fixed sum is entered in so'm and emitted as tiyin.
const props = defineProps<{
  open: boolean
  title: string
  /** So'm-option hint, e.g. "aniq chegirma so'mda". */
  fixedHint: string
  currentTiyin: number
  currentReason: string | null
  applyLabel: string
  removeLabel: string
  busy: boolean
  pending: 'apply' | 'remove' | null
  /** A server-side apply/remove error, surfaced inside the modal (it would
   * otherwise hide behind the modal on the page-level banner). */
  submitError: string | null
}>()

const emit = defineEmits<{
  apply: [payload: { kind: WorkshopAdjustmentKind; value: number; reason: string }]
  remove: []
  close: []
}>()

const { t } = useI18n()

const kind = ref<WorkshopAdjustmentKind>('fixed')
const value = ref('')
const reason = ref('')
const error = ref<string | null>(null)
const valueInput = ref<HTMLInputElement | null>(null)

const options = computed<ChoiceOption[]>(() => [
  { value: 'fixed', label: t('orders.adjustment.som'), meta: props.fixedHint },
  {
    value: 'percent',
    label: t('orders.adjustment.percent'),
    meta: t('orders.adjustment.percentHint'),
  },
])
const valueErrorId = 'adjustment-value-error'

// Type-time sanitization (PhoneInput precedent) — the money charset covers both
// kinds (a percent is digits).
watch(value, (next) => {
  const clean = sanitizeMoneyInput(next)
  if (clean !== next) value.value = clean
})

// Reset to a blank fixed entry each time the modal opens, carrying only the
// existing reason forward so an update starts from what's on the order.
watch(
  () => props.open,
  (open) => {
    if (!open) return
    kind.value = 'fixed'
    value.value = ''
    reason.value = props.currentReason ?? ''
    error.value = null
  },
)

function submit() {
  error.value = null
  const parsed = parseOrderAdjustmentDraft(kind.value, value.value, reason.value)
  if (!parsed.ok) {
    error.value = parsed.message
    void nextTick(() => valueInput.value?.focus({ preventScroll: true }))
    return
  }
  emit('apply', parsed.payload)
}
</script>

<template>
  <AppModal :open="open" :title="title" @close="emit('close')">
    <div class="grid gap-3">
      <p v-if="currentTiyin > 0" class="rounded-md bg-sunk p-3 text-sm text-ink-soft">
        {{ $t('orders.adjustment.current', { amount: formatTiyin(currentTiyin) }) }}
      </p>
      <FormSelect v-model="kind" :label="$t('orders.adjustment.kind')" :options="options" />
      <div class="grid gap-1">
        <label class="field !mb-0"
          ><span>{{ $t('orders.adjustment.value') }}</span
          ><input
            ref="valueInput"
            v-model="value"
            class="mp-input"
            :class="error ? 'border-danger' : ''"
            inputmode="numeric"
            :aria-invalid="error ? 'true' : undefined"
            :aria-describedby="error ? valueErrorId : undefined"
        /></label>
        <p v-if="error" :id="valueErrorId" role="alert" class="text-sm font-bold text-danger">
          {{ error }}
        </p>
      </div>
      <label class="field !mb-0"
        ><span>{{ $t('orders.adjustment.reason') }}</span
        ><input v-model="reason" class="mp-input"
      /></label>
      <p
        v-if="submitError"
        role="alert"
        class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
      >
        {{ submitError }}
      </p>
      <div class="grid gap-2">
        <button
          type="button"
          class="mp-button mp-button-primary w-full whitespace-normal text-center leading-tight"
          :disabled="busy"
          @click="submit"
        >
          {{ pending === 'apply' ? $t('orders.busy.saving') : applyLabel }}
        </button>
        <button
          v-if="currentTiyin > 0"
          type="button"
          class="mp-button mp-button-outline w-full whitespace-normal text-center leading-tight text-danger"
          :disabled="busy"
          @click="emit('remove')"
        >
          {{ pending === 'remove' ? $t('orders.busy.saving') : removeLabel }}
        </button>
      </div>
    </div>
  </AppModal>
</template>
