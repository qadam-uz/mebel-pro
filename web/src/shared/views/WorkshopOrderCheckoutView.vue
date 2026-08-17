<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { isUzPhone, normalizeUzPhone } from '@/shared/app/clientUi'
import { materialSwatchStyle } from '@/shared/app/cuttingDisplay'
import { useRolePath } from '@/shared/app/paths'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import { formatTiyin } from '@/shared/formatters'
import OrderWizardHead from '@/shared/components/OrderWizardHead.vue'
import { metres, useCuttingStore } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderQuote } from '@/shared/stores/orders'

// Slim single-branch checkout for a staff-created walk-in order: quote the
// draft's fixed branch, prefill the contact from the resolved client (staff can
// edit), and place — the order lands confirmed. Refresh-safe: everything is
// re-fetched from the draft id in the route.
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const cutting = useCuttingStore()
const orders = useOrdersStore()
const { t } = useI18n()

const draftId = computed(() => String(route.params.draft_id))
const loading = ref(true)
const loadError = ref<string | null>(null)
const quote = ref<OrderQuote | null>(null)
const branchId = ref<string | null>(null)
const contactName = ref('')
const contactPhone = ref('')
const note = ref('')
const placing = ref(false)
const placeError = ref<string | null>(null)

const canPlace = computed(
  () =>
    quote.value !== null &&
    contactName.value.trim().length > 0 &&
    isUzPhone(contactPhone.value) &&
    !placing.value,
)

// One place decides which result this screen is describing. Four blocks below
// read it — contents, the totals line, the cutting label, the swatches — and
// each used to re-`find()` it, so the chosen-result rule lived in four copies.
const chosenResult = computed(() =>
  cutting.currentDraft?.results.find(
    (result) => result.id === cutting.currentDraft?.chosen_result_id,
  ),
)

// The order's contents, read off the quote and the chosen result — both already
// loaded for the price, so this block costs no extra request.
const materialLines = computed(() => {
  const current = quote.value
  if (!current) return []
  const parts = chosenResult.value?.parts_snapshot
  const snapshots = chosenResult.value?.material_snapshots
  return current.material_lines.map((line) => {
    const count = (parts ?? [])
      .filter((part) => part.material_id === line.material_id)
      .reduce((sum, part) => sum + part.quantity, 0)
    return {
      id: line.material_id,
      name: line.material_name,
      own: line.own_panels > 0,
      // The frozen snapshot, never the composed label and never `own`: the
      // swatch has to be the same colour this board wore one step earlier, and
      // a customer's own board is hatched off `customer_supplied`, which is not
      // the same thing as a catalog board the client brought sheets for.
      swatch: materialSwatchStyle(snapshots?.[line.material_id]),
      sub: `${line.panels_used} ${t('cutting.unit.sheet', line.panels_used)} · ${count} ${t('cutting.unit.part', count)}`,
    }
  })
})

const contentsTotalLine = computed(() => {
  const sheets = (quote.value?.material_lines ?? []).reduce(
    (sum, line) => sum + line.panels_used,
    0,
  )
  const parts = (chosenResult.value?.parts_snapshot ?? []).reduce(
    (sum, part) => sum + part.quantity,
    0,
  )
  return `${parts} ${t('cutting.unit.part', parts)} · ${sheets} ${t('cutting.unit.sheet', sheets)}`
})

// The propil is what the cutting fee is charged against, so it belongs on the
// label rather than as a figure the reader has to go find on the previous step.
const cuttingLabel = computed(() => {
  const chosen = chosenResult.value
  if (!chosen?.total_cut_length_mm) return t('orders.checkout.cutting')
  return t('orders.checkout.cuttingWithLength', { length: metres(chosen.total_cut_length_mm) })
})

onMounted(async () => {
  loading.value = true
  loadError.value = null
  try {
    // loadDraft stores into cutting.currentDraft and swallows its own error.
    await cutting.loadDraft(draftId.value)
    const draft = cutting.currentDraft
    if (!draft) {
      loadError.value = workshopErrorMessage(cutting.error)
      return
    }
    if (!draft.chosen_result_id) {
      // Nothing to order yet — send them back to the editor.
      void router.replace(rolePath(`/workshop/orders/cutting/${draftId.value}`))
      return
    }
    branchId.value = draft.preferred_branch_id
    const client = await cutting.loadWalkInClient(draft.client_id)
    contactName.value = client.name
    contactPhone.value = client.phone
    if (branchId.value) {
      quote.value = await orders.quoteWorkshopBranch(draftId.value, branchId.value)
    }
  } catch (caught) {
    loadError.value = workshopErrorMessage(apiErrorCode(caught))
  } finally {
    loading.value = false
  }
})

