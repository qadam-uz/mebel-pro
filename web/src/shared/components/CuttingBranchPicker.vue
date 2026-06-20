<script setup lang="ts">
import { computed, ref } from 'vue'

import { formatTodayHours } from '@/shared/app/clientUi'
import Icon from '@/shared/components/AppIcon.vue'
import type { ClientBranchOption } from '@/shared/stores/cutting'

// A single flat list of branches (CB-51, cutting.md §"Branch pre-filter"). Each
// row names the branch + its workshop + today's hours; one tap selects it.
// `temporarily_closed` branches stay selectable (CB-77) — the preference is
// durable even while a branch is briefly closed; the row just flags why.
const props = defineProps<{
  options: ClientBranchOption[]
  modelValue: string | null
}>()
const emit = defineEmits<{ 'update:modelValue': [string | null] }>()

const query = ref('')
const filtered = computed(() => {
  const value = query.value.trim().toLowerCase()
  if (!value) return props.options
  return props.options.filter((branch) =>
    `${branch.branch_name} ${branch.workshop_name}`.toLowerCase().includes(value),
  )
})
</script>

<template>
  <div
    v-if="options.length === 0"
    class="rounded-lg border border-hairline bg-sunk p-4 text-sm text-ink-muted"
  >
    Hozircha tanlash uchun filial yo'q.
  </div>
  <div v-else class="grid gap-3" role="group" aria-label="Filial tanlash">
    <div v-if="options.length > 6" class="relative">
      <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted">
        <Icon name="search" class="size-[18px]" />
      </span>
      <input
        v-model="query"
        type="search"
        class="mp-input pl-10"
        placeholder="Filial yoki ustaxona qidiring"
        aria-label="Filial qidirish"
      />
    </div>

    <ul class="m-0 grid max-h-80 list-none gap-2 overflow-auto p-0" aria-label="Filiallar">
      <li v-for="branch in filtered" :key="branch.branch_id">
        <button
          type="button"
          class="flex w-full items-center gap-3 rounded-xl border p-3 text-left transition"
          :class="
            branch.branch_id === modelValue
              ? 'border-accent bg-accent-soft'
              : 'border-hairline bg-elevated hover:border-hairline-strong'
          "
          :aria-pressed="branch.branch_id === modelValue"
          @click="emit('update:modelValue', branch.branch_id)"
        >
          <span
            class="grid size-10 shrink-0 place-items-center rounded-lg"
            :class="
              branch.branch_id === modelValue ? 'bg-accent text-white' : 'bg-sunk text-ink-soft'
            "
          >
            <Icon :name="branch.branch_id === modelValue ? 'check' : 'store'" class="size-5" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="flex items-center gap-2">
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
            <span class="mt-0.5 block truncate text-sm text-ink-muted">
              {{ branch.workshop_name }} · {{ formatTodayHours(branch.today_hours) }}
              <template v-if="branch.status === 'temporarily_closed' && branch.closed_reason">
                · {{ branch.closed_reason }}
              </template>
            </span>
          </span>
        </button>
      </li>
      <li
        v-if="filtered.length === 0"
        class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-4 text-center text-sm text-ink-muted"
      >
        Mos filial topilmadi.
      </li>
    </ul>
  </div>
</template>
