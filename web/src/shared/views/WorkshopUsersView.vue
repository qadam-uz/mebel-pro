<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  tempPassword,
  type FieldErrors,
  uzPhone,
} from '@/shared/app/adminValidation'
import { copyText } from '@/shared/app/clipboard'
import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
import { useRolePath } from '@/shared/app/paths'
import type { DropdownOption } from '@/shared/app/roleConfig'
import {
  grantSummary,
  initials,
  loginPrefix,
  permissionLabels,
  workshopErrorMessage,
} from '@/shared/app/workshopUi'
import AppModal from '@/shared/components/AppModal.vue'
import MultiSelectFilter from '@/shared/components/MultiSelectFilter.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import FilterStatus from '@/shared/components/FilterStatus.vue'
import ProjectDropdown from '@/shared/components/ProjectDropdown.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatDate } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { permissionCatalog, useWorkshopStore } from '@/shared/stores/workshop'

type StaffField = 'fullName' | 'phone' | 'login' | 'branches' | 'tempPassword'

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

// The reset-all appears from the second active filter on — with one, it would
// duplicate that filter's own clear sitting right beside it (DESIGN.md).
const activeUserFilterCount = computed(
  () =>
    (search.value.trim() ? 1 : 0) +
    (branchFilter.value === 'all' ? 0 : 1) +
    (statusFilter.value === 'all' ? 0 : 1),
)

function resetUserFilters() {
  search.value = ''
  branchFilter.value = 'all'
  statusFilter.value = 'all'
}
const selected = ref<Set<string>>(new Set())
const createdTempPassword = ref<string | null>(null)
const copiedTempPassword = ref(false)
let usersSearchTimer: number | undefined
let copiedResetTimer: number | undefined

// Copy the freshly generated temp password to the clipboard. copyText guards
// insecure contexts / older browsers and returns false, in which case the mono
// value stays select-all so the owner can still copy it by hand.
async function copyTempPassword(value: string | null) {
  if (!value) return
  const ok = await copyText(value)
  if (!ok) {
    toast.danger("Nusxalab bo'lmadi. Parolni belgilab, qo'lda nusxalang.")
    return
  }
  toast.success('Parol nusxalandi.')
  copiedTempPassword.value = true
  window.clearTimeout(copiedResetTimer)
  copiedResetTimer = window.setTimeout(() => {
    copiedTempPassword.value = false
  }, 1800)
}
const form = reactive({
  fullName: '',
  phone: '',
  login: '',
  branchIds: [] as string[],
  tempPassword: '',
})
const staffFieldErrors = reactive<FieldErrors<StaffField>>({})
const staffFieldOrder: StaffField[] = ['fullName', 'phone', 'login', 'branches', 'tempPassword']
const staffFieldIds: Record<StaffField, string> = {
  fullName: 'staff-full-name',
  phone: 'staff-phone',
  login: 'staff-login',
  branches: 'staff-branches',
  tempPassword: 'staff-temp-password',
}

const branchOptions = computed(() => [
  ...workshop.branches.map((branch) => ({
    value: branch.id,
    label: branch.name,
    meta: branch.address,
    status: branch.status === 'active' ? ('active' as const) : ('pending' as const),
  })),
])
const branchFilterOptions = computed<DropdownOption[]>(() => [
  { value: 'all', label: 'Barcha filiallar' },
  ...workshop.branches.map((branch) => ({ value: branch.id, label: branch.name })),
])
const statusOptions: DropdownOption[] = [
  { value: 'all', label: 'Hammasi' },
  { value: 'active', label: 'Faol', dot: 'success' },
  { value: 'blocked', label: 'Bloklangan', dot: 'danger' },
]
const createGrantBranches = computed(() =>
  workshop.branches.filter((branch) => form.branchIds.includes(branch.id)),
)
// The home branch (cutter/edger assignment home) is the FIRST selected branch.
// Surface it explicitly so the derived value is never silently wrong when the
// selection order changes.
const homeBranchName = computed(() =>
  form.branchIds.length ? branchName(form.branchIds[0]) : null,
)

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

function defaultHomeBranchId() {
  const selectedBranch = workshop.branches.find(
    (branch) => branch.id === workshop.selectedBranchContext,
  )
  return (
    selectedBranch?.id ??
    workshop.branches.find((branch) => branch.status === 'active')?.id ??
    workshop.branches[0]?.id ??
    ''
  )
}

