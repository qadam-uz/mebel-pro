<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { formatDate } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

const auth = useAuthStore()
const notifications = useNotificationsStore()
const router = useRouter()
const roleConfig = useRoleConfig()
const rolePath = useRolePath()
const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const badgeText = computed(() => (notifications.unread > 9 ? '9+' : String(notifications.unread)))

function title(item: NotificationItem) {
  const summary = item.payload.summary
  if (typeof summary === 'string' && summary.trim()) return summary
  return item.event_code
}

function destination(item: NotificationItem) {
  if (!item.entity_type || !item.entity_id) return null
  if (item.entity_type === 'order' && roleConfig.role === 'client') {
    return `/c/orders/${item.entity_id}`
  }
  if (item.entity_type === 'order' && roleConfig.role === 'workshop') {
    return `/workshop/orders/${item.entity_id}`
  }
  if (item.entity_type === 'branch' && roleConfig.role === 'workshop') {
    return `/workshop/branches/${item.entity_id}`
  }
  if (item.entity_type === 'workshop' && roleConfig.role === 'admin') {
    return `/admin/workshops/${item.entity_id}`
  }
  return null
}

async function toggle() {
  open.value = !open.value
  if (open.value) await notifications.loadList()
}

async function openItem(item: NotificationItem) {
  if (item.read_at === null) await notifications.markRead(item.id)
  const to = destination(item)
  open.value = false
  if (to) await router.push(rolePath(to))
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (rootRef.value?.contains(target)) return
  open.value = false
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
})

watch(
  () => auth.accessToken,
  (accessToken) => {
    if (accessToken) void notifications.loadUnreadCount()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
})
</script>

<template>
  <div ref="rootRef" class="relative">
    <button
      type="button"
      class="mp-button mp-button-outline min-h-9 px-3 text-xs"
      :aria-expanded="open"
      aria-haspopup="menu"
      @click="toggle"
    >
      Notifications
      <span v-if="notifications.unread > 0" class="mp-chip bg-danger-soft text-danger">
        {{ badgeText }}
      </span>
    </button>

    <div
      v-if="open"
      class="absolute right-0 z-50 mt-2 w-[min(360px,calc(100vw-2rem))] overflow-hidden rounded-md border border-hairline-strong bg-elevated shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
      role="menu"
    >
      <div class="flex items-center justify-between gap-3 border-b border-hairline px-4 py-3">
        <div class="font-bold text-ink">Notifications</div>
        <button
          type="button"
          class="text-xs font-bold text-accent"
          :disabled="notifications.unread === 0"
          @click="notifications.markAllRead"
        >
          Mark all read
        </button>
      </div>
      <div v-if="notifications.loading" class="px-4 py-5 text-sm font-bold text-ink-soft">
        Loading notifications
      </div>
      <div v-else-if="notifications.error" class="px-4 py-5 text-sm font-bold text-danger">
        Notifications could not be loaded.
      </div>
      <div v-else-if="notifications.items.length === 0" class="px-4 py-5 text-sm text-ink-soft">
        Nothing new.
      </div>
      <template v-else>
        <button
          v-for="item in notifications.items"
          :key="item.id"
          type="button"
          class="block w-full border-b border-hairline px-4 py-3 text-left transition last:border-b-0 hover:bg-sunk"
          role="menuitem"
          @click="openItem(item)"
        >
          <span class="flex items-start justify-between gap-3">
            <span class="min-w-0">
              <span class="block truncate text-sm font-bold text-ink">{{ title(item) }}</span>
              <span class="mt-1 block font-mono text-[11px] text-ink-muted">
                {{ item.event_code }} · {{ formatDate(item.created_at) }}
              </span>
            </span>
            <span v-if="item.read_at === null" class="mt-1 size-2 rounded-full bg-accent"></span>
          </span>
        </button>
      </template>
    </div>
  </div>
</template>
