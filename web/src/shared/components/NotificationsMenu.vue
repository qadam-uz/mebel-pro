<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import {
  notificationBody,
  notificationDestination,
  notificationIconName,
  notificationTitle,
} from '@/shared/app/notificationPresenter'
import Icon from '@/shared/components/AppIcon.vue'
import { useToast } from '@/shared/composables/useToast'
import { useRolePath } from '@/shared/app/paths'
import { useRoleConfig } from '@/shared/app/roleConfig'
import { formatClientDateTime, formatDate } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useNotificationsStore, type NotificationItem } from '@/shared/stores/notifications'

const auth = useAuthStore()
const notifications = useNotificationsStore()
const router = useRouter()
const roleConfig = useRoleConfig()
const rolePath = useRolePath()
const toast = useToast()
const { t } = useI18n()
const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLButtonElement | null>(null)

const badgeText = computed(() => (notifications.unread > 9 ? '9+' : String(notifications.unread)))
const isClient = computed(() => roleConfig.role === 'client')
const isWorkshop = computed(() => roleConfig.role === 'workshop')
const isAdmin = computed(() => roleConfig.role === 'admin')
// Accessible name for the dropdown + its header (notifications.md: a proper menu
// with a descriptive name), shared by the panel's `aria-label` and its heading.
const menuLabel = computed(() => t('shell.notifications.title'))
const bellLabel = computed(() =>
  t('shell.notifications.bellAria', { n: notifications.unread }, notifications.unread),
)
const menuPositionClass = computed(() =>
  isAdmin.value
    ? 'fixed inset-x-4 top-16 mt-0 w-auto sm:absolute sm:inset-x-auto sm:right-0 sm:top-auto sm:mt-2 sm:w-[min(360px,calc(100vw-2rem))]'
    : 'absolute right-0 mt-2 w-[min(360px,calc(100vw-2rem))]',
)

function title(item: NotificationItem) {
  return notificationTitle(item, roleConfig.role)
}

function body(item: NotificationItem) {
  return notificationBody(item)
}

function iconName(item: NotificationItem) {
  return notificationIconName(item)
}

// The bell hangs in all three shells, so the row's timestamp follows the role:
// one client date format everywhere the client looks (decision 22), and the
// compact `dd.mm.yyyy` the workshop and admin screens use elsewhere.
function when(item: NotificationItem) {
  return isClient.value ? formatClientDateTime(item.created_at) : formatDate(item.created_at)
}

function destination(item: NotificationItem) {
  return notificationDestination(item, roleConfig.role)
}

// Reuse the loaded list for ~30s instead of refetching on every bell open (CB-52);
// the unread badge is kept live by the ~45s poll regardless. The rows come from
// the store's `recent` slice, never `items` — the notifications page owns that
// one, and the bell's shorter page must not overwrite the feed behind it (CB-131).
let listLoadedAt = 0
async function toggle() {
  open.value = !open.value
  if (open.value) {
    if (notifications.recent.length === 0 || Date.now() - listLoadedAt > 30000) {
      await notifications.loadRecent()
      listLoadedAt = Date.now()
    }
    await nextTick()
    menuItems()[0]?.focus()
  }
}

function closeMenu() {
  open.value = false
  triggerRef.value?.focus()
}

// The dropdown advertises role=menu, so wire the menu keyboard contract (CB-32):
// Escape closes + restores focus to the bell; Up/Down/Home/End move between items.
function menuItems(): HTMLElement[] {
  return Array.from(
    menuRef.value?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])') ?? [],
  )
}

function onMenuKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeMenu()
    return
  }
  const items = menuItems()
  if (items.length === 0) return
  const current = items.indexOf(document.activeElement as HTMLElement)
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    items[current < 0 ? 0 : (current + 1) % items.length]?.focus()
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    items[current < 0 ? items.length - 1 : (current - 1 + items.length) % items.length]?.focus()
  } else if (event.key === 'Home') {
    event.preventDefault()
    items[0]?.focus()
  } else if (event.key === 'End') {
    event.preventDefault()
    items[items.length - 1]?.focus()
  }
}

async function openItem(item: NotificationItem) {
  const to = destination(item)
  if (!to) {
    // No viewable target (entity gone / not visible): don't silently mark read —
    // tell the user and keep the row unread (CB-125).
    toast.warn(t('shell.notifications.notOpenable'))
    return
  }
  // markRead is best-effort: opening the entity is the user's intent, so navigate
  // regardless. A failure leaves the row unread (the badge stays) — that is its own
  // feedback, with no disjointed toast-then-navigate.
  if (item.read_at === null) await notifications.markRead(item.id)
  open.value = false
  await router.push(rolePath(to))
}

