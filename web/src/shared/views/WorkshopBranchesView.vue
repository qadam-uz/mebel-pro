<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import {
  clearFieldErrors,
  fieldErrorsFromApi,
  focusFirstFieldError,
  requiredText,
  type FieldErrors,
  uzPhone,
} from '@/shared/app/adminValidation'
import { additionalPhoneErrors } from '@/shared/app/branchPhones'
import { useRolePath } from '@/shared/app/paths'
import { branchPillClass, branchStatusUz } from '@/shared/app/workshopUi'
import AppModal from '@/shared/components/AppModal.vue'
import BranchPhonesField from '@/shared/components/BranchPhonesField.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useToast } from '@/shared/composables/useToast'
import { useAuthStore } from '@/shared/stores/auth'
import { useWorkshopStore } from '@/shared/stores/workshop'

type BranchField = 'name' | 'address' | 'phone' | 'phones'

const auth = useAuthStore()
const workshop = useWorkshopStore()
const rolePath = useRolePath()
const router = useRouter()
const toast = useToast()
const showCreate = ref(false)
const creatingBranch = ref(false)
const branchError = ref<string | null>(null)
const branchForm = reactive({
  name: '',
  address: '',
  phone: '',
})
const additionalPhones = ref<string[]>([])
// Per-row phone errors only start showing once the owner has tried to submit —
// then they stay live so fixing or removing a row clears its message.
const phonesValidated = ref(false)
const phoneRowErrors = computed(() =>
  phonesValidated.value ? additionalPhoneErrors(additionalPhones.value, branchForm.phone) : [],
)
const branchFieldErrors = reactive<FieldErrors<BranchField>>({})
const branchFieldOrder: BranchField[] = ['name', 'address', 'phone', 'phones']
const branchFieldIds: Record<BranchField, string> = {
  name: 'branch-name',
  phone: 'branch-phone',
  address: 'branch-address',
  phones: 'branch-additional-phone-0',
}
function validateBranchForm() {
  clearFieldErrors(branchFieldErrors)
  phonesValidated.value = true
  branchFieldErrors.name = requiredText(branchForm.name) ?? undefined
  branchFieldErrors.address = requiredText(branchForm.address) ?? undefined
  branchFieldErrors.phone = requiredText(branchForm.phone) ?? uzPhone(branchForm.phone) ?? undefined
  const hasErrors = branchFieldOrder.some((field) => Boolean(branchFieldErrors[field]))
  if (hasErrors) focusFirstFieldError(branchFieldErrors, branchFieldOrder, branchFieldIds)
  const firstPhoneRowError = phoneRowErrors.value.findIndex(Boolean)
  if (!hasErrors && firstPhoneRowError >= 0) {
    document.getElementById(`branch-additional-phone-${firstPhoneRowError}`)?.focus()
  }
  return !hasErrors && firstPhoneRowError < 0
}

async function createBranch() {
  if (!validateBranchForm()) return
  creatingBranch.value = true
  branchError.value = null
  try {
    const created = await workshop.createBranch({
      name: branchForm.name,
      address: branchForm.address,
      phone: branchForm.phone,
      additional_phones: additionalPhones.value,
    })
    branchForm.name = ''
    branchForm.address = ''
    branchForm.phone = ''
    additionalPhones.value = []
    phonesValidated.value = false
    showCreate.value = false
    // The branch is live for client orders the moment it exists, but with no
    // cutting/banding pricing yet — land the owner on the detail page where
    // those two numbers are set instead of silently closing the form.
    toast.success("Filial qo'shildi. Endi kesish va kromka narxlarini kiriting.")
    await router.push(rolePath(`/workshop/branches/${created.id}`))
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
          phone: 'phone',
          address: 'address',
          additional_phones: 'phones',
        },
      ),
    )
    if (branchFieldOrder.some((field) => Boolean(branchFieldErrors[field]))) {
      focusFirstFieldError(branchFieldErrors, branchFieldOrder, branchFieldIds)
    }
    branchError.value = 'branch_create_failed'
  } finally {
    creatingBranch.value = false
  }
}

