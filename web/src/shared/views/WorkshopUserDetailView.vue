<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { initials, permissionLabels } from '@/shared/app/workshopUi'
import { formatDate } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { permissionCatalog, useWorkshopStore } from '@/shared/stores/workshop'

const route = useRoute()
const rolePath = useRolePath()
const auth = useAuthStore()
const workshop = useWorkshopStore()
const userId = String(route.params.user_id)
const activeTab = ref<'profile' | 'permissions' | 'sessions'>('profile')
const reason = ref('')
const actionError = ref<string | null>(null)
const acting = ref(false)
const selected = ref<Set<string>>(new Set())
const user = computed(() => workshop.selectedUser)
const canBlock = computed(
  () => user.value?.status === 'active' && !user.value.is_owner && reason.value.trim().length > 0,
)
const canUnblock = computed(() => user.value?.status === 'blocked' && !user.value.is_owner)
const grants = computed(() =>
  [...selected.value].map((value) => {
    const [permission, branch_id] = value.split('|')
    return { permission, branch_id }
  }),
)

function branchName(id: string | null) {
  if (!id) return '—'
  return workshop.branches.find((branch) => branch.id === id)?.name ?? 'Filial'
}

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
  if (!auth.me?.is_owner) return
  await workshop.loadBranchContext()
  await workshop.loadUser(userId)
  selected.value = new Set(
    user.value?.grants.map((grant) => grantKey(grant.permission, grant.branch_id)) ?? [],
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
  <section>
    <RouterLink :to="rolePath('/workshop/settings/users')" class="back">← Xodimlar</RouterLink>

    <section v-if="!auth.me?.is_owner" class="st-empty">
      <h3>Bu bo'lim faqat ustaxona egasi uchun</h3>
      <p>Ruxsatlar va sessiyalarni egasi boshqaradi.</p>
    </section>

    <section v-else-if="workshop.loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="workshop.error" class="st-error">
      <h3>Xodimni yuklab bo'lmadi</h3>
      <p>trace_id: {{ workshop.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="!user" class="st-empty">
      <h3>Xodim topilmadi</h3>
    </section>

    <template v-else>
      <div class="page-head mt-2">
        <div>
          <div class="flex items-center gap-4">
            <span
              class="grid size-14 place-items-center rounded-full bg-accent font-serif text-xl font-bold text-white"
            >
              {{ initials(user.full_name, 'U') }}
            </span>
            <div>
              <h1>
                {{ user.full_name }}
                <span v-if="user.is_owner" class="pill p-cut ml-2 align-middle">Egasi</span>
              </h1>
              <p class="sub">
                {{ user.login }} · {{ user.phone }} · {{ branchName(user.home_branch_id) }}
              </p>
            </div>
          </div>
        </div>
        <div class="tools">
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            :disabled="acting"
            @click="resetPassword"
          >
            Parol qaytarish
          </button>
          <button
            v-if="!user.is_owner && user.status === 'active'"
            type="button"
            class="mp-button bg-danger text-white min-h-9 px-3 text-xs"
            :disabled="acting || !canBlock"
            @click="block"
          >
            Bloklash
          </button>
          <button
            v-else-if="!user.is_owner"
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            :disabled="acting || !canUnblock"
            @click="unblock"
          >
            Faollashtirish
          </button>
        </div>
      </div>

      <div class="tabs">
        <button
          class="tab"
          :class="{ on: activeTab === 'profile' }"
          type="button"
          @click="activeTab = 'profile'"
        >
          Profil
        </button>
        <button
          class="tab"
          :class="{ on: activeTab === 'permissions' }"
          type="button"
          @click="activeTab = 'permissions'"
        >
          Ruxsatlar
        </button>
        <button
          class="tab"
          :class="{ on: activeTab === 'sessions' }"
          type="button"
          @click="activeTab = 'sessions'"
        >
          Sessiyalar
        </button>
      </div>

      <section v-if="activeTab === 'profile'" class="grid gap-5 lg:grid-cols-2">
        <div class="card">
          <div class="card-h"><h2>Profil</h2></div>
          <div class="card-b">
            <div class="row-item">
              <div><div class="nm">F.I.O</div></div>
              <div class="meta">{{ user.full_name }}</div>
            </div>
            <div class="row-item">
              <div><div class="nm">Telefon</div></div>
              <div class="meta">{{ user.phone }}</div>
            </div>
            <div class="row-item">
              <div><div class="nm">Login</div></div>
              <div class="meta">{{ user.login }}</div>
            </div>
            <div class="row-item">
              <div><div class="nm">Asosiy filial</div></div>
              <div class="meta">{{ branchName(user.home_branch_id) }}</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-h"><h2>Status</h2></div>
          <div class="card-b">
            <span :class="user.status === 'active' ? 'pill p-ok' : 'pill p-bad'">
              <span class="pd"></span>{{ user.status === 'active' ? 'Faol' : 'Bloklangan' }}
            </span>
            <label v-if="!user.is_owner" class="field mt-4">
              <span>Bloklash sababi</span>
              <input v-model="reason" class="mp-input" placeholder="sessiyalar yopiladi" />
            </label>
            <p v-if="user.is_owner" class="muted mt-4 text-sm">
              Egasi bloklanmaydi va barcha ruxsatlarga ega.
            </p>
          </div>
        </div>
      </section>

      <section v-else-if="activeTab === 'permissions'" class="card">
        <div class="card-h">
          <h2>Ruxsatlar matritsasi</h2>
          <button
            v-if="!user.is_owner"
            type="button"
            class="mp-button mp-button-primary min-h-9 px-3 text-xs"
            :disabled="acting"
            @click="saveGrants"
          >
            Saqlash
          </button>
        </div>
        <div class="card-b">
          <div v-if="user.is_owner" class="banner info">
            <div class="grow">Egasi avtomatik tarzda barcha filialda barcha ruxsatga ega.</div>
          </div>
          <div class="table-wrap">
            <table class="matrix">
              <thead>
                <tr>
                  <th class="permission">Ruxsat</th>
                  <th v-for="branch in workshop.branches" :key="branch.id">{{ branch.name }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="permission in permissionCatalog" :key="permission">
                  <td class="permission">
                    {{ permissionLabels[permission] ?? permission }}
                    <small class="block font-mono text-[10.5px] font-normal text-ink-muted">{{
                      permission
                    }}</small>
                  </td>
                  <td v-for="branch in workshop.branches" :key="branch.id">
                    <input
                      type="checkbox"
                      class="size-4 accent-accent"
                      :checked="user.is_owner || selected.has(grantKey(permission, branch.id))"
                      :disabled="user.is_owner"
                      @change="toggleGrant(permission, branch.id)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section v-else class="card">
        <div class="card-h">
          <h2>Faol sessiyalar</h2>
          <button
            type="button"
            class="mp-button bg-danger text-white min-h-9 px-3 text-xs"
            :disabled="acting || workshop.sessions.length === 0"
            @click="revokeAllSessions"
          >
            Hammasi yopilsin
          </button>
        </div>
        <div class="card-b">
          <div v-if="workshop.sessions.length === 0" class="st-empty !border-0 !py-8">
            <h3>Faol sessiya yo'q</h3>
          </div>
          <div v-for="session in workshop.sessions" v-else :key="session.id" class="row-item">
            <div>
              <div class="nm">
                {{ session.device_info?.browser ?? 'Qurilma' }}
                <span v-if="session.is_current" class="pill p-ok ml-1">Joriy</span>
              </div>
              <small class="text-ink-muted">
                Yaratildi {{ formatDate(session.created_at) }} · oxirgi
                {{ formatDate(session.last_used_at) }}
              </small>
            </div>
            <div class="meta">
              <button
                type="button"
                class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                :disabled="acting"
                @click="revokeSession(session.id)"
              >
                Yopish
              </button>
            </div>
          </div>
        </div>
      </section>

      <div v-if="workshop.lastTempPassword" class="banner info mt-4">
        <div class="grow">
          <b>Yangi vaqtinchalik parol:</b>
          <span class="font-mono">{{ workshop.lastTempPassword }}</span>
        </div>
      </div>
      <div v-if="actionError" class="banner danger mt-4">
        <div class="grow">{{ actionError }}</div>
      </div>
    </template>
  </section>
</template>
