<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import {
  grantSummary,
  initials,
  permissionLabels,
  workshopErrorMessage,
} from '@/shared/app/workshopUi'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatDate } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { permissionCatalog, useWorkshopStore } from '@/shared/stores/workshop'

const auth = useAuthStore()
const workshop = useWorkshopStore()
const toast = useToast()
const rolePath = useRolePath()
const route = useRoute()
const showCreate = ref(false)
const creating = ref(false)
const createError = ref<string | null>(null)
const createTraceId = ref<string | null>(null)
const search = ref('')
const branchFilter = ref('all')
const statusFilter = ref('all')
const selected = ref<Set<string>>(new Set())
let usersSearchTimer: number | undefined
const form = reactive({
  fullName: '',
  phone: '+998',
  login: '',
  homeBranchId: '',
  tempPassword: '',
})

const branchOptions = computed(() => [
  { value: '', label: 'Asosiy filial yo`q', meta: 'ixtiyoriy', status: 'pending' as const },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  })),
])
const branchFilterOptions = computed(() => [
  {
    value: 'all',
    label: 'Barcha filiallar',
    meta: `${workshop.branches.length} filial`,
    status: 'active' as const,
  },
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  })),
])
const statusOptions = [
  { value: 'all', label: 'Hammasi', meta: 'barcha xodimlar', status: 'active' as const },
  { value: 'active', label: 'Faol', meta: 'kirishi mumkin', status: 'active' as const },
  {
    value: 'blocked',
    label: 'Bloklangan',
    meta: 'kirishi to`xtatilgan',
    status: 'blocked' as const,
  },
]
function branchName(id: string | null) {
  if (!id) return '—'
  return workshop.branches.find((branch) => branch.id === id)?.name ?? 'Filial'
}

function lastLoginLabel(value: string | null) {
  return value ? formatDate(value) : "Hali yo'q"
}

function userFilters() {
  return {
    search: search.value.trim(),
    branch_id: branchFilter.value === 'all' ? null : branchFilter.value,
    status: statusFilter.value === 'all' ? null : (statusFilter.value as 'active' | 'blocked'),
  }
}

async function refreshUsers() {
  if (!auth.me?.is_owner) return
  await workshop.loadUsers({ filters: userFilters() })
}

function scheduleUsersRefresh() {
  window.clearTimeout(usersSearchTimer)
  usersSearchTimer = window.setTimeout(() => void refreshUsers(), 250)
}

function routeSearchValue() {
  const value = route.query.search
  return typeof value === 'string' ? value : ''
}

