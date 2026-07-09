<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { apiTraceId } from '@/shared/api/client'
import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
  uzPhone,
} from '@/shared/app/adminValidation'
import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import { useRolePath } from '@/shared/app/paths'
import { branchPillClass, branchStatusUz } from '@/shared/app/workshopUi'
import FormSelect from '@/shared/components/FormSelect.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatTiyin, parseSomToTiyin } from '@/shared/formatters'
import { useWorkshopStore } from '@/shared/stores/workshop'

type WorkingDay = {
  key: string
  label: string
  open: boolean
  from: string
  to: string
}
type BranchField = 'name' | 'address' | 'phone' | 'cuttingRate' | 'edgeBandingRate'
type StatusField = 'reason'

const route = useRoute()
const rolePath = useRolePath()
const workshop = useWorkshopStore()
const toast = useToast()
const branchId = computed(() => String(route.params.branch_id ?? ''))
const loading = ref(false)
const pageError = ref<string | null>(null)
const pageTraceId = ref<string | null>(null)
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveTraceId = ref<string | null>(null)
const saved = ref(false)
const statusSaving = ref(false)
const statusError = ref<string | null>(null)
const statusTraceId = ref<string | null>(null)
const statusSaved = ref(false)

const branchForm = reactive({
  name: '',
  address: '',
  phone: '',
})
const pricingForm = reactive({
  cuttingRateSom: '',
  edgeBandingRateSom: '',
})
// Rates are optional (empty = "not set"), but a non-empty value must parse via
// the strict so'm parser — bare Number() read "12.500" as 12,5 so'm (1000x) and
// turned "12 500" into NaN that silently cleared the rate on save.
const cuttingRateTiyin = computed(() =>
  pricingForm.cuttingRateSom.trim() ? parseSomToTiyin(pricingForm.cuttingRateSom) : null,
)
const edgeBandingRateTiyin = computed(() =>
  pricingForm.edgeBandingRateSom.trim() ? parseSomToTiyin(pricingForm.edgeBandingRateSom) : null,
)

// Type-time sanitization (PhoneInput precedent) — invalid characters never stick.
watch(
  () => pricingForm.cuttingRateSom,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) pricingForm.cuttingRateSom = clean
  },
)
watch(
  () => pricingForm.edgeBandingRateSom,
  (value) => {
    const clean = sanitizeMoneyInput(value)
    if (clean !== value) pricingForm.edgeBandingRateSom = clean
  },
)
const statusForm = reactive({
  status: 'active',
  reason: '',
})
const branchFieldErrors = reactive<FieldErrors<BranchField>>({})
const branchFieldOrder: BranchField[] = [
  'name',
  'address',
  'phone',
  'cuttingRate',
  'edgeBandingRate',
]
const branchFieldIds: Record<BranchField, string> = {
  name: 'branch-detail-name',
  address: 'branch-detail-address',
  phone: 'branch-detail-phone',
  cuttingRate: 'branch-detail-cutting-rate',
  edgeBandingRate: 'branch-detail-edge-rate',
}
const statusFieldErrors = reactive<FieldErrors<StatusField>>({})
const statusFieldOrder: StatusField[] = ['reason']
const statusFieldIds: Record<StatusField, string> = {
  reason: 'branch-status-reason',
}
const hours = reactive<WorkingDay[]>([
  { key: 'monday', label: 'Du', open: true, from: '09:00', to: '18:00' },
  { key: 'tuesday', label: 'Se', open: true, from: '09:00', to: '18:00' },
  { key: 'wednesday', label: 'Cho', open: true, from: '09:00', to: '18:00' },
  { key: 'thursday', label: 'Pa', open: true, from: '09:00', to: '18:00' },
  { key: 'friday', label: 'Ju', open: true, from: '09:00', to: '18:00' },
  { key: 'saturday', label: 'Sha', open: true, from: '10:00', to: '16:00' },
  { key: 'sunday', label: 'Yak', open: false, from: '10:00', to: '16:00' },
])
const statusOptions = [
  { value: 'active', label: 'Faol', meta: "mijozlarga ko'rinadi" },
  { value: 'temporarily_closed', label: 'Vaqtincha yopiq', meta: 'sabab bilan ko`rinadi' },
  { value: 'inactive', label: 'Faol emas', meta: 'mijozlardan yashirilgan' },
]

function workingHoursPayload() {
  return Object.fromEntries(
    hours.map((day) => [
      day.key,
      day.open ? { open: day.from, close: day.to } : { open: null, close: null },
    ]),
  )
}