function defaultBranchIds() {
  const branchId = defaultHomeBranchId()
  return branchId ? [branchId] : []
}

function ensureCreateBranches() {
  const valid = new Set(workshop.branches.map((branch) => branch.id))
  form.branchIds = form.branchIds.filter((branchId) => valid.has(branchId))
  if (form.branchIds.length === 0) form.branchIds = defaultBranchIds()
}

// Logins are unique platform-wide, so a bare "admin" is usually taken by now.
// Prefill the workshop's own prefix and drop the caret after it: the owner types
// "akmal" and gets "mebelmaster_akmal". Editable and clearable — never enforced.
const suggestedLoginPrefix = computed(() => loginPrefix(workshop.settings?.name))

function resetLoginToPrefix() {
  form.login = suggestedLoginPrefix.value
}

// Focusing an input by Tab selects its whole value in most browsers, so the
// first keystroke would wipe the suggestion. While the field still holds nothing
// but the untouched prefix, collapse the caret to the end so typing extends it.
// Once the owner has edited the value, focus behaves natively again — select-all
// and replace has to keep working.
function collapseLoginCaret(event: FocusEvent) {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) return
  if (!suggestedLoginPrefix.value || input.value !== suggestedLoginPrefix.value) return
  const caret = input.value.length
  input.setSelectionRange(caret, caret)
}

function openCreateForm() {
  ensureCreateBranches()
  if (!form.login) resetLoginToPrefix()
  showCreate.value = true
}

