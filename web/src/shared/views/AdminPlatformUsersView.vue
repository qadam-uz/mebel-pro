<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { useAdminStore, type PlatformUserStatus } from '@/shared/stores/admin'
import { useAuthStore } from '@/shared/stores/auth'

const admin = useAdminStore()
const auth = useAuthStore()
const saving = ref(false)
const actionId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const blockTargetId = ref<string | null>(null)
const blockReason = ref('')

const form = reactive({
  fullName: '',
  login: '',
  phone: '+998',
  tempPassword: '',
})

const statusTone: Record<PlatformUserStatus, string> = {
  active: 'bg-success-soft text-success',
  blocked: 'bg-danger-soft text-danger',
}

const canConfirmBlock = computed(() => blockReason.value.trim().length > 0)

function formatDate(value: string | null) {
  if (!value) return 'Never'
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function resetForm() {
  form.fullName = ''
  form.login = ''
  form.phone = '+998'
  form.tempPassword = ''
}

async function createUser() {
  saving.value = true
  actionError.value = null
  try {
    await admin.createPlatformUser({
      full_name: form.fullName,
      login: form.login,
      phone: form.phone,
      temp_password: form.tempPassword || null,
    })
    resetForm()
  } catch {
    actionError.value = 'platform_user_save_failed'
  } finally {
    saving.value = false
  }
}

async function resetPassword(id: string) {
  actionId.value = id
  actionError.value = null
  try {
    await admin.resetPlatformUserPassword(id)
  } catch {
    actionError.value = 'platform_user_reset_failed'
  } finally {
    actionId.value = null
  }
}

function askBlock(id: string) {
  blockTargetId.value = id
  blockReason.value = ''
}

async function confirmBlock() {
  if (!blockTargetId.value || !canConfirmBlock.value) return
  actionId.value = blockTargetId.value
  actionError.value = null
  try {
    await admin.blockPlatformUser(blockTargetId.value, blockReason.value)
    blockTargetId.value = null
    blockReason.value = ''
  } catch {
    actionError.value = 'platform_user_block_failed'
  } finally {
    actionId.value = null
  }
}

async function unblock(id: string) {
  actionId.value = id
  actionError.value = null
  try {
    await admin.unblockPlatformUser(id)
  } catch {
    actionError.value = 'platform_user_unblock_failed'
  } finally {
    actionId.value = null
  }
}

onMounted(admin.loadPlatformUsers)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">Platform users</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Operators who can provision workshops and monitor platform operations.
        </p>
      </div>
      <button type="button" class="mp-button mp-button-outline" @click="admin.loadPlatformUsers">
        Refresh
      </button>
    </div>

    <section class="mp-surface p-5">
      <h2 class="font-serif text-xl font-semibold text-ink">Create platform user</h2>
      <form class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4" @submit.prevent="createUser">
        <label class="block text-sm font-bold text-ink" for="platform-user-full-name">
          Full name
          <input
            id="platform-user-full-name"
            v-model="form.fullName"
            class="mp-input mt-1"
            autocomplete="name"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="platform-user-login">
          Login
          <input
            id="platform-user-login"
            v-model="form.login"
            class="mp-input mt-1"
            autocomplete="username"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="platform-user-phone">
          Phone
          <input
            id="platform-user-phone"
            v-model="form.phone"
            class="mp-input mt-1"
            autocomplete="tel"
            inputmode="tel"
            required
          />
        </label>
        <label class="block text-sm font-bold text-ink" for="platform-user-temp-password">
          Temp password
          <input
            id="platform-user-temp-password"
            v-model="form.tempPassword"
            class="mp-input mt-1"
            autocomplete="new-password"
          />
        </label>
        <button
          type="submit"
          class="mp-button mp-button-primary md:col-span-2 xl:col-span-4"
          :disabled="saving"
        >
          {{ saving ? 'Creating' : 'Create platform user' }}
        </button>
      </form>

      <div
        v-if="admin.lastPlatformUserSecret"
        class="mt-4 rounded-md bg-success-soft p-4 text-success"
      >
        <div class="font-extrabold">
          Temp password for {{ admin.lastPlatformUserSecret.user.login }}
        </div>
        <p class="mt-1 break-all font-mono text-sm">
          {{ admin.lastPlatformUserSecret.temp_password }}
        </p>
      </div>
    </section>

    <section v-if="admin.opsLoading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
      Loading platform users
    </section>
    <section v-else-if="admin.opsError" class="mp-surface p-5 text-sm font-bold text-danger">
      Platform users could not be loaded.
      <span v-if="admin.opsTraceId" class="font-mono">trace {{ admin.opsTraceId }}</span>
    </section>
    <section
      v-else-if="admin.platformUsers.length === 0"
      class="mp-surface p-5 text-sm text-ink-soft"
    >
      No platform users yet.
    </section>
    <section v-else class="mp-surface overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-left text-sm">
          <thead class="bg-sunk text-xs uppercase text-ink-muted">
            <tr>
              <th class="px-5 py-3">User</th>
              <th class="px-5 py-3">Phone</th>
              <th class="px-5 py-3">Status</th>
              <th class="px-5 py-3">Last login</th>
              <th class="px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-hairline">
            <tr v-for="user in admin.platformUsers" :key="user.id">
              <td class="px-5 py-3">
                <div class="font-bold text-ink">{{ user.full_name }}</div>
                <div class="font-mono text-xs text-ink-soft">{{ user.login }}</div>
              </td>
              <td class="px-5 py-3 font-mono text-xs text-ink-soft">{{ user.phone }}</td>
              <td class="px-5 py-3">
                <span class="mp-chip" :class="statusTone[user.status]">
                  <span class="mp-dot" aria-hidden="true"></span>
                  {{ user.status }}
                </span>
              </td>
              <td class="px-5 py-3 font-mono text-xs text-ink-soft">
                {{ formatDate(user.last_login_at) }}
              </td>
              <td class="px-5 py-3">
                <div class="flex flex-wrap gap-2">
                  <button
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="actionId === user.id"
                    @click="resetPassword(user.id)"
                  >
                    Reset password
                  </button>
                  <button
                    v-if="user.status === 'active'"
                    type="button"
                    class="mp-button mp-button-outline min-h-9 px-3 text-xs"
                    :disabled="user.id === auth.me?.principal_id"
                    @click="askBlock(user.id)"
                  >
                    Block
                  </button>
                  <button
                    v-else
                    type="button"
                    class="mp-button mp-button-primary min-h-9 px-3 text-xs"
                    :disabled="actionId === user.id"
                    @click="unblock(user.id)"
                  >
                    Unblock
                  </button>
                </div>

                <form
                  v-if="blockTargetId === user.id"
                  class="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_auto]"
                  @submit.prevent="confirmBlock"
                >
                  <label class="block text-sm font-bold text-ink" :for="`block-reason-${user.id}`">
                    Block reason
                    <input
                      :id="`block-reason-${user.id}`"
                      v-model="blockReason"
                      class="mp-input mt-1"
                      required
                    />
                  </label>
                  <button
                    type="submit"
                    class="mp-button mp-button-primary self-end"
                    :disabled="!canConfirmBlock || actionId === user.id"
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    class="mp-button mp-button-outline self-end"
                    @click="blockTargetId = null"
                  >
                    Cancel
                  </button>
                </form>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p v-if="actionError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
      Platform user action could not be completed.
    </p>
  </section>
</template>
