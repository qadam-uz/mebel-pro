<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { clientErrorLabel, isUzPhone, normalizeUzPhone } from '@/shared/app/clientUi'
import {
  buildBillRows,
  canPlaceBlocker,
  canPlaceBlockerLabel,
} from '@/shared/app/clientOrderReview'
import { clientResultFigures } from '@/shared/app/cuttingResultsDisplay'
import { traceLine, traceSuffix } from '@/shared/app/errorTrace'
import { useRolePath } from '@/shared/app/paths'
import BranchContact from '@/shared/components/BranchContact.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { useCuttingStore } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderQuote } from '@/shared/stores/orders'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const auth = useAuthStore()
const cutting = useCuttingStore()
const orders = useOrdersStore()
const toast = useToast()

const draftId = computed(() => String(route.params.draft_id))
const quote = ref<OrderQuote | null>(null)
const quoteLoading = ref(false)
const contactName = ref('')
const contactPhone = ref('')
const placing = ref(false)
const localError = ref<string | null>(null)

const draft = computed(() => cutting.currentDraft)
/**
 * Cold read only. Arriving from the result stage the drawing is already the
 * store's current draft, so the page paints while it revalidates rather than
 * showing a full-page skeleton on every visit (client audit 2026-09-03).
 */
const showSkeleton = computed(() => cutting.loading && !draft.value)
const chosenResult = computed(() =>
  draft.value?.results.find((result) => result.id === draft.value?.chosen_result_id),
)
const branchId = computed(() => draft.value?.preferred_branch_id ?? null)

// §7.7: the same four figures the result stage shows — Detallar, Listlar,
// Kromka, Foydali qoldiq — from the one composer, so the two pages cannot
// disagree about the layout the client is about to buy. «Chiqim» is gone: a
// yield percentage on a fixed-price quote is a number the client cannot act on.
const figures = computed(() => (chosenResult.value ? clientResultFigures(chosenResult.value) : []))
// The drawing's own name, as the page subtitle. Untitled shows nothing rather
// than a grey placeholder.
const draftName = computed(() => draft.value?.name?.trim() || '')

// "To'liq xulosa" (step 4): the itemized bill, derived via the pure helpers in
// clientOrderReview.ts so it stays unit-testable. The per-part table this step
// used to carry is gone — the rail's part count is the summary now.
const billRows = computed(() => (quote.value ? buildBillRows(quote.value) : []))

/**
 * §7.7: **the phone must be an Uzbek number** (`+998` + 9 digits).
 *
 * A Telegram sign-up can bring a foreign number into the profile, and that
 * number is prefilled here — so this is the one field on the client that
 * regularly arrives already invalid. It is rejected **on blur and on submit**,
 * never per keystroke (the UX bar), and «Buyurtmani tasdiqlash» stays disabled
 * until it is fixed. The profile is not overwritten either way: the order
 * carries the corrected number, and changing the profile is the profile page's
 * job.
 *
 * The field is a plain `tel` input rather than the shared `PhoneInput`
 * deliberately. `PhoneInput` *forces* the shape — it strips a country code and
 * keeps nine digits — which would silently rewrite `+7 926 123 45 67` into a
 * well-formed but wrong `+998 79 261 23 45`. Showing the foreign number as it
 * is, and refusing it, is the whole point of this rule.
 */
const phoneTouched = ref(false)
const phoneRejected = computed(
  () =>
    phoneTouched.value && contactPhone.value.trim().length > 0 && !isUzPhone(contactPhone.value),
)

const blocker = computed(() =>
  canPlaceBlocker({
    hasQuote: Boolean(quote.value),
    name: contactName.value,
    phone: contactPhone.value,
  }),
)
const canPlace = computed(() => blocker.value === null)
// Shown under the CTA whenever it is disabled — unless a load/submit error is
// already explaining itself there, or the rejected phone field is already
// carrying the same message beside itself, which is where an error belongs.
const reasonLine = computed(() => {
  if (canPlace.value || localError.value) return null
  if (blocker.value === 'phone' && phoneRejected.value) return null
  return canPlaceBlockerLabel(blocker.value)
})

async function loadQuote() {
  if (!branchId.value) return
  quoteLoading.value = true
  localError.value = null
  try {
    quote.value = await orders.quoteForDraft(draftId.value, branchId.value)
  } catch {
    quote.value = null
    localError.value = clientErrorLabel(orders.error, t('client.orderNew.quoteError'))
  } finally {
    quoteLoading.value = false
  }
}

