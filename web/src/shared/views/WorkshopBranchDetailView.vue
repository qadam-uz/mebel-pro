<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
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
import { additionalPhoneErrors } from '@/shared/app/branchPhones'
import { traceSuffix } from '@/shared/app/errorTrace'
import { sanitizeMoneyInput } from '@/shared/app/inputSanitizers'
import { useRolePath } from '@/shared/app/paths'
import { branchPillClass, branchStatusUz } from '@/shared/app/workshopUi'
import BranchMap from '@/shared/components/BranchMap.vue'
import BranchPhonesField from '@/shared/components/BranchPhonesField.vue'
import FormSelect from '@/shared/components/FormSelect.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useOnboardingContinuation } from '@/shared/composables/useOnboardingContinuation'
import { useToast } from '@/shared/composables/useToast'
import { parseSomToTiyin } from '@/shared/formatters'
import { useWorkshopStore } from '@/shared/stores/workshop'

type BranchField =
  | 'name'
  | 'address'
  | 'phone'
  | 'phones'
  | 'cuttingRate'
  | 'edgeBandingRate'
  | 'kerfMm'
  | 'edgeTrimMm'
type StatusField = 'reason'

const route = useRoute()
const rolePath = useRolePath()
const workshop = useWorkshopStore()
const toast = useToast()
const { t } = useI18n()
const { notifyProgress } = useOnboardingContinuation()
const branchId = computed(() => String(route.params.branch_id ?? ''))
// Order numbers read `#<2-digit year>-<branch_no>-<per-year sequence>`
// (docs/ref/entities/sales.md). Showing the live prefix turns the branch number
// from a bare integer into the thing the owner actually reads off a cutting map.
const orderNumberPrefix = computed(() => {
  const branch = workshop.selectedBranch
  if (!branch) return ''
  return `#${String(new Date().getFullYear() % 100).padStart(2, '0')}-${branch.branch_no}-…`
})
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
  kerfMm: '',
  edgeTrimMm: '',
})
const additionalPhones = ref<string[]>([])
// Per-row phone errors surface from the first save attempt on, then stay live so
// fixing or removing a row clears its message.
const phonesValidated = ref(false)
const phoneRowErrors = computed(() =>
  phonesValidated.value ? additionalPhoneErrors(additionalPhones.value, branchForm.phone) : [],
)
// Integers only — kerf/trim are millimetres, never fractional (bounds mirror
// the backend CheckConstraints: kerf 1-20, trim 0-50).
const KERF_MM_MIN = 1
const KERF_MM_MAX = 20
const EDGE_TRIM_MM_MIN = 0
const EDGE_TRIM_MM_MAX = 50
function parseMm(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null
  return Number(value.trim())
}
const kerfMmValue = computed(() => parseMm(branchForm.kerfMm))
const edgeTrimMmValue = computed(() => parseMm(branchForm.edgeTrimMm))
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
  'phones',
  'cuttingRate',
  'edgeBandingRate',
  'kerfMm',
  'edgeTrimMm',
]
const branchFieldIds: Record<BranchField, string> = {
  name: 'branch-detail-name',
  address: 'branch-detail-address',
  phone: 'branch-detail-phone',
  phones: 'branch-detail-additional-phone-0',
  cuttingRate: 'branch-detail-cutting-rate',
  edgeBandingRate: 'branch-detail-edge-rate',
  kerfMm: 'branch-detail-kerf-mm',
  edgeTrimMm: 'branch-detail-edge-trim-mm',
}
const statusFieldErrors = reactive<FieldErrors<StatusField>>({})
const statusFieldOrder: StatusField[] = ['reason']
const statusFieldIds: Record<StatusField, string> = {
  reason: 'branch-status-reason',
}
const statusOptions = computed(() => [
  {
    value: 'active',
    label: branchStatusUz('active'),
    meta: t('workshopAdmin.branchDetail.statusActiveMeta'),
  },
  {
    value: 'temporarily_closed',
    label: branchStatusUz('temporarily_closed'),
    meta: t('workshopAdmin.branchDetail.statusClosedMeta'),
  },
  {
    value: 'inactive',
    label: branchStatusUz('inactive'),
    meta: t('workshopAdmin.branchDetail.statusInactiveMeta'),
  },
])

