<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { presetRange, type DateRangePreset } from '@/shared/app/dateRange'
import type { DropdownOption } from '@/shared/app/roleConfig'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import DateRangePicker from '@/shared/components/DateRangePicker.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatStockQuantity } from '@/shared/formatters'
import {
  useFinanceStore,
  type WorkerProductionEdgeLine,
  type WorkerProductionRow,
} from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const finance = useFinanceStore()
const workshop = useWorkshopStore()
const permissions = useWorkshopPermissions()
const today = new Date()
const initialRange = presetRange('month', today)
const datePreset = ref<DateRangePreset>('month')
const dateFrom = ref(initialRange.from ?? '')
const dateTo = ref(initialRange.to ?? '')
const branchId = ref('all')

const financePermissions = [p.manageFinance, p.viewFinanceReports]
const canViewFinance = computed(() => permissions.canAny(financePermissions))
const accessibleBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, financePermissions),
)

const branchOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: 'Barcha filiallar' },
  ...accessibleBranches.value.map((branch) => ({ value: branch.id, label: branch.name })),
])

function applyContextBranch() {
  const contextBranchId = workshop.selectedBranchContext
  if (!contextBranchId) return
  if (!accessibleBranches.value.some((branch) => branch.id === contextBranchId)) return
  branchId.value = contextBranchId
}

// One entry per edge material / thickness so the cell can stack them as lines
// (label left, metres right) instead of one unreadable `·`-joined string.
interface EdgeCellLine {
  label: string
  length: string
}

function edgeLengthLines(row: WorkerProductionRow): EdgeCellLine[] {
  if (row.edge_lines.length > 0) {
    return row.edge_lines.map((line) => ({
      label: edgeLabel(line),
      length: formatStockQuantity(line.length_mm, 'm'),
    }))
  }
  return Object.entries(row.edge_length_by_material).map(([key, length]) => ({
    label: `Material ${key.slice(0, 8)}`,
    length: formatStockQuantity(length, 'm'),
  }))
}

function thicknessLines(row: WorkerProductionRow): EdgeCellLine[] {
  return row.edge_length_by_thickness.map((line) => ({
    label: line.thickness_mm ? `${line.thickness_mm} mm` : "Noma'lum",
    length: formatStockQuantity(line.length_mm, 'm'),
  }))
}

function edgeLabel(line: WorkerProductionEdgeLine) {
  return [line.material_label, line.thickness_mm ? `${line.thickness_mm} mm` : null, line.color]
    .filter(Boolean)
    .join(' · ')
}

async function refresh() {
  if (!canViewFinance.value) return
  await finance.loadProduction({
    date_from: dateFrom.value,
    date_to: dateTo.value,
    branch_id: branchId.value === 'all' ? null : branchId.value,
  })
}

onMounted(async () => {
  await workshop.loadBranchContext().catch(() => undefined)
  applyContextBranch()
  if (canViewFinance.value) await refresh()
})

watch(branchId, (value) => {
  if (value !== 'all') workshop.setSelectedBranchContext(value)
  void refresh()
})

// Date range auto-applies now that the explicit "Qo'llash" button is gone.
let dateTimer: number | undefined
watch([dateFrom, dateTo], () => {
  window.clearTimeout(dateTimer)
  dateTimer = window.setTimeout(() => void refresh(), 250)
})

watch(
  () => workshop.selectedBranchContext,
  () => {
    applyContextBranch()
  },
)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Xodimlar mehnati</h1>
      </div>
    </div>

    <section v-if="!canViewFinance" class="mp-surface p-5 text-sm font-bold text-warning">
      Ishlab chiqarish hisobotlariga ruxsatingiz yo'q.
    </section>

    <section v-else class="mp-surface p-4">
      <div class="mp-filters !mb-0">
        <ProjectDropdown v-model="branchId" label="Filial" :options="branchOptions" top-label />
        <DateRangePicker
          v-model:preset="datePreset"
          v-model:date-from="dateFrom"
          v-model:date-to="dateTo"
        />
      </div>
    </section>

    <section
      v-if="canViewFinance && finance.loading"
      class="mp-surface p-5 text-sm font-bold text-ink-soft"
    >
      Hisobot yuklanmoqda
    </section>
    <section v-else-if="finance.error" class="mp-surface p-5" role="alert">
      <p class="text-sm font-bold text-danger">Hisobotni yuklab bo'lmadi.</p>
      <p class="mt-1 text-sm text-ink-soft">Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="finance.loading"
        @click="refresh"
      >
        Qayta urinish
      </button>
      <p v-if="finance.traceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ finance.traceId }}
      </p>
    </section>
    <section
      v-else-if="!finance.production || finance.production.rows.length === 0"
      class="mp-surface p-5 text-sm text-ink-soft"
    >
      Bu davrda ishlab chiqarish yo'q.
    </section>
    <section v-else class="mp-surface overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-left text-sm">
          <thead class="bg-sunk text-xs uppercase text-ink-muted">
            <tr>
              <th class="px-5 py-3">Xodim</th>
              <th class="px-5 py-3">Kesilgan panel</th>
              <th class="px-5 py-3">Kesimlar</th>
              <th class="px-5 py-3">Kromlangan buyurtma</th>
              <th class="px-5 py-3">Krom metri</th>
              <th class="px-5 py-3">Qalinlik jamlanmasi</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-hairline">
            <tr v-for="row in finance.production.rows" :key="row.user_id">
              <td class="px-5 py-3 font-bold text-ink">{{ row.full_name }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.panels_cut }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.cut_count }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.orders_banded }}</td>
              <td class="px-5 py-3 text-xs">
                <span v-if="edgeLengthLines(row).length === 0" class="text-ink-muted">
                  Krom metri yo'q
                </span>
                <ul v-else class="grid min-w-52 gap-1">
                  <li
                    v-for="(line, index) in edgeLengthLines(row)"
                    :key="index"
                    class="flex items-baseline justify-between gap-4"
                  >
                    <span class="text-ink-soft">{{ line.label }}</span>
                    <b class="whitespace-nowrap font-mono text-ink">{{ line.length }}</b>
                  </li>
                </ul>
              </td>
              <td class="px-5 py-3 text-xs">
                <span v-if="thicknessLines(row).length === 0" class="text-ink-muted">
                  Jamlanma yo'q
                </span>
                <ul v-else class="grid min-w-32 gap-1">
                  <li
                    v-for="(line, index) in thicknessLines(row)"
                    :key="index"
                    class="flex items-baseline justify-between gap-4"
                  >
                    <span class="text-ink-soft">{{ line.label }}</span>
                    <b class="whitespace-nowrap font-mono text-ink">{{ line.length }}</b>
                  </li>
                </ul>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