async function place() {
  placeError.value = null
  if (!branchId.value) return
  if (!contactName.value.trim()) {
    placeError.value = t('orders.error.nameRequired')
    return
  }
  if (!isUzPhone(contactPhone.value)) {
    placeError.value = t('orders.error.phoneInvalid')
    return
  }
  placing.value = true
  try {
    const order = await orders.createWorkshopOrder({
      draft_id: draftId.value,
      branch_id: branchId.value,
      contact_name: contactName.value.trim(),
      contact_phone: normalizeUzPhone(contactPhone.value),
      note_client: note.value.trim() || null,
    })
    void router.push(rolePath(`/workshop/orders/${order.id}`))
  } catch (caught) {
    const code = apiErrorCode(caught)
    placeError.value =
      code === 'missing_cutting_rate' || code === 'missing_edge_banding_rate'
        ? t('orders.error.missingRates')
        : workshopErrorMessage(code)
  } finally {
    placing.value = false
  }
}
</script>

<template>
  <section>
    <!-- The last step of the flow, so it wears the flow's head. The back link
         moves down beside the button it is the alternative to; keeping it up
         here as well would put two ways back on one short screen. -->
    <OrderWizardHead
      :step="4"
      cancellable
      :subtitle="quote ? quote.branch_name : $t('orders.checkout.branchFallback')"
      @cancel="router.push(rolePath('/workshop/orders/drafts'))"
    />

    <section v-if="loading" class="card p-5" aria-live="polite">
      <span class="sk-line"></span>
      <span class="sk-line mt-3"></span>
    </section>

    <section v-else-if="loadError" class="st-error" role="alert">
      <h3>{{ $t('orders.state.loadFailed') }}</h3>
      <p>{{ loadError }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        @click="router.go(0)"
      >
        {{ $t('orders.state.retry') }}
      </button>
    </section>

    <div
      v-else-if="quote"
      class="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
    >
      <div class="card">
        <div class="card-b !pt-[22px]">
          <h2 class="mb-4 font-display text-[19px] font-bold tracking-[-0.02em] text-ink">
            {{ $t('orders.checkout.client') }}
          </h2>
          <!-- Read-only: the client was identified and confirmed on step 1, so
               this is the receipt of that decision, not a second chance to type
               a different person into the same order. -->
          <div
            class="flex items-baseline justify-between gap-3.5 border-t border-divider py-[13px]"
          >
            <span class="text-sm text-ink-soft">{{ $t('orders.checkout.name') }}</span>
            <span class="text-[14.5px] font-semibold text-ink">{{ contactName }}</span>
          </div>
          <div
            class="flex items-baseline justify-between gap-3.5 border-t border-divider py-[13px]"
          >
            <span class="text-sm text-ink-soft">{{ $t('orders.checkout.phone') }}</span>
            <span class="num text-[14.5px] font-semibold text-ink">{{ contactPhone }}</span>
          </div>
          <div
            class="flex items-baseline justify-between gap-3.5 border-t border-divider py-[13px]"
          >
            <span class="text-sm text-ink-soft">{{ $t('orders.checkout.branch') }}</span>
            <span class="text-[14.5px] font-semibold text-ink">{{ quote.branch_name }}</span>
          </div>

          <div class="mt-1 border-t border-divider pt-3.5">
            <div class="mb-1.5 flex items-baseline justify-between gap-3">
              <span class="text-[13.5px] font-semibold text-ink">
                {{ $t('orders.checkout.contents') }}
              </span>
              <span class="num text-[13px] text-ink-muted">{{ contentsTotalLine }}</span>
            </div>
            <div
              v-for="line in materialLines"
              :key="line.id"
              class="flex items-center gap-2.5 py-[7px]"
            >
              <span
                class="size-6 shrink-0 rounded-[7px] border border-hairline"
                :style="line.swatch"
                aria-hidden="true"
              ></span>
              <span class="min-w-0 flex-1">
                <span class="block text-[13.5px] font-semibold leading-tight text-ink">
                  {{ line.name }}
                </span>
                <span class="num block text-[12.5px] text-ink-soft">{{ line.sub }}</span>
              </span>
              <span
                class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold"
                :class="
                  line.own ? 'bg-accent-soft text-accent-strong' : 'bg-neutral-soft text-ink-nav'
                "
              >
                {{ line.own ? $t('cutting.source.own') : $t('cutting.source.shop') }}
              </span>
            </div>
          </div>

          <label class="field !mb-0 mt-1 border-t border-divider pt-4">
            <!-- `(ixtiyoriy)` is a qualifier on the label, not fine print: same
                 size as the label, lighter weight. `<small>` shrank it to ~10.8px
                 and kept the label's 600, which read as a badge. -->
            <span
              >{{ $t('orders.checkout.note') }}
              <span class="font-normal text-ink-muted">{{
                $t('orders.checkout.optional')
              }}</span></span
            >
            <textarea
              v-model="note"
              class="mp-input min-h-[84px] resize-y px-[13px] py-[11px]"
              :placeholder="$t('orders.checkout.notePlaceholder')"
            ></textarea>
          </label>
          <p v-if="placeError" class="mp-field-error mt-3">{{ placeError }}</p>
        </div>
      </div>

      <div class="card content-start">
        <div class="card-b !pt-[22px]">
          <h2 class="mb-4 font-display text-[19px] font-bold tracking-[-0.02em] text-ink">
            {{ $t('orders.checkout.price') }}
          </h2>
          <div
            class="flex items-baseline justify-between gap-3.5 border-t border-divider py-[13px]"
          >
            <span class="text-sm text-ink-soft">{{ $t('orders.checkout.materials') }}</span>
            <span class="num text-[14.5px] font-semibold text-ink">
              {{ formatTiyin(quote.subtotal_materials_tiyin) }}
            </span>
          </div>
          <div
            class="flex items-baseline justify-between gap-3.5 border-t border-divider py-[13px]"
          >
            <span class="text-sm text-ink-soft">{{ cuttingLabel }}</span>
            <span class="num text-[14.5px] font-semibold text-ink">
              {{ formatTiyin(quote.subtotal_cutting_tiyin) }}
            </span>
          </div>
          <div
            v-if="quote.subtotal_edge_banding_tiyin > 0"
            class="flex items-baseline justify-between gap-3.5 border-t border-divider py-[13px]"
          >
            <span class="text-sm text-ink-soft">{{ $t('orders.checkout.edge') }}</span>
            <span class="num text-[14.5px] font-semibold text-ink">
              {{ formatTiyin(quote.subtotal_edge_banding_tiyin) }}
            </span>
          </div>
          <div class="flex items-baseline justify-between border-t border-divider pb-1 pt-4">
            <span class="text-[15px] font-semibold text-ink">{{
              $t('orders.checkout.total')
            }}</span>
            <span class="num font-display text-[26px] font-bold tracking-[-0.03em] text-ink">
              {{ formatTiyin(quote.total_tiyin) }}
            </span>
          </div>
          <!-- Above the buttons, not under them: it is the condition the click
               commits to, so it has to be read before the click, not after. -->
          <p class="mb-[18px] mt-3 text-[13.5px] text-ink-soft">
            {{ $t('orders.checkout.autoConfirm') }}
          </p>
          <div class="flex flex-wrap justify-between gap-3">
            <RouterLink
              :to="rolePath(`/workshop/orders/cutting/${draftId}`)"
              class="mp-button mp-button-outline h-[42px]"
            >
              <!-- Its own key, not the shared `orders.action.backToDrawing`:
                   that label also titles the revision-review screen, where the
                   destination is not the step the reader just came from. -->
              {{ $t('orders.checkout.back') }}
            </RouterLink>
            <button
              type="button"
              class="mp-button mp-button-primary h-[42px]"
              :disabled="!canPlace"
              @click="place"
            >
              {{ placing ? $t('orders.checkout.placing') : $t('orders.checkout.place') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
