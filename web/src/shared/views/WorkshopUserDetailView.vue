<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { formatDate } from '@/shared/formatters'
import { permissionCatalog, useWorkshopStore } from '@/shared/stores/workshop'

const route = useRoute()
const workshop = useWorkshopStore()
const userId = String(route.params.user_id)
const reason = ref('')
const actionError = ref<string | null>(null)
const acting = ref(false)
const selected = ref<Set<string>>(new Set())
const canBlock = computed(
  () => workshop.selectedUser?.status === 'active' && reason.value.trim().length > 0,
)
const canUnblock = computed(() => workshop.selectedUser?.status === 'blocked')

const grants = computed(() =>
  [...selected.value].map((value) => {
    const [permission, branch_id] = value.split('|')
    return { permission, branch_id }
  }),
)

function grantKey(permission: string, branchId: string) {
  return `${permission}|${branchId}`
}

function toggleGrant(permission: string, branchId: string) {
  const next = new Set(selected.value)
  const key = grantKey(permission, branchId)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  selected.value = next
}

async function load() {
  await workshop.loadBranchContext()
  await workshop.loadUser(userId)
  selected.value = new Set(
    workshop.selectedUser?.grants.map((grant) => grantKey(grant.permission, grant.branch_id)) ?? [],
  )
}

async function saveGrants() {
  actionError.value = null
  acting.value = true
  try {
    await workshop.replaceGrants(userId, grants.value)
    await load()
  } catch {
    actionError.value = 'grants_save_failed'
  } finally {
    acting.value = false
  }
}

async function resetPassword() {
  actionError.value = null
  acting.value = true
  try {
    await workshop.resetPassword(userId)
  } catch {
    actionError.value = 'password_reset_failed'
  } finally {
    acting.value = false
  }
}

async function block() {
  if (!canBlock.value) return
  actionError.value = null
  acting.value = true
  try {
    await workshop.blockUser(userId, reason.value)
    reason.value = ''
  } catch {
    actionError.value = 'user_block_failed'
  } finally {
    acting.value = false
  }
}

async function unblock() {
  if (!canUnblock.value) return
  actionError.value = null
  acting.value = true
  try {
    await workshop.unblockUser(userId)
  } catch {
    actionError.value = 'user_unblock_failed'
  } finally {
    acting.value = false
  }
}

async function revokeAllSessions() {
  actionError.value = null
  acting.value = true
  try {
    await workshop.revokeUserSessions(userId)
  } catch {
    actionError.value = 'sessions_revoke_failed'
  } finally {
    acting.value = false
  }
}

async function revokeSession(sessionId: string) {
  actionError.value = null
  acting.value = true
  try {
    await workshop.revokeUserSession(userId, sessionId)
  } catch {
    actionError.value = 'session_revoke_failed'
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<template>
  <section v-if="workshop.loading" class="mp-surface p-5 text-sm font-bold text-ink-soft">
    Loading user
  </section>
  <section v-else-if="workshop.error" class="mp-surface p-5 text-sm font-bold text-danger">
    User could not be loaded.
  </section>
  <section v-else-if="workshop.selectedUser" class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-semibold text-ink">
          {{ workshop.selectedUser.full_name }}
        </h1>
        <p class="mt-2 font-mono text-sm text-ink-soft">{{ workshop.selectedUser.login }}</p>
      </div>
      <span
        class="mp-chip"
        :class="
          workshop.selectedUser.status === 'active'
            ? 'bg-success-soft text-success'
            : 'bg-danger-soft text-danger'
        "
      >
        <span class="mp-dot" aria-hidden="true"></span>
        {{ workshop.selectedUser.status }}
      </span>
    </div>

    <section class="mp-surface p-5">
      <h2 class="font-serif text-xl font-semibold">Access</h2>
      <div class="mt-4 overflow-x-auto">
        <table class="w-full min-w-[680px] text-left text-sm">
          <thead class="text-xs uppercase text-ink-muted">
            <tr>
              <th class="py-2 pr-3">Permission</th>
              <th v-for="branch in workshop.branches" :key="branch.id" class="px-3 py-2">
                {{ branch.name }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-hairline">
            <tr v-for="permission in permissionCatalog" :key="permission">
              <th class="py-2 pr-3 font-mono text-xs">{{ permission }}</th>
              <td v-for="branch in workshop.branches" :key="branch.id" class="px-3 py-2">
                <input
                  type="checkbox"
                  :checked="selected.has(grantKey(permission, branch.id))"
                  @change="toggleGrant(permission, branch.id)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <button
        type="button"
        class="mp-button mp-button-primary mt-4"
        :disabled="acting"
        @click="saveGrants"
      >
        Save grants
      </button>
    </section>

    <section class="grid gap-5 lg:grid-cols-2">
      <div class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold">Password</h2>
        <button
          class="mp-button mp-button-outline mt-4"
          type="button"
          :disabled="acting"
          @click="resetPassword"
        >
          Reset password
        </button>
        <p v-if="workshop.lastTempPassword" class="mt-3 font-mono text-sm text-success">
          {{ workshop.lastTempPassword }}
        </p>
      </div>
      <div class="mp-surface p-5">
        <h2 class="font-serif text-xl font-semibold">Status</h2>
        <div class="mt-4 flex gap-2">
          <input
            v-model="reason"
            class="min-h-10 flex-1 rounded-md border border-hairline-strong px-3"
            placeholder="Block reason"
          />
          <button
            class="mp-button mp-button-outline"
            type="button"
            :disabled="acting || !canBlock"
            @click="block"
          >
            Block
          </button>
          <button
            class="mp-button mp-button-primary"
            type="button"
            :disabled="acting || !canUnblock"
            @click="unblock"
          >
            Unblock
          </button>
        </div>
      </div>
    </section>

    <section class="mp-surface overflow-hidden">
      <div
        class="flex flex-wrap items-center justify-between gap-3 border-b border-hairline px-5 py-4"
      >
        <h2 class="font-serif text-xl font-semibold">Sessions</h2>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
          :disabled="acting || workshop.sessions.length === 0"
          @click="revokeAllSessions"
        >
          Revoke all
        </button>
      </div>
      <div v-if="workshop.sessions.length === 0" class="px-5 py-6 text-sm text-ink-soft">
        No active staff sessions.
      </div>
      <div v-else class="divide-y divide-hairline">
        <div
          v-for="session in workshop.sessions"
          :key="session.id"
          class="grid gap-3 px-5 py-4 sm:grid-cols-[1fr_auto]"
        >
          <div>
            <div class="font-mono text-sm text-ink">{{ session.id }}</div>
            <div class="mt-1 text-sm text-ink-soft">
              Created {{ formatDate(session.created_at) }} · last used
              {{ formatDate(session.last_used_at) }}
            </div>
          </div>
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            :disabled="acting"
            @click="revokeSession(session.id)"
          >
            Revoke
          </button>
        </div>
      </div>
    </section>

    <p v-if="actionError" class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger">
      Action could not be completed.
    </p>
  </section>
</template>
