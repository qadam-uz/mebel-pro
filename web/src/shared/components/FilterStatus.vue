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
    /**
     * Whether the list is narrowed. Drives the `forms.filterStatus.found`
     * sentence. With no `total` and no active filter the line is hidden — an
     * unfiltered list needs no receipt.
     */
    active: boolean
    loading?: boolean
    count: number
    /** `true` when the page holds only the first slice, so the count reads `12+`. */
    hasMore?: boolean
    /**
     * Plural noun for what was counted, already in the active locale and in the
     * form the sentence needs: `buyurtma` / `заказов`. It is the page's word,
     * not this component's, so the page translates it.
     */
    noun: string
    /**
     * Pre-formatted money for the same rows, or null to leave it off. When set,
     * the line renders even at rest: on a ledger the total is a fact about the
     * period, not feedback about a filter, and finding 14 was that the finance
     * module never stated it at all.
     */
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
    v-if="active || total"
    class="mb-3 -mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs font-bold text-ink-soft"
    role="status"
    aria-live="polite"
  >
    <template v-if="loading">{{ $t('forms.filterStatus.refreshing') }}</template>
    <template v-else>
      <!-- `i18n-t` rather than `$t`: the figure is mono and bold *inside* the
           sentence, and Russian does not put it where Uzbek does — splitting the
           message around the <b> would make the word order untranslatable. -->
      <i18n-t v-if="active" keypath="forms.filterStatus.found" tag="span" scope="global">
        <template #count>
          <b class="text-ink">{{ count }}{{ hasMore ? '+' : '' }}</b>
        </template>
        <template #noun>{{ noun }}</template>
      </i18n-t>
      <i18n-t v-else-if="total" keypath="forms.filterStatus.count" tag="span" scope="global">
        <template #count>
          <b class="text-ink">{{ count }}</b>
        </template>
        <template #noun>{{ noun }}</template>
      </i18n-t>
      <span v-if="active && total" class="text-ink-muted">·</span>
      <i18n-t v-if="total" keypath="forms.filterStatus.total" tag="span" scope="global">
        <template #total>
          <b class="text-ink">{{ total }}</b>
        </template>
      </i18n-t>
      <button
        v-if="onReset"
        type="button"
        class="text-accent-deep underline underline-offset-2"
        @click="onReset()"
      >
        {{ $t('forms.filterStatus.resetAll') }}
      </button>
    </template>
  </p>
</template>
