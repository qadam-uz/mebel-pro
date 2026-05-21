<script setup lang="ts">
// Branches list (owner writes) — table + create/edit dialog + status change.
// Mirrors prototype workshop/branches.html.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppModal, ErrorState, FormField, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtPhone } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopAuth } from '../store'
import { useBranchesStore } from '../stores/branches'
import * as api from '../api'
import type { BranchStatus, BranchSummary } from '../api/types'

const router = useRouter()
const toast = useToast()
const auth = useWorkshopAuth()
const branchesStore = useBranchesStore()

const loading = ref(true)
const error = ref<ApiError | null>(null)

const formOpen = ref(false)
const editing = ref<BranchSummary | null>(null)
const form = ref({ name: '', address: '', phone: '', latitude: '', longitude: '' })
const saving = ref(false)

const pillTone = (s: BranchStatus) =>
  s === 'active' ? 'ok' : s === 'temporarily_closed' ? 'warn' : 'bad'

const branches = computed(() => branchesStore.branches)

async function load() {
  loading.value = true
  error.value = null
  try {
    await branchesStore.load(true)
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', address: '', phone: '', latitude: '', longitude: '' }
  formOpen.value = true
}

function openEdit(b: BranchSummary) {
  editing.value = b
  form.value = {
    name: b.name,
    address: b.address,
    phone: b.phone,
    latitude: b.latitude == null ? '' : String(b.latitude),
    longitude: b.longitude == null ? '' : String(b.longitude),
  }
  formOpen.value = true
}

async function save() {
  saving.value = true
  try {
    const body = {
      name: form.value.name.trim(),
      address: form.value.address.trim(),
      phone: form.value.phone.trim(),
      latitude: form.value.latitude ? Number(form.value.latitude) : null,
      longitude: form.value.longitude ? Number(form.value.longitude) : null,
    }
    if (editing.value) {
      await api.editBranch(editing.value.id, body)
      toast.ok(t('workshop.branchUpdated'))
    } else {
      await api.createBranch(body)
      toast.ok(t('workshop.branchCreated'))
    }
    formOpen.value = false
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

const canCreate = computed(() => auth.isOwner)

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('workshop.branchesTitle') }}</h1>
        <p class="sub">{{ t('workshop.branchesSub') }}</p>
      </div>
      <div class="tools">
        <button v-if="canCreate" class="btn btn-acc btn-sm" type="button" @click="openCreate">
          {{ t('workshop.newBranch') }}
        </button>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />

    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>

    <div v-else-if="branches.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.branchesEmpty') }}</h3>
      <p>{{ t('workshop.branchesEmptyBody') }}</p>
    </div>

    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.branchName') }}</th>
            <th>{{ t('workshop.branchPhone') }}</th>
            <th>{{ t('workshop.colStatus') }}</th>
            <th class="right">{{ t('workshop.colMaterials') }}</th>
            <th class="right">{{ t('workshop.colLowStock') }}</th>
            <th class="right">{{ t('workshop.colActiveOrders') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="b in branches"
            :key="b.id"
            class="clickable"
            @click="router.push(`/workshop/branches/${b.id}`)"
          >
            <td class="nm">
              {{ b.name }}<small>{{ b.address }}</small>
            </td>
            <td>{{ fmtPhone(b.phone) }}</td>
            <td>
              <StatusBadge :tone="pillTone(b.status)" :label="t(`branchStatus.${b.status}`)" />
            </td>
            <td class="amt">{{ b.materials_count }}</td>
            <td class="amt" :class="{ 'warn-text': b.low_stock_count > 0 }">
              {{ b.low_stock_count }}
            </td>
            <td class="amt">{{ b.active_orders_count }}</td>
            <td @click.stop>
              <button
                v-if="canCreate"
                class="btn btn-ghost btn-sm"
                type="button"
                @click="openEdit(b)"
              >
                {{ t('common.edit') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AppModal
      v-model:open="formOpen"
      :title="editing ? t('workshop.editBranch') : t('workshop.newBranch')"
    >
      <FormField v-model="form.name" :label="t('workshop.branchName')" required />
      <FormField v-model="form.address" :label="t('workshop.branchAddress')" required />
      <FormField v-model="form.phone" :label="t('workshop.branchPhone')" required />
      <div class="field-row">
        <FormField v-model="form.latitude" type="number" :label="t('workshop.branchLat')" />
        <FormField v-model="form.longitude" type="number" :label="t('workshop.branchLng')" />
      </div>
      <template #footer>
        <button class="btn btn-outline" type="button" @click="formOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button
          class="btn btn-acc"
          type="button"
          :disabled="saving || !form.name.trim() || !form.address.trim() || !form.phone.trim()"
          @click="save"
        >
          {{ t('common.save') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>
