<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import {
  clientErrorLabel,
  formatPercent,
  formatPhone,
  isUzPhone,
  normalizeUzPhone,
} from '@/shared/app/clientUi'
import {
  buildBillRows,
  buildPartRows,
  canPlaceBlocker,
  canPlaceBlockerLabel,
  fieldDiffersFromProfile,
} from '@/shared/app/clientOrderReview'
import { snapshotMaterialLabel } from '@/shared/app/cuttingDisplay'
import { traceLine } from '@/shared/app/errorTrace'
import { useRolePath } from '@/shared/app/paths'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { metres, useCuttingStore } from '@/shared/stores/cutting'
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
const chosenResult = computed(() =>
  draft.value?.results.find((result) => result.id === draft.value?.chosen_result_id),
)
const branchId = computed(() => draft.value?.preferred_branch_id ?? null)

const totalQuantity = computed(
  () => draft.value?.parts_snapshot.reduce((sum, part) => sum + Math.max(0, part.quantity), 0) ?? 0,
)
const totalPanels = computed(() =>
  chosenResult.value
    ? Object.values(chosenResult.value.panels_used_by_material).reduce(
        (sum, count) => sum + count,
        0,
      )
    : 0,
)
const totalEdge = computed(() =>
  chosenResult.value
    ? Object.values(chosenResult.value.edge_consumed_shop_by_material).reduce(
        (sum, value) => sum + value,
        0,
      ) +
      Object.values(chosenResult.value.edge_consumed_own_by_material).reduce(
        (sum, value) => sum + value,
        0,
      )
    : 0,
)

// Resolves a part/line material id to its full canonical display label from
// the chosen result's snapshot — the only place that identity is carried on
// the wire. Same shape everywhere a material/edge is shown (see
// snapshotMaterialLabel's own doc): `{type} {manufacturer} {decor or name}` ·
// `{color}` · `{L}×{W}×{T} mm`.
function resolveMaterialName(materialId: string): string {
  const snapshot = chosenResult.value?.material_snapshots[materialId]
  if (!snapshot) return materialId
  return snapshotMaterialLabel(snapshot, materialId)
}

// "To'liq xulosa" (step 4): the full parts list and itemized bill, derived via
// the pure helpers in clientOrderReview.ts so they stay unit-testable.
const partRows = computed(() =>
  draft.value ? buildPartRows(draft.value.parts_snapshot, resolveMaterialName) : [],
)
const billRows = computed(() => (quote.value ? buildBillRows(quote.value) : []))

const blocker = computed(() =>
  canPlaceBlocker({
    hasQuote: Boolean(quote.value),
    name: contactName.value,
    phone: contactPhone.value,
  }),
)
const canPlace = computed(() => blocker.value === null)
// Shown under the CTA whenever it's disabled — unless a load/submit error is
// already explaining itself there, which would just repeat the point.
const reasonLine = computed(() =>
  !canPlace.value && !localError.value ? canPlaceBlockerLabel(blocker.value) : null,
)

const nameDiffers = computed(() => fieldDiffersFromProfile(contactName.value, auth.me?.name))
const phoneDiffers = computed(() => fieldDiffersFromProfile(contactPhone.value, auth.me?.phone))

