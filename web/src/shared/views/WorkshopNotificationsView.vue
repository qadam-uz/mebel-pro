<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
const filter = ref('all')

const filterOptions = [
  { value: 'all', label: 'Hammasi' },
  { value: 'unread', label: "O'qilmagan" },
  { value: 'order', label: 'Buyurtmalar' },
  { value: 'inventory', label: 'Ombor' },
  { value: 'finance', label: 'Moliya' },
]

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
    toast.warn("Bu bildirishnoma ochib bo'lmaydi.")
    return
  }
  if (item.read_at === null) {
    await notifications.markRead(item.id)
    if (notifications.actionError) {
      toast.danger("Bildirishnomani o'qilgan deb belgilab bo'lmadi. Qayta urinib ko'ring.")
    }
  }
  await router.push(rolePath(to))
}

async function markAll() {
  await notifications.markAllRead()
  if (notifications.actionError) {
    toast.danger("Hammasini o'qilgan deb belgilab bo'lmadi. Qayta urinib ko'ring.")
    return
  }
  await notifications.loadList(50)
  toast.success("Hammasi o'qilgan deb belgilandi.")
}

onMounted(() => {
  void notifications.loadList(50)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Bildirishnomalar</h1>
      </div>
    </div>

    <div class="mp-filters">
      <ProjectDropdown v-model="filter" label="Tur" :options="filterOptions" top-label />
      <!-- Page heads are title-only; a bulk action lives at the right end of the
           filter row like every create button (DESIGN.md, QAD-182). -->
      <button
        class="mp-button mp-button-outline"
        type="button"
        :disabled="notifications.unread === 0"
        @click="markAll"
      >
        Hammasini o'qilgan deb belgilash
      </button>
    </div>

    <div v-if="notifications.loading" class="card max-w-[800px] p-5" aria-live="polite">
      <span class="sk-line"></span>
      <span class="sk-line mt-3"></span>
      <span class="sk-line mt-3"></span>
    </div>

    <div v-else-if="notifications.error" class="st-error max-w-[800px]" role="alert">
      <h3>Bildirishnomalarni yuklab bo'lmadi</h3>
      <p>Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="notifications.loading"
        @click="notifications.loadList(50)"
      >
        Qayta urinish
      </button>
      <p v-if="notifications.traceId" class="mt-3 text-xs text-ink-muted">
        trace_id: {{ notifications.traceId }}
      </p>
    </div>

    <div v-else-if="filtered.length === 0" class="st-empty max-w-[800px]">
      <h3>{{ filter === 'unread' ? "O'qilmagan bildirishnoma yo'q" : "Bildirishnoma yo'q" }}</h3>
      <p>Yangi buyurtma, ombor yoki moliya hodisalari shu yerda chiqadi.</p>
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
