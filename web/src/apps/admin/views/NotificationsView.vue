<script setup lang="ts">
// Operator notifications — error spikes and failed jobs. Read/unread filter +
// mark-all-read; rows deep-link to the errors or jobs console.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, notificationsApi } from '@/shared/api'
import { ErrorState } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import type { Notification } from '@/shared/types'

const router = useRouter()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const items = ref<Notification[]>([])
const filter = ref<'all' | 'unread' | 'read'>('all')

const FILTERS = [
  { id: 'all', key: 'workshop.notifFilterAll' },
  { id: 'unread', key: 'workshop.notifFilterUnread' },
  { id: 'read', key: 'workshop.notifFilterRead' },
] as const

const filtered = computed(() =>
  items.value.filter(
    (n) =>
      filter.value === 'all' ||
      (filter.value === 'unread' && !n.read_at) ||
      (filter.value === 'read' && !!n.read_at),
  ),
)

function title(n: Notification): string {
  const payload = n.payload ?? {}
  return (payload.title as string) || (payload.code as string) || n.event_code
}
function body(n: Notification): string {
  const payload = n.payload ?? {}
  return (payload.body as string) || (payload.message as string) || ''
}
function kind(n: Notification): 'error' | 'job' {
  return n.event_code.includes('job') ? 'job' : 'error'
}

async function load() {
  loading.value = true
  error.value = null
  try {
    items.value = await notificationsApi.fetchNotifications()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

async function open(n: Notification) {
  if (!n.read_at) {
    try {
      await notificationsApi.markRead(n.id)
      n.read_at = new Date().toISOString()
    } catch {
      /* non-fatal */
    }
  }
  if (kind(n) === 'job') router.push('/admin/platform/jobs')
  else router.push('/admin/platform/errors')
}

async function markAll() {
  try {
    await notificationsApi.markAllRead()
    const now = new Date().toISOString()
    items.value = items.value.map((n) => ({ ...n, read_at: n.read_at ?? now }))
    toast.ok(t('workshop.allMarkedRead'))
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('workshop.notificationsTitle') }}</h1>
      </div>
      <div class="tools">
        <button class="btn btn-outline btn-sm" type="button" @click="markAll">
          {{ t('workshop.markAllRead') }}
        </button>
      </div>
    </div>

    <div class="filters" style="margin-bottom: 14px">
      <div class="chips">
        <button
          v-for="f in FILTERS"
          :key="f.id"
          class="chip"
          :class="{ on: filter === f.id }"
          type="button"
          @click="filter = f.id"
        >
          {{ t(f.key) }}
        </button>
      </div>
    </div>

    <div style="max-width: 760px">
      <div v-if="loading">
        <div v-for="n in 5" :key="n" class="card" style="margin-bottom: 8px; padding: 14px 18px">
          <div class="sk sk-line" style="width: 60%" />
        </div>
      </div>

      <ErrorState v-else-if="error" :error="error" :retry="load" />

      <div v-else-if="filtered.length === 0" class="st-empty">
        <div class="ic">✓</div>
        <h3>{{ t('workshop.notifEmptyTitle') }}</h3>
        <p>{{ t('workshop.notifEmptyAll') }}</p>
      </div>

      <button
        v-for="n in filtered"
        v-else
        :key="n.id"
        class="note-card"
        :class="{ unread: !n.read_at }"
        type="button"
        @click="open(n)"
      >
        <div class="ic" :class="kind(n)">{{ kind(n)[0].toUpperCase() }}</div>
        <div>
          <div class="nm">{{ title(n) }}</div>
          <div v-if="body(n)" class="body">{{ body(n) }}</div>
        </div>
        <div class="tm">{{ fmtDateTime(n.created_at) }}</div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.note-card {
  display: grid;
  grid-template-columns: 38px 1fr auto;
  gap: 14px;
  padding: 14px 18px;
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 9px;
  margin-bottom: 8px;
  align-items: center;
  cursor: pointer;
  text-align: left;
  width: 100%;
  box-sizing: border-box;
}
.note-card:hover {
  border-color: var(--ink-12);
}
.note-card.unread {
  background: var(--accent-soft);
  border-color: var(--accent-tint);
}
.note-card .ic {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font: 700 14px var(--f-display);
  color: #fff;
}
.note-card .ic.error {
  background: var(--danger);
}
.note-card .ic.job {
  background: var(--warn);
}
.note-card .nm {
  font: 600 14px var(--f-ui);
  color: var(--ink-12);
}
.note-card .body {
  font-size: 12.5px;
  color: var(--ink-8);
  margin-top: 2px;
}
.note-card .tm {
  font-family: var(--f-mono);
  font-size: 11.5px;
  color: var(--ink-6);
  white-space: nowrap;
}
</style>