function validateCreateStaff() {
  clearFieldErrors(staffFieldErrors)
  staffFieldErrors.fullName = requiredText(form.fullName) ?? undefined
  staffFieldErrors.phone = requiredText(form.phone) ?? uzPhone(form.phone) ?? undefined
  staffFieldErrors.login = requiredText(form.login) ?? undefined
  staffFieldErrors.branches = form.branchIds.length > 0 ? undefined : 'Kamida bitta filial tanlang.'
  staffFieldErrors.tempPassword = tempPassword(form.tempPassword) ?? undefined
  const hasErrors = staffFieldOrder.some((field) => Boolean(staffFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(staffFieldErrors, staffFieldOrder, staffFieldIds)
  return !hasErrors
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

// A rejected login is only rejected as typed — editing it clears the verdict,
// so the field never argues with what the owner is currently looking at.
watch(
  () => form.login,
  () => {
    staffFieldErrors.login = undefined
  },
)

watch(
  () => form.branchIds.slice(),
  (branchIds) => {
    const allowed = new Set(branchIds)
    selected.value = new Set(
      [...selected.value].filter((value) => allowed.has(value.split('|')[1] ?? '')),
    )
    staffFieldErrors.branches = undefined
  },
)

async function createStaff() {
  ensureCreateBranches()
  if (!validateCreateStaff()) return
  creating.value = true
  createError.value = null
  createTraceId.value = null
  createdTempPassword.value = null
  try {
    const created = await workshop.createUser({
      full_name: form.fullName,
      phone: form.phone,
      login: form.login,
      home_branch_id: form.branchIds[0],
      temp_password: form.tempPassword || undefined,
      grants: [...selected.value].map((value) => {
        const [permission, branch_id] = value.split('|')
        return { permission, branch_id }
      }),
    })
    form.fullName = ''
    form.phone = ''
    resetLoginToPrefix()
    form.branchIds = defaultBranchIds()
    form.tempPassword = ''
    selected.value = new Set()
    showCreate.value = false
    createdTempPassword.value = created.temp_password
    toast.success("Xodim qo'shildi.")
  } catch (caught) {
    Object.assign(
      staffFieldErrors,
      fieldErrorsFromApi<StaffField>(
        caught,
        {
          full_name_required: 'fullName',
          invalid_phone: 'phone',
          login_required: 'login',
          home_branch_required: 'branches',
          branch_not_found: 'branches',
          weak_password: 'tempPassword',
          login_exists: 'login',
        },
        {
          full_name: 'fullName',
          phone: 'phone',
          login: 'login',
          home_branch_id: 'branches',
          temp_password: 'tempPassword',
        },
      ),
    )
    if (staffFieldOrder.some((field) => Boolean(staffFieldErrors[field]))) {
      focusFirstFieldError(staffFieldErrors, staffFieldOrder, staffFieldIds)
    }
    // A taken login is fully explained on the field itself — a second, vaguer
    // banner under the submit button would only compete with it.
    if (apiErrorCode(caught) === 'login_exists') return
    createError.value = workshopErrorMessage(workshop.actionError ?? 'user_create_failed')
    createTraceId.value = workshop.actionTraceId
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  applyRouteSearch()
  await workshop.loadBranchContext().catch(() => undefined)
  ensureCreateBranches()
  if (!auth.me?.is_owner) return
  // Owner-only endpoint; the workshop name feeds the login prefix suggestion.
  await workshop.loadSettings().catch(() => undefined)
  void refreshUsers()
})

onBeforeUnmount(() => {
  window.clearTimeout(usersSearchTimer)
  window.clearTimeout(copiedResetTimer)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Xodimlar</h1>
      </div>
    </div>

    <section v-if="!auth.me?.is_owner" class="st-empty">
      <h3>Bu bo'lim faqat ustaxona rahbari uchun</h3>
      <p>Xodimlar va ruxsatlar matritsasini rahbar boshqaradi.</p>
    </section>

    <template v-else>
      <AppModal
        :open="showCreate"
        title="Yangi xodim"
        max-width="max-w-2xl"
        @close="showCreate = false"
      >
        <!-- grid-cols-1 pins the track to minmax(0,1fr) so the 720px-min permission
             matrix h-scrolls inside its table-wrap instead of widening the modal. -->
        <form class="grid grid-cols-1 gap-4" novalidate @submit.prevent="createStaff">
          <div class="grid gap-3 md:grid-cols-2">
            <label class="field" for="staff-full-name">
              <span>F.I.O</span>
              <input
                id="staff-full-name"
                v-model="form.fullName"
                class="mp-input"
                autocomplete="name"
                required
                :aria-invalid="!!staffFieldErrors.fullName"
                :aria-describedby="staffFieldErrors.fullName ? 'staff-full-name-error' : undefined"
              />
              <span
                v-if="staffFieldErrors.fullName"
                id="staff-full-name-error"
                class="mp-field-error"
              >
                {{ staffFieldErrors.fullName }}
              </span>
            </label>
            <label class="field" for="staff-phone">
              <span>Telefon</span>
              <PhoneInput
                id="staff-phone"
                v-model="form.phone"
                required
                :aria-invalid="!!staffFieldErrors.phone"
                :aria-describedby="staffFieldErrors.phone ? 'staff-phone-error' : undefined"
              />
              <span v-if="staffFieldErrors.phone" id="staff-phone-error" class="mp-field-error">
                {{ staffFieldErrors.phone }}
              </span>
            </label>
            <label class="field" for="staff-login">
              <span>Login</span>
              <input
                id="staff-login"
                v-model="form.login"
                class="mp-input"
                autocomplete="username"
                required
                :aria-invalid="!!staffFieldErrors.login"
                :aria-describedby="
                  staffFieldErrors.login ? 'staff-login-error' : 'staff-login-hint'
                "
                @focus="collapseLoginCaret"
              />
              <span v-if="!staffFieldErrors.login" id="staff-login-hint" class="mp-field-hint">
                Ustaxona prefiksi — o'zgartirish mumkin.
              </span>
              <span v-if="staffFieldErrors.login" id="staff-login-error" class="mp-field-error">
                {{ staffFieldErrors.login }}
              </span>
            </label>
            <div class="grid gap-1">
              <MultiSelectFilter
                id="staff-branches"
                v-model="form.branchIds"
                label="Filiallar"
                :options="branchOptions"
                empty-label="Filial tanlang"
                selected-label="filial tanlandi"
                :error="staffFieldErrors.branches"
                required
              />
              <p v-if="homeBranchName" class="text-xs text-ink-soft">
                Asosiy filial: <b class="text-ink">{{ homeBranchName }}</b> (birinchi tanlangan)
              </p>
            </div>
            <label class="field md:col-span-2" for="staff-temp-password">
              <span>Vaqtinchalik parol</span>
              <input
                id="staff-temp-password"
                v-model="form.tempPassword"
                class="mp-input"
                autocomplete="new-password"
                placeholder="Bo'sh qoldirilsa avtomatik yaratiladi"
                :aria-invalid="!!staffFieldErrors.tempPassword"
                :aria-describedby="
                  staffFieldErrors.tempPassword ? 'staff-temp-password-error' : undefined
                "
              />
              <span
                v-if="staffFieldErrors.tempPassword"
                id="staff-temp-password-error"
                class="mp-field-error"
              >
                {{ staffFieldErrors.tempPassword }}
              </span>
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
            <div v-if="createGrantBranches.length > 0" class="table-wrap">
              <table class="matrix">
                <thead>
                  <tr>
                    <th class="permission">Ruxsat</th>
                    <th v-for="branch in createGrantBranches" :key="branch.id">
                      {{ branch.name }}
                    </th>
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
                    <td v-for="branch in createGrantBranches" :key="branch.id">
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
            <div v-else class="st-empty !border-0 !py-6">
              <h3>Filial tanlang</h3>
            </div>
          </div>

          <button class="mp-button mp-button-primary" type="submit" :disabled="creating">
            {{ creating ? "Qo'shilmoqda" : "Qo'shish" }}
          </button>
          <p
            v-if="createError"
            class="rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
          >
            {{ createError }}{{ traceSuffix(createTraceId) }}
          </p>
        </form>
      </AppModal>

      <div v-if="createdTempPassword" class="banner info" role="status">
        <div class="grow">
          <b>Vaqtinchalik parol</b>
          <div class="mt-1.5 flex flex-wrap items-center gap-2">
            <span
              class="select-all rounded bg-white px-2.5 py-1 font-mono text-base font-bold text-ink"
            >
              {{ createdTempPassword }}
            </span>
            <button
              type="button"
              class="mp-button mp-button-outline min-h-9 px-3 text-xs"
              @click="copyTempPassword(createdTempPassword)"
            >
              {{ copiedTempPassword ? 'Nusxalandi' : 'Nusxalash' }}
            </button>
          </div>
          <p class="mt-1.5 text-xs">
            Bu parol faqat 1 marta ko'rsatiladi — xodimga yetkazib qo'ying.
          </p>
        </div>
      </div>

      <div class="mp-filters">
        <label class="mp-filter-input">
          <span>Qidirish</span>
          <input v-model="search" placeholder="Ism yoki login" />
        </label>
        <ProjectDropdown
          v-model="branchFilter"
          label="Filial"
          :options="branchFilterOptions"
          top-label
        />
        <ProjectDropdown v-model="statusFilter" label="Holat" :options="statusOptions" top-label />
        <button type="button" class="mp-button mp-button-primary" @click="openCreateForm">
          + Yangi xodim
        </button>
      </div>

      <FilterStatus
        :active="activeUserFilterCount > 0"
        :loading="workshop.loading"
        :count="workshop.users.length"
        noun="xodim"
        :on-reset="activeUserFilterCount > 1 ? resetUserFilters : null"
      />

      <section v-if="workshop.loading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="workshop.error" class="st-error">
        <h3>Xodimlarni yuklab bo'lmadi</h3>
        <p>{{ traceLine(workshop.traceId) }}</p>
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
              <tr v-for="user in workshop.users" :key="user.id">
                <td>
                  <div class="flex min-w-0 items-center gap-3">
                    <span class="user-avatar">{{ initials(user.full_name, 'U') }}</span>
                    <span class="min-w-0">
                      <span class="nm">
                        {{ user.full_name }}
                        <span v-if="user.is_owner" class="pill p-cut ml-1">Rahbar</span>
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
                    Ochish
                  </RouterLink>
                </td>
              </tr>
              <tr v-if="workshop.users.length === 0">
                <td colspan="7">
                  <div class="st-empty !border-0 !py-8">
                    <h3>{{ search.trim() ? 'Mos xodim topilmadi' : "Hali xodim yo'q" }}</h3>
                    <p>
                      {{
                        search.trim()
                          ? "Ism yoki login bo'yicha qidiruvni o'zgartiring."
                          : "«+ Yangi xodim» orqali birinchi xodimni qo'shing."
                      }}
                    </p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
