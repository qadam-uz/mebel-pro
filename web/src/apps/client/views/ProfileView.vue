<script setup lang="ts">
// Profile — Telegram-synced fields (read-only) + active sessions with
// current marker + revoke / logout-all. Mirrors prototype client/profile.html.
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, authApi } from '@/shared/api'
import { ErrorState } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime, fmtPhone } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import type { SessionInfo } from '@/shared/types'
import { useClientAuth } from '../store'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const router = useRouter()
const toast = useToast()
const auth = useClientAuth()

const sessions = ref<SessionInfo[]>([])
const loading = ref(true)
const error = ref<ApiError | null>(null)

const logoutAllOpen = ref(false)
const signOutOpen = ref(false)

async function load() {
  loading.value = true
  error.value = null
  try {
    sessions.value = await authApi.listSessions()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function deviceLabel(s: SessionInfo): string {
  const info = s.device_info ?? {}
  const platform = (info.platform as string) || (info.os as string) || ''
  const browser = (info.browser as string) || (info.client as string) || ''
  const parts = [platform, browser].filter(Boolean)
  return parts.length ? parts.join(' · ') : (info.user_agent as string)?.slice(0, 40) || '—'
}

async function revoke(id: string) {
  try {
    await authApi.revokeSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    toast.ok(t('client.sessionClosed'))
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

async function logoutAll() {
  try {
    await authApi.logoutAll()
    sessions.value = sessions.value.filter((s) => s.current)
    toast.ok(t('client.sessionsClosed'))
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

async function signOut() {
  await auth.logout()
  toast.ok(t('client.signedOut'))
  router.push('/auth/telegram')
}

onMounted(load)
</script>

<template>
  <div>
    <button class="back" type="button" @click="router.back()">← {{ t('common.back') }}</button>

    <div class="page-head">
      <div>
        <h1>{{ t('client.profileTitle') }}</h1>
        <p class="sub">{{ t('client.profileSub') }}</p>
      </div>
      <div class="tools">
        <button class="btn btn-outline" type="button" @click="signOutOpen = true">
          {{ t('client.signOut') }}
        </button>
      </div>
    </div>

    <div style="display: grid; gap: 18px; max-width: 720px">
      <section class="card">
        <div class="card-h">
          <h2>{{ t('client.syncedFromTelegram') }}</h2>
        </div>
        <div class="card-b">
          <div class="row-item">
            <div>
              <div class="nm">{{ t('client.fieldName') }}</div>
              <small style="color: var(--ink-6)">{{ t('client.fieldNameSub') }}</small>
            </div>
            <div class="meta" style="font-weight: 500; color: var(--ink-12)">
              {{ auth.me?.first_name ?? auth.me?.full_name ?? '—' }}
            </div>
          </div>
          <div class="row-item" style="border-bottom: 0">
            <div>
              <div class="nm">{{ t('client.fieldPhone') }}</div>
              <small style="color: var(--ink-6)">{{ t('client.fieldPhoneSub') }}</small>
            </div>
            <div class="meta">{{ fmtPhone(auth.me?.phone) || '—' }}</div>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-h">
          <h2>{{ t('client.activeSessions') }}</h2>
          <button
            v-if="sessions.length > 1"
            class="btn btn-danger btn-sm"
            type="button"
            @click="logoutAllOpen = true"
          >
            {{ t('client.logoutAll') }}
          </button>
        </div>
        <div class="card-b">
          <div v-if="loading">
            <div class="sk sk-line" style="width: 60%" />
            <div class="sk sk-line" style="width: 50%; margin-top: 12px" />
          </div>
          <ErrorState v-else-if="error" :error="error" :retry="load" />
          <div
            v-else-if="sessions.length === 0"
            class="st-empty"
            style="border: 0; padding: 24px 0"
          >
            <div class="ic">∅</div>
            <h3>{{ t('client.noSessions') }}</h3>
          </div>
          <template v-else>
            <div
              v-for="(s, i) in sessions"
              :key="s.id"
              class="row-item"
              :style="i === sessions.length - 1 ? 'border-bottom:0' : ''"
            >
              <div>
                <div class="nm">
                  {{ deviceLabel(s) }}
                  <span v-if="s.current" class="pill p-ok" style="margin-left: 6px"
                    ><span class="pd" />{{ t('client.sessionCurrent') }}</span
                  >
                </div>
                <small style="color: var(--ink-6)">{{ fmtDateTime(s.last_used_at) }}</small>
              </div>
              <div class="meta">
                <button
                  v-if="!s.current"
                  class="btn btn-outline btn-sm"
                  type="button"
                  @click="revoke(s.id)"
                >
                  {{ t('client.sessionRevoke') }}
                </button>
                <span v-else style="color: var(--ink-6)">—</span>
              </div>
            </div>
          </template>
        </div>
      </section>
    </div>

    <ConfirmDialog
      v-model:open="logoutAllOpen"
      :title="t('client.logoutAllTitle')"
      :message="t('client.logoutAllMsg')"
      :ok-text="t('client.logoutAll')"
      danger
      @confirm="logoutAll"
    />
    <ConfirmDialog
      v-model:open="signOutOpen"
      :title="t('client.signOutTitle')"
      :message="t('client.signOutMsg')"
      :ok-text="t('client.signOut')"
      danger
      @confirm="signOut"
    />
  </div>
</template>