function validateBranchForm() {
  clearFieldErrors(branchFieldErrors)
  branchFieldErrors.name = requiredText(branchForm.name) ?? undefined
  branchFieldErrors.address = requiredText(branchForm.address) ?? undefined
  branchFieldErrors.phone = requiredText(branchForm.phone) ?? uzPhone(branchForm.phone) ?? undefined
  branchFieldErrors.cuttingRate =
    pricingForm.cuttingRateSom.trim() && cuttingRateTiyin.value === null
      ? "Kesish narxini to'g'ri kiriting — masalan: 25 000."
      : undefined
  branchFieldErrors.edgeBandingRate =
    pricingForm.edgeBandingRateSom.trim() && edgeBandingRateTiyin.value === null
      ? "Krom narxini to'g'ri kiriting — masalan: 5 000."
      : undefined
  const hasErrors = branchFieldOrder.some((field) => Boolean(branchFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(branchFieldErrors, branchFieldOrder, branchFieldIds)
  return !hasErrors
}

function validateStatusForm() {
  clearFieldErrors(statusFieldErrors)
  if (statusForm.status !== 'active') {
    statusFieldErrors.reason = requiredText(statusForm.reason) ?? undefined
  }
  const hasErrors = statusFieldOrder.some((field) => Boolean(statusFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(statusFieldErrors, statusFieldOrder, statusFieldIds)
  return !hasErrors
}

function syncForms() {
  const branch = workshop.selectedBranch
  if (!branch) return
  branchForm.name = branch.name
  branchForm.address = branch.address
  branchForm.phone = branch.phone
  statusForm.status = branch.status
  statusForm.reason = branch.closed_reason ?? ''
  for (const day of hours) {
    const raw = branch.working_hours[day.key]
    const entry = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : null
    const open = typeof entry?.open === 'string' ? entry.open : ''
    const close = typeof entry?.close === 'string' ? entry.close : ''
    day.open = Boolean(open && close)
    if (open) day.from = open
    if (close) day.to = close
  }
  // The rate fields are entered in so'm; the backend stores tiyin (1 so'm = 100
  // tiyin). Show so'm on load; convert back on submit.
  const pricing = workshop.selectedBranchPricing
  pricingForm.cuttingRateSom =
    pricing?.cutting_rate_tiyin != null ? String(pricing.cutting_rate_tiyin / 100) : ''
  pricingForm.edgeBandingRateSom =
    pricing?.edge_banding_rate_tiyin != null ? String(pricing.edge_banding_rate_tiyin / 100) : ''
}

async function refreshBranch() {
  if (!branchId.value) return
  loading.value = true
  pageError.value = null
  pageTraceId.value = null
  try {
    await workshop.loadBranchContext()
    workshop.setSelectedBranchContext(branchId.value)
    await workshop.loadBranch(branchId.value)
    syncForms()
  } catch {
    pageError.value = 'branch_detail_load_failed'
    pageTraceId.value = workshop.traceId ?? workshop.setupTraceId
  } finally {
    loading.value = false
  }
}

async function saveBranch() {
  if (!validateBranchForm()) return
  saving.value = true
  saveError.value = null
  saveTraceId.value = null
  saved.value = false
  try {
    await workshop.updateBranch(branchId.value, {
      name: branchForm.name,
      address: branchForm.address,
      phone: branchForm.phone,
      working_hours: workingHoursPayload(),
    })
    await workshop.updateBranchPricing(branchId.value, {
      cutting_rate_tiyin: cuttingRateTiyin.value,
      edge_banding_rate_tiyin: edgeBandingRateTiyin.value,
    })
    saved.value = true
    toast.success('Filial saqlandi.')
  } catch (caught) {
    Object.assign(
      branchFieldErrors,
      fieldErrorsFromApi<BranchField>(
        caught,
        {
          branch_name_required: 'name',
          branch_address_required: 'address',
          invalid_phone: 'phone',
        },
        {
          name: 'name',
          address: 'address',
          phone: 'phone',
        },
      ),
    )
    if (branchFieldOrder.some((field) => Boolean(branchFieldErrors[field]))) {
      focusFirstFieldError(branchFieldErrors, branchFieldOrder, branchFieldIds)
    }
    saveError.value = 'branch_save_failed'
    saveTraceId.value = apiTraceId(caught)
  } finally {
    saving.value = false
  }
}

async function changeBranchStatus() {
  if (!validateStatusForm()) return
  statusSaving.value = true
  statusError.value = null
  statusTraceId.value = null
  statusSaved.value = false
  try {
    await workshop.setBranchStatus(branchId.value, {
      status: statusForm.status,
      reason: statusForm.status === 'active' ? null : statusForm.reason,
    })
    syncForms()
    statusSaved.value = true
    toast.success("Filial holati o'zgartirildi.")
  } catch (caught) {
    Object.assign(
      statusFieldErrors,
      fieldErrorsFromApi<StatusField>(caught, { reason_required: 'reason' }, { reason: 'reason' }),
    )
    if (statusFieldErrors.reason) {
      focusFirstFieldError(statusFieldErrors, statusFieldOrder, statusFieldIds)
    }
    statusError.value = 'branch_status_failed'
    statusTraceId.value = apiTraceId(caught)
  } finally {
    statusSaving.value = false
  }
}

watch(branchId, refreshBranch)
watch(
  () => statusForm.status,
  () => {
    clearFieldErrors(statusFieldErrors)
    statusSaved.value = false
  },
)
onMounted(refreshBranch)
</script>

<template>
  <section>
    <RouterLink :to="rolePath('/workshop/branches')" class="back">← Filiallar</RouterLink>
    <div class="page-head">
      <div>
        <h1>{{ workshop.selectedBranch?.name ?? 'Filial' }}</h1>
      </div>
      <span
        v-if="workshop.selectedBranch"
        class="mp-chip"
        :class="branchPillClass(workshop.selectedBranch.status)"
      >
        <span class="pd"></span>{{ branchStatusUz[workshop.selectedBranch.status] }}
      </span>
    </div>

    <section v-if="loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="pageError" class="st-error" role="alert">
      <h3>Filialni yuklab bo'lmadi</h3>
      <p>Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="loading"
        @click="refreshBranch"
      >
        Qayta urinish
      </button>
      <p v-if="pageTraceId" class="mt-3 text-xs text-ink-muted">trace_id: {{ pageTraceId }}</p>
    </section>

    <template v-else-if="workshop.selectedBranch">
      <div
        v-if="workshop.selectedBranch.status === 'temporarily_closed'"
        class="banner warn mb-5"
        role="status"
      >
        <div class="grow">
          <b>Vaqtincha yopiq</b>
          <span v-if="workshop.selectedBranch.closed_reason">
            · {{ workshop.selectedBranch.closed_reason }}
          </span>
        </div>
      </div>
      <div v-else-if="workshop.selectedBranch.status === 'inactive'" class="banner danger mb-5">
        <div class="grow"><b>Faol emas</b> · bu filial yangi buyurtma qabul qilmaydi.</div>
      </div>

      <form class="card max-w-[1120px]" novalidate @submit.prevent="saveBranch">
        <div class="card-h">
          <h2>Filial ma'lumotlari</h2>
        </div>
        <div class="card-b grid gap-3">
          <div class="grid gap-3 md:grid-cols-2">
            <label class="field" for="branch-detail-name">
              <span>Nom</span>
              <input
                id="branch-detail-name"
                v-model="branchForm.name"
                class="mp-input"
                required
                :aria-invalid="!!branchFieldErrors.name"
                :aria-describedby="branchFieldErrors.name ? 'branch-detail-name-error' : undefined"
              />
              <span
                v-if="branchFieldErrors.name"
                id="branch-detail-name-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.name }}
              </span>
            </label>
            <label class="field" for="branch-detail-address">
              <span>Manzil</span>
              <input
                id="branch-detail-address"
                v-model="branchForm.address"
                class="mp-input"
                required
                :aria-invalid="!!branchFieldErrors.address"
                :aria-describedby="
                  branchFieldErrors.address ? 'branch-detail-address-error' : undefined
                "
              />
              <span
                v-if="branchFieldErrors.address"
                id="branch-detail-address-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.address }}
              </span>
            </label>
          </div>
          <label class="field" for="branch-detail-phone">
            <span>Telefon</span>
            <PhoneInput
              id="branch-detail-phone"
              v-model="branchForm.phone"
              required
              :aria-invalid="!!branchFieldErrors.phone"
              :aria-describedby="branchFieldErrors.phone ? 'branch-detail-phone-error' : undefined"
            />
            <span
              v-if="branchFieldErrors.phone"
              id="branch-detail-phone-error"
              class="mp-field-error"
            >
              {{ branchFieldErrors.phone }}
            </span>
          </label>
          <fieldset>
            <legend class="mb-2 text-sm font-extrabold text-ink">Ish vaqti</legend>
            <div class="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              <div
                v-for="day in hours"
                :key="day.key"
                class="rounded-md border border-hairline bg-sunk p-3"
              >
                <label class="flex items-center gap-2 text-sm font-extrabold text-ink">
                  <input v-model="day.open" type="checkbox" class="size-4 accent-accent" />
                  {{ day.label }}
                </label>
                <div class="mt-2 grid grid-cols-2 gap-2">
                  <input
                    v-model="day.from"
                    class="mp-input min-h-9 px-2 text-sm"
                    type="time"
                    :disabled="!day.open"
                  />
                  <input
                    v-model="day.to"
                    class="mp-input min-h-9 px-2 text-sm"
                    type="time"
                    :disabled="!day.open"
                  />
                </div>
              </div>
            </div>
          </fieldset>
          <div class="grid gap-3 md:grid-cols-2">
            <label class="field" for="branch-detail-cutting-rate">
              <span>Kesish narxi (so'm)</span>
              <input
                id="branch-detail-cutting-rate"
                v-model="pricingForm.cuttingRateSom"
                class="mp-input"
                inputmode="numeric"
                :aria-invalid="!!branchFieldErrors.cuttingRate"
                :aria-describedby="
                  branchFieldErrors.cuttingRate ? 'branch-detail-cutting-rate-error' : undefined
                "
              />
              <small v-if="cuttingRateTiyin !== null" class="text-ink-muted">
                = {{ formatTiyin(cuttingRateTiyin) }}
              </small>
              <span
                v-if="branchFieldErrors.cuttingRate"
                id="branch-detail-cutting-rate-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.cuttingRate }}
              </span>
            </label>
            <label class="field" for="branch-detail-edge-rate">
              <span>Krom yopishtirish narxi (so'm)</span>
              <input
                id="branch-detail-edge-rate"
                v-model="pricingForm.edgeBandingRateSom"
                class="mp-input"
                inputmode="numeric"
                :aria-invalid="!!branchFieldErrors.edgeBandingRate"
                :aria-describedby="
                  branchFieldErrors.edgeBandingRate ? 'branch-detail-edge-rate-error' : undefined
                "
              />
              <small v-if="edgeBandingRateTiyin !== null" class="text-ink-muted">
                = {{ formatTiyin(edgeBandingRateTiyin) }}
              </small>
              <span
                v-if="branchFieldErrors.edgeBandingRate"
                id="branch-detail-edge-rate-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.edgeBandingRate }}
              </span>
            </label>
          </div>
          <div class="flex flex-wrap items-center justify-end gap-3">
            <p v-if="saved" class="text-sm font-bold text-success">Saqlandi</p>
            <p v-else-if="saveError" class="text-sm font-bold text-danger">
              Saqlab bo'lmadi · trace_id: {{ saveTraceId ?? 'unavailable' }}
            </p>
            <button class="mp-button mp-button-primary" type="submit" :disabled="saving">
              {{ saving ? 'Saqlanmoqda' : 'Saqlash' }}
            </button>
          </div>
        </div>
      </form>

      <form
        class="card mt-5 max-w-[760px] overflow-visible"
        novalidate
        @submit.prevent="changeBranchStatus"
      >
        <div class="card-h">
          <h2>Holat</h2>
        </div>
        <div class="card-b grid gap-3">
          <FormSelect v-model="statusForm.status" label="Holat" :options="statusOptions" required />
          <label v-if="statusForm.status !== 'active'" class="field" for="branch-status-reason">
            <span>Sabab</span>
            <input
              id="branch-status-reason"
              v-model="statusForm.reason"
              class="mp-input"
              required
              :aria-invalid="!!statusFieldErrors.reason"
              :aria-describedby="
                statusFieldErrors.reason ? 'branch-status-reason-error' : undefined
              "
            />
            <span
              v-if="statusFieldErrors.reason"
              id="branch-status-reason-error"
              class="mp-field-error"
            >
              {{ statusFieldErrors.reason }}
            </span>
          </label>
          <div class="flex flex-wrap items-center justify-end gap-3">
            <p v-if="statusSaved" class="text-sm font-bold text-success">Holat saqlandi</p>
            <p v-else-if="statusError" class="text-sm font-bold text-danger">
              Holat saqlanmadi · trace_id: {{ statusTraceId ?? 'unavailable' }}
            </p>
            <button class="mp-button mp-button-primary" type="submit" :disabled="statusSaving">
              {{ statusSaving ? "O'zgartirilmoqda" : "Holatni o'zgartirish" }}
            </button>
          </div>
        </div>
      </form>
    </template>
  </section>
</template>
