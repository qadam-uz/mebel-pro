<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import ClientChipFilter from '@/shared/components/ClientChipFilter.vue'
import { NOTIFICATIONS_PAGE_LIMIT } from '@/shared/app/constants'
import {
  notificationBody,
  notificationDestination,
  notificationIconName,
  notificationTitle,
} from '@/shared/app/notificationPresenter'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { formatClientDateTime } from '@/shared/formatters'
import { useToast } from '@/shared/composables/useToast'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

const notifications = useNotificationsStore()
const router = useRouter()
const rolePath = useRolePath()
const toast = useToast()
const { t } = useI18n()
const readFilter = ref<'all' | 'unread' | 'read'>('all')

function goBack() {
  // Reached via a deep link / refresh, history may have no in-app entry to return to.
  if (window.history.state?.back) router.back()
  else router.push(rolePath('/c'))
}

// The same chip row Buyurtmalar uses (UX review 2026-09-05): three mutually
// exclusive choices, all visible, no popover to open for a one-word answer.
const filterOptions = computed(() => [
  { value: 'all', label: t('shell.notifications.clientFilterAll') },
  { value: 'unread', label: t('shell.notifications.clientFilterUnread') },
  { value: 'read', label: t('shell.notifications.clientFilterRead') },
])

/**
 * Stale-while-revalidate: the skeleton is for a cold feed only. Re-opening the
 * page — or flipping the chip row — keeps the rows in hand under a dim while
 * the refresh lands, instead of blanking the list on every visit (client audit
 * 2026-09-03). Gated on the store's raw items, not `visibleItems`: the read/
 * unread split is applied client-side, and an empty *filter* result is an empty
 * state, never a skeleton.
 */
const showSkeleton = computed(() => notifications.loading && notifications.items.length === 0)

const visibleItems = computed(() =>
  notifications.items.filter((item) => {
    if (readFilter.value === 'unread') return item.read_at === null
    if (readFilter.value === 'read') return item.read_at !== null
    return true
  }),
)

function title(item: NotificationItem) {
  return notificationTitle(item, 'client')
}

function body(item: NotificationItem) {
  // Defer entirely to the shared presenter so the page and the bell render the same
  // body for the same notification (CB-101); the template hides the line when null
  // instead of forcing a generic fallback the bell never shows.
  return notificationBody(item)
}

function iconName(item: NotificationItem) {
  return notificationIconName(item)
}

// The glyph colour travels with the fill: bone on graphite (pure white on
// graphite reads as glare), white on the saturated status reds and greens.
function iconClass(item: NotificationItem) {
  if (item.event_code.includes('cancel')) return 'bg-danger text-white'
  if (item.event_code.includes('ready') || item.event_code.includes('complete'))
    return 'bg-success text-white'
  return 'bg-accent text-on-accent'
}

function destination(item: NotificationItem) {
  return notificationDestination(item, 'client')
}

async function openItem(item: NotificationItem) {
  const to = destination(item)
  if (!to) {
    // No viewable target — keep it unread and tell the user rather than a dead tap (CB-125).
    toast.warn(t('shell.notifications.notOpenable'))
    return
  }
  // markRead is best-effort: opening the order is the intent, so navigate
  // regardless. A failure leaves the row unread (the badge stays) as its own
  // feedback — no disjointed toast-then-navigate.
  if (item.read_at === null) await notifications.markRead(item.id)
  await router.push(rolePath(to))
}

// 'unread' filters server-side so pagination stays accurate; 'all'/'read' load
// the full feed and the read/unread split is applied client-side (CB-41).
const unreadOnly = () => readFilter.value === 'unread'

async function markAllRead() {
  await notifications.markAllRead()
  if (notifications.actionError) {
    toast.danger(t('shell.notifications.markAllFailed'))
    return
  }
  await notifications.loadList(NOTIFICATIONS_PAGE_LIMIT, 0, unreadOnly())
  toast.success(t('shell.notifications.markAllDone'))
}

function loadMore() {
  void notifications.loadList(NOTIFICATIONS_PAGE_LIMIT, notifications.items.length, unreadOnly())
}

// Changing the filter restarts pagination from offset 0 so the load-more button
// and the loaded page reflect the active filter, not a stale full-feed page.
watch(readFilter, () => {
  void notifications.loadList(NOTIFICATIONS_PAGE_LIMIT, 0, unreadOnly())
})

onMounted(() => {
  void notifications.loadList(NOTIFICATIONS_PAGE_LIMIT, 0, unreadOnly())
})
</script>