function validateBranchForm() {
  clearFieldErrors(branchFieldErrors)
  phonesValidated.value = true
  branchFieldErrors.name = requiredText(branchForm.name) ?? undefined
  branchFieldErrors.address = requiredText(branchForm.address) ?? undefined
  branchFieldErrors.phone = requiredText(branchForm.phone) ?? uzPhone(branchForm.phone) ?? undefined
  branchFieldErrors.cuttingRate =
    pricingForm.cuttingRateSom.trim() && cuttingRateTiyin.value === null
      ? t('workshopAdmin.branchDetail.cuttingRateError')
      : undefined
  branchFieldErrors.edgeBandingRate =
    pricingForm.edgeBandingRateSom.trim() && edgeBandingRateTiyin.value === null
      ? t('workshopAdmin.branchDetail.edgeRateError')
      : undefined
  branchFieldErrors.kerfMm =
    kerfMmValue.value === null || kerfMmValue.value < KERF_MM_MIN || kerfMmValue.value > KERF_MM_MAX
      ? t('workshopAdmin.branchDetail.kerfError', { min: KERF_MM_MIN, max: KERF_MM_MAX })
      : undefined
  branchFieldErrors.edgeTrimMm =
    edgeTrimMmValue.value === null ||
    edgeTrimMmValue.value < EDGE_TRIM_MM_MIN ||
    edgeTrimMmValue.value > EDGE_TRIM_MM_MAX
      ? t('workshopAdmin.branchDetail.edgeTrimError', {
          min: EDGE_TRIM_MM_MIN,
          max: EDGE_TRIM_MM_MAX,
        })
      : undefined
  const hasErrors = branchFieldOrder.some((field) => Boolean(branchFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(branchFieldErrors, branchFieldOrder, branchFieldIds)
  const firstPhoneRowError = phoneRowErrors.value.findIndex(Boolean)
  if (!hasErrors && firstPhoneRowError >= 0) {
    document.getElementById(`branch-detail-additional-phone-${firstPhoneRowError}`)?.focus()
  }
  return !hasErrors && firstPhoneRowError < 0
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
  additionalPhones.value = [...branch.additional_phones]
  phonesValidated.value = false
  branchForm.kerfMm = String(branch.kerf_mm)
  branchForm.edgeTrimMm = String(branch.edge_trim_mm)
  statusForm.status = branch.status
  statusForm.reason = branch.closed_reason ?? ''
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
      additional_phones: additionalPhones.value,
      kerf_mm: kerfMmValue.value,
      edge_trim_mm: edgeTrimMmValue.value,
    })
    await workshop.updateBranchPricing(branchId.value, {
      cutting_rate_tiyin: cuttingRateTiyin.value,
      edge_banding_rate_tiyin: edgeBandingRateTiyin.value,
    })
    saved.value = true
    if (!(await notifyProgress())) toast.success(t('workshopAdmin.branchDetail.saved'))
  } catch (caught) {
    Object.assign(
      branchFieldErrors,
      fieldErrorsFromApi<BranchField>(
        caught,
        {
          branch_name_required: 'name',
          branch_address_required: 'address',
          invalid_phone: 'phone',
          too_many_branch_phones: 'phones',
          duplicate_branch_phone: 'phones',
        },
        {
          name: 'name',
          address: 'address',
          phone: 'phone',
          additional_phones: 'phones',
          kerf_mm: 'kerfMm',
          edge_trim_mm: 'edgeTrimMm',
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
    toast.success(t('workshopAdmin.branchDetail.statusChanged'))
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
    <RouterLink :to="rolePath('/workshop/branches')" class="back">
      {{ $t('workshopAdmin.branchDetail.back') }}
    </RouterLink>
    <div class="page-head">
      <div>
        <h1>
          {{ workshop.selectedBranch?.name ?? $t('workshopAdmin.branchDetail.fallbackName') }}
        </h1>
        <!-- The branch number is printed on every order and cutting map that
             leaves the building; this is the only place it can be looked up. -->
        <i18n-t
          v-if="workshop.selectedBranch"
          keypath="workshopAdmin.branchDetail.numberHint"
          tag="p"
          scope="global"
          class="sub"
        >
          <template #no>
            <span class="id">{{ workshop.selectedBranch.branch_no }}</span>
          </template>
          <template #prefix>
            <span class="id">{{ orderNumberPrefix }}</span>
          </template>
        </i18n-t>
      </div>
      <span
        v-if="workshop.selectedBranch"
        class="mp-chip"
        :class="branchPillClass(workshop.selectedBranch.status)"
      >
        <span class="pd"></span>{{ branchStatusUz(workshop.selectedBranch.status) }}
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
      <h3>{{ $t('workshopAdmin.branchDetail.loadFailed') }}</h3>
      <p>{{ $t('workshopAdmin.action.connectionRetry') }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        :disabled="loading"
        @click="refreshBranch"
      >
        {{ $t('workshopAdmin.action.retry') }}
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
          <b>{{ $t('workshopAdmin.branchStatus.temporarily_closed') }}</b>
          <span v-if="workshop.selectedBranch.closed_reason">
            · {{ workshop.selectedBranch.closed_reason }}
          </span>
        </div>
      </div>
      <div v-else-if="workshop.selectedBranch.status === 'inactive'" class="banner danger mb-5">
        <div class="grow">
          <b>{{ $t('workshopAdmin.branchStatus.inactive') }}</b> ·
          {{ $t('workshopAdmin.branchDetail.inactiveBody') }}
        </div>
      </div>

      <form class="card max-w-[1120px]" novalidate @submit.prevent="saveBranch">
        <div class="card-h">
          <h2>{{ $t('workshopAdmin.branchDetail.infoTitle') }}</h2>
        </div>
        <div class="card-b grid gap-3">
          <div class="grid gap-3 md:grid-cols-2">
            <label class="field" for="branch-detail-name">
              <span>{{ $t('workshopAdmin.branches.name') }}</span>
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
              <span>{{ $t('workshopAdmin.branches.address') }}</span>
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
          <div class="field">
            <span>{{ $t('workshopAdmin.branches.map.label') }}</span>
            <BranchMap
              :latitude="mapPoint?.latitude ?? null"
              :longitude="mapPoint?.longitude ?? null"
              @update:point="mapPoint = $event"
            />
          </div>
          <label class="field" for="branch-detail-phone">
            <span>{{ $t('workshopAdmin.branches.phone') }}</span>
            <PhoneInput
              id="branch-detail-phone"
              v-model="branchForm.phone"
              required
              :aria-invalid="!!branchFieldErrors.phone"
              :aria-describedby="
                branchFieldErrors.phone ? 'branch-detail-phone-error' : 'branch-detail-phone-hint'
              "
            />
            <small id="branch-detail-phone-hint" class="text-ink-muted">
              {{ $t('workshopAdmin.branches.phoneHint') }}
            </small>
            <span
              v-if="branchFieldErrors.phone"
              id="branch-detail-phone-error"
              class="mp-field-error"
            >
              {{ branchFieldErrors.phone }}
            </span>
          </label>
          <BranchPhonesField
            v-model="additionalPhones"
            id-prefix="branch-detail-additional-phone"
            :errors="phoneRowErrors"
          />
          <p v-if="branchFieldErrors.phones" class="mp-field-error">
            {{ branchFieldErrors.phones }}
          </p>
          <div class="grid gap-3 md:grid-cols-2" data-onboard="branch-pricing">
            <!-- The unit is the price. `subtotal_cutting = panels_used ×
                 cutting_rate` and edge labour is `length_mm × rate ÷ 1000`, so
                 one is per panel and the other per metre (QAD-182). -->
            <label class="field" for="branch-detail-cutting-rate">
              <span>{{ $t('workshopAdmin.branchDetail.cuttingRate') }}</span>
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
              <span
                v-if="branchFieldErrors.cuttingRate"
                id="branch-detail-cutting-rate-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.cuttingRate }}
              </span>
            </label>
            <label class="field" for="branch-detail-edge-rate">
              <span>{{ $t('workshopAdmin.branchDetail.edgeRate') }}</span>
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
              <span
                v-if="branchFieldErrors.edgeBandingRate"
                id="branch-detail-edge-rate-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.edgeBandingRate }}
              </span>
            </label>
          </div>
          <fieldset>
            <legend class="mb-2 text-sm font-extrabold text-ink">
              {{ $t('workshopAdmin.branchDetail.cuttingSettings') }}
            </legend>
            <div class="grid gap-3 md:grid-cols-2">
              <label class="field" for="branch-detail-kerf-mm">
                <span>{{ $t('workshopAdmin.branchDetail.kerf') }}</span>
                <input
                  id="branch-detail-kerf-mm"
                  v-model="branchForm.kerfMm"
                  class="mp-input"
                  inputmode="numeric"
                  required
                  :aria-invalid="!!branchFieldErrors.kerfMm"
                  :aria-describedby="
                    branchFieldErrors.kerfMm ? 'branch-detail-kerf-mm-error' : undefined
                  "
                />
                <span
                  v-if="branchFieldErrors.kerfMm"
                  id="branch-detail-kerf-mm-error"
                  class="mp-field-error"
                >
                  {{ branchFieldErrors.kerfMm }}
                </span>
              </label>
              <label class="field" for="branch-detail-edge-trim-mm">
                <span>{{ $t('workshopAdmin.branchDetail.edgeTrim') }}</span>
                <input
                  id="branch-detail-edge-trim-mm"
                  v-model="branchForm.edgeTrimMm"
                  class="mp-input"
                  inputmode="numeric"
                  required
                  :aria-invalid="!!branchFieldErrors.edgeTrimMm"
                  :aria-describedby="
                    branchFieldErrors.edgeTrimMm ? 'branch-detail-edge-trim-mm-error' : undefined
                  "
                />
                <span
                  v-if="branchFieldErrors.edgeTrimMm"
                  id="branch-detail-edge-trim-mm-error"
                  class="mp-field-error"
                >
                  {{ branchFieldErrors.edgeTrimMm }}
                </span>
              </label>
            </div>
            <p class="mt-2 text-xs text-ink-muted">
              {{ $t('workshopAdmin.branchDetail.usableArea') }}
            </p>
          </fieldset>
          <div class="flex flex-wrap items-center justify-end gap-3">
            <p v-if="saved" class="text-sm font-bold text-success">
              {{ $t('workshopAdmin.action.saved') }}
            </p>
            <p v-else-if="saveError" class="text-sm font-bold text-danger">
              {{ $t('workshopAdmin.action.saveFailed') }}{{ traceSuffix(saveTraceId) }}
            </p>
            <button class="mp-button mp-button-primary" type="submit" :disabled="saving">
              {{ saving ? $t('workshopAdmin.action.saving') : $t('workshopAdmin.action.save') }}
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
          <h2>{{ $t('workshopAdmin.branchDetail.statusTitle') }}</h2>
        </div>
        <div class="card-b grid gap-3">
          <FormSelect
            v-model="statusForm.status"
            :label="$t('workshopAdmin.branchDetail.statusTitle')"
            :options="statusOptions"
            required
          />
          <label v-if="statusForm.status !== 'active'" class="field" for="branch-status-reason">
            <span>{{ $t('workshopAdmin.branchDetail.reason') }}</span>
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
            <p v-if="statusSaved" class="text-sm font-bold text-success">
              {{ $t('workshopAdmin.branchDetail.statusSaved') }}
            </p>
            <p v-else-if="statusError" class="text-sm font-bold text-danger">
              {{ $t('workshopAdmin.branchDetail.statusSaveFailed')
              }}{{ traceSuffix(statusTraceId) }}
            </p>
            <button class="mp-button mp-button-primary" type="submit" :disabled="statusSaving">
              {{
                statusSaving
                  ? $t('workshopAdmin.branchDetail.statusSaving')
                  : $t('workshopAdmin.branchDetail.statusSubmit')
              }}
            </button>
          </div>
        </div>
      </form>
    </template>
  </section>
</template>
