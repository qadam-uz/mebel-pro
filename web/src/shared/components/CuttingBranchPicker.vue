<script setup lang="ts">
import { computed, ref } from 'vue'

import Icon from '@/shared/components/AppIcon.vue'
import BranchRow from '@/shared/components/BranchRow.vue'
import type { ClientBranchOption } from '@/shared/stores/cutting'

interface BranchQuote {
  total_tiyin: number
  panels_used: number
  subtotal_cutting_tiyin: number
  subtotal_materials_tiyin: number
  subtotal_edge_banding_tiyin: number
}

const props = defineProps<{
  options: ClientBranchOption[]
  modelValue: string | null
  recommendedBranchId?: string | null
  quotes?: Record<string, BranchQuote>
  quoteErrors?: Record<string, string>
  /**
   * The pinned workshop's name. Set → the picker is **scoped** (spec §4): one
   * workshop's branches under its own header, and no affordance that could reach
   * another workshop — no cross-workshop search, no grouping by workshop, no
   * "see more". Unset → the cross-workshop picker the organic, un-pinned client
   * still gets. Scoping the `options` themselves is the caller's job; this prop
   * is what removes the *controls* that only make sense across workshops.
   */
  pinnedWorkshopName?: string | null
}>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const query = ref('')
const scoped = computed(() => Boolean(props.pinnedWorkshopName))
const quoteMode = computed(() => props.quotes !== undefined)
const filtered = computed(() => {
  const value = query.value.trim().toLowerCase()
  return value
    ? props.options.filter((row) =>
        `${row.workshop_name} ${row.branch_name} ${row.address}`.toLowerCase().includes(value),
      )
    : props.options
})
const recommended = computed(
  () =>
    filtered.value.find(
      (row) =>
        row.branch_id === props.recommendedBranchId &&
        (!quoteMode.value || props.quotes?.[row.branch_id]),
    ) ?? null,
)
const groups = computed(() => {
  const grouped = new Map<string, ClientBranchOption[]>()
  for (const row of filtered.value) {
    if (row.branch_id === recommended.value?.branch_id) continue
    grouped.set(row.workshop_id, [...(grouped.get(row.workshop_id) ?? []), row])
  }
  const price = (row: ClientBranchOption) => props.quotes?.[row.branch_id]?.total_tiyin
  const sortRows = (rows: ClientBranchOption[]) =>
    [...rows].sort((a, b) => {
      const ap = price(a)
      const bp = price(b)
      if (quoteMode.value && Boolean(ap) !== Boolean(bp)) return ap == null ? 1 : -1
      return ap != null && bp != null ? ap - bp : a.branch_name.localeCompare(b.branch_name)
    })
  return [...grouped.values()].map(sortRows).sort((a, b) => {
    const ap = price(a[0])
    const bp = price(b[0])
    if (quoteMode.value && Boolean(ap) !== Boolean(bp)) return ap == null ? 1 : -1
    return ap != null && bp != null ? ap - bp : a[0].workshop_name.localeCompare(b[0].workshop_name)
  })
})
function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
}
function select(row: ClientBranchOption) {
  if (!quoteMode.value || props.quotes?.[row.branch_id]) emit('update:modelValue', row.branch_id)
}
</script>

<template>
  <div
    v-if="options.length === 0"
    class="rounded-lg border border-hairline bg-sunk p-4 text-sm text-ink-muted"
  >
    {{ $t('cutting.branch.emptyOptions') }}
  </div>
  <div v-else class="grid gap-3" role="group" :aria-label="$t('cutting.branch.pick')">
    <!-- Scoped: the workshop names itself once, and there is nothing to search
         across — picking among its counters is a pickup choice, not a
         comparison. The search field only exists in the cross-workshop form. -->
    <h3
      v-if="scoped"
      class="font-display text-base font-semibold text-ink"
      data-testid="branch-picker-scope"
    >
      {{ $t('cutting.branch.scopedHeader', { workshop: pinnedWorkshopName }) }}
    </h3>
    <div v-else class="relative">
      <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
        ><Icon name="search" class="size-[18px]" /></span
      ><input
        v-model="query"
        type="search"
        class="mp-input pl-10"
        :placeholder="$t('cutting.branch.searchPlaceholder')"
        :aria-label="$t('cutting.branch.searchAria')"
      />
    </div>
    <div v-if="recommended" class="rounded-lg border-2 border-accent-tint bg-accent-soft p-3">
      <span class="rounded-full bg-accent px-2 py-0.5 text-[11px] font-bold text-on-accent">{{
        $t('cutting.branch.recommended')
      }}</span
      ><BranchRow
        :branch="recommended"
        :selected="recommended.branch_id === modelValue"
        :quote="quotes?.[recommended.branch_id]"
        :error="quoteErrors?.[recommended.branch_id]"
        @select="select(recommended)"
      />
    </div>
    <div
      v-for="rows in groups"
      :key="rows[0].workshop_id"
      class="overflow-hidden rounded-lg border border-hairline bg-elevated"
    >
      <!-- The per-group workshop header is what makes the cross-workshop list
           readable; scoped, the heading above already named the one workshop and
           repeating it here would be a second label for the same thing. -->
      <div
        v-if="!scoped"
        class="flex items-center gap-2 border-b border-hairline bg-sunk px-3 py-2 text-sm font-bold text-ink"
      >
        <span
          class="grid size-7 place-items-center rounded-full bg-accent-soft text-[11px] text-accent-strong"
          >{{ initials(rows[0].workshop_name) }}</span
        >{{ rows[0].workshop_name }}
        <span class="text-ink-muted"
          >{{ rows.length }} {{ $t('cutting.unit.branch', rows.length) }}</span
        >
      </div>
      <BranchRow
        v-for="row in rows"
        :key="row.branch_id"
        :branch="row"
        :selected="row.branch_id === modelValue"
        :quote="quotes?.[row.branch_id]"
        :error="quoteErrors?.[row.branch_id]"
        @select="select(row)"
      />
    </div>
    <div
      v-if="filtered.length === 0"
      class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-4 text-center text-sm text-ink-muted"
    >
      {{ $t('cutting.branch.noMatches') }}
    </div>
  </div>
</template>