<template>
  <section>
    <button type="button" class="client-back" @click="goBack">{{ $t('shell.action.back') }}</button>

    <!-- §2: one title per phone screen — the compact header names this page,
         so the body opens on the sub-line. Desktop keeps its H1. -->
    <div class="client-page-head hidden md:flex">
      <div>
        <h1>{{ $t('shell.notifications.title') }}</h1>
        <p class="sub">{{ $t('shell.notifications.clientSubtitle') }}</p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="markAllRead">
        {{ $t('shell.notifications.markAll') }}
      </button>
    </div>
    <p class="mb-3 mt-2.5 text-[13px] leading-[1.45] text-ink-soft md:hidden">
      {{ $t('shell.notifications.clientSubtitle') }}
    </p>
    <button
      type="button"
      class="mp-button mp-button-outline mb-3 w-full md:hidden"
      @click="markAllRead"
    >
      {{ $t('shell.notifications.markAll') }}
    </button>

    <ClientChipFilter
      v-model="readFilter"
      class="mb-3 md:mb-4"
      :label="$t('shell.notifications.readFilterLabel')"
      :options="filterOptions"
    />

    <div class="max-w-[760px]">
      <div v-if="showSkeleton" class="grid gap-2" aria-live="polite">
        <div
          v-for="item in 5"
          :key="item"
          class="client-card grid grid-cols-[38px_minmax(0,1fr)_auto] gap-4 p-4 max-[480px]:grid-cols-[38px_minmax(0,1fr)]"
        >
          <div class="client-skeleton h-[38px]"></div>
          <div>
            <div class="client-skeleton h-3 w-3/5"></div>
            <div class="client-skeleton mt-2 h-3 w-5/6"></div>
          </div>
          <div class="client-skeleton h-3"></div>
        </div>
      </div>

      <!-- Only when there is nothing else to show: a refresh that fails behind
           a feed already on screen leaves the feed there. -->
      <ClientErrorState
        v-else-if="notifications.error && notifications.items.length === 0"
        :title="$t('shell.notifications.loadFailedTitle')"
        :message="$t('shell.notifications.loadFailedClientBody')"
        :trace-id="notifications.traceId"
        @retry="notifications.loadList(NOTIFICATIONS_PAGE_LIMIT, 0, unreadOnly())"
      />

      <div v-else-if="visibleItems.length === 0" class="client-empty">
        <div class="client-empty-icon"><Icon name="inbox" /></div>
        <h3>{{ $t('shell.notifications.emptyTitle') }}</h3>
        <p v-if="readFilter === 'unread'">{{ $t('shell.notifications.emptyUnreadBody') }}</p>
        <p v-else-if="readFilter === 'read'">{{ $t('shell.notifications.emptyReadBody') }}</p>
        <p v-else>{{ $t('shell.notifications.emptyClientBody') }}</p>
      </div>

      <div
        v-else
        class="grid gap-2 transition-opacity"
        :class="notifications.loading ? 'opacity-60' : ''"
      >
        <!-- The unread edge is a ring, and the ring utility re-declares
             `box-shadow` from the utilities layer — which would drop the card's
             own `--shadow-card` — so the two shadow utilities come along to put
             the elevation and the hover lift back. -->
        <button
          v-for="item in visibleItems"
          :key="item.id"
          type="button"
          class="client-card grid w-full grid-cols-[38px_minmax(0,1fr)_auto] items-center gap-4 p-4 text-left client-card-link max-[480px]:grid-cols-[38px_minmax(0,1fr)]"
          :class="
            item.read_at === null
              ? 'shadow-card ring-1 ring-hairline-strong hover:shadow-lifted'
              : ''
          "
          @click="openItem(item)"
        >
          <span
            class="client-notif-icon grid size-[38px] place-items-center rounded-lg shadow-[0_2px_6px_-2px_color-mix(in_srgb,var(--color-ink)_22%,transparent)]"
            :class="iconClass(item)"
            aria-hidden="true"
          >
            <Icon :name="iconName(item)" />
          </span>
          <span class="min-w-0">
            <span class="block truncate text-sm font-bold text-ink">{{ title(item) }}</span>
            <span v-if="body(item)" class="mt-1 block text-sm text-ink-soft">{{ body(item) }}</span>
          </span>
          <!-- Unread reads as emphasised, not selected: the signal dot plus a
               heavier edge, on the same white card. A `sunk` fill would pull the
               row down towards the canvas and make the unread ones look dimmer
               than the read ones. The dot carries its word for anyone who cannot
               see it. The edge is a RING, not a border — `.client-card` is
               shadow-only, so `border-hairline-strong` alone would set a colour
               on a zero-width border and the row would carry the dot and nothing
               else. See the class binding above for why the shadow utilities
               ride along. -->
          <span
            class="flex items-center gap-2 text-xs text-ink-muted max-[480px]:col-start-2 max-[480px]:mt-1"
          >
            <template v-if="item.read_at === null">
              <span class="size-2 shrink-0 rounded-full bg-signal" aria-hidden="true"></span>
              <span class="sr-only">{{ $t('shell.notifications.unreadMark') }}</span>
            </template>
            {{ formatClientDateTime(item.created_at) }}
          </span>
        </button>
      </div>

      <button
        v-if="notifications.hasMore"
        type="button"
        class="mp-button mp-button-outline mt-3 w-full"
        :disabled="notifications.loading"
        @click="loadMore"
      >
        {{ $t('shell.action.loadMore') }}
      </button>
    </div>
  </section>
</template>
