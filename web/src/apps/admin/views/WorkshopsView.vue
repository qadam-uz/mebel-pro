<script setup lang="ts">
// Workshops registry — table (name, owner, status, branches, orders-30d),
// status filter + search, + Workshop provisioning dialog → one-time secret.
// Mirrors prototype admin/workshops.html.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, FilterBar, FilterChip, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDate, fmtPhone } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { genTempPassword } from '../lib/admin'
import * as api from '../api'
import type { WorkshopProvisionResult, WorkshopSummary } from '../api/types'

const router = useRouter()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<WorkshopSummary[]>([])

const search = ref('')
const statusFilter = ref<'all' | 'active' | 'blocked'>('all')

const createOpen = ref(false)
const saving = ref(false)
const form = ref({
  name: '',
  phone: '',
  address: '',
  owner_full_name: '',
  owner_phone: '',
  owner_login: '',
})
const pwMode = ref<'auto' | 'manual'>('auto')
const password = ref(genTempPassword())

const secret = ref<WorkshopProvisionResult | null>(null)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return rows.value.filter(
    (w) =>
      (statusFilter.value === 'all' || w.status === statusFilter.value) &&
      (!q || w.name.toLowerCase().includes(q) || (w.owner_name ?? '').toLowerCase().includes(q)),
  )
})

const canSave = computed(
  () =>
    form.value.name.trim() &&
    form.value.phone.trim() &&
    form.value.owner_full_name.trim() &&
    form.value.owner_phone.trim() &&
    form.value.owner_login.trim().length >= 3 &&
    (pwMode.value === 'auto' || password.value.length >= 8),
)

