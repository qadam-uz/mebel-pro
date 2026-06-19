<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { formatTodayHours } from '@/shared/app/clientUi'
import type { ClientBranchOption } from '@/shared/stores/cutting'

// Two-pane branch pre-filter (CB-51, cutting.md §"Branch pre-filter"): workshops on
// the left, the chosen workshop's branches on the right. `temporarily_closed`
// branches stay selectable (CB-77) — the preference is durable even while a branch
// is briefly closed; the row just flags why.
const props = defineProps<{
  options: ClientBranchOption[]
  modelValue: string | null
}>()
const emit = defineEmits<{ 'update:modelValue': [string | null] }>()

interface WorkshopGroup {
  id: string
  name: string
  count: number
}

const workshops = computed<WorkshopGroup[]>(() => {
  const grouped = new Map<string, WorkshopGroup>()
  for (const branch of props.options) {
    const existing = grouped.get(branch.workshop_id)
    if (existing) existing.count += 1
    else
      grouped.set(branch.workshop_id, {
        id: branch.workshop_id,
        name: branch.workshop_name,
        count: 1,
      })
  }
  return [...grouped.values()]
})

function workshopOfBranch(branchId: string | null): string | null {
  return props.options.find((branch) => branch.branch_id === branchId)?.workshop_id ?? null
}

const activeWorkshopId = ref<string | null>(
  workshopOfBranch(props.modelValue) ?? workshops.value[0]?.id ?? null,
)

// Keep the active workshop in step with the list/selection: follow the selected
// branch to its workshop, and fall back to a valid workshop when the current one
// disappears (options loaded late) or nothing is selected.
watch(
  () => [props.options, props.modelValue] as const,
  () => {
    const selectedWorkshop = workshopOfBranch(props.modelValue)
    if (selectedWorkshop) {
      activeWorkshopId.value = selectedWorkshop
      return
    }
    if (activeWorkshopId.value && workshops.value.some((w) => w.id === activeWorkshopId.value))
      return
    activeWorkshopId.value = workshops.value[0]?.id ?? null
  },
)

const branchesForActive = computed(() =>
  props.options.filter((branch) => branch.workshop_id === activeWorkshopId.value),
)
</script>

<template>
  <div
    v-if="workshops.length === 0"
    class="rounded-md border border-hairline bg-sunk p-4 text-sm text-ink-muted"
  >
    Hozircha tanlash uchun ustaxona yo'q.
  </div>
  <div
    v-else
    class="grid gap-3 md:grid-cols-[minmax(0,15rem)_1fr]"
    role="group"
    aria-label="Ustaxona va filial tanlash"
  >
    <ul class="m-0 grid max-h-72 list-none gap-1 overflow-auto p-0" aria-label="Ustaxonalar">
      <li v-for="workshop in workshops" :key="workshop.id">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition"
          :class="
            workshop.id === activeWorkshopId
              ? 'bg-accent-soft font-bold text-accent'
              : 'hover:bg-sunk text-ink'
          "
          :aria-pressed="workshop.id === activeWorkshopId"
          @click="activeWorkshopId = workshop.id"
        >
          <span class="truncate">{{ workshop.name }}</span>
          <span class="shrink-0 text-xs text-ink-muted">{{ workshop.count }}</span>
        </button>
      </li>
    </ul>

    <ul class="m-0 grid max-h-72 list-none gap-2 overflow-auto p-0" aria-label="Filiallar">
      <li v-for="branch in branchesForActive" :key="branch.branch_id">
        <button
          type="button"
          class="flex w-full flex-col gap-1 rounded-md border px-3 py-2 text-left transition"
          :class="
            branch.branch_id === modelValue
              ? 'border-accent bg-accent-soft'
              : 'border-hairline hover:bg-sunk'
          "
          :aria-pressed="branch.branch_id === modelValue"
          @click="emit('update:modelValue', branch.branch_id)"
        >
          <span class="flex items-center justify-between gap-2">
            <span class="truncate font-bold text-ink">{{ branch.branch_name }}</span>
            <span
              class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold"
              :class="
                branch.status === 'temporarily_closed'
                  ? 'bg-warning-soft text-warning'
                  : 'bg-success-soft text-success'
              "
            >
              {{ branch.status === 'temporarily_closed' ? 'vaqtincha yopiq' : 'faol' }}
            </span>
          </span>
          <span class="text-xs text-ink-muted">
            Bugun: {{ formatTodayHours(branch.today_hours) }}
            <template v-if="branch.status === 'temporarily_closed' && branch.closed_reason">
              · {{ branch.closed_reason }}
            </template>
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>