async function placeOrder() {
  // Submit is the second validation trigger: a client who never left the field
  // still sees the message rather than a button that does nothing.
  phoneTouched.value = true
  // The button is disabled whenever `blocker` is set, so this only guards a
  // stray programmatic call — no message needed, there's nothing to submit.
  if (!branchId.value || !quote.value || blocker.value) return
  placing.value = true
  localError.value = null
  try {
    const order = await orders.createClientOrder({
      draft_id: draftId.value,
      branch_id: branchId.value,
      contact_name: contactName.value.trim(),
      contact_phone: normalizeUzPhone(contactPhone.value),
    })
    toast.success(t('client.orderNew.placedToast'))
    await router.push(rolePath(`/c/orders/${order.id}?new=1`))
  } catch {
    // createClientOrder captures the failure to actionError/actionTraceId —
    // `orders.error` belongs to loads (the quote) and would be stale or null here.
    localError.value =
      clientErrorLabel(orders.actionError, t('client.orderNew.placeFailed')) +
      traceSuffix(orders.actionTraceId)
  } finally {
    placing.value = false
  }
}

onMounted(async () => {
  contactName.value = auth.me?.name ?? ''
  contactPhone.value = auth.me?.phone ?? ''
  await cutting.loadDraft(draftId.value)

  const boundOrderId = cutting.currentDraft?.results.find((result) => result.order_id)?.order_id
  if (boundOrderId) {
    toast.warn(t('client.orderNew.alreadyOrdered'))
    await router.replace(rolePath(`/c/orders/${boundOrderId}`))
    return
  }
  if (cutting.currentDraft && !chosenResult.value) {
    toast.warn(t('client.orderNew.optimizeFirst'))
    await router.replace(rolePath(`/c/cutting/${draftId.value}`))
    return
  }
  if (!branchId.value) {
    toast.warn(t('client.orderNew.branchFirst'))
    await router.replace(rolePath(`/c/cutting/${draftId.value}`))
    return
  }
  await loadQuote()
})
</script>

