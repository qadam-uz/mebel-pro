<script setup lang="ts">
// Settings → Users (owner-only) — users table + create-user dialog (profile +
// home branch + temp password auto/manual + initial grants matrix) →
// one-time-secret confirmation. Mirrors prototype workshop/users.html.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, FormField, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDate, fmtPhone } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { useBranchesStore } from '../../stores/branches'
import * as api from '../../api'
import type { CreatedSecret, WorkshopUser } from '../../api/types'
import type { Permission } from '@/shared/types'
import { PERMISSIONS, grantKey, grantsFromSet } from '../../lib/orders'

const router = useRouter()
const toast = useToast()
const branchesStore = useBranchesStore()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const users = ref<WorkshopUser[]>([])

const createOpen = ref(false)
const saving = ref(false)
const form = ref({ full_name: '', login: '', phone: '', home_branch_id: '' })
const pwMode = ref<'auto' | 'manual'>('auto')
const manualPw = ref('')
const grantSet = ref<Set<string>>(new Set())

const secret = ref<CreatedSecret | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    await branchesStore.load()
    users.value = await api.listUsers()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { full_name: '', login: '', phone: '', home_branch_id: '' }
  pwMode.value = 'auto'
  manualPw.value = ''
  grantSet.value = new Set()
  createOpen.value = true
}

function toggleGrant(permission: Permission, branchId: string) {
  const key = grantKey(permission, branchId)
  const next = new Set(grantSet.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  grantSet.value = next
}

async function create() {
  saving.value = true
  try {
    const created = await api.createUser({
      full_name: form.value.full_name.trim(),
      login: form.value.login.trim(),
      phone: form.value.phone.trim(),
      home_branch_id: form.value.home_branch_id || null,
      grants: grantsFromSet(grantSet.value),
      password: pwMode.value === 'manual' ? manualPw.value : null,
    })
    createOpen.value = false
    secret.value = created
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

async function copySecret() {
  if (!secret.value) return
  try {
    await navigator.clipboard.writeText(secret.value.temp_password)
    toast.ok(t('common.copied'))
  } catch {
    toast.warn(t('common.copyFailed'))
  }
}

const canSave = computed(
  () =>
    form.value.full_name.trim() &&
    form.value.login.trim().length >= 3 &&
    form.value.phone.trim() &&
    (pwMode.value === 'auto' || manualPw.value.length >= 8),
)

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('workshop.usersTitle') }}</h1>
        <p class="sub">{{ t('workshop.usersSub') }}</p>
      </div>
      <div class="tools">
        <button class="btn btn-acc btn-sm" type="button" @click="openCreate">
          {{ t('workshop.newUser') }}
        </button>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />
    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>
    <div v-else-if="users.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.usersEmpty') }}</h3>
    </div>
    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.colName') }}</th>
            <th>{{ t('workshop.colLogin') }}</th>
            <th>{{ t('workshop.colPhone') }}</th>
            <th>{{ t('workshop.colHomeBranch') }}</th>
            <th>{{ t('workshop.colStatus') }}</th>
            <th>{{ t('workshop.colLastLogin') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="u in users"
            :key="u.id"
            class="clickable"
            @click="router.push(`/workshop/settings/users/${u.id}`)"
          >
            <td class="nm">
              {{ u.full_name }}<small v-if="u.is_owner">{{ t('workshop.owner') }}</small>
            </td>
            <td class="id">{{ u.login }}</td>
            <td>{{ fmtPhone(u.phone) }}</td>
            <td>{{ branchesStore.nameOf(u.home_branch_id) }}</td>
            <td>
              <StatusBadge
                :tone="u.status === 'active' ? 'ok' : 'bad'"
                :label="
                  u.status === 'active' ? t('workshop.statusActive') : t('workshop.statusBlocked')
                "
              />
            </td>
            <td style="font-size: 11.5px; color: var(--ink-6)">
              {{ u.last_login_at ? fmtDate(u.last_login_at) : '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- CREATE -->
    <AppModal v-model:open="createOpen" :title="t('workshop.createUser')" wide>
      <FormField v-model="form.full_name" :label="t('workshop.fullName')" required />
      <FormField v-model="form.login" :label="t('workshop.loginField')" required />
      <FormField v-model="form.phone" :label="t('workshop.colPhone')" required />
      <div class="field">
        <label>{{ t('workshop.homeBranch') }}</label>
        <select v-model="form.home_branch_id">
          <option value="">—</option>
          <option v-for="b in branchesStore.branches" :key="b.id" :value="b.id">
            {{ b.name }}
          </option>
        </select>
      </div>
      <div class="field">
        <label>{{ t('workshop.tempPassword') }}</label>
        <div class="chips">
          <button
            class="chip"
            :class="{ on: pwMode === 'auto' }"
            type="button"
            @click="pwMode = 'auto'"
          >
            {{ t('workshop.autoGenerate') }}
          </button>
          <button
            class="chip"
            :class="{ on: pwMode === 'manual' }"
            type="button"
            @click="pwMode = 'manual'"
          >
            {{ t('workshop.manual') }}
          </button>
        </div>
        <input
          v-if="pwMode === 'manual'"
          v-model="manualPw"
          type="text"
          style="margin-top: 8px"
          :placeholder="t('workshop.tempPassword')"
        />
      </div>

      <div class="field">
        <label>{{ t('workshop.grantsMatrix') }}</label>
        <table class="matrix">
          <thead>
            <tr>
              <th>{{ t('workshop.permissionCol') }}</th>
              <th v-for="b in branchesStore.branches" :key="b.id">{{ b.name }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in PERMISSIONS" :key="p">
              <td>{{ t(`permission.${p}`) }}</td>
              <td v-for="b in branchesStore.branches" :key="b.id" style="text-align: center">
                <input
                  type="checkbox"
                  :checked="grantSet.has(grantKey(p, b.id))"
                  @change="toggleGrant(p, b.id)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <template #footer>
        <button class="btn btn-outline" type="button" @click="createOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button class="btn btn-acc" type="button" :disabled="saving || !canSave" @click="create">
          {{ t('common.save') }}
        </button>
      </template>
    </AppModal>

    <!-- ONE-TIME SECRET -->
    <AppModal
      :open="secret !== null"
      :title="t('workshop.secretTitle')"
      @update:open="secret = null"
    >
      <p style="margin: 0 0 12px; color: var(--ink-10); font-size: 14px">
        {{ t('workshop.secretBody') }}
      </p>
      <div v-if="secret" class="secret-box">
        <div class="row">
          <span>{{ t('workshop.colLogin') }}</span
          ><b>{{ secret.login }}</b>
        </div>
        <div class="row">
          <span>{{ t('workshop.tempPassword') }}</span
          ><b class="num">{{ secret.temp_password }}</b>
        </div>
      </div>
      <template #footer>
        <button class="btn btn-outline" type="button" @click="copySecret">
          {{ t('common.copy') }}
        </button>
        <button class="btn btn-acc" type="button" @click="secret = null">
          {{ t('common.close') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>
