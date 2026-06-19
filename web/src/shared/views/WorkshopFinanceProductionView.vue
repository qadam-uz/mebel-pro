<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDateInputValue, formatStockQuantity } from '@/shared/formatters'
import {
  useFinanceStore,
  type WorkerProductionEdgeLine,
  type WorkerProductionRow,
  type WorkerProductionThicknessLine,
} from '@/shared/stores/finance'
import { useWorkshopStore } from '@/shared/stores/workshop'

const finance = useFinanceStore()
const workshop = useWorkshopStore()
const permissions = useWorkshopPermissions()
const rolePath = useRolePath()
const today = new Date()
const dateFrom = ref(formatDateInputValue(new Date(today.getFullYear(), today.getMonth(), 1)))
const dateTo = ref(formatDateInputValue(today))
const branchId = ref('all')

const financePermissions = [p.manageFinance, p.viewFinanceReports]
const canViewFinance = computed(() => permissions.canAny(financePermissions))
const accessibleBranches = computed(() =>
  permissions.accessibleBranches(workshop.branches, financePermissions),
)

const branchOptions = computed<ChoiceOption[]>(() => [
  { value: 'all', label: 'Barcha filiallar', meta: 'ruxsatli ishlab chiqarish' },
  ...accessibleBranches.value.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.status === 'temporarily_closed' ? 'vaqtincha yopiq' : branch.address,
  })),
])

function applyContextBranch() {
  const contextBranchId = workshop.selectedBranchContext
  if (!contextBranchId) return
  if (!accessibleBranches.value.some((branch) => branch.id === contextBranchId)) return
  branchId.value = contextBranchId
}

function edgeLengths(row: WorkerProductionRow) {
  if (row.edge_lines.length > 0) {
    return row.edge_lines.map((line) => edgeLine(line)).join(' · ')
  }
  const entries = Object.entries(row.edge_length_by_material)
  if (entries.length === 0) return "Krom metri yo'q"
  return entries
    .map(([key, length]) => `Material ${key.slice(0, 8)}: ${formatStockQuantity(length, 'm')}`)
    .join(' · ')
}

function thicknessLengths(row: WorkerProductionRow) {
  if (row.edge_length_by_thickness.length === 0) return "Qalinlik bo'yicha jamlanma yo'q"
  return row.edge_length_by_thickness.map((line) => thicknessLine(line)).join(' · ')
}

function edgeLine(line: WorkerProductionEdgeLine) {
  return `${edgeLabel(line)}: ${formatStockQuantity(line.length_mm, 'm')}`
}

function edgeLabel(line: WorkerProductionEdgeLine) {
  return [line.material_label, line.thickness_mm ? `${line.thickness_mm} mm` : null, line.color]
    .filter(Boolean)
    .join(' · ')
}

function thicknessLine(line: WorkerProductionThicknessLine) {
  return `${line.thickness_mm ? `${line.thickness_mm} mm` : "Noma'lum"}: ${formatStockQuantity(
    line.length_mm,
    'm',
  )}`
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
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Maosh hisoblashda buxgalter ishlatadigan ishlab chiqarish sanog'i.
        </p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="refresh">Yangilash</button>
    </div>

    <section v-if="!canViewFinance" class="mp-surface p-5 text-sm font-bold text-warning">
      Ishlab chiqarish hisobotlariga ruxsatingiz yo'q.
    </section>

    <section v-else class="mp-surface p-4">
      <div class="grid gap-3 md:grid-cols-[220px_1fr_1fr_auto]">
        <FormSelect v-model="branchId" label="Filial" :options="branchOptions" />
        <label class="block text-sm font-bold text-ink" for="production-filter-from">
          Boshlanish
          <input id="production-filter-from" v-model="dateFrom" type="date" class="mp-input mt-1" />
        </label>
        <label class="block text-sm font-bold text-ink" for="production-filter-to">
          Tugash
          <input id="production-filter-to" v-model="dateTo" type="date" class="mp-input mt-1" />
        </label>
        <button type="button" class="mp-button mp-button-primary self-end" @click="refresh">
          Qo'llash
        </button>
      </div>
    </section>

    <section
      v-if="canViewFinance && finance.loading"
      class="mp-surface p-5 text-sm font-bold text-ink-soft"
    >
      Hisobot yuklanmoqda
    </section>
    <section v-else-if="finance.error" class="mp-surface p-5 text-sm font-bold text-danger">
      Hisobotni yuklab bo'lmadi.
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
              <th class="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-hairline">
            <tr v-for="row in finance.production.rows" :key="row.user_id">
              <td class="px-5 py-3 font-bold text-ink">{{ row.full_name }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.panels_cut }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.cut_count }}</td>
              <td class="px-5 py-3 font-mono text-xs">{{ row.orders_banded }}</td>
              <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                {{ edgeLengths(row) }}
              </td>
              <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                {{ thicknessLengths(row) }}
              </td>
              <td class="px-5 py-3 text-right">
                <RouterLink
                  :to="{
                    path: rolePath('/workshop/finance/expenses'),
                    query: { preset: 'salary', worker: row.full_name },
                  }"
                  class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                >
                  Maosh yozish
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
