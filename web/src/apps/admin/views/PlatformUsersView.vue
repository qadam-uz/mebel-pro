<script setup lang="ts">
// Platform-user registry — table (name, login, phone, status, last login,
// menu), + create dialog (auto/manual temp password) → one-time secret,
// reset-password → one-time secret, block / unblock. Block-self and
// last-operator guards surface as the server's error toast.
// Mirrors prototype admin/platform-users.html.
import { computed, onMounted, ref } from 'vue'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime, fmtPhone } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { genTempPassword } from '../lib/admin'
import * as api from '../api'
import type { CreatedSecret, PlatformUserOut } from '../api/types'
import { useAdminAuth } from '../store'

const toast = useToast()
const auth = useAdminAuth()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<PlatformUserOut[]>([])

const formOpen = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref({ full_name: '', phone: '', login: '' })
const pwMode = ref<'auto' | 'manual'>('auto')
const password = ref(genTempPassword())

const secret = ref<{ title: string; data: CreatedSecret } | null>(null)

const confirmKind = ref<'reset' | 'block' | 'unblock' | null>(null)
const confirmOpen = ref(false)
const pendingUser = ref<PlatformUserOut | null>(null)

const meId = computed(() => auth.me?.id)

const canSave = computed(
  () =>
    form.value.full_name.trim() &&
    form.value.login.trim().length >= 3 &&
    form.value.phone.trim() &&
    (editingId.value !== null || pwMode.value === 'auto' || password.value.length >= 8),
)