async function load() {
  loading.value = true
  error.value = null
  try {
    rows.value = await api.listWorkshops()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = {
    name: '',
    phone: '',
    address: '',
    owner_full_name: '',
    owner_phone: '',
    owner_login: '',
  }
  pwMode.value = 'auto'
  password.value = genTempPassword()
  createOpen.value = true
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

async function create() {
  saving.value = true
  try {
    const created = await api.provisionWorkshop({
      name: form.value.name.trim(),
      phone: form.value.phone.trim(),
      address: form.value.address.trim() || null,
      owner_full_name: form.value.owner_full_name.trim(),
      owner_login: form.value.owner_login.trim(),
      owner_phone: form.value.owner_phone.trim(),
      owner_password: pwMode.value === 'manual' ? password.value : null,
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

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('admin.workshopsTitle') }}</h1>
        <p class="sub">{{ t('admin.workshopsSub') }}</p>
      </div>
      <div class="tools">
        <button class="btn btn-acc" type="button" @click="openCreate">
          {{ t('admin.newWorkshop') }}
        </button>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :title="t('admin.workshopsLoadFailed')" :retry="load" />

    <template v-else>
      <FilterBar v-if="!loading">
        <div class="input">
          <input v-model="search" :placeholder="t('admin.workshopSearchPlaceholder')" />
        </div>
        <div class="chips">
          <FilterChip :active="statusFilter === 'all'" @click="statusFilter = 'all'">{{
            t('admin.statusAll')
          }}</FilterChip>
          <FilterChip :active="statusFilter === 'active'" @click="statusFilter = 'active'">{{
            t('admin.statusActive')
          }}</FilterChip>
          <FilterChip :active="statusFilter === 'blocked'" @click="statusFilter = 'blocked'">{{
            t('admin.statusBlocked')
          }}</FilterChip>
        </div>
      </FilterBar>

      <div v-if="loading" class="card">
        <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
      </div>

      <div v-else-if="filtered.length === 0" class="st-empty">
        <div class="ic">▥</div>
        <h3>{{ t('admin.workshopsEmpty') }}</h3>
        <p>{{ t('admin.workshopsEmptyBody') }}</p>
      </div>

      <div v-else class="card">
        <table class="tbl">
          <thead>
            <tr>
              <th>{{ t('admin.colWorkshop') }}</th>
              <th>{{ t('admin.colOwner') }}</th>
              <th>{{ t('admin.colBranches') }}</th>
              <th class="right">{{ t('admin.colOrders30d') }}</th>
              <th>{{ t('admin.colCreated') }}</th>
              <th>{{ t('admin.colStatus') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="w in filtered"
              :key="w.id"
              class="clickable"
              @click="router.push(`/admin/workshops/${w.id}`)"
            >
              <td class="nm">{{ w.name }}</td>
              <td>
                <div class="nm" style="font-weight: 500">
                  {{ w.owner_name ?? '—'
                  }}<small style="color: var(--ink-6)">{{ fmtPhone(w.owner_phone) }}</small>
                </div>
              </td>
              <td class="num">{{ w.branches_count }}</td>
              <td class="num right">{{ w.orders_30d_count }}</td>
              <td class="num" style="font-size: 11.5px; color: var(--ink-6)">
                {{ fmtDate(w.created_at) }}
              </td>
              <td>
                <StatusBadge
                  :tone="w.status === 'active' ? 'ok' : 'bad'"
                  :label="
                    w.status === 'active' ? t('admin.statusActive') : t('admin.statusBlocked')
                  "
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- PROVISION -->
    <AppModal v-model:open="createOpen" :title="t('admin.provisionTitle')" wide>
      <h4 class="form-section">{{ t('admin.provisionWorkshopFields') }}</h4>
      <div class="field-row">
        <div class="field">
          <label>{{ t('admin.workshopName') }}</label>
          <input v-model="form.name" placeholder="Furniture House" />
        </div>
        <div class="field">
          <label>{{ t('admin.phone') }}</label>
          <input v-model="form.phone" placeholder="+998 71 ..." />
        </div>
      </div>
      <div class="field">
        <label>{{ t('admin.address') }}</label>
        <input v-model="form.address" placeholder="Toshkent, ..." />
      </div>

      <h4 class="form-section">{{ t('admin.provisionOwnerFields') }}</h4>
      <div class="field-row">
        <div class="field">
          <label>{{ t('admin.fullName') }}</label>
          <input v-model="form.owner_full_name" placeholder="Hasan Karimov" />
        </div>
        <div class="field">
          <label>{{ t('admin.phone') }}</label>
          <input v-model="form.owner_phone" placeholder="+998 90 ..." />
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>{{ t('admin.login') }}</label>
          <input v-model="form.owner_login" placeholder="hasan" />
        </div>
        <div class="field">
          <label>{{ t('admin.tempPassword') }}</label>
          <div class="chips" style="margin-bottom: 8px">
            <FilterChip
              :active="pwMode === 'auto'"
              @click="((pwMode = 'auto'), (password = genTempPassword()))"
              >{{ t('admin.autoGenerate') }}</FilterChip
            >
            <FilterChip
              :active="pwMode === 'manual'"
              @click="((pwMode = 'manual'), (password = ''))"
              >{{ t('admin.manual') }}</FilterChip
            >
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
      </div>
      <div class="banner info">
        <div class="ic">i</div>
        <div class="grow">{{ t('admin.secretHint') }}</div>
      </div>

      <template #footer>
        <button class="btn btn-outline" type="button" @click="createOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button class="btn btn-acc" type="button" :disabled="saving || !canSave" @click="create">
          {{ t('admin.create') }}
        </button>
      </template>
    </AppModal>

    <!-- ONE-TIME SECRET -->
    <AppModal
      :open="secret !== null"
      :title="t('admin.provisionSecretTitle')"
      @update:open="secret = null"
    >
      <p style="margin: 0 0 12px; color: var(--ink-10); font-size: 14px">
        {{ t('admin.secretShareOnce') }}
      </p>
      <div v-if="secret" class="secret-box">
        <div class="row">
          <span>{{ t('admin.workshopName') }}</span
          ><b>{{ secret.workshop.name }}</b>
        </div>
        <div class="row">
          <span>{{ t('admin.login') }}</span
          ><b class="num">{{ secret.owner_login }}</b>
        </div>
        <div class="row">
          <span>{{ t('admin.tempPassword') }}</span
          ><b class="num">{{ secret.temp_password }}</b>
        </div>
      </div>
      <p v-if="secret" class="hint" style="margin-top: 10px">{{ t('admin.secretHint') }}</p>
      <template #footer>
        <button class="btn btn-outline" type="button" @click="copyValue(secret!.temp_password)">
          {{ t('common.copy') }}
        </button>
        <button class="btn btn-acc" type="button" @click="secret = null">
          {{ t('common.close') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.form-section {
  font: 600 12px var(--f-ui);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-6);
  margin: 20px 0 10px;
}
.form-section:first-child {
  margin-top: 0;
}
</style>
