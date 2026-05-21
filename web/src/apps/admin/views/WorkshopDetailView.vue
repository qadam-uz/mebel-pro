<script setup lang="ts">
// Workshop detail — header + tabs: Profile (operator edit via PATCH .../profile),
// Branches (read-only count), Block/Unblock (mandatory reason, destructive).
// Mirrors prototype admin/workshop-detail.html.
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppTabs, ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDate, fmtPhone } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import * as api from '../api'
import type { WorkshopSummary } from '../api/types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const id = route.params.id as string

const loading = ref(true)
const error = ref<ApiError | null>(null)
const ws = ref<WorkshopSummary | null>(null)

const tab = ref('profile')
const tabs = computed(() => [
  { id: 'profile', label: t('admin.tabProfile') },
  { id: 'branches', label: t('admin.tabBranches') },
  { id: 'block', label: t('admin.tabBlock') },
])

const editing = ref(false)
const saving = ref(false)
const form = ref({ name: '', phone: '', address: '' })

const confirmOpen = ref(false)
const isBlocked = computed(() => ws.value?.status === 'blocked')

async function load() {
  loading.value = true
  error.value = null
  try {
    ws.value = await api.getWorkshop(id)
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function startEdit() {
  if (!ws.value) return
  form.value = {
    name: ws.value.name,
    phone: ws.value.phone,
    address: ws.value.address ?? '',
  }
  editing.value = true
}

async function saveProfile() {
  if (!ws.value) return
  saving.value = true
  try {
    await api.editWorkshopProfile(ws.value.id, {
      name: form.value.name.trim(),
      phone: form.value.phone.trim(),
      address: form.value.address.trim() || null,
    })
    toast.ok(t('common.save'))
    editing.value = false
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

async function confirmBlockToggle(reason: string) {
  if (!ws.value) return
  try {
    if (isBlocked.value) {
      await api.unblockWorkshop(ws.value.id, reason)
      toast.ok(t('admin.unblocked'))
    } else {
      await api.blockWorkshop(ws.value.id, reason)
      toast.danger(t('admin.blocked'))
    }
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <button class="back" type="button" @click="router.push('/admin/workshops')">
      {{ t('admin.backToWorkshops') }}
    </button>

    <ErrorState v-if="error" :error="error" :title="t('admin.workshopLoadFailed')" :retry="load" />

    <div v-else-if="loading" class="card" style="max-width: 720px; margin-top: 8px">
      <div class="card-b" style="padding: 24px">
        <div v-for="n in 5" :key="n" class="sk sk-line" />
      </div>
    </div>

    <div v-else-if="!ws" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('admin.workshopNotFound') }}</h3>
      <p>{{ t('admin.workshopNotFoundBody') }}</p>
    </div>

    <template v-else>
      <div class="page-head" style="margin-top: 8px">
        <div>
          <h1>{{ ws.name }}</h1>
          <p class="sub">
            {{ ws.branches_count }} {{ t('admin.kpiBranches') }} · {{ ws.orders_30d_count }}
            {{ t('admin.colOrders30d') }} · {{ fmtDate(ws.created_at) }}
          </p>
          <div style="margin-top: 6px">
            <StatusBadge
              :tone="isBlocked ? 'bad' : 'ok'"
              :label="isBlocked ? t('admin.statusBlocked') : t('admin.statusActive')"
            />
          </div>
        </div>
      </div>

      <div v-if="isBlocked" class="banner danger">
        <div class="ic">!</div>
        <div class="grow">{{ t('admin.blockedBanner') }}</div>
      </div>

      <AppTabs v-model="tab" :tabs="tabs" />

      <!-- PROFILE -->
      <section v-if="tab === 'profile'">
        <div class="card" style="max-width: 720px">
          <div class="card-h">
            <h2>{{ t('admin.tabProfile') }}</h2>
            <button v-if="!editing" class="btn btn-outline btn-sm" type="button" @click="startEdit">
              {{ t('common.edit') }}
            </button>
          </div>
          <div class="card-b" style="padding-top: 0">
            <template v-if="!editing">
              <div class="row-item">
                <div class="nm">{{ t('admin.workshopName') }}</div>
                <div class="meta">{{ ws.name }}</div>
              </div>
              <div class="row-item">
                <div class="nm">{{ t('admin.phone') }}</div>
                <div class="meta">{{ fmtPhone(ws.phone) }}</div>
              </div>
              <div class="row-item">
                <div class="nm">{{ t('admin.address') }}</div>
                <div class="meta">{{ ws.address || '—' }}</div>
              </div>
              <div class="row-item">
                <div class="nm">{{ t('admin.colOwner') }}</div>
                <div class="meta">{{ ws.owner_name ?? '—' }}</div>
              </div>
              <div class="row-item">
                <div class="nm">{{ t('admin.ownerPhone') }}</div>
                <div class="meta">{{ fmtPhone(ws.owner_phone) || '—' }}</div>
              </div>
              <div class="row-item" style="border-bottom: 0">
                <div class="nm">{{ t('admin.colCreated') }}</div>
                <div class="meta">{{ fmtDate(ws.created_at) }}</div>
              </div>
            </template>

            <template v-else>
              <div class="field">
                <label>{{ t('admin.workshopName') }}</label>
                <input v-model="form.name" />
              </div>
              <div class="field">
                <label>{{ t('admin.phone') }}</label>
                <input v-model="form.phone" />
              </div>
              <div class="field">
                <label>{{ t('admin.address') }}</label>
                <input v-model="form.address" />
              </div>
              <div class="flex-end" style="gap: 8px">
                <button class="btn btn-outline btn-sm" type="button" @click="editing = false">
                  {{ t('common.cancel') }}
                </button>
                <button
                  class="btn btn-acc btn-sm"
                  type="button"
                  :disabled="saving || !form.name.trim() || !form.phone.trim()"
                  @click="saveProfile"
                >
                  {{ t('common.save') }}
                </button>
              </div>
            </template>
          </div>
        </div>
      </section>

      <!-- BRANCHES -->
      <section v-else-if="tab === 'branches'">
        <div class="card" style="max-width: 720px">
          <div class="card-h">
            <h2>{{ t('admin.branchesReadOnly') }}</h2>
          </div>
          <div class="card-b">
            <div class="banner info">
              <div class="ic">i</div>
              <div class="grow">{{ t('admin.branchesNoEndpoint') }}</div>
            </div>
            <div class="row-item" style="border-bottom: 0">
              <div class="nm">{{ t('admin.branchesCountLabel') }}</div>
              <div class="meta num">{{ ws.branches_count }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- BLOCK -->
      <section v-else>
        <div class="card" style="max-width: 720px">
          <div class="card-h">
            <h2>{{ isBlocked ? t('admin.unblockTitle') : t('admin.blockTitle') }}</h2>
          </div>
          <div class="card-b">
            <div :class="isBlocked ? 'banner info' : 'banner danger'">
              <div class="ic">{{ isBlocked ? 'i' : '!' }}</div>
              <div class="grow">
                {{ isBlocked ? t('admin.unblockBody') : t('admin.blockBody') }}
              </div>
            </div>
            <button
              :class="isBlocked ? 'btn btn-acc' : 'btn btn-danger'"
              type="button"
              @click="confirmOpen = true"
            >
              {{ isBlocked ? t('admin.unblockBtn') : t('admin.blockBtn') }}
            </button>
          </div>
        </div>
      </section>

      <ConfirmDialog
        v-model:open="confirmOpen"
        :title="isBlocked ? t('admin.unblockTitle') : t('admin.blockTitle')"
        :message="isBlocked ? t('admin.unblockBody') : t('admin.blockBody')"
        :ok-text="isBlocked ? t('admin.unblockBtn') : t('admin.blockBtn')"
        :danger="!isBlocked"
        reason
        :reason-label="isBlocked ? t('admin.unblockReason') : t('admin.blockReason')"
        @confirm="confirmBlockToggle"
      />
    </template>
  </div>
</template>