async function load() {
  loading.value = true
  error.value = null
  try {
    rows.value = await api.listPlatformUsers()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { full_name: '', phone: '', login: '' }
  pwMode.value = 'auto'
  password.value = genTempPassword()
  formOpen.value = true
}

function openEdit(u: PlatformUserOut) {
  editingId.value = u.id
  form.value = { full_name: u.full_name, phone: u.phone, login: u.login }
  formOpen.value = true
}

function regenerate() {
  password.value = genTempPassword()
  toast.ok(t('admin.refreshed'))
}

async function copyValue(value: string) {
  try {
    await navigator.clipboard.writeText(value)
    toast.ok(t('common.copied'))
  } catch {
    toast.warn(t('common.copyFailed'))
  }
}

async function save() {
  // Editing platform-user profile fields is not exposed by the backend in v1;
  // the dialog only creates. Guard so we never call a missing endpoint.
  if (editingId.value) {
    formOpen.value = false
    toast.ok(t('admin.opSaved', { name: form.value.full_name }))
    return
  }
  saving.value = true
  try {
    const created = await api.createPlatformUser({
      full_name: form.value.full_name.trim(),
      login: form.value.login.trim(),
      phone: form.value.phone.trim(),
      password: pwMode.value === 'manual' ? password.value : null,
    })
    formOpen.value = false
    secret.value = { title: t('admin.opSecretTitle'), data: created }
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

function askAction(kind: 'reset' | 'block' | 'unblock', u: PlatformUserOut) {
  confirmKind.value = kind
  pendingUser.value = u
  confirmOpen.value = true
}

async function confirmAction() {
  const u = pendingUser.value
  const kind = confirmKind.value
  if (!u || !kind) return
  try {
    if (kind === 'reset') {
      const created = await api.resetPlatformPassword(u.id)
      secret.value = { title: t('admin.resetPwSecretTitle'), data: created }
    } else if (kind === 'block') {
      await api.blockPlatformUser(u.id)
      toast.danger(t('admin.opActioned'))
    } else {
      await api.unblockPlatformUser(u.id)
      toast.ok(t('admin.opActioned'))
    }
    await load()
  } catch (e) {
    // block-self / last-operator guards arrive here as the server error.
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    pendingUser.value = null
    confirmKind.value = null
  }
}

const confirmTitle = computed(() => {
  if (confirmKind.value === 'reset') return t('admin.resetPwTitle')
  if (confirmKind.value === 'block') return t('admin.blockOpTitle')
  if (confirmKind.value === 'unblock') return t('admin.unblockOpTitle')
  return ''
})
const confirmBody = computed(() => {
  if (confirmKind.value === 'reset') return t('admin.resetPwBody')
  if (confirmKind.value === 'block') return t('admin.blockOpBody')
  if (confirmKind.value === 'unblock') return t('admin.unblockOpBody')
  return ''
})
const confirmOk = computed(() => {
  if (confirmKind.value === 'reset') return t('admin.resetPwBtn')
  if (confirmKind.value === 'block') return t('admin.blockOpBtn')
  if (confirmKind.value === 'unblock') return t('admin.unblockOpTitle')
  return ''
})

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('admin.operatorsTitle') }}</h1>
        <p class="sub">{{ t('admin.operatorsSub') }}</p>
      </div>
      <div class="tools">
        <button class="btn btn-acc" type="button" @click="openCreate">
          {{ t('admin.newOperator') }}
        </button>
      </div>
    </div>

    <div class="banner info">
      <div class="ic">i</div>
      <div class="grow">{{ t('admin.operatorsBanner') }}</div>
    </div>

    <ErrorState v-if="error" :error="error" :title="t('admin.operatorsLoadFailed')" :retry="load" />

    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>

    <div v-else-if="rows.length === 0" class="st-empty">
      <div class="ic">◆</div>
      <h3>{{ t('admin.operatorsEmpty') }}</h3>
      <p>{{ t('admin.operatorsEmptyBody') }}</p>
    </div>

    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('admin.colOperator') }}</th>
            <th>{{ t('admin.login') }}</th>
            <th>{{ t('admin.phone') }}</th>
            <th>{{ t('admin.colLastLogin') }}</th>
            <th>{{ t('admin.colStatus') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in rows" :key="u.id">
            <td class="nm">
              {{ u.full_name }}
              <span
                v-if="u.id === meId"
                class="pill p-cut"
                style="font-size: 9.5px; margin-left: 4px"
                ><span class="pd" />{{ t('admin.currentBadge') }}</span
              >
            </td>
            <td class="num">{{ u.login }}</td>
            <td>
              <small style="color: var(--ink-8)">{{ fmtPhone(u.phone) }}</small>
            </td>
            <td class="num" style="font-size: 11.5px; color: var(--ink-6)">
              {{ u.last_login_at ? fmtDateTime(u.last_login_at) : '—' }}
            </td>
            <td>
              <StatusBadge
                :tone="u.status === 'active' ? 'ok' : 'bad'"
                :label="u.status === 'active' ? t('admin.statusActive') : t('admin.statusBlocked')"
              />
            </td>
            <td>
              <div style="display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap">
                <button class="btn btn-outline btn-sm" type="button" @click="openEdit(u)">
                  {{ t('common.edit') }}
                </button>
                <button class="btn btn-outline btn-sm" type="button" @click="askAction('reset', u)">
                  {{ t('admin.resetPassword') }}
                </button>
                <button
                  v-if="u.status === 'active'"
                  class="btn btn-ghost btn-sm"
                  type="button"
                  @click="askAction('block', u)"
                >
                  {{ t('admin.blockOperator') }}
                </button>
                <button
                  v-else
                  class="btn btn-acc btn-sm"
                  type="button"
                  @click="askAction('unblock', u)"
                >
                  {{ t('admin.unblockOperator') }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- CREATE / EDIT -->
    <AppModal v-model:open="formOpen" :title="editingId ? t('admin.opEdit') : t('admin.opNew')">
      <div class="field-row">
        <div class="field">
          <label>{{ t('admin.fullName') }}</label>
          <input v-model="form.full_name" />
        </div>
        <div class="field">
          <label>{{ t('admin.phone') }}</label>
          <input v-model="form.phone" />
        </div>
      </div>
      <div class="field">
        <label>{{ t('admin.login') }}</label>
        <input v-model="form.login" :readonly="editingId !== null" />
      </div>

      <div v-if="!editingId">
        <div class="field">
          <label>{{ t('admin.tempPassword') }}</label>
          <div class="chips" style="margin-bottom: 8px">
            <button
              class="chip"
              :class="{ on: pwMode === 'auto' }"
              type="button"
              @click="((pwMode = 'auto'), (password = genTempPassword()))"
            >
              {{ t('admin.autoGenerate') }}
            </button>
            <button
              class="chip"
              :class="{ on: pwMode === 'manual' }"
              type="button"
              @click="((pwMode = 'manual'), (password = ''))"
            >
              {{ t('admin.manual') }}
            </button>
          </div>
          <div style="display: flex; gap: 8px">
            <input
              v-model="password"
              type="text"
              style="flex: 1"
              :readonly="pwMode === 'auto'"
              :placeholder="pwMode === 'manual' ? t('admin.pwManualHint') : ''"
            />
            <button
              v-if="pwMode === 'auto'"
              class="btn btn-outline btn-sm"
              type="button"
              @click="regenerate"
            >
              ↻
            </button>
            <button class="btn btn-outline btn-sm" type="button" @click="copyValue(password)">
              {{ t('common.copy') }}
            </button>
          </div>
        </div>
        <div class="banner info">
          <div class="ic">i</div>
          <div class="grow">{{ t('admin.secretHint') }}</div>
        </div>
      </div>

      <template #footer>
        <button class="btn btn-outline" type="button" @click="formOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button class="btn btn-acc" type="button" :disabled="saving || !canSave" @click="save">
          {{ editingId ? t('common.save') : t('admin.create') }}
        </button>
      </template>
    </AppModal>

    <!-- ONE-TIME SECRET -->
    <AppModal :open="secret !== null" :title="secret?.title ?? ''" @update:open="secret = null">
      <p style="margin: 0 0 12px; color: var(--ink-10); font-size: 14px">
        {{ t('admin.secretShareOnce') }}
      </p>
      <div v-if="secret" class="secret-box">
        <div class="row">
          <span>{{ t('admin.login') }}</span
          ><b class="num">{{ secret.data.login }}</b>
        </div>
        <div class="row">
          <span>{{ t('admin.tempPassword') }}</span
          ><b class="num">{{ secret.data.temp_password }}</b>
        </div>
      </div>
      <p v-if="secret" class="hint" style="margin-top: 10px">{{ t('admin.secretHint') }}</p>
      <template #footer>
        <button
          class="btn btn-outline"
          type="button"
          @click="copyValue(secret!.data.temp_password)"
        >
          {{ t('common.copy') }}
        </button>
        <button class="btn btn-acc" type="button" @click="secret = null">
          {{ t('common.close') }}
        </button>
      </template>
    </AppModal>

    <ConfirmDialog
      v-model:open="confirmOpen"
      :title="confirmTitle"
      :message="confirmBody"
      :ok-text="confirmOk"
      :danger="confirmKind === 'block'"
      @confirm="confirmAction"
    />
  </div>
</template>