onMounted(() => {
  if (auth.me?.is_owner) void workshop.loadManagedBranches()
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Filiallar</h1>
      </div>
    </div>

    <section v-if="!auth.me?.is_owner" class="st-empty">
      <h3>Bu bo'lim faqat ustaxona rahbari uchun</h3>
      <p>Filial qo'shish va holatini boshqarish egaga tegishli.</p>
    </section>

    <template v-else>
      <!-- No filters on this page — the create action still sits in the standard
           filter-row slot above the table (right-aligned; :only-child drops the
           caption baseline offset). -->
      <div class="mp-filters">
        <button type="button" class="mp-button mp-button-primary" @click="showCreate = true">
          + Yangi filial
        </button>
      </div>

      <AppModal
        :open="showCreate"
        title="Yangi filial"
        max-width="max-w-2xl"
        @close="showCreate = false"
      >
        <form class="grid gap-3" novalidate @submit.prevent="createBranch">
          <div class="grid gap-3 md:grid-cols-2">
            <label class="field" for="branch-name">
              <span>Nom</span>
              <input
                id="branch-name"
                v-model="branchForm.name"
                class="mp-input"
                placeholder="Sergeli"
                required
                :aria-invalid="!!branchFieldErrors.name"
                :aria-describedby="branchFieldErrors.name ? 'branch-name-error' : undefined"
              />
              <span v-if="branchFieldErrors.name" id="branch-name-error" class="mp-field-error">
                {{ branchFieldErrors.name }}
              </span>
            </label>
            <label class="field" for="branch-address">
              <span>Manzil</span>
              <input
                id="branch-address"
                v-model="branchForm.address"
                class="mp-input"
                placeholder="Sergeli 1-mavze 4"
                required
                :aria-invalid="!!branchFieldErrors.address"
                :aria-describedby="branchFieldErrors.address ? 'branch-address-error' : undefined"
              />
              <span
                v-if="branchFieldErrors.address"
                id="branch-address-error"
                class="mp-field-error"
              >
                {{ branchFieldErrors.address }}
              </span>
            </label>
          </div>
          <label class="field" for="branch-phone">
            <span>Asosiy telefon</span>
            <PhoneInput
              id="branch-phone"
              v-model="branchForm.phone"
              required
              :aria-invalid="!!branchFieldErrors.phone"
              :aria-describedby="
                branchFieldErrors.phone ? 'branch-phone-error' : 'branch-phone-hint'
              "
            />
            <small id="branch-phone-hint" class="text-ink-muted">
              Mijozlar buyurtmalarida shu raqam ko'rinadi.
            </small>
            <span v-if="branchFieldErrors.phone" id="branch-phone-error" class="mp-field-error">
              {{ branchFieldErrors.phone }}
            </span>
          </label>
          <BranchPhonesField
            v-model="additionalPhones"
            id-prefix="branch-additional-phone"
            :errors="phoneRowErrors"
          />
          <p v-if="branchFieldErrors.phones" class="mp-field-error">
            {{ branchFieldErrors.phones }}
          </p>
          <div class="flex flex-wrap items-center justify-end gap-3">
            <p v-if="branchError" class="text-sm font-bold text-danger">Filial qo'shilmadi.</p>
            <button type="button" class="mp-button mp-button-outline" @click="showCreate = false">
              Bekor
            </button>
            <button type="submit" class="mp-button mp-button-primary" :disabled="creatingBranch">
              {{ creatingBranch ? "Qo'shilmoqda" : "Qo'shish" }}
            </button>
          </div>
        </form>
      </AppModal>

      <section v-if="workshop.setupLoading" class="card p-5" aria-live="polite">
        <div class="grid gap-3">
          <span class="sk-line"></span>
          <span class="sk-line"></span>
          <span class="sk-line"></span>
        </div>
      </section>

      <section v-else-if="workshop.setupError" class="st-error" role="alert">
        <h3>Filiallarni yuklab bo'lmadi</h3>
        <p>Internet aloqasini tekshirib, qayta urinib ko'ring.</p>
        <button
          type="button"
          class="mp-button mp-button-outline mt-4 min-h-11 px-4"
          :disabled="workshop.setupLoading"
          @click="workshop.loadManagedBranches()"
        >
          Qayta urinish
        </button>
        <p v-if="workshop.setupTraceId" class="mt-3 text-xs text-ink-muted">
          trace_id: {{ workshop.setupTraceId }}
        </p>
      </section>

      <section v-else-if="workshop.managedBranches.length === 0" class="st-empty">
        <h3>Hali filial yo'q</h3>
        <p>Birinchi filial qo'shilgach, mijozlar buyurtma beradigan manzil paydo bo'ladi.</p>
      </section>

      <section v-else class="card">
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <!-- The number printed in the middle of this branch's order
                     numbers (#26-1-0003). First and mono so an owner holding a
                     cutting map can scan straight down it. -->
                <th>Raqam</th>
                <th>Filial</th>
                <th>Manzil</th>
                <th>Telefon</th>
                <th>Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="branch in workshop.managedBranches" :key="branch.id">
                <td class="id">{{ branch.branch_no }}</td>
                <td class="nm">{{ branch.name }}</td>
                <td>{{ branch.address }}</td>
                <td class="num">{{ branch.phone }}</td>
                <td>
                  <span :class="branchPillClass(branch.status)">
                    <span class="pd"></span>{{ branchStatusUz[branch.status] }}
                  </span>
                </td>
                <td class="right">
                  <RouterLink
                    :to="rolePath(`/workshop/branches/${branch.id}`)"
                    class="mp-button mp-button-outline min-h-8 px-2 text-xs"
                  >
                    Ochish
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