function resetField(field: 'name' | 'phone') {
  if (field === 'name') contactName.value = auth.me?.name ?? ''
  else contactPhone.value = auth.me?.phone ?? ''
}

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
    localError.value = clientErrorLabel(orders.error, t('client.orderNew.placeFailed'))
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
        <p class="sub">{{ $t('client.orderNew.subtitle') }}</p>
      </div>
    </div>

    <section v-if="cutting.loading" class="grid gap-3" aria-live="polite">
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
         at every breakpoint below xl. -->
    <section
      v-else-if="draft && chosenResult"
      class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_330px] xl:items-start"
    >
      <div class="grid min-w-0 gap-4">
        <!-- Pickup: read-only static context, not worth a full card (CB: was
             198px of a card for four lines of text). -->
        <div class="grid gap-1.5">
          <span class="text-xs font-bold uppercase tracking-wide text-ink-muted">{{
            $t('client.orderNew.pickupPlace')
          }}</span>
          <div v-if="quote" class="grid gap-1">
            <div class="font-serif text-lg font-semibold text-ink">{{ quote.branch_name }}</div>
            <div class="font-mono text-xs text-ink-muted">
              {{ quote.branch_address }} · {{ formatPhone(quote.branch_phone) }}
            </div>
          </div>
          <div v-else-if="quoteLoading" class="client-skeleton h-20"></div>
          <p v-else class="text-sm font-bold text-danger">
            {{ $t('client.orderNew.quoteFailed') }}
          </p>
          <i18n-t
            keypath="client.orderNew.branchLocked"
            tag="p"
            class="text-xs text-ink-muted"
            scope="global"
          >
            <template #link>
              <RouterLink
                :to="rolePath(`/c/cutting/${draftId}`)"
                class="font-bold text-accent underline"
                >{{ $t('client.orderNew.branchLockedLink') }}</RouterLink
              >
            </template>
          </i18n-t>
        </div>

        <section class="client-card">
          <div class="client-card-h">
            <h2>{{ $t('client.orderNew.contactTitle') }}</h2>
          </div>
          <div class="client-card-b">
            <div class="client-banner success">
              <span class="font-mono font-black">i</span>
              <span>{{ $t('client.orderNew.contactNote') }}</span>
            </div>
            <div class="grid gap-3 md:grid-cols-2">
              <label class="grid gap-1 text-sm font-bold text-ink">
                {{ $t('client.common.name') }}
                <input v-model="contactName" class="mp-input" autocomplete="name" />
                <button
                  v-if="nameDiffers"
                  type="button"
                  class="w-fit text-xs font-bold text-accent underline"
                  @click="resetField('name')"
                >
                  {{ $t('client.orderNew.resetFromProfile') }}
                </button>
              </label>
              <label class="grid gap-1 text-sm font-bold text-ink">
                {{ $t('client.common.phone') }}
                <PhoneInput v-model="contactPhone" required />
                <span v-if="contactPhone && !isUzPhone(contactPhone)" class="text-xs text-danger">{{
                  $t('client.orderNew.phoneInvalid')
                }}</span>
                <button
                  v-if="phoneDiffers"
                  type="button"
                  class="w-fit text-xs font-bold text-accent underline"
                  @click="resetField('phone')"
                >
                  {{ $t('client.orderNew.resetFromProfile') }}
                </button>
              </label>
            </div>
          </div>
        </section>

        <!-- To'liq xulosa: the full order review — the client confirms without
             ever seeing this today. Parts list stays collapsed by default so
             it never competes with step 1's above-the-fold acceptance. -->
        <section class="client-card">
          <div class="client-card-h">
            <h2>{{ $t('client.orderNew.summaryTitle') }}</h2>
          </div>
          <div class="client-card-b grid gap-3">
            <p class="font-mono text-xs text-ink-muted">
              {{
                $t('client.orderNew.cuttingParams', {
                  kerf: chosenResult.kerf_mm,
                  trim: chosenResult.edge_trim_mm,
                })
              }}
            </p>

            <details>
              <summary class="cursor-pointer text-sm font-bold text-accent select-none">
                {{ $t('client.orderNew.partsToggle', partRows.length) }}
              </summary>
              <div class="mt-3 overflow-x-auto rounded-md border border-hairline">
                <table class="w-full min-w-[560px] border-collapse text-xs">
                  <thead>
                    <tr class="bg-sunk text-left text-ink-muted">
                      <th class="px-3 py-2 font-bold">{{ $t('client.orderNew.colName') }}</th>
                      <th class="px-3 py-2 font-bold">{{ $t('client.common.material') }}</th>
                      <th class="px-3 py-2 text-right font-bold">
                        {{ $t('client.orderNew.colSize') }}
                      </th>
                      <th class="px-3 py-2 text-right font-bold">
                        {{ $t('client.orderNew.colQuantity') }}
                      </th>
                      <th class="px-3 py-2 font-bold">{{ $t('client.orderDetail.edge') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in partRows" :key="row.key" class="border-t border-hairline">
                      <td class="px-3 py-2 font-bold text-ink">
                        {{ row.name }}
                        <!-- `follow_grain` defaults to true, so marking it would
                             tag nearly every row. Mark the deliberate exception
                             instead — the row where rotation was allowed. -->
                        <span
                          v-if="!row.followGrain"
                          class="ml-1 text-[10px] font-bold text-ink-muted"
                          :title="$t('client.orderNew.rotationTitle')"
                          >· {{ $t('client.orderNew.rotation') }}</span
                        >
                      </td>
                      <td class="px-3 py-2 text-ink-soft">{{ row.materialLabel }}</td>
                      <td class="px-3 py-2 text-right font-mono text-ink">{{ row.sizeLabel }}</td>
                      <td class="px-3 py-2 text-right font-mono text-ink">{{ row.quantity }}</td>
                      <td class="px-3 py-2 text-ink-soft">{{ row.edgeLabel }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </details>

            <p class="text-xs text-ink-soft">{{ $t('client.orderNew.paymentNote') }}</p>
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
          <div class="grid gap-2 text-sm">
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">{{ $t('client.common.parts') }}</span
              ><span class="font-mono font-bold text-ink">{{ totalQuantity }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">{{ $t('client.orderNew.sheets') }}</span
              ><span class="font-mono font-bold text-ink">{{ totalPanels }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <!-- "Kromka" length here, "Kromka: <material>" money below — never
                   the same bare word for two different units (CB collision). -->
              <span class="text-ink-soft">{{ $t('client.orderNew.edgeLength') }}</span
              ><span class="font-mono font-bold text-ink">{{ metres(totalEdge) }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">{{ $t('client.orderNew.waste') }}</span
              ><span class="font-mono font-bold text-ink">{{
                formatPercent(chosenResult.waste_percentage)
              }}</span>
            </div>
          </div>

          <div class="grid gap-1.5 border-t border-hairline pt-3 font-mono text-xs">
            <div v-for="row in billRows" :key="row.key" class="flex justify-between gap-3">
              <span class="min-w-0 text-ink-soft"
                >{{ row.label
                }}<span class="block text-[10px] text-ink-muted">{{ row.detail }}</span></span
              >
              <span class="shrink-0 font-bold text-ink">{{ formatTiyin(row.amount_tiyin) }}</span>
            </div>
            <div
              class="mt-1 flex justify-between gap-3 border-t border-hairline pt-2 text-sm font-extrabold text-accent"
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

            <div v-if="localError" class="client-banner danger mb-0">
              <span class="font-mono font-black">!</span><span>{{ localError }}</span>
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
