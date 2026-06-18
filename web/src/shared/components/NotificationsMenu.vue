<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { adminNotificationDestination, adminNotificationTitle } from '@/shared/app/adminUi'
import { useToast } from '@/shared/composables/useToast'
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
const toast = useToast()
const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const badgeText = computed(() => (notifications.unread > 9 ? '9+' : String(notifications.unread)))
const isClient = computed(() => roleConfig.role === 'client')
const isWorkshop = computed(() => roleConfig.role === 'workshop')
const isAdmin = computed(() => roleConfig.role === 'admin')

function title(item: NotificationItem) {
  if (isAdmin.value) return adminNotificationTitle(item)
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
  if (roleConfig.role === 'admin') return adminNotificationDestination(item)
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

async function openAll() {
  open.value = false
  if (roleConfig.role === 'client') await router.push(rolePath('/c/notifications'))
  if (roleConfig.role === 'workshop') await router.push(rolePath('/workshop/notifications'))
  if (roleConfig.role === 'admin') await router.push(rolePath('/admin/notifications'))
}

async function markAllRead() {
  await notifications.markAllRead()
  await notifications.loadList()
  toast.success("Hammasi o'qilgan deb belgilandi.")
}

function onDocumentPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (rootRef.value?.contains(target)) return
  open.value = false
}

// Notifications are the only v1 update channel, so poll the unread count
// (~45s) while the tab is visible and a session exists — otherwise a "ready"
// or cancelled order shows a stale badge until manual reload (CB-10).
const POLL_INTERVAL_MS = 45000
let pollTimer: number | undefined

function pollUnread() {
  if (document.visibilityState === 'visible' && auth.accessToken) {
    void notifications.loadUnreadCount()
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  pollTimer = window.setInterval(pollUnread, POLL_INTERVAL_MS)
})

// Surface a toast when polling discovers new notifications (CB-14) — the badge
// alone is easy to miss. We only start toasting once the session's initial count
// has loaded (`primed`), so the unread that already existed at sign-in doesn't
// fire a toast.
let seenUnread = 0
let primed = false
watch(
  () => notifications.unread,
  (unread) => {
    if (primed && unread > seenUnread) toast.success('Yangi bildirishnoma bor.')
    seenUnread = unread
  },
)

watch(
  () => auth.accessToken,
  async (accessToken) => {
    primed = false
    if (!accessToken) {
      seenUnread = 0
      return
    }
    await notifications.loadUnreadCount()
    seenUnread = notifications.unread
    primed = true
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
})
</script>

<template>
  <div ref="rootRef" class="relative">
    <button
      type="button"
      :class="isClient ? 'client-icon-button' : isWorkshop ? 'workshop-bell' : 'admin-icon-button'"
      :aria-expanded="open"
      aria-haspopup="menu"
      :aria-label="`Bildirishnomalar - ${notifications.unread} o'qilmagan`"
      @click="toggle"
    >
      <template v-if="isClient || isWorkshop || isAdmin">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
      </template>
      <template v-else>Bildirishnomalar</template>
      <span
        v-if="notifications.unread > 0"
        :class="
          isClient || isWorkshop || isAdmin ? 'client-badge' : 'mp-chip bg-danger-soft text-danger'
        "
      >
        {{ badgeText }}
      </span>
    </button>

    <div
      v-if="open"
      class="absolute right-0 z-50 mt-2 w-[min(360px,calc(100vw-2rem))] overflow-hidden rounded-[10px] border border-hairline-strong bg-elevated shadow-[0_18px_44px_-16px_rgb(15_27_45_/_35%)]"
      role="menu"
    >
      <div class="flex items-center justify-between gap-3 border-b border-hairline px-4 py-3">
        <div class="font-bold text-ink">
          {{ isClient || isWorkshop || isAdmin ? 'Bildirishnomalar' : 'Notifications' }}
        </div>
        <button
          type="button"
          class="text-xs font-bold text-accent"
          :disabled="notifications.unread === 0"
          @click="markAllRead"
        >
          {{ isClient || isWorkshop ? "Hammasini o'qilgan deb belgilash" : 'Mark all read' }}
        </button>
      </div>
      <div v-if="notifications.loading" class="px-4 py-5 text-sm font-bold text-ink-soft">
        {{
          isClient || isWorkshop || isAdmin
            ? 'Bildirishnomalar yuklanmoqda'
            : 'Loading notifications'
        }}
      </div>
      <div v-else-if="notifications.error" class="px-4 py-5 text-sm font-bold text-danger">
        {{
          isClient || isWorkshop || isAdmin
            ? "Bildirishnomalarni yuklab bo'lmadi."
            : 'Notifications could not be loaded.'
        }}
      </div>
      <div v-else-if="notifications.items.length === 0" class="px-4 py-5 text-sm text-ink-soft">
        {{ isClient || isWorkshop || isAdmin ? "Bildirishnoma yo'q." : 'Nothing new.' }}
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
      <button
        v-if="isClient || isWorkshop || isAdmin"
        type="button"
        class="block w-full border-t border-hairline px-4 py-3 text-center text-xs font-bold text-accent transition hover:bg-sunk"
        @click="openAll"
      >
        Hammasini ko'rish
      </button>
    </div>
  </div>
</template>
