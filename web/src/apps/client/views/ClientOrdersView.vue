<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { clientStatusLabel, clientStatusPillClass, workshopBranchName } from '@/shared/app/clientUi'
import { SEARCH_DEBOUNCE_MS } from '@/shared/app/constants'
import { useRolePath } from '@/shared/app/paths'
import ClientChipFilter from '@/shared/components/ClientChipFilter.vue'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import SegmentedControl from '@/shared/components/SegmentedControl.vue'
import { formatClientDateTime, formatOrderNumber, formatTiyin } from '@/shared/formatters'
import { useOrdersStore, type OrderSummary } from '@/shared/stores/orders'

/**
 * Mening buyurtmalarim (spec §4).
 *
 * Chip filters mirrored to `?status=`, a search that expands out of an
 * icon-button on phones, and a two-column card that is itself the link. No
 * per-card button of any kind: cancel lives on the detail page, which is the
 * only place the client cancels from.
 */
const { t } = useI18n()
const orders = useOrdersStore()
const rolePath = useRolePath()
const route = useRoute()
const router = useRouter()

/**
 * Chip order and default (decision 28). **Faol first and default**: the list a
 * client opens is the orders they are waiting on, not an archive that grows for
 * ever. «Hammasi» is last and explicit — it is the way back to history, never
 * the landing state. There is no «Bekor» chip: a cancelled order is read from
 * Hammasi, and a filter nobody arms is a chip stealing width from the four that
 * matter on a 375px row.
 */
const DEFAULT_STATUS = 'active'
const STATUSES = ['active', 'ready', 'completed', 'all'] as const
type StatusFilter = (typeof STATUSES)[number]

function readStatus(value: unknown): StatusFilter {
  const raw = String(value ?? DEFAULT_STATUS)
  return (STATUSES as readonly string[]).includes(raw) ? (raw as StatusFilter) : DEFAULT_STATUS
}

/**
 * The filter lives in the URL, not only in the component, so the browser's back
 * button lands on the filter the client left. Only a non-default chip is
 * written: no `?status` **is** Faol, which keeps home's «Barchasi →» a plain
 * `/c/orders` and the address bar clean on the view everybody opens.
 */
const status = computed({
  get: () => readStatus(route.query.status),
  set: (value: string) => {
    const query = { ...route.query }
    if (value === DEFAULT_STATUS) delete query.status
    else query.status = value
    void router.replace({ query })
  },
})

const search = ref('')
const searchOpen = ref(false)
const searchInput = ref<HTMLInputElement | null>(null)

// Computed, not a plain array: the labels are copy and must follow a language
// switch made while the page is open.
const statusOptions = computed(() =>
  STATUSES.map((value) => ({ value, label: t(`client.orders.filter.${value}`) })),
)

const visibleOrders = computed(() => orders.clientOrders)
/** Hammasi with no search: an empty list here means the client has no orders. */
const noFilter = computed(() => status.value === 'all' && !search.value)
/** The landing view — its empty state offers Hammasi rather than first-run copy. */
const isDefaultView = computed(() => status.value === DEFAULT_STATUS && !search.value)
const isTrueEmpty = computed(
  () => !orders.loading && !orders.error && visibleOrders.value.length === 0 && noFilter.value,
)
/** The skeleton is for a cold list only — a filter change dims the old rows. */
const showSkeleton = computed(() => orders.loading && visibleOrders.value.length === 0)

function clearFilters() {
  search.value = ''
  searchOpen.value = false
  status.value = 'all'
}

function reloadOrders() {
  void orders.loadClientOrders({ status: status.value, search: search.value })
}

function loadMoreOrders() {
  void orders.loadClientOrders({
    status: status.value,
    search: search.value,
    offset: orders.clientOrders.length,
  })
}

async function toggleSearch() {
  searchOpen.value = !searchOpen.value
  if (searchOpen.value) {
    await nextTick()
    searchInput.value?.focus()
    return
  }
  // Collapsing clears: a hidden filter that still filters is a list the client
  // cannot explain.
  if (search.value) search.value = ''
}

let timer: number | undefined
watch([status, search], () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(reloadOrders, SEARCH_DEBOUNCE_MS)
})

// Line 3 of the card, by the naming rule (decision 23): the workshop's own
// name when it has one counter, «{Workshop} · {Branch}» when it has several.
// The count is the payload's, never inferred — a client with one branch on
// screen and a second one they have never ordered from must still read the
// joined form.
function cardWhere(order: OrderSummary) {
  return workshopBranchName(order.workshop_name, order.branch_name, order.workshop_branch_count)
}

function openOrder(order: OrderSummary) {
  void router.push(rolePath(`/c/orders/${order.id}`))
}

onMounted(() => {
  void orders.loadClientOrders({ status: status.value })
})
</script>