function applyRouteSearch() {
  const value = routeSearchValue()
  if (value !== search.value) search.value = value
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

watch(
  () => route.query.search,
  () => {
    applyRouteSearch()
  },
)

watch(search, scheduleUsersRefresh)

watch([branchFilter, statusFilter], () => {
  void refreshUsers()
})

async function createStaff() {
  creating.value = true
  createError.value = null
  createTraceId.value = null
  try {
    await workshop.createUser({
      full_name: form.fullName,
      phone: form.phone,
      login: form.login,
      home_branch_id: form.homeBranchId || null,
      temp_password: form.tempPassword || undefined,
      grants: [...selected.value].map((value) => {
        const [permission, branch_id] = value.split('|')
        return { permission, branch_id }
      }),
    })
    form.fullName = ''
    form.phone = '+998'
    form.login = ''
    form.homeBranchId = ''
    form.tempPassword = ''
    selected.value = new Set()
    showCreate.value = false
    toast.success("Xodim qo'shildi.")
  } catch {
    createError.value = workshopErrorMessage(workshop.actionError ?? 'user_create_failed')
    createTraceId.value = workshop.actionTraceId
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  if (auth.me?.is_owner) void refreshUsers()
})

onBeforeUnmount(() => {
  window.clearTimeout(usersSearchTimer)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Xodimlar</h1>
        <p class="sub">Ustaxona xodimlari · ruxsatlar. Faqat egasi yangi xodim qo'shadi.</p>
      </div>
      <div class="tools">
        <button
          v-if="auth.me?.is_owner"
          type="button"
          class="mp-button mp-button-primary"
          @click="showCreate = !showCreate"
        >
          Yangi xodim
        </button>
      </div>
    </div>

    <section v-if="!auth.me?.is_owner" class="st-empty">
      <h3>Bu bo'lim faqat ustaxona egasi uchun</h3>
      <p>Xodimlar va ruxsatlar matritsasini egasi boshqaradi.</p>
    </section>

    <template v-else>
      <section v-if="showCreate" class="card mb-5">
        <div class="card-h">
          <h2>Yangi xodim</h2>
          <button
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="showCreate = false"
          >
            Bekor
          </button>
        </div>
        <form class="card-b grid gap-4" @submit.prevent="createStaff">
          <div class="grid gap-3 md:grid-cols-2">
            <label class="field">
              <span>F.I.O</span>
              <input v-model="form.fullName" class="mp-input" autocomplete="name" required />
            </label>
            <label class="field">
              <span>Telefon</span>
              <input
                v-model="form.phone"
                class="mp-input"
                autocomplete="tel"
                inputmode="tel"
                required
              />
            </label>
            <label class="field">
              <span>Login</span>
              <input v-model="form.login" class="mp-input" autocomplete="username" required />
            </label>
            <ProjectDropdown
              v-model="form.homeBranchId"
              label="Asosiy filial"
              :options="branchOptions"
            />
            <label class="field md:col-span-2">
              <span>Vaqtinchalik parol</span>
              <input
                v-model="form.tempPassword"
                class="mp-input"
                autocomplete="new-password"
                placeholder="bo'sh qoldirilsa avtomatik yaratiladi"
              />
            </label>
          </div>

          <div class="banner info">
            <div class="grow">
              Vaqtinchalik parol faqat 1 marta ko'rsatiladi. Xodim kirgandan keyin parolni yangilash
              haqida ogohlantirish ko'radi.
            </div>
          </div>

          <div>
            <h3 class="mb-2 text-xs font-extrabold uppercase tracking-[0.12em] text-ink-muted">
              Boshlang'ich ruxsatlar
            </h3>
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
                        :aria-label="`${permissionLabels[permission] ?? permission} — ${branch.name}`"
                        :checked="selected.has(grantKey(permission, branch.id))"
                        @change="toggleGrant(permission, branch.id)"
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <button class="mp-button mp-button-primary" type="submit" :disabled="creating">
            {{ creating ? 'Yaratilmoqda' : 'Yaratish' }}
          </button>
          <p
            v-if="createError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            {{ createError }} · trace_id: {{ createTraceId ?? 'unavailable' }}
          </p>
        </form>
      </section>

      <div v-if="workshop.lastTempPassword" class="banner info">
        <div class="grow">
          <b>Vaqtinchalik parol:</b>
          <span class="font-mono">{{ workshop.lastTempPassword }}</span>
        </div>
      </div>

      <div class="filters">
        <label class="field">
          <span>Qidirish</span>
          <input v-model="search" class="mp-input min-w-64" placeholder="Ism yoki login..." />
        </label>
        <ProjectDropdown v-model="branchFilter" label="Filial" :options="branchFilterOptions" />
        <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" />
      </div>

      <section v-if="workshop.loading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="workshop.error" class="st-error">
        <h3>Xodimlarni yuklab bo'lmadi</h3>
        <p>trace_id: {{ workshop.traceId ?? 'unavailable' }}</p>
      </section>

      <section v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Xodim</th>
                <th>Login</th>
                <th>Asosiy filial</th>
                <th>Ruxsatlar</th>
                <th>Oxirgi kirish</th>
                <th>Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in workshop.users" :key="user.id" class="clickable">
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="user-avatar">{{ initials(user.full_name, 'U') }}</span>
                    <span class="min-w-0">
                      <span class="nm">
                        {{ user.full_name }}
                        <span v-if="user.is_owner" class="pill p-cut ml-1">Egasi</span>
                      </span>
                      <small class="block truncate text-ink-muted">{{ user.phone }}</small>
                    </span>
                  </div>
                </td>
                <td class="num">{{ user.login }}</td>
                <td>{{ branchName(user.home_branch_id) }}</td>
                <td>
                  <small class="text-ink-soft">{{
                    grantSummary(user.is_owner, user.grants)
                  }}</small>
                </td>
                <td class="num text-ink-muted">{{ lastLoginLabel(user.last_login_at) }}</td>
                <td>
                  <span :class="user.status === 'active' ? 'pill p-ok' : 'pill p-bad'">
                    <span class="pd"></span>{{ user.status === 'active' ? 'Faol' : 'Bloklangan' }}
                  </span>
                </td>
                <td class="right">
                  <RouterLink
                    :to="rolePath(`/workshop/settings/users/${user.id}`)"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  >
                    Tahrir
                  </RouterLink>
                </td>
              </tr>
              <tr v-if="workshop.users.length === 0">
                <td colspan="7">
                  <div class="st-empty !border-0 !py-8"><h3>Mos xodim topilmadi</h3></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
