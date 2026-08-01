<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import {
  notificationBody,
  notificationIconName,
  notificationTitle,
} from '@/shared/app/notificationPresenter'
import { useRolePath } from '@/shared/app/paths'
import {
  workshopNotificationDestination,
  workshopNotificationMatchesFilter,
} from '@/shared/app/workshopNotifications'
import Icon from '@/shared/components/AppIcon.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatDate } from '@/shared/formatters'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

const notifications = useNotificationsStore()
const router = useRouter()
const rolePath = useRolePath()
const toast = useToast()
const { t } = useI18n()
const filter = ref('all')

const filterOptions = computed(() => [
  { value: 'all', label: t('shell.notifications.filterAll') },
  { value: 'unread', label: t('shell.notifications.filterUnread') },
  { value: 'order', label: t('shell.notifications.filterOrders') },
  { value: 'inventory', label: t('shell.notifications.filterInventory') },
  { value: 'finance', label: t('shell.notifications.filterFinance') },
])

const filtered = computed(() =>
  notifications.items.filter((item) => workshopNotificationMatchesFilter(item, filter.value)),
)

// Render through the same shared presenter as the bell menu (CB-101) so the
// full page never falls back to raw event codes / entity types.
function title(item: NotificationItem) {
  return notificationTitle(item, 'workshop')
}

function body(item: NotificationItem) {
  return notificationBody(item)
}

function destination(item: NotificationItem) {
  return workshopNotificationDestination(item)
}

async function openItem(item: NotificationItem) {
  const to = destination(item)
  if (!to) {
    toast.warn(t('shell.notifications.notOpenable'))
    return
  }
  if (item.read_at === null) {
    await notifications.markRead(item.id)
    if (notifications.actionError) {
      toast.danger(t('shell.notifications.markReadFailed'))
    }
  }
  await router.push(rolePath(to))
}

async function markAll() {
  await notifications.markAllRead()
  if (notifications.actionError) {
    toast.danger(t('shell.notifications.markAllFailed'))
    return
  }
  await notifications.loadList(50)
  toast.success(t('shell.notifications.markAllDone'))
}

onMounted(() => {
  void notifications.loadList(50)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>{{ $t('shell.notifications.title') }}</h1>
      </div>
    </div>

    <div class="mp-filters">
      <ProjectDropdown
        v-model="filter"
        :label="$t('shell.notifications.filterLabel')"
        :options="filterOptions"
        top-label
      />
      <!-- Page heads are title-only; a bulk action lives at the right end of the
           filter row like every create button (DESIGN.md, QAD-182). -->
      <button
        class="mp-button mp-button-outline"
        type="button"
        :disabled="notifications.unread === 0"
        @click="markAll"
      >
        {{ $t('shell.notifications.markAll') }}
      </button>
    </div>

    <div v-if="notifications.loading" class="card max-w-[800px] p-5" aria-live="polite">
      <span class="sk-line"></span>
      <span class="sk-line mt-3"></span>
      <span class="sk-line mt-3"></span>
    </div>

    <div v-else-if="notifications.error" class="st-error max-w-[800px]" role="alert">
      <h3>{{ $t('shell.notifications.loadFailedTitle') }}</h3>
      <p>{{ $t('shell.notifications.loadFailedBody') }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="notifications.loading"
        @click="notifications.loadList(50)"
      >
        {{ $t('shell.action.retry') }}
      </button>
      <p v-if="notifications.traceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ notifications.traceId }}
      </p>
    </div>

    <div v-else-if="filtered.length === 0" class="st-empty max-w-[800px]">
      <h3>
        {{
          filter === 'unread'
            ? $t('shell.notifications.emptyUnreadTitle')
            : $t('shell.notifications.emptyTitle')
        }}
      </h3>
      <p>{{ $t('shell.notifications.emptyWorkshopBody') }}</p>
    </div>

    <div v-else class="grid max-w-[800px] gap-2">
      <button
        v-for="item in filtered"
        :key="item.id"
        type="button"
        class="grid grid-cols-[40px_minmax(0,1fr)_auto] items-center gap-4 rounded-lg border border-hairline p-4 text-left transition hover:border-ink"
        :class="item.read_at === null ? 'bg-accent-soft' : 'bg-elevated'"
        @click="openItem(item)"
      >
        <span
          class="client-notif-icon grid size-10 place-items-center rounded-lg bg-sunk text-ink-soft"
          aria-hidden="true"
        >
          <Icon :name="notificationIconName(item)" />
        </span>
        <span class="min-w-0">
          <span class="block truncate text-sm font-extrabold text-ink">{{ title(item) }}</span>
          <span v-if="body(item)" class="mt-1 block truncate text-xs text-ink-soft">
            {{ body(item) }}
          </span>
        </span>
        <span class="font-mono text-[11px] text-ink-muted">{{ formatDate(item.created_at) }}</span>
      </button>
    </div>
  </section>
</template>
