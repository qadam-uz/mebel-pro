<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppModal from '@/shared/components/AppModal.vue'
import type { OrderPriceLine } from '@/shared/stores/orders'

// "Client brings their own sheets", set at the counter on a placed order
// (orders.md → Pricing). Deliberately not the client's wizard dialog: that one
// is priced against a live quote and speaks to the client, while this one edits
// a frozen order and speaks to the operator. Panels only — a tape claim has no
// working path on the client side either.
const props = defineProps<{
  open: boolean
  panelLines: OrderPriceLine[]
  busy: boolean
  /** Server-side error, shown inside the modal rather than behind it. */
  submitError: string | null
}>()

const emit = defineEmits<{
  save: [ownPanelCounts: Record<string, number>]
  close: []
}>()

const counts = ref<Record<string, number>>({})

// The layout's own total per material: what the shop charges for plus what the
// client already brings. That sum is the ceiling — a claim beyond it buys
// nothing, and the server clamps it to exactly this anyway.
const rows = computed(() =>
  props.panelLines.map((line) => ({
    materialId: line.material_id,
    materialName: line.material_name,
    total: (line.panels_used ?? 0) + line.own_panels,
  })),
)

watch(
  () => [props.open, props.panelLines] as const,
  ([open]) => {
    if (!open) return
    counts.value = Object.fromEntries(
      props.panelLines.map((line) => [line.material_id, line.own_panels]),
    )
  },
  { immediate: true, deep: true },
)

function adjust(materialId: string, delta: number, total: number) {
  const next = (counts.value[materialId] ?? 0) + delta
  counts.value[materialId] = Math.min(total, Math.max(0, next))
}

function save() {
  // Zero entries are dropped rather than sent: the payload is the whole claim,
  // and "0 sheets of X" says the same thing as leaving X out.
  emit('save', Object.fromEntries(Object.entries(counts.value).filter(([, count]) => count > 0)))
}
</script>

<template>
  <AppModal :open="open" :title="$t('orders.own.editTitle')" @close="emit('close')">
    <div class="grid gap-3">
      <p class="text-sm text-ink-muted">{{ $t('orders.own.editBody') }}</p>

      <div v-for="row in rows" :key="row.materialId" class="grid gap-1">
        <span class="text-sm font-bold text-ink">{{ row.materialName }}</span>
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="mp-button min-h-11 min-w-11"
            :disabled="busy || (counts[row.materialId] ?? 0) <= 0"
            :aria-label="$t('orders.own.decrease')"
            @click="adjust(row.materialId, -1, row.total)"
          >
            −
          </button>
          <span class="font-mono text-lg font-extrabold text-ink">
            {{ counts[row.materialId] ?? 0 }}
          </span>
          <button
            type="button"
            class="mp-button min-h-11 min-w-11"
            :disabled="busy || (counts[row.materialId] ?? 0) >= row.total"
            :aria-label="$t('orders.own.increase')"
            @click="adjust(row.materialId, 1, row.total)"
          >
            +
          </button>
          <!-- Information, not a second control: it says how many the layout
               needs in total, so the operator can see what "all of it" is. -->
          <small class="text-ink-muted">
            {{ $t('orders.own.ofTotal', { total: row.total }) }}
          </small>
        </div>
      </div>

      <p v-if="rows.length === 0" class="text-sm text-ink-muted">
        {{ $t('orders.own.noPanels') }}
      </p>

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
          class="mp-button mp-button-primary w-full"
          :disabled="busy || rows.length === 0"
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
