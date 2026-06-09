<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { formatDate } from '@/shared/formatters'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

const notifications = useNotificationsStore()
const router = useRouter()
const rolePath = useRolePath()
const filter = ref('all')

const filterOptions = [
  { value: 'all', label: 'Hammasi', meta: 'barcha bildirishnomalar', status: 'active' as const },
  { value: 'unread', label: "O'qilmagan", meta: 'faqat yangi', status: 'pending' as const },
  { value: 'order', label: 'Buyurtmalar', meta: 'order event', status: 'active' as const },
  { value: 'inventory', label: 'Ombor', meta: 'stock event', status: 'active' as const },
  { value: 'finance', label: 'Moliya', meta: 'ledger event', status: 'active' as const },
]

const filtered = computed(() =>
  notifications.items.filter((item) => {
    if (filter.value === 'unread') return item.read_at === null
    if (filter.value === 'all') return true
    return item.event_code.includes(filter.value) || item.entity_type === filter.value
  }),
)

function title(item: NotificationItem) {
  const summary = item.payload.summary
  if (typeof summary === 'string' && summary.trim()) return summary
  return item.event_code
}

function body(item: NotificationItem) {
  const detail = item.payload.detail ?? item.payload.body ?? item.payload.branch_name
  return typeof detail === 'string' ? detail : (item.entity_type ?? 'system')
}

function destination(item: NotificationItem) {
  if (item.entity_type === 'order' && item.entity_id) return `/workshop/orders/${item.entity_id}`
  if (item.entity_type === 'branch' && item.entity_id) return `/workshop/branches/${item.entity_id}`
  return null
}

async function openItem(item: NotificationItem) {
  if (item.read_at === null) await notifications.markRead(item.id)
  const to = destination(item)
  if (to) await router.push(rolePath(to))
}

async function markAll() {
  await notifications.markAllRead()
  await notifications.loadList(50)
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
        <p class="sub">Buyurtma, ombor, moliya va tizim ogohlantirishlari.</p>
      </div>
      <div class="tools">
        <button class="mp-button mp-button-outline" type="button" @click="markAll">
          Hammasini o'qilgan deb belgilash
        </button>
      </div>
    </div>

    <div class="filters">
      <ProjectDropdown v-model="filter" label="Tur" :options="filterOptions" />
    </div>

    <div v-if="notifications.loading" class="card max-w-[800px] p-5" aria-live="polite">
      <span class="sk-line"></span>
      <span class="sk-line mt-3"></span>
      <span class="sk-line mt-3"></span>
    </div>

    <div v-else-if="notifications.error" class="st-error max-w-[800px]">
      <h3>Bildirishnomalarni yuklab bo'lmadi</h3>
      <p>Asosiy ma'lumotlar tegishli sahifalarda baribir mavjud.</p>
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
        class="grid grid-cols-[40px_minmax(0,1fr)_auto] items-center gap-4 rounded-lg border border-hairline bg-elevated p-4 text-left transition hover:border-ink"
        :class="{ 'bg-accent-soft': item.read_at === null }"
        @click="openItem(item)"
      >
        <span
          class="grid size-10 place-items-center rounded-lg font-serif font-bold text-white"
          :class="
            item.entity_type === 'order'
              ? 'bg-accent'
              : item.event_code.includes('stock')
                ? 'bg-warning'
                : item.event_code.includes('finance')
                  ? 'bg-success'
                  : 'bg-ink-soft'
          "
          aria-hidden="true"
        >
          {{ (item.entity_type ?? item.event_code).slice(0, 1).toUpperCase() }}
        </span>
        <span class="min-w-0">
          <span class="block truncate text-sm font-extrabold text-ink">{{ title(item) }}</span>
          <span class="mt-1 block truncate text-xs text-ink-soft">{{ body(item) }}</span>
        </span>
        <span class="font-mono text-[11px] text-ink-muted">{{ formatDate(item.created_at) }}</span>
      </button>
    </div>
  </section>
</template>
