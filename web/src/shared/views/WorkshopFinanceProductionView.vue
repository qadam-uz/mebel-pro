<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { formatDateInputValue, formatStockQuantity } from '@/shared/formatters'
import { useFinanceStore } from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const finance = useFinanceStore()
const workshop = useWorkshopStore()
const today = new Date()
const dateFrom = ref(formatDateInputValue(new Date(today.getFullYear(), today.getMonth(), 1)))
const dateTo = ref(formatDateInputValue(today))
const branchId = ref('all')

const branchOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: 'All branches', meta: 'accessible production' },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.status === 'temporarily_closed' ? 'temporarily closed' : branch.address,
  })),
])

function edgeLengths(value: Record<string, number>) {
  const entries = Object.entries(value)
  if (entries.length === 0) return 'No banding metres'
  return entries.map(([key, length]) => `${key}: ${formatStockQuantity(length, 'm')}`).join(' · ')
}

async function refresh() {
  await finance.loadProduction({
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: branchId.value === 'all' ? null : branchId.value,
  })
}

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  await refresh()
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Worker production</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Raw production counts used by the accountant for salary calculations.
        </p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="refresh">Refresh</button>
    </div>

    <section class="mp-surface p-4">
      <div class="grid gap-3 md:grid-cols-[220px_1fr_1fr_auto]">
        <FormSelect v-model="branchId" label="Branch" :options="branchOptions" />
        <label class="block text-sm font-bold text-ink" for="production-filter-from">
          Date from
          <input id="production-filter-from" v-model="dateFrom" type="date" class="mp-input mt-1" />
        </label>
        <label class="block text-sm font-bold text-ink" for="production-filter-to">
          Date to
          <input id="production-filter-to" v-model="dateTo" type="date" class="mp-input mt-1" />
        </label>
        <button type="button" class="mp-button mp-button-primary self-end" @click="refresh">
          Apply
        </button>
      </div>
    </section>

    <section v-if="finance.loading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
      Loading production report
    </section>
    <section v-else-if="finance.error" class="mp-surface p-5 text-sm font-bold text-danger">
      Production report could not be loaded.
    </section>
    <section
      v-else-if="!finance.production || finance.production.rows.length === 0"
      class="mp-surface p-5 text-sm text-ink-soft"
    >
      No production in this period.
    </section>
    <section v-else class="mp-surface overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-left text-sm">
          <thead class="bg-sunk text-xs uppercase text-ink-muted">
            <tr>
              <th class="px-5 py-3">Worker</th>
              <th class="px-5 py-3">Panels cut</th>
              <th class="px-5 py-3">Cuts</th>
              <th class="px-5 py-3">Orders banded</th>
              <th class="px-5 py-3">Banding metres</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-hairline">
            <tr v-for="row in finance.production.rows" :key="row.user_id">
              <td class="px-5 py-3 font-bold text-ink">{{ row.full_name }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.panels_cut }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.cut_count }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.orders_banded }}</td>
              <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                {{ edgeLengths(row.edge_length_by_material) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