<template>
  <section>
    <!-- §2: one title per phone screen — the compact header names this page. -->
    <div class="client-page-head mb-[22px] hidden md:flex">
      <div>
        <h1>{{ $t('client.orders.title') }}</h1>
      </div>
      <RouterLink
        v-if="!isTrueEmpty"
        :to="rolePath('/c/cutting/drafts')"
        class="mp-button mp-button-primary"
      >
        {{ $t('client.common.newOrder') }}
      </RouterLink>
    </div>

    <!-- Phone: a scrolling chip row beside a search icon-button that expands.
         Desktop: the segmented control and a search field, both always open. -->
    <div class="mb-[11px] flex items-center gap-2 md:mb-[18px] md:gap-3">
      <ClientChipFilter
        v-model="status"
        class="min-w-0 flex-1 md:hidden"
        :label="$t('client.orders.filter.label')"
        :options="statusOptions"
      />
      <SegmentedControl
        v-model="status"
        class="hidden min-w-0 flex-1 md:block"
        :label="$t('client.orders.filter.label')"
        hide-label
        :options="statusOptions"
      />

      <button
        type="button"
        class="grid size-11 shrink-0 place-items-center rounded-[11px] border border-hairline bg-elevated text-ink transition hover:bg-sunk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent md:hidden"
        :aria-label="
          searchOpen ? $t('client.orders.searchClose') : $t('client.orders.searchToggle')
        "
        :aria-expanded="searchOpen"
        aria-controls="client-orders-search"
        @click="toggleSearch"
      >
        <Icon :name="searchOpen ? 'x' : 'search'" class="size-[18px]" />
      </button>

      <label class="hidden md:block md:w-[300px] md:shrink-0">
        <span class="sr-only">{{ $t('client.common.search') }}</span>
        <span class="mp-input flex items-center gap-2">
          <Icon name="search" class="size-[18px] shrink-0 text-ink-muted" />
          <input
            v-model="search"
            type="text"
            class="min-w-0 flex-1 border-0 bg-transparent p-0 outline-none"
            :placeholder="$t('client.orders.searchPlaceholder')"
          />
        </span>
      </label>
    </div>

    <label v-if="searchOpen" id="client-orders-search" class="mb-[11px] block md:hidden">
      <span class="sr-only">{{ $t('client.common.search') }}</span>
      <span class="mp-input flex items-center gap-2">
        <Icon name="search" class="size-[18px] shrink-0 text-ink-muted" />
        <!-- `text`, not `inputmode="numeric"`: drawing names are searchable too. -->
        <input
          ref="searchInput"
          v-model="search"
          type="text"
          class="min-w-0 flex-1 border-0 bg-transparent p-0 outline-none"
          :placeholder="$t('client.orders.searchPlaceholder')"
        />
      </span>
    </label>

    <div v-if="showSkeleton" class="grid gap-[11px]" aria-live="polite">
      <span class="sr-only">{{ $t('client.common.loading') }}</span>
      <div
        v-for="item in 4"
        :key="item"
        class="client-card flex justify-between gap-3 p-3.5 md:p-5"
      >
        <!-- Sized like the real card's five lines — number, name, workshop,
             counts, and the date's own line on phones — so nothing jumps when
             the rows land. -->
        <div class="min-w-0 flex-1">
          <div class="client-skeleton h-[19px] w-28"></div>
          <div class="client-skeleton mt-1.5 h-[18px] w-2/5"></div>
          <div class="client-skeleton mt-2 h-4 w-3/5"></div>
          <div class="client-skeleton mt-1.5 h-3.5 w-2/5"></div>
          <div class="client-skeleton mt-1 h-3.5 w-1/3 md:hidden"></div>
        </div>
        <div class="shrink-0 text-right">
          <div class="client-skeleton ml-auto h-[19px] w-24 rounded-full"></div>
          <div class="client-skeleton ml-auto mt-2 h-4 w-24"></div>
        </div>
      </div>
    </div>

    <ClientErrorState
      v-else-if="orders.error"
      :title="$t('client.orders.loadFailed')"
      :trace-id="orders.traceId"
      @retry="reloadOrders"
    />

    <div v-else-if="visibleOrders.length === 0" class="client-empty">
      <div class="client-empty-icon"><Icon name="box" /></div>
      <template v-if="noFilter">
        <h3>{{ $t('client.orders.emptyTitle') }}</h3>
        <p>{{ $t('client.orders.emptyBody') }}</p>
        <RouterLink :to="rolePath('/c/cutting/drafts')" class="mp-button mp-button-primary mt-4">
          {{ $t('client.common.newOrder') }}
        </RouterLink>
      </template>
      <!-- The landing chip empties for every client who is between orders, so
           it says so plainly and hands over the one filter that still has
           rows — not «no results», which reads like a broken search. -->
      <template v-else-if="isDefaultView">
        <h3>{{ $t('client.orders.emptyActiveTitle') }}</h3>
        <p>{{ $t('client.orders.emptyActiveBody') }}</p>
        <RouterLink :to="{ query: { status: 'all' } }" class="mp-button mp-button-outline mt-4">
          {{ $t('client.orders.viewAllStatuses') }}
        </RouterLink>
      </template>
      <template v-else>
        <h3>{{ $t('client.orders.emptyFilteredTitle') }}</h3>
        <p>{{ $t('client.orders.emptyFilteredHint') }}</p>
        <button type="button" class="mp-button mp-button-outline mt-4" @click="clearFilters">
          {{ $t('client.orders.clearFilters') }}
        </button>
      </template>
    </div>

    <!-- Stale-while-revalidate: the rows stay put under a dim while the next
         page lands, so nothing jumps and the scroll position survives. -->
    <div
      v-else
      class="grid gap-[11px] transition-opacity md:gap-3.5"
      :class="orders.loading ? 'opacity-60' : ''"
    >
      <article
        v-for="order in visibleOrders"
        :key="order.id"
        class="client-card client-card-link flex cursor-pointer items-start justify-between gap-3 p-3.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 md:gap-6 md:p-5"
        role="link"
        tabindex="0"
        :aria-label="`${formatOrderNumber(order.order_number)} — ${clientStatusLabel(order.status)}`"
        @click="openOrder(order)"
        @keydown.enter="openOrder(order)"
        @keydown.space.prevent="openOrder(order)"
      >
        <!-- One descending ladder, top to bottom (decision 28): 15 / 14 / 13.5
             / 12.5. The number is the identity and so the largest thing in the
             column; every line under it is a qualifier and reads smaller. -->
        <div class="min-w-0 flex-1">
          <span class="block text-[15px] font-bold leading-[1.3] text-ink md:text-base">
            {{ formatOrderNumber(order.order_number) }}
          </span>
          <!-- The name is a subtitle, never bigger than the number it belongs
               to — and in the Text face: display is for identity and magnitude,
               not for a truncated line of user input. Rendered only when there
               is one: an untitled drawing shows no line at all, because a grey
               "Nomsiz chizma" placeholder was the worst element on the old card. -->
          <h2
            v-if="order.draft_name"
            class="mt-[3px] truncate text-sm font-semibold leading-[1.3] text-ink md:mt-1 md:text-[15px]"
          >
            {{ order.draft_name }}
          </h2>
          <!-- Staff-minted drawings stay hidden from the client's own list
               until the order exists, so this is the first time they see it. -->
          <span
            v-if="order.created_via_workshop"
            class="client-pill client-pill-info mt-[5px] md:mt-1.5"
          >
            {{ $t('client.orders.createdByWorkshop') }}
          </span>
          <!-- The workshop is who the client deals with, so it sits above the
               counts and stays `ink-soft` rather than muted: readable at a
               glance, still clearly under the name. Two short lines, not one
               wrapping one — the right column leaves the left about 200px on a
               phone. -->
          <p
            class="mt-[3px] text-[13.5px] font-medium leading-[1.4] text-ink-soft md:mt-1 md:text-sm"
          >
            {{ cardWhere(order) }}
          </p>
          <!-- Counts and date: joined by «·» from `md` up, the date on its own
               line under them on a phone (decision 22, amended 2026-09-06
               evening) — joined, the date wrapped in the middle at 375px. -->
          <div
            class="mt-0.5 flex flex-col text-[12.5px] leading-[1.4] text-ink-muted md:flex-row md:items-baseline md:gap-x-[3px] md:text-[13px]"
          >
            <p>
              <b class="font-semibold">{{ order.item_count }}</b>
              {{ $t('client.unit.part', order.item_count) }} ·
              <b class="font-semibold">{{ order.planned_panels || '—' }}</b>
              {{ $t('client.unit.sheet', order.planned_panels) }}
            </p>
            <span class="hidden shrink-0 md:inline" aria-hidden="true">·</span>
            <p class="whitespace-nowrap">{{ formatClientDateTime(order.created_at) }}</p>
          </div>
        </div>

        <div class="flex shrink-0 flex-col items-end gap-[5px] md:gap-[7px]">
          <span :class="clientStatusPillClass(order.status)">
            {{ clientStatusLabel(order.status) }}
          </span>
          <span class="whitespace-nowrap text-base font-bold leading-[1.25] text-ink">
            {{ formatTiyin(order.total_tiyin) }}
          </span>
        </div>
      </article>

      <button
        v-if="orders.ordersHasMore"
        type="button"
        class="mp-button mp-button-outline w-full"
        :disabled="orders.loading"
        @click="loadMoreOrders"
      >
        {{ $t('client.orders.loadMore') }}
      </button>
    </div>
  </section>
</template>
