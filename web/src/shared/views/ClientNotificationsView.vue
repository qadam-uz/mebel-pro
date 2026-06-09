<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import FormSelect from '@/shared/components/FormSelect.vue'
import { formatRelativeDate } from '@/shared/app/clientUi'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

const notifications = useNotificationsStore()
const router = useRouter()
const rolePath = useRolePath()
const readFilter = ref<'all' | 'unread' | 'read'>('all')

const filterOptions = [
  { value: 'all', label: 'Hammasi', meta: 'barcha xabarlar' },
  { value: 'unread', label: "O'qilmagan", meta: 'hali ochilmagan' },
  { value: 'read', label: "O'qilgan", meta: "ko'rilgan xabarlar" },
]

const visibleItems = computed(() =>
  notifications.items.filter((item) => {
    if (readFilter.value === 'unread') return item.read_at === null
    if (readFilter.value === 'read') return item.read_at !== null
    return true
  }),
)

function title(item: NotificationItem) {
  const summary = item.payload.summary
  if (typeof summary === 'string' && summary.trim()) return summary
  return item.event_code
}

function body(item: NotificationItem) {
  const value = item.payload.body ?? item.payload.detail ?? item.payload.message
  if (typeof value === 'string' && value.trim()) return value
  if (item.entity_type === 'order') return "Buyurtma holati o'zgardi."
  return 'Yangi xabar mavjud.'
}

function iconClass(item: NotificationItem) {
  if (item.event_code.includes('cancel')) return 'bg-danger'
  if (item.event_code.includes('ready') || item.event_code.includes('complete')) return 'bg-success'
  return 'bg-accent'
}

function destination(item: NotificationItem) {
  if (item.entity_type === 'order' && item.entity_id) return `/c/orders/${item.entity_id}`
  return null
}

async function openItem(item: NotificationItem) {
  if (item.read_at === null) await notifications.markRead(item.id)
  const to = destination(item)
  if (to) await router.push(rolePath(to))
}

async function markAllRead() {
  await notifications.markAllRead()
  await notifications.loadList(50)
}

onMounted(() => {
  void notifications.loadList(50)
})
</script>

<template>
  <section>
    <button type="button" class="client-back" @click="$router.back()">← Orqaga</button>

    <div class="client-page-head">
      <div>
        <h1>Bildirishnomalar</h1>
        <p class="sub">Buyurtma o'zgarishlari va ustaxonadan xabarlar.</p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="markAllRead">
        Hammasini o'qilgan deb belgilash
      </button>
    </div>

    <div class="mb-4 max-w-60">
      <FormSelect v-model="readFilter" label="Holat" :options="filterOptions" />
    </div>

    <div class="max-w-[760px]">
      <div v-if="notifications.loading" class="grid gap-2" aria-live="polite">
        <div
          v-for="item in 5"
          :key="item"
          class="client-card grid grid-cols-[38px_1fr_64px] gap-4 p-4"
        >
          <div class="client-skeleton h-[38px]"></div>
          <div>
            <div class="client-skeleton h-3 w-3/5"></div>
            <div class="client-skeleton mt-2 h-3 w-5/6"></div>
          </div>
          <div class="client-skeleton h-3"></div>
        </div>
      </div>

      <div v-else-if="notifications.error" class="client-error">
        <div class="client-error-icon">!</div>
        <h3>Bildirishnomalarni yuklab bo'lmadi</h3>
        <p>Ulanishda xatolik. Birozdan so'ng qayta urinib ko'ring.</p>
        <button
          type="button"
          class="mp-button mp-button-outline mt-4"
          @click="notifications.loadList(50)"
        >
          Qayta urinish
        </button>
      </div>

      <div v-else-if="visibleItems.length === 0" class="client-empty">
        <div class="client-empty-icon">✓</div>
        <h3>Bildirishnoma yo'q</h3>
        <p v-if="readFilter === 'unread'">
          O'qilmagan bildirishnoma yo'q — hammasini ko'rib chiqdingiz.
        </p>
        <p v-else-if="readFilter === 'read'">O'qilgan bildirishnoma yo'q.</p>
        <p v-else>Hozircha bildirishnoma yo'q — buyurtma holati o'zgarsa shu yerda ko'rinadi.</p>
      </div>

      <div v-else class="grid gap-2">
        <button
          v-for="item in visibleItems"
          :key="item.id"
          type="button"
          class="client-card grid w-full grid-cols-[38px_minmax(0,1fr)_auto] items-center gap-4 p-4 text-left transition hover:border-ink"
          :class="item.read_at === null ? 'bg-accent-soft border-accent-tint' : ''"
          @click="openItem(item)"
        >
          <span
            class="grid size-[38px] place-items-center rounded-lg font-serif text-sm font-bold text-white"
            :class="iconClass(item)"
            aria-hidden="true"
          >
            {{ item.entity_type?.slice(0, 1).toUpperCase() ?? 'N' }}
          </span>
          <span class="min-w-0">
            <span class="block truncate text-sm font-bold text-ink">{{ title(item) }}</span>
            <span class="mt-1 block text-sm text-ink-soft">{{ body(item) }}</span>
          </span>
          <span class="font-mono text-xs text-ink-muted">
            {{ formatRelativeDate(item.created_at) }}
          </span>
        </button>
      </div>
    </div>
  </section>
</template>