<template>
  <section>
    <RouterLink :to="rolePath(`/c/cutting/${draftId}/result`)" class="client-back">
      <span aria-hidden="true">←</span>
      {{ $t('client.orderNew.back') }}
    </RouterLink>

    <div class="client-page-head">
      <div>
        <h1>{{ $t('client.orderNew.title') }}</h1>
        <!-- §7.7: the subtitle is the draft name alone. -->
        <p v-if="draftName" class="mt-1 text-[13.5px] text-ink-soft">{{ draftName }}</p>
      </div>
    </div>

    <section v-if="showSkeleton" class="grid gap-3" aria-live="polite">
      <div class="client-skeleton h-32"></div>
      <div class="client-skeleton h-64"></div>
    </section>

    <section v-else-if="cutting.error" class="client-error">
      <div class="client-error-icon">!</div>
      <h3>{{ $t('client.orderNew.draftFailedTitle') }}</h3>
      <p>{{ $t('client.orderNew.draftFailedBody') }}</p>
      <p class="client-trace">{{ traceLine(cutting.traceId) }}</p>
    </section>

    <!-- Two columns swapped by importance: left is read-only context + the one
         form (contact); the right rail carries the decision (money + CTA) and
         is the last thing in the DOM so it's also the last thing on the page
         at every breakpoint below xl.
         The left column is capped rather than flexible: its cards hold short
         text and two inputs, so extra width only stretches them. The receipt
         gets the wider share because its itemised lines are what actually needs
         the room — but capped too, so neither column sprawls on a wide screen. -->
    <section
      v-else-if="draft && chosenResult"
      class="grid gap-6 xl:grid-cols-[minmax(0,480px)_minmax(360px,560px)] xl:items-start"
    >
      <div class="grid min-w-0 gap-4">
        <!-- Who does the work and where it is collected. The branch alone read
             as an address with no owner, so the workshop names itself first. -->
        <section class="client-card">
          <div class="client-card-h">
            <h2>{{ $t('client.orderNew.workshopTitle') }}</h2>
          </div>
          <div class="client-card-b">
            <div v-if="quoteLoading" class="client-skeleton h-24"></div>
            <p v-else-if="!quote" class="text-sm font-bold text-danger">
              {{ $t('client.orderNew.quoteFailed') }}
            </p>
            <!-- Workshop and branch read as one name — "Mebel Master · Yunusobod
                 filiali" — because that is how the client says it out loud. -->
            <div v-else class="grid gap-2">
              <div class="client-row-name">{{ quote.workshop_name }} · {{ quote.branch_name }}</div>
              <BranchContact
                :address="quote.branch_address"
                :phone="quote.branch_phone"
                :additional-phones="quote.branch_additional_phones"
                :latitude="quote.branch_latitude"
                :longitude="quote.branch_longitude"
              />
            </div>
          </div>
        </section>

        <!-- §7.7: two ordinary labelled fields, prefilled and editable. The
             explanation is a muted label-style line under the title, not an
             info banner — it is a caption on a two-field form, and a banner
             gave it the weight of a warning. No «Profildan tiklash»: the
             fields already hold the profile values, so the link only ever
             appeared after the client deliberately changed one. -->
        <section class="client-card">
          <div class="client-card-h !block">
            <h2>{{ $t('client.orderNew.contactTitle') }}</h2>
            <p class="mt-1 text-[12.5px] font-semibold text-ink-muted">
              {{ $t('client.orderNew.contactHint') }}
            </p>
          </div>
          <div class="client-card-b">
            <div class="grid gap-3.5 md:grid-cols-2">
              <label class="grid gap-1.5">
                <span class="text-[12.5px] font-semibold text-ink">
                  {{ $t('client.common.name') }}
                </span>
                <input v-model="contactName" class="mp-input" autocomplete="name" />
              </label>
              <label class="grid gap-1.5">
                <span class="text-[12.5px] font-semibold text-ink">
                  {{ $t('client.common.phone') }}
                </span>
                <!-- All three signals a rejected field owes the reader
                     (DESIGN.md): the danger border, `aria-invalid`, and a
                     message tied to it by `aria-describedby`. -->
                <input
                  v-model="contactPhone"
                  type="tel"
                  inputmode="tel"
                  autocomplete="tel"
                  class="mp-input"
                  :class="phoneRejected ? 'border-danger' : ''"
                  :aria-invalid="phoneRejected || undefined"
                  :aria-describedby="phoneRejected ? 'order-phone-error' : undefined"
                  @blur="phoneTouched = true"
                />
                <span
                  v-if="phoneRejected"
                  id="order-phone-error"
                  class="text-[12.5px] font-semibold leading-[1.25] text-danger"
                >
                  {{ $t('client.orderNew.phoneUzOnly') }}
                </span>
              </label>
            </div>
          </div>
        </section>
      </div>

      <!-- The sticky rail: compact cutting stats -> itemized money -> Jami ->
           the primary CTA -> error/retry, in that order, so the decision and
           the action to make it sit next to each other above the fold. -->
      <aside class="client-card h-fit xl:sticky xl:top-24">
        <div class="client-card-h">
          <h2>{{ $t('client.orderNew.railTitle') }}</h2>
        </div>
        <div class="client-card-b grid gap-4">
          <!-- §7.7: the four figures, as the 2×2 grid the canvas draws — the
               same four the result stage shows, from the same composer. -->
          <dl class="grid grid-cols-2 gap-x-3.5 gap-y-3">
            <div v-for="figure in figures" :key="figure.key">
              <dt class="text-[12.5px] font-semibold text-ink-muted">{{ figure.label }}</dt>
              <dd class="mt-0.5 text-[15px] font-bold text-ink">{{ figure.value }}</dd>
            </div>
          </dl>

          <div class="grid gap-1.5 border-t border-hairline pt-3 text-xs">
            <div v-for="row in billRows" :key="row.key" class="flex justify-between gap-3">
              <span class="min-w-0 text-ink-soft"
                >{{ row.label
                }}<span class="block text-[10px] text-ink-muted">{{ row.detail }}</span></span
              >
              <span class="shrink-0 font-bold text-ink">{{ formatTiyin(row.amount_tiyin) }}</span>
            </div>
            <div
              class="mt-1 flex justify-between gap-3 border-t border-hairline pt-2 text-sm font-extrabold text-ink"
            >
              <span>{{ $t('client.common.total') }}</span
              ><span>{{ formatTiyin(quote?.total_tiyin ?? 0) }}</span>
            </div>
          </div>

          <div class="grid gap-2">
            <button
              type="button"
              class="mp-button mp-button-primary w-full"
              :disabled="placing || !canPlace"
              @click="placeOrder"
            >
              {{ placing ? $t('client.orderNew.submitting') : $t('client.orderNew.submit') }}
            </button>

            <p v-if="reasonLine" class="text-xs font-semibold text-ink-muted">{{ reasonLine }}</p>

            <!-- What happens after the tap — it belongs beside the CTA, not in a
                 review section the client scrolls past. -->
            <p class="text-xs text-ink-soft">{{ $t('client.orderNew.paymentNote') }}</p>

            <div v-if="localError" class="client-banner danger mb-0">
              <span class="font-black">!</span><span>{{ localError }}</span>
            </div>
            <button
              v-if="!quote && !quoteLoading"
              type="button"
              class="mp-button mp-button-outline w-full"
              @click="loadQuote"
            >
              {{ $t('client.common.retry') }}
            </button>
          </div>
        </div>
      </aside>
    </section>
  </section>
</template>
