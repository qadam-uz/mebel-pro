<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import {
  adminDateTime,
  adminErrorMessage,
  adminNotificationDestination,
  adminNotificationTitle,
  dropdownOption,
} from '@/shared/app/adminUi'
import { useRolePath } from '@/shared/app/paths'
import AdminErrorState from '@/shared/components/AdminErrorState.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import { useToast } from '@/shared/composables/useToast'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

const notifications = useNotificationsStore()
const rolePath = useRolePath()
const toast = useToast()
const filter = ref('all')
const markingId = ref<string | null>(null)
const PAGE_SIZE = 50
const filterOptions = [
  dropdownOption('all', 'Hammasi', 'barcha yozuvlar'),
  dropdownOption('unread', "O'qilmagan", 'faqat yangi'),
  dropdownOption('read', "O'qilgan", 'arxiv'),
]

const rows = computed(() => {
  if (filter.value === 'unread') return notifications.items.filter((item) => item.read_at === null)
  if (filter.value === 'read') return notifications.items.filter((item) => item.read_at !== null)
  return notifications.items
})

// AB-24: a colored kind tile so a failed-task vs error-growth alert is
// distinguishable at a glance (the inbox's whole purpose).
function kindMeta(item: NotificationItem) {
  if (item.event_code.includes('job')) return { letter: 'J', cls: 'bg-warning-soft text-warning' }
  if (item.event_code.includes('error')) return { letter: 'E', cls: 'bg-danger-soft text-danger' }
  return { letter: '•', cls: 'bg-sunk text-ink-muted' }
}

async function markRead(id: string) {
  markingId.value = id
  try {
    await notifications.markRead(id)
    if (notifications.actionError) {
      toast.danger(
        adminErrorMessage(
          notifications.actionError,
          "Bildirishnomani o'qilgan deb belgilab bo'lmadi. Qayta urinib ko'ring.",
        ),
      )
    }
  } finally {
    markingId.value = null
  }
}

function markOpened(item: NotificationItem) {
  if (item.read_at === null) void markRead(item.id)
}

async function markAll() {
  await notifications.markAllRead()
  if (notifications.actionError) {
    toast.danger(
      adminErrorMessage(
        notifications.actionError,
        "Hammasini o'qilgan deb belgilab bo'lmadi. Qayta urinib ko'ring.",
      ),
    )
  } else toast.success("Hammasi o'qilgan deb belgilandi")
}

function loadFirstPage() {
  return notifications.loadList(PAGE_SIZE, 0, filter.value === 'unread')
}

function loadMore() {
  return notifications.loadList(PAGE_SIZE, notifications.items.length, filter.value === 'unread')
}

let pollTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  void loadFirstPage()
  pollTimer = setInterval(() => {
    if (document.visibilityState === 'visible') void notifications.loadUnreadCount()
  }, 45000)
})
watch(filter, () => {
  void loadFirstPage()
})
onBeforeUnmount(() => clearInterval(pollTimer))
</script>

<template>
  <section>
    <div class="admin-page-head">
      <div>
        <h1>Bildirishnomalar</h1>
      </div>
      <button
        type="button"
        class="mp-button mp-button-outline"
        :disabled="notifications.unread === 0"
        @click="markAll"
      >
        Hammasini o'qilgan deb belgilash
      </button>
    </div>

    <div class="admin-filters">
      <FormSelect
        v-model="filter"
        class="admin-filter-select"
        label="Tur"
        :options="filterOptions"
      />
    </div>

    <section
      v-if="notifications.loading && notifications.items.length === 0"
      class="admin-card p-5"
      aria-live="polite"
    >
      <div class="admin-skeleton-line w-3/5"></div>
      <div class="admin-skeleton-line w-4/5"></div>
      <div class="admin-skeleton-line w-2/5"></div>
    </section>

    <AdminErrorState
      v-else-if="notifications.error"
      :code="notifications.error"
      :trace-id="notifications.traceId"
      title="Bildirishnomalar yuklanmadi"
      @retry="loadFirstPage"
    />

    <section v-else-if="rows.length === 0" class="admin-empty">
      <h3>Yangilik yo'q</h3>
      <p>Platforma adminiga tegishli bildirishnomalar shu yerda ko'rinadi.</p>
    </section>

    <section v-else class="admin-card">
      <div class="admin-card-b py-2">
        <article
          v-for="item in rows"
          :key="item.id"
          class="admin-row-item"
          :class="{ 'border-l-2 border-accent pl-2': item.read_at === null }"
        >
          <span
            class="flex size-8 shrink-0 items-center justify-center rounded-md text-sm font-extrabold"
            :class="kindMeta(item).cls"
            aria-hidden="true"
          >
            {{ kindMeta(item).letter }}
          </span>
          <span class="min-w-0">
            <RouterLink
              :to="rolePath(adminNotificationDestination(item))"
              class="block truncate font-bold text-ink no-underline"
              :aria-label="`${adminNotificationTitle(item)} bildirishnomasini ochish`"
              @click="markOpened(item)"
            >
              {{ adminNotificationTitle(item) }}
            </RouterLink>
            <small class="block truncate text-ink-muted">
              {{ adminDateTime(item.created_at) }}
            </small>
          </span>
          <button
            v-if="item.read_at === null"
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            :disabled="markingId === item.id"
            @click="markRead(item.id)"
          >
            O'qilgan deb belgilash
          </button>
          <span v-else class="admin-mono text-ink-muted">{{ adminDateTime(item.read_at) }}</span>
        </article>
        <div v-if="notifications.hasMore" class="mt-3 flex justify-center">
          <button
            type="button"
            class="mp-button mp-button-outline"
            :disabled="notifications.loading"
            @click="loadMore"
          >
            {{ notifications.loading ? 'Yuklanmoqda' : 'Yana yuklash' }}
          </button>
        </div>
      </div>
    </section>
  </section>
</template>
