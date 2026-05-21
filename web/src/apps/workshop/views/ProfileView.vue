<script setup lang="ts">
// Self profile — read-only identity fields, change password (strength meter),
// and active sessions (revoke / logout-all). Mirrors prototype profile.html.
import { computed, onMounted, ref } from 'vue'
import { ApiError, authApi } from '@/shared/api'
import { ErrorState } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime, fmtPhone } from '@/shared/format'
import { pwStrength } from '@/shared/password'
import { useToast } from '@/shared/composables/useToast'
import type { SessionInfo } from '@/shared/types'
import { useWorkshopAuth } from '../store'

const toast = useToast()
const auth = useWorkshopAuth()

const sessions = ref<SessionInfo[]>([])
const loading = ref(true)
const error = ref<ApiError | null>(null)

const curPw = ref('')
const newPw = ref('')
const confirmPw = ref('')
const changing = ref(false)

const strength = computed(() => pwStrength(newPw.value))
const canChange = computed(
  () => curPw.value && strength.value.ok && newPw.value === confirmPw.value,
)

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

async function changePassword() {
  if (!canChange.value) return
  changing.value = true
  try {
    await auth.changePassword(curPw.value, newPw.value)
    toast.ok(t('auth.passwordSet'))
    curPw.value = ''
    newPw.value = ''
    confirmPw.value = ''
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    changing.value = false
  }
}

async function revoke(id: string) {
  try {
    await authApi.revokeSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    toast.ok(t('workshop.sessionRevoked'))
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

async function logoutAll() {
  try {
    await authApi.logoutAll()
    sessions.value = sessions.value.filter((s) => s.current)
    toast.ok(t('workshop.loggedOutAll'))
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
        <h1>{{ t('workshop.profileTitle') }}</h1>
      </div>
    </div>

    <div style="display: grid; gap: 18px; max-width: 720px">
      <section class="card">
        <div class="card-h">
          <h2>{{ t('workshop.myProfile') }}</h2>
        </div>
        <div class="card-b">
          <div class="row-item">
            <div class="nm">{{ t('workshop.fullName') }}</div>
            <div class="meta" style="color: var(--ink-12)">{{ auth.me?.full_name ?? '—' }}</div>
          </div>
          <div class="row-item" style="border-bottom: 0">
            <div class="nm">{{ t('workshop.colPhone') }}</div>
            <div class="meta">{{ fmtPhone(auth.me?.phone) || '—' }}</div>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-h">
          <h2>{{ t('workshop.changePassword') }}</h2>
        </div>
        <div class="card-b">
          <div class="field">
            <label>{{ t('auth.currentPassword') }}</label>
            <input v-model="curPw" type="password" autocomplete="current-password" />
          </div>
          <div class="field">
            <label>{{ t('auth.newPassword') }}</label>
            <input v-model="newPw" type="password" autocomplete="new-password" />
            <div class="pw-meter" :data-score="strength.score"><i /><i /><i /><i /></div>
            <div class="pw-reqs hint">
              <span :class="{ ok: strength.len }">{{ t('auth.pwReqLen') }}</span> ·
              <span :class="{ ok: strength.hasU }">{{ t('auth.pwReqUpper') }}</span> ·
              <span :class="{ ok: strength.hasL }">{{ t('auth.pwReqLower') }}</span> ·
              <span :class="{ ok: strength.hasD }">{{ t('auth.pwReqDigit') }}</span>
            </div>
          </div>
          <div class="field">
            <label>{{ t('auth.confirmPassword') }}</label>
            <input v-model="confirmPw" type="password" autocomplete="new-password" />
            <span v-if="confirmPw && confirmPw !== newPw" class="err">{{
              t('auth.passwordsDontMatch')
            }}</span>
          </div>
          <button
            class="btn btn-acc btn-sm"
            type="button"
            :disabled="changing || !canChange"
            @click="changePassword"
          >
            {{ t('workshop.changePassword') }}
          </button>
        </div>
      </section>

      <section class="card">
        <div class="card-h">
          <h2>{{ t('workshop.sessionsTitle') }}</h2>
          <button
            v-if="sessions.length > 1"
            class="btn btn-danger btn-sm"
            type="button"
            @click="logoutAll"
          >
            {{ t('workshop.logoutAll') }}
          </button>
        </div>
        <div class="card-b">
          <div v-if="loading"><div class="sk sk-line" style="width: 60%" /></div>
          <ErrorState v-else-if="error" :error="error" :retry="load" />
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
                    ><span class="pd" />{{ t('workshop.currentSession') }}</span
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
                  {{ t('workshop.revoke') }}
                </button>
                <span v-else style="color: var(--ink-6)">—</span>
              </div>
            </div>
          </template>
        </div>
      </section>
    </div>
  </div>
</template>
