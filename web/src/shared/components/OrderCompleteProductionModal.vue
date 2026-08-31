<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ProductionStockLine } from '@/shared/app/workshopOrderDetail'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'

// Simple mode's composite **Tayyor** (orders.md). Success-styled, not danger:
// it is the ordinary way an order finishes, and the destructive twin is Orqaga.
// The dialog names its effects before the button — the stock it will spend
// first, then the two OPTIONAL worker credits, because in simple mode a worker
// account is a reporting dimension and never a gate.
const props = defineProps<{
  open: boolean
  /** Panels and edge tape this action decrements — the money card's own figures. */
  stockLines: ProductionStockLine[]
  workerOptions: ChoiceOption[]
  /** Hidden on a full→simple leftover already past cutting: the cutter credit is
   *  written, and the backend refuses a second one (`cutting_already_started`). */
  showCutter: boolean
  /** Only when a side is actually banded — otherwise there is no edger to credit. */
  showEdger: boolean
  /** The branch's last pick, offered as a suggestion; always clearable. */
  defaultCutterId: string | null
  defaultEdgerId: string | null
  busy?: boolean
  submitError?: string | null
}>()

const emit = defineEmits<{
  confirm: [{ cutterUserId: string | null; edgerUserId: string | null }]
  cancel: []
}>()

const { t } = useI18n()

// '' is the explicit "nobody" choice, so the preselect can be cleared without
// reaching for a keyboard — `null` would only render the placeholder.
const NONE = ''
const cutterId = ref<string | null>(NONE)
const edgerId = ref<string | null>(NONE)

function optionExists(id: string | null) {
  return Boolean(id) && props.workerOptions.some((option) => option.value === id)
}

watch(
  () => props.open,
  (open) => {
    if (!open) return
    // A remembered pick is only a suggestion: it has to still be a worker this
    // branch offers, or the select would show a stale name it cannot resolve.
    cutterId.value = optionExists(props.defaultCutterId) ? props.defaultCutterId : NONE
    edgerId.value = optionExists(props.defaultEdgerId) ? props.defaultEdgerId : NONE
  },
  { immediate: true },
)

const selectOptions = computed<ChoiceOption[]>(() => [
  { value: NONE, label: t('orders.confirm.complete.noWorker') },
  ...props.workerOptions,
])
const showWorkerPicks = computed(
  () => props.workerOptions.length > 0 && (props.showCutter || props.showEdger),
)

function confirm() {
  emit('confirm', {
    cutterUserId: props.showCutter && cutterId.value ? cutterId.value : null,
    edgerUserId: props.showEdger && edgerId.value ? edgerId.value : null,
  })
}
</script>

<template>
  <ConfirmDialog
    :open="open"
    :title="$t('orders.confirm.complete.title')"
    :message="$t('orders.confirm.complete.message')"
    :confirm-label="$t('orders.confirm.complete.action')"
    :cancel-label="$t('orders.confirm.backLabel')"
    :busy-label="$t('orders.busy.completing')"
    :busy="busy ?? false"
    @cancel="emit('cancel')"
    @confirm="confirm"
  >
    <div class="grid gap-4">
      <div>
        <p class="text-sm font-bold text-ink">{{ $t('orders.confirm.complete.stockIntro') }}</p>
        <ul v-if="stockLines.length > 0" class="mt-2 grid gap-1.5" data-test="complete-stock-lines">
          <li
            v-for="line in stockLines"
            :key="`${line.kind}-${line.materialId}`"
            class="flex items-baseline justify-between gap-3 text-sm"
          >
            <span class="min-w-0 text-ink-soft">{{ line.name }}</span>
            <b class="shrink-0 whitespace-nowrap text-ink">{{ line.amount }}</b>
          </li>
        </ul>
        <!-- A fully client-supplied order spends nothing; say so rather than
             leaving an intro with no list under it. -->
        <p v-else class="mt-2 text-sm text-ink-muted">
          {{ $t('orders.confirm.complete.noStock') }}
        </p>
      </div>

      <div v-if="showWorkerPicks" class="grid gap-2 border-t border-hairline pt-4">
        <FormSelect
          v-if="showCutter"
          v-model="cutterId"
          :label="$t('orders.confirm.complete.cutter')"
          :options="selectOptions"
          :disabled="busy"
        />
        <FormSelect
          v-if="showEdger"
          v-model="edgerId"
          :label="$t('orders.confirm.complete.edger')"
          :options="selectOptions"
          :disabled="busy"
        />
        <p class="text-xs text-ink-muted">{{ $t('orders.confirm.complete.workersHint') }}</p>
      </div>

      <p
        v-if="submitError"
        class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
        role="alert"
      >
        {{ submitError }}
      </p>
    </div>
  </ConfirmDialog>
</template>