async function openAll() {
  open.value = false
  if (roleConfig.role === 'client') await router.push(rolePath('/c/notifications'))
  if (roleConfig.role === 'workshop') await router.push(rolePath('/workshop/notifications'))
  if (roleConfig.role === 'admin') await router.push(rolePath('/admin/notifications'))
}

async function markAllRead() {
  await notifications.markAllRead()
  if (notifications.actionError) {
    toast.danger(t('shell.notifications.markAllFailed'))
    return
  }
  await notifications.loadRecent()
  listLoadedAt = Date.now()
  toast.success(t('shell.notifications.markAllDone'))
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
    if (primed && unread > seenUnread) toast.success(t('shell.notifications.newArrived'))
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
      ref="triggerRef"
      type="button"
      :class="isClient ? 'client-icon-button' : isWorkshop ? 'workshop-bell' : 'admin-icon-button'"
      :aria-expanded="open"
      aria-haspopup="menu"
      :aria-label="bellLabel"
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
      <template v-else>{{ menuLabel }}</template>
      <!-- The workshop bell shows an 8×8 signal dot, not a digit: the exact
           number is not actionable at a glance, and the count is not lost —
           `bellLabel` carries it in the trigger's accessible name, so the state
           is never conveyed by colour alone. -->
      <span
        v-if="isWorkshop && notifications.unread > 0"
        class="workshop-bell-dot"
        aria-hidden="true"
      ></span>
      <span
        v-else-if="notifications.unread > 0"
        :class="isClient || isAdmin ? 'client-badge' : 'mp-chip bg-danger-soft text-danger'"
      >
        {{ badgeText }}
      </span>
    </button>

    <div
      v-if="open"
      ref="menuRef"
      class="z-50 overflow-hidden rounded-xl border border-hairline bg-elevated shadow-[0_1px_2px_color-mix(in_srgb,var(--color-ink)_6%,transparent),0_14px_32px_-20px_color-mix(in_srgb,var(--color-ink)_60%,transparent)]"
      :class="menuPositionClass"
      role="menu"
      :aria-label="menuLabel"
      @keydown="onMenuKeydown"
    >
      <div class="flex items-center justify-between gap-3 border-b border-hairline px-4 py-3">
        <div class="font-semibold text-ink">{{ menuLabel }}</div>
        <button
          type="button"
          role="menuitem"
          class="text-[12.5px] font-semibold text-accent-deep"
          :disabled="notifications.unread === 0"
          @click="markAllRead"
        >
          {{ $t('shell.notifications.markAll') }}
        </button>
      </div>
      <div v-if="notifications.recentLoading" class="px-4 py-5 text-sm text-ink-soft">
        {{ $t('shell.notifications.loading') }}
      </div>
      <div
        v-else-if="notifications.recentError"
        class="px-4 py-5 text-sm font-semibold text-danger"
      >
        {{ $t('shell.notifications.loadFailedMenu') }}
      </div>
      <div v-else-if="notifications.recent.length === 0" class="px-4 py-5 text-sm text-ink-soft">
        {{ $t('shell.notifications.emptyMenu') }}
      </div>
      <template v-else>
        <button
          v-for="item in notifications.recent"
          :key="item.id"
          type="button"
          class="block w-full border-b border-hairline px-4 py-3 text-left transition last:border-b-0 hover:bg-sunk"
          role="menuitem"
          @click="openItem(item)"
        >
          <span class="flex items-start gap-3">
            <span class="client-notif-icon mt-0.5 shrink-0 text-ink-soft" aria-hidden="true">
              <Icon :name="iconName(item)" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-semibold text-ink">{{ title(item) }}</span>
              <span v-if="body(item)" class="mt-0.5 block truncate text-[12.5px] text-ink-soft">
                {{ body(item) }}
              </span>
              <span class="mt-1 block text-[12.5px] text-ink-muted">
                {{ when(item) }}
              </span>
            </span>
            <span
              v-if="item.read_at === null"
              class="mt-1 size-2 shrink-0 rounded-full bg-signal"
            ></span>
          </span>
        </button>
      </template>
      <button
        v-if="isClient || isWorkshop || isAdmin"
        type="button"
        role="menuitem"
        class="block w-full border-t border-hairline px-4 py-3 text-center text-[12.5px] font-semibold text-accent-deep transition hover:bg-sunk"
        @click="openAll"
      >
        {{ $t('shell.notifications.viewAll') }}
      </button>
    </div>
  </div>
</template>
