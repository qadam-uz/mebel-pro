<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { sanitizeSignedQuantityInput } from '@/shared/app/inputSanitizers'
import AppModal from '@/shared/components/AppModal.vue'
import SearchCombobox from '@/shared/components/SearchCombobox.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatStockUnit, parseDisplayQuantity } from '@/shared/formatters'
import { useWorkshopStore, type StockItem } from '@/shared/stores/workshop'

/**
 * A stock correction — the one tool for stock-takes and write-offs of every
 * kind — as a dialog both stock surfaces open.
 *
 * Two call sites (the material page, and the list while a material is picked)
 * with one set of rules: the sign is required, the reason is required, and the
 * material is settled before the quantity is typed. Duplicating that per screen
 * is how one of them ends up letting an unsigned quantity through.
 */
const props = defineProps<{
  open: boolean
  /** Materials the picker offers; empty when the caller settles the material. */
  options?: Array<{ value: string; label: string; meta?: string }>
  /** Opened from a row or a page: the material is already known. */
  material?: StockItem | null
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'saved'): void
}>()

const { t } = useI18n()
const workshop = useWorkshopStore()
const toast = useToast()

const form = reactive({
  materialId: null as string | null,
  // A signed quantity with a REQUIRED leading + or − ("-2" decreases, "+5"
  // increases) — the explicit prefix is the sign-safety mechanism.
  quantity: '',
  note: '',
})
const saving = ref(false)
const materialError = ref<string | null>(null)
const saveError = ref<string | null>(null)

const pickerOptions = computed(() => props.options ?? [])
const selected = computed<StockItem | null>(() => {
  if (props.material && props.material.branch_material_id === form.materialId) return props.material
  return workshop.stockPickerItems.find((row) => row.branch_material_id === form.materialId) ?? null
})
// The field is incomplete (not wrong) until the required prefix arrives —
// a muted nudge while typing; the danger copy is reserved for submit.
const needsSign = computed(() => form.quantity.length > 0 && !/^[+-]/.test(form.quantity))

// Type-time sanitization (PhoneInput precedent) — invalid characters never stick.
watch(
  () => form.quantity,
  (value) => {
    const clean = sanitizeSignedQuantityInput(value)
    if (clean !== value) form.quantity = clean
  },
)

watch(
  () => props.open,
  (open) => {
    if (!open) {
      reset()
      return
    }
    form.materialId = props.material?.branch_material_id ?? null
    // The material is settled, so the operator's next keystroke is the quantity.
    if (form.materialId) {
      void nextTick(() => document.querySelector<HTMLInputElement>('[data-adjust-qty]')?.focus())
    }
  },
  { immediate: true },
)

function reset() {
  form.materialId = null
  form.quantity = ''
  form.note = ''
  materialError.value = null
  saveError.value = null
}

/** Back to the picker — the invoice-line pattern, in the adjustment form. */
function clearMaterial() {
  form.materialId = null
  materialError.value = null
}

/**
 * Requires an explicit leading + or − and a positive magnitude; returns the
 * SIGNED quantity in the stock unit, or null when either is missing.
 */
function signedQuantity(item: StockItem | null) {
  const raw = form.quantity
  const sign = raw.startsWith('+') ? 1 : raw.startsWith('-') ? -1 : 0
  if (sign === 0) return null
  const magnitude = parseDisplayQuantity(raw.slice(1), item?.display_unit ?? 'piece')
  return Number.isFinite(magnitude) && magnitude > 0 ? sign * magnitude : null
}

async function save() {
  const item = selected.value
  const quantity = signedQuantity(item)
  saveError.value = null
  materialError.value = null
  if (!item || quantity === null) {
    materialError.value = t('inventory.adjustment.materialRequired')
    return
  }
  saving.value = true
  try {
    await workshop.recordAdjustment(item.branch_id, {
      branch_material_id: item.branch_material_id,
      quantity,
      note: form.note,
    })
    toast.success(t('inventory.adjustment.saved'))
    emit('saved')
    emit('close')
  } catch {
    saveError.value = 'adjustment_failed'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <AppModal :open="open" :title="$t('inventory.adjustment.title')" @close="emit('close')">
    <form class="grid gap-3" @submit.prevent="save">
      <!-- Opened from a row or a page, the material is already settled: it
           renders as its resolved label (clickable to re-pick when a picker was
           supplied, the invoice-line pattern) and focus lands on the quantity. -->
      <div v-if="selected" class="field !mb-0">
        <span>{{ $t('inventory.adjustment.material') }}</span>
        <button
          v-if="pickerOptions.length > 0"
          type="button"
          class="w-full text-left text-sm font-bold leading-snug text-ink hover:underline"
          :title="$t('inventory.invoice.changeMaterial')"
          @click="clearMaterial"
        >
          {{ selected.material.label }}
        </button>
        <p v-else class="text-sm font-bold leading-snug text-ink">
          {{ selected.material.label }}
        </p>
      </div>
      <SearchCombobox
        v-else
        v-model="form.materialId"
        :label="$t('inventory.adjustment.material')"
        :options="pickerOptions"
        :error="materialError"
      />
      <label class="field">
        <span>{{
          selected
            ? $t('inventory.adjustment.quantityWithUnit', {
                unit: formatStockUnit(selected.display_unit),
              })
            : $t('inventory.adjustment.quantity')
        }}</span>
        <!-- Signed quantity: "-2" decreases, "+5" increases — the prefix is
             required, so inputmode stays text (numeric keypads lack +/−). -->
        <input
          v-model="form.quantity"
          data-adjust-qty
          class="mp-input"
          :placeholder="$t('inventory.adjustment.quantityPlaceholder')"
          :aria-invalid="selected && materialError ? 'true' : undefined"
          aria-describedby="stock-adjust-error"
          required
        />
        <small v-if="needsSign" class="text-ink-muted">
          {{ $t('inventory.adjustment.signHint') }}
        </small>
        <small v-else-if="selected && materialError" id="stock-adjust-error" class="mp-field-error">
          {{ materialError }}
        </small>
      </label>
      <label class="field">
        <span>{{ $t('inventory.adjustment.noteLabel') }}</span>
        <input v-model="form.note" class="mp-input" required />
      </label>
      <p v-if="saveError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
        {{ $t('inventory.error.adjustment_failed') }}
      </p>
      <button type="submit" class="mp-button mp-button-primary" :disabled="saving">
        {{ saving ? $t('inventory.action.saving') : $t('inventory.action.save') }}
      </button>
    </form>
  </AppModal>
</template>
