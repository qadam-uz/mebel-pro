<script setup lang="ts">
/**
 * The line under a filter bar that proves the filter worked.
 *
 * Filters auto-apply, and auto-apply is invisible by itself: the list swaps and
 * nothing says why, which reads as "nothing happened" (DESIGN.md, UX bar).
 * `WorkshopOrdersView` had this and no other page did (QAD-182), so the block
 * lives here now and every `.mp-filters` bar can wear it.
 *
 * `total` is optional and only for money surfaces: on a ledger the count alone
 * answers the wrong question — an accountant filtering to one category wants
 * the sum of what they are looking at.
 */
withDefaults(
  defineProps<{
    /** Hidden entirely when no filter is active — an unfiltered list needs no receipt. */
    active: boolean
    loading?: boolean
    count: number
    /** `true` when the page holds only the first slice, so the count reads `12+`. */
    hasMore?: boolean
    /** Plural noun for what was counted: `buyurtma`, `xarajat`, `material`. */
    noun: string
    /** Pre-formatted money for the same rows, or null to leave it off. */
    total?: string | null
    /** Shown from the second active filter on — with one, it duplicates that filter's own clear. */
    onReset?: (() => void) | null
  }>(),
  {
    loading: false,
    hasMore: false,
    total: null,
    onReset: null,
  },
)
</script>

<template>
  <p
    v-if="active"
    class="mb-3 -mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs font-bold text-ink-soft"
    role="status"
    aria-live="polite"
  >
    <template v-if="loading">Yangilanmoqda…</template>
    <template v-else>
      <span>
        Filtr bo'yicha
        <b class="font-mono text-ink">{{ count }}{{ hasMore ? '+' : '' }}</b>
        ta {{ noun }} topildi
      </span>
      <span v-if="total" class="text-ink-muted">·</span>
      <span v-if="total">
        jami
        <b class="font-mono text-ink">{{ total }}</b>
      </span>
      <button
        v-if="onReset"
        type="button"
        class="text-accent underline underline-offset-2"
        @click="onReset()"
      >
        Hammasini tozalash
      </button>
    </template>
  </p>
</template>
