<script setup lang="ts">
// User detail (owner-only) — tabs Profile / Permissions (grants matrix, save +
// unsaved guard). Row actions: edit profile, reset password (one-time-secret),
// block/unblock. Mirrors prototype workshop/user-detail.html.
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppModal, AppTabs, ErrorState, FormField, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDate, fmtPhone } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { useBranchesStore } from '../../stores/branches'
import * as api from '../../api'
import type { CreatedSecret, WorkshopUserDetail } from '../../api/types'
import type { Permission } from '@/shared/types'
import { PERMISSIONS, diffGrants, grantKey, grantsFromSet } from '../../lib/orders'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const branchesStore = useBranchesStore()

const userId = computed(() => String(route.params.id))
const loading = ref(true)
const error = ref<ApiError | null>(null)
const user = ref<WorkshopUserDetail | null>(null)
const activeTab = ref('profile')

const tabs = computed(() => [
  { id: 'profile', label: t('workshop.tabProfile') },
  { id: 'permissions', label: t('workshop.tabPermissions') },
])

// profile edit
const editName = ref('')
const editPhone = ref('')
const editHome = ref('')
const savingProfile = ref(false)

// grants matrix
const grantSet = ref<Set<string>>(new Set())
const savingGrants = ref(false)

const secret = ref<CreatedSecret | null>(null)

const grantsDirty = computed(() =>
  user.value ? diffGrants(user.value.grants, grantSet.value).changed : false,
)

async function load() {
  loading.value = true
  error.value = null
  try {
    await branchesStore.load()
    const u = await api.getUser(userId.value)
    user.value = u
    editName.value = u.full_name
    editPhone.value = u.phone
    editHome.value = u.home_branch_id ?? ''
    grantSet.value = new Set(u.grants.map((g) => grantKey(g.permission, g.branch_id)))
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function toggleGrant(permission: Permission, branchId: string) {
  const key = grantKey(permission, branchId)
  const next = new Set(grantSet.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  grantSet.value = next
}

async function saveProfile() {
  savingProfile.value = true
  try {
    await api.editUser(userId.value, {
      full_name: editName.value.trim(),
      phone: editPhone.value.trim(),
      home_branch_id: editHome.value || null,
      home_branch_set: true,
    })
    toast.ok(t('workshop.userUpdated'))
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    savingProfile.value = false
  }
}

async function saveGrants() {
  savingGrants.value = true
  try {
    await api.setGrants(userId.value, grantsFromSet(grantSet.value))
    toast.ok(t('workshop.grantsSaved'))
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    savingGrants.value = false
  }
}

async function resetPassword() {
  try {
    secret.value = await api.resetUserPassword(userId.value)
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

async function toggleBlock() {
  if (!user.value) return
  try {
    if (user.value.status === 'blocked') {
      await api.unblockUser(userId.value)
      toast.ok(t('workshop.unblocked'))
    } else {
      await api.blockUser(userId.value)
      toast.ok(t('workshop.blocked'))
    }
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
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

onBeforeRouteLeave(() => {
  if (grantsDirty.value && !window.confirm(t('workshop.unsavedGuard'))) return false
  return true
})

watch(userId, load)
onMounted(load)
</script>

<template>
  <div>
    <button class="back" type="button" @click="router.push('/workshop/settings/users')">
      ← {{ t('workshop.usersTitle') }}
    </button>

    <ErrorState v-if="error" :error="error" :retry="load" />
    <div v-else-if="loading" class="card" style="margin-top: 12px">
      <div class="card-b"><div class="sk sk-line" style="width: 50%" /></div>
    </div>

    <template v-else-if="user">
      <div class="page-head" style="margin-top: 8px">
        <div>
          <h1>{{ user.full_name }}</h1>
          <p class="sub">{{ user.login }} · {{ fmtPhone(user.phone) }}</p>
        </div>
        <div class="tools" style="align-items: center; gap: 8px">
          <StatusBadge
            :tone="user.status === 'active' ? 'ok' : 'bad'"
            :label="
              user.status === 'active' ? t('workshop.statusActive') : t('workshop.statusBlocked')
            "
          />
          <button
            v-if="!user.is_owner"
            class="btn btn-outline btn-sm"
            type="button"
            @click="resetPassword"
          >
            {{ t('workshop.resetPassword') }}
          </button>
          <button
            v-if="!user.is_owner"
            class="btn btn-outline btn-sm"
            type="button"
            @click="toggleBlock"
          >
            {{ user.status === 'blocked' ? t('workshop.unblock') : t('workshop.block') }}
          </button>
        </div>
      </div>

      <AppTabs v-model="activeTab" :tabs="tabs" />

      <!-- PROFILE -->
      <section v-show="activeTab === 'profile'" class="card" style="margin-top: 16px">
        <div class="card-b">
          <FormField v-model="editName" :label="t('workshop.fullName')" :disabled="user.is_owner" />
          <FormField
            v-model="editPhone"
            :label="t('workshop.colPhone')"
            :disabled="user.is_owner"
          />
          <div class="field">
            <label>{{ t('workshop.homeBranch') }}</label>
            <select v-model="editHome" :disabled="user.is_owner">
              <option value="">—</option>
              <option v-for="b in branchesStore.branches" :key="b.id" :value="b.id">
                {{ b.name }}
              </option>
            </select>
          </div>
          <button
            v-if="!user.is_owner"
            class="btn btn-acc btn-sm"
            type="button"
            :disabled="savingProfile"
            @click="saveProfile"
          >
            {{ t('common.save') }}
          </button>
          <p style="font-size: 11.5px; color: var(--ink-6); margin: 12px 0 0">
            {{ t('workshop.colLastLogin') }}:
            {{ user.last_login_at ? fmtDate(user.last_login_at) : '—' }}
          </p>
        </div>
      </section>

      <!-- PERMISSIONS -->
      <section v-show="activeTab === 'permissions'" style="margin-top: 16px">
        <div v-if="user.is_owner" class="banner">
          <div class="ic">i</div>
          <div class="grow">{{ t('workshop.owner') }} · {{ t('common.all') }}</div>
        </div>
        <div v-else class="card">
          <div class="card-b">
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
            <button
              class="btn btn-acc btn-sm"
              type="button"
              style="margin-top: 14px"
              :disabled="savingGrants || !grantsDirty"
              @click="saveGrants"
            >
              {{ t('workshop.saveChanges') }}
            </button>
          </div>
        </div>
      </section>
    </template>

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
