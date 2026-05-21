<script setup lang="ts">
// Notification bell + dropdown shared by all three apps. Polls the unread
// count every ~45s and refreshes it on `notifs:change`. Loads the recent list
// lazily when the dropdown opens. `variant` switches between the workshop/admin
// .nd-* dropdown and the client .cl-bell-* dropdown so each app matches its
// prototype shell.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { Notification } from '@/shared/types'
import { fetchNotifications, fetchUnreadCount, markAllRead } from '@/shared/api/notifications'
import { ApiError } from '@/shared/api/client'
import { fmtDateTime } from '@/shared/format'
import { t } from '@/shared/i18n'

const props = withDefaults(
  defineProps<{
    variant?: 'app' | 'client'
    // Where "see all" navigates.
    allRoute?: string
    pollMs?: number
  }>(),
  { variant: 'app', pollMs: 45000 },
)

const router = useRouter()
const open = ref(false)
const unread = ref(0)
const items = ref<Notification[]>([])
const loading = ref(false)
const wrap = ref<HTMLElement | null>(null)
let timer: ReturnType<typeof setInterval> | undefined

const badge = computed(() => (unread.value > 9 ? '9+' : String(unread.value)))

async function refreshCount() {
  try {
    unread.value = (await fetchUnreadCount()).unread
  } catch (e) {
    if (!(e instanceof ApiError)) throw e
    // Silent on transient errors — the bell is non-critical chrome.
  }
}

async function loadList() {
  loading.value = true
  try {
    items.value = await fetchNotifications()
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function toggle() {
  open.value = !open.value
  if (open.value && items.value.length === 0) await loadList()
}

async function onMarkAll() {
  try {
    const res = await markAllRead()
    unread.value = res.unread
    items.value = items.value.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() }))
  } catch {
    /* ignore */
  }
}

function titleOf(n: Notification): string {
  const payloadTitle = n.payload?.title
  return typeof payloadTitle === 'string' ? payloadTitle : n.event_code
}

function bodyOf(n: Notification): string {
  const b = n.payload?.body
  return typeof b === 'string' ? b : ''
}

function onItemClick(n: Notification) {
  open.value = false
  const link = n.payload?.link
  if (typeof link === 'string' && link.startsWith('/')) router.push(link)
}

function onDocClick(e: MouseEvent) {
  if (wrap.value && !wrap.value.contains(e.target as Node)) open.value = false
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  void refreshCount()
  timer = setInterval(refreshCount, props.pollMs)
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('notifs:change', refreshCount as EventListener)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('notifs:change', refreshCount as EventListener)
})

function goAll() {
  open.value = false
  if (props.allRoute) router.push(props.allRoute)
}
</script>

<template>
  <!-- Workshop / admin style -->
  <div v-if="variant === 'app'" ref="wrap" class="menu-wrap">
    <button
      class="ib"
      type="button"
      :aria-label="t('notif.title')"
      aria-haspopup="true"
      :aria-expanded="open ? 'true' : 'false'"
      @click="toggle"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
      >
        <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
      </svg>
      <span class="badge" :data-count="unread">{{ badge }}</span>
    </button>
    <div class="menu nd-menu" :class="{ on: open }" role="menu" :aria-label="t('notif.title')">
      <div class="nd-head">
        <b>{{ t('notif.title') }}</b>
        <button class="nd-mark" type="button" @click.stop="onMarkAll">
          {{ t('notif.markAllRead') }}
        </button>
      </div>
      <div class="nd-body">
        <div v-if="loading" style="padding: 16px">
          <div class="sk-line w-80" />
          <div class="sk-line w-60" />
        </div>
        <a
          v-for="n in items"
          v-else
          :key="n.id"
          class="nd-item"
          :class="{ unread: !n.read_at }"
          href="#"
          role="menuitem"
          @click.prevent="onItemClick(n)"
        >
          <span class="nd-ic job">N</span>
          <span class="nd-tx"
            ><b>{{ titleOf(n) }}</b
            ><small>{{ bodyOf(n) }}</small></span
          >
          <span class="nd-t">{{ fmtDateTime(n.created_at) }}</span>
        </a>
        <div v-if="!loading && items.length === 0" class="nd-empty">{{ t('notif.empty') }}</div>
      </div>
      <a v-if="allRoute" class="nd-all" href="#" @click.prevent="goAll">{{ t('notif.seeAll') }}</a>
    </div>
  </div>

  <!-- Client style -->
  <div v-else ref="wrap" class="cl-bell-wrap">
    <button
      class="ib"
      type="button"
      :aria-label="t('notif.title')"
      aria-haspopup="true"
      :aria-expanded="open ? 'true' : 'false'"
      @click="toggle"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
      </svg>
      <span class="badge" :data-count="unread">{{ badge }}</span>
    </button>
    <div class="cl-bell-dd" :class="{ on: open }" role="menu" :aria-label="t('notif.title')">
      <div class="cl-bell-hd">
        <span>{{ t('notif.title') }}</span>
        <button type="button" class="cl-bell-mark" @click.stop="onMarkAll">
          {{ t('notif.markAllRead') }}
        </button>
      </div>
      <div class="cl-bell-list">
        <button
          v-for="n in items"
          :key="n.id"
          type="button"
          class="cl-bell-it"
          :class="{ unread: !n.read_at }"
          @click="onItemClick(n)"
        >
          <span class="cl-bell-dot" aria-hidden="true" />
          <span class="cl-bell-tx">
            <span class="cl-bell-tt">{{ titleOf(n) }}</span>
            <span class="cl-bell-bd">{{ bodyOf(n) }}</span>
            <span class="cl-bell-tm">{{ fmtDateTime(n.created_at) }}</span>
          </span>
        </button>
        <div v-if="!loading && items.length === 0" class="cl-bell-empty">
          {{ t('notif.empty') }}
        </div>
      </div>
      <div v-if="allRoute" class="cl-bell-foot">
        <a href="#" @click.prevent="goAll">{{ t('notif.seeAll') }}</a>
      </div>
    </div>
  </div>
</template>
