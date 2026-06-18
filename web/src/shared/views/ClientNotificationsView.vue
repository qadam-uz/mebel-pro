<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import FormSelect from '@/shared/components/FormSelect.vue'
import {
  clientNotificationBody,
  clientNotificationIconName,
  clientNotificationTitle,
  formatRelativeDate,
} from '@/shared/app/clientUi'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

const notifications = useNotificationsStore()
const router = useRouter()
const rolePath = useRolePath()
const readFilter = ref<'all' | 'unread' | 'read'>('all')

function goBack() {
  // Reached via a deep link / refresh, history may have no in-app entry to return to.
  if (window.history.state?.back) router.back()
  else router.push(rolePath('/c'))
}

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
  return clientNotificationTitle(item)
}

function body(item: NotificationItem) {
  return (
    clientNotificationBody(item) ??
    (item.entity_type === 'order' ? "Buyurtma holati o'zgardi." : 'Yangi xabar mavjud.')
  )
}

function iconName(item: NotificationItem) {
  return clientNotificationIconName(item)
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
    <button type="button" class="client-back" @click="goBack">← Orqaga</button>

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

      <ClientErrorState
        v-else-if="notifications.error"
        title="Bildirishnomalarni yuklab bo'lmadi"
        message="Ulanishda xatolik. Birozdan so'ng qayta urinib ko'ring."
        :trace-id="notifications.traceId"
        @retry="notifications.loadList(50)"
      />

      <div v-else-if="visibleItems.length === 0" class="client-empty">
        <div class="client-empty-icon"><Icon name="inbox" /></div>
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
          class="client-card grid w-full grid-cols-[38px_minmax(0,1fr)_auto] items-center gap-4 p-4 text-left transition hover:border-ink max-[480px]:grid-cols-[38px_minmax(0,1fr)]"
          :class="item.read_at === null ? 'bg-accent-soft border-accent-tint' : ''"
          @click="openItem(item)"
        >
          <span
            class="client-notif-icon grid size-[38px] place-items-center rounded-lg text-white"
            :class="iconClass(item)"
            aria-hidden="true"
          >
            <Icon :name="iconName(item)" />
          </span>
          <span class="min-w-0">
            <span class="block truncate text-sm font-bold text-ink">{{ title(item) }}</span>
            <span class="mt-1 block text-sm text-ink-soft">{{ body(item) }}</span>
          </span>
          <span class="font-mono text-xs text-ink-muted max-[480px]:col-start-2 max-[480px]:mt-1">
            {{ formatRelativeDate(item.created_at) }}
          </span>
        </button>
      </div>
    </div>
  </section>
</template>
