<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { isUzPhone, normalizeUzPhone } from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import Icon from '@/shared/components/AppIcon.vue'
import OrderWizardHead from '@/shared/components/OrderWizardHead.vue'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useCuttingStore } from '@/shared/stores/cutting'
import { useWorkshopStore } from '@/shared/stores/workshop'

// First step of the staff order flow: identify the walk-in client by phone.
// The phone is the identity, so the moment it is complete the base is asked who
// owns it — a hit fills the name and the operator only has to read it, a miss
// asks for one. That read is deliberately a separate, non-writing endpoint:
// `resolveWalkInClient` is find-or-create, so asking it on a half-typed number
// would mint a client per typo.
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const workshop = useWorkshopStore()
const { t } = useI18n()

// How long the phone has to stand still before we spend a lookup on it. Long
// enough that correcting the last digit costs one call, not two.
const LOOKUP_SETTLE_MS = 350

const phone = ref('')
const name = ref('')
const resolving = ref(false)
const error = ref<string | null>(null)
// The client the base returned for the current phone. While it is set the name
// is theirs, not the operator's, so the field goes read-only.
const matched = ref<{ id: string; name: string } | null>(null)
const lookingUp = ref(false)
// Set once a complete phone has been answered for. Until then a miss is
// indistinguishable from "not asked yet", and the name field must not accuse
// the operator of leaving it blank.
const lookedUpPhone = ref<string | null>(null)

let settleTimer: ReturnType<typeof setTimeout> | undefined

const branch = computed(() =>
  workshop.branches.find((item) => item.id === workshop.selectedBranchContext),
)
const phoneComplete = computed(() => isUzPhone(phone.value))
const answered = computed(
  () => phoneComplete.value && lookedUpPhone.value === normalizeUzPhone(phone.value),
)
// A known client needs no name from the operator; a new one does. Before the
// answer is in, nothing is ready — including during the lookup itself, so the
// button cannot be clicked out from under an in-flight answer.
const canContinue = computed(() => {
  if (!phoneComplete.value || resolving.value || lookingUp.value || !answered.value) return false
  return matched.value !== null || name.value.trim().length > 0
})

watch(phone, (next) => {
  clearTimeout(settleTimer)
  // Any edit invalidates the previous answer: the name on screen belongs to the
  // number that produced it, and leaving it up while the number changes is how
  // an order gets written for the wrong person.
  matched.value = null
  lookedUpPhone.value = null
  error.value = null
  if (!isUzPhone(next)) return
  settleTimer = setTimeout(() => void lookup(normalizeUzPhone(next)), LOOKUP_SETTLE_MS)
})

async function lookup(normalized: string) {
  lookingUp.value = true
  try {
    const found = await cutting.lookupWalkInClient(normalized)
    // The field moved on while the request was in flight — this answer is about
    // a number the operator is no longer typing.
    if (!isUzPhone(phone.value) || normalizeUzPhone(phone.value) !== normalized) return
    lookedUpPhone.value = normalized
    if (found.found && found.id && found.name) {
      matched.value = { id: found.id, name: found.name }
      name.value = found.name
    } else {
      matched.value = null
      name.value = ''
    }
  } catch (caught) {
    // A failed lookup must not block the order: the operator can still type a
    // name, and `resolve` will find the client on the way through anyway.
    lookedUpPhone.value = normalized
    error.value = workshopErrorMessage(apiErrorCode(caught))
  } finally {
    lookingUp.value = false
  }
}

async function resolve() {
  error.value = null
  if (!isUzPhone(phone.value)) {
    error.value = t('orders.error.phoneInvalid')
    return
  }
  resolving.value = true
  try {
    const resolved = await cutting.resolveWalkInClient({
      phone: normalizeUzPhone(phone.value),
      name: name.value.trim() || undefined,
    })
    void router.push({
      path: rolePath('/workshop/orders/new/cutting'),
      query: { client: resolved.id },
    })
  } catch (caught) {
    const code = apiErrorCode(caught)
    error.value =
      code === 'client_name_required'
        ? t('orders.error.clientNameRequired')
        : workshopErrorMessage(code)
  } finally {
    resolving.value = false
  }
}
</script>

<template>
  <section class="wizard-page">
    <!-- Nothing exists server-side yet, so leaving here costs nothing and asks
         nothing. The button is still drawn: the head must not change shape
         between step 1 and step 2, or the strip stops reading as one journey. -->
    <OrderWizardHead
      :step="1"
      cancellable
      :subtitle="
        branch
          ? $t('orders.walkIn.branch', { branch: branch.name })
          : $t('orders.walkIn.branchMissing')
      "
      @cancel="router.push(rolePath('/workshop/orders'))"
    />

    <!-- `.card-b` carries no top padding — it is shaped for a card that already
         has a `.card-h` above it. This one starts at its own content, so the
         padding has to be restored or the first line sits on the card edge. -->
    <div class="card max-w-[560px]">
      <div class="card-b grid gap-4 !pt-6">
        <p class="mb-1 text-sm text-ink-soft">{{ $t('orders.walkIn.intro') }}</p>

        <label class="field !mb-0">
          <span>{{ $t('orders.walkIn.phone') }}</span>
          <PhoneInput v-model="phone" />
        </label>

        <label class="field !mb-0">
          <span>
            {{ $t('orders.walkIn.name') }}
            <small v-if="!matched" class="text-ink-muted">{{ $t('orders.walkIn.nameHint') }}</small>
          </span>
          <span class="relative block">
            <input
              v-model="name"
              class="mp-input w-full"
              :class="matched ? 'bg-sunk pr-10' : ''"
              :readonly="matched !== null"
              :placeholder="$t('orders.walkIn.namePlaceholder')"
              :aria-describedby="matched ? 'walkin-found' : undefined"
            />
            <!-- The check is the whole disclosure signal, so it never stands
                 alone: the caption under it says the same thing in words. -->
            <Icon
              v-if="matched"
              name="check"
              class="pointer-events-none absolute right-3 top-1/2 size-[17px] -translate-y-1/2 text-success"
              aria-hidden="true"
            />
          </span>
          <span
            v-if="matched"
            id="walkin-found"
            class="text-[13.5px] font-medium text-success"
            role="status"
          >
            {{ $t('orders.walkIn.foundHint') }}
          </span>
          <span v-else-if="lookingUp" class="text-[13.5px] text-ink-muted" role="status">
            {{ $t('orders.walkIn.checking') }}
          </span>
        </label>

        <p v-if="error" class="mp-field-error !text-[13.5px] !font-medium">{{ error }}</p>

        <div class="flex justify-end">
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="!canContinue"
            @click="resolve"
          >
            {{ resolving ? $t('orders.walkIn.checking') : $t('orders.walkIn.continue') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
