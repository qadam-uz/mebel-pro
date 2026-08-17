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

// Each price line names what it was counted from, so the operator can answer
// "why this much?" without leaving the screen. The figure stays on the right;
// the basis sits under the label, where it reads as evidence rather than as a
// second number to add up.
const priceRows = computed(() => {
  const current = quote.value
  if (!current) return []
  const chosen = chosenResult.value
  const shopSheets = current.material_lines.reduce(
    (sum, line) => sum + Math.max(0, line.panels_used - line.own_panels),
    0,
  )
  const ownSheets = current.material_lines.reduce((sum, line) => sum + line.own_panels, 0)
  const edgeMm = Object.values(chosen?.edge_consumed_shop_by_material ?? {}).reduce(
    (sum, value) => sum + value,
    0,
  )

  const rows = [
    {
      key: 'materials',
      label: t('orders.checkout.materials'),
      sub: shopSheets
        ? `${shopSheets} ${t('cutting.unit.sheet', shopSheets)}` +
          (ownSheets ? ` · ${t('orders.checkout.ownSheets', { count: ownSheets })}` : '')
        : t('orders.checkout.allOwnMaterial'),
      value: formatTiyin(current.subtotal_materials_tiyin),
    },
    {
      key: 'cutting',
      label: t('orders.checkout.cutting'),
      sub: chosen?.total_cut_length_mm
        ? t('orders.checkout.cuttingBasis', { length: metres(chosen.total_cut_length_mm) })
        : '',
      value: formatTiyin(current.subtotal_cutting_tiyin),
    },
  ]
  if (current.subtotal_edge_banding_tiyin > 0) {
    rows.push({
      key: 'edge',
      label: t('orders.checkout.edge'),
      sub: edgeMm > 0 ? t('orders.checkout.edgeBasis', { length: metres(edgeMm) }) : '',
      value: formatTiyin(current.subtotal_edge_banding_tiyin),
    })
  }
  return rows
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
      class="grid items-start gap-5 min-[990px]:grid-cols-[minmax(0,1.32fr)_minmax(300px,0.68fr)]"
    >
      <div class="grid gap-5">
        <!-- The client is a heading now, not a three-row table. It was decided on
             step 1 and only has to be recognised here — name large, the two facts
             that disambiguate it underneath, and one way back if it is wrong. -->
        <div class="card">
          <div class="card-b !py-5">
            <div class="flex flex-wrap items-center gap-3">
              <span class="min-w-0 flex-1">
                <span
                  class="block font-display text-xl font-bold leading-tight tracking-[-0.02em] text-ink"
                >
                  {{ contactName }}
                </span>
                <span class="num mt-[3px] block text-[13.5px] text-ink-soft">
                  {{ contactPhone }} · {{ quote.branch_name }}
                </span>
              </span>
              <RouterLink
                :to="rolePath('/workshop/orders/new')"
                class="mp-button mp-button-outline h-[34px] flex-none rounded-[10px] px-[13px] text-[13px]"
              >
                {{ $t('orders.checkout.changeClient') }}
              </RouterLink>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-b !pb-[22px] !pt-5">
            <div class="mb-1.5 flex flex-wrap items-baseline justify-between gap-3">
              <h2 class="font-display text-[17px] font-bold tracking-[-0.02em] text-ink">
                {{ $t('orders.checkout.contents') }}
              </h2>
              <span class="num text-[13px] text-ink-muted">{{ contentsTotalLine }}</span>
            </div>
            <div
              v-for="line in materialLines"
              :key="line.id"
              class="grid items-center gap-[11px] border-t border-divider py-[11px] [grid-template-columns:26px_minmax(0,1fr)_auto]"
            >
              <span
                class="size-[26px] rounded-[7px] border border-hairline"
                :style="line.swatch"
                aria-hidden="true"
              ></span>
              <span class="min-w-0">
                <span class="block truncate text-[13.5px] font-semibold text-ink">
                  {{ line.name }}
                </span>
                <span class="num block text-[12.5px] text-ink-soft">{{ line.sub }}</span>
              </span>
              <span
                class="inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-[3px] text-[11px] font-bold"
                :class="line.own ? 'bg-track text-ink' : 'bg-neutral-soft text-ink-nav'"
              >
                {{ line.own ? $t('cutting.source.own') : $t('cutting.source.shop') }}
              </span>
            </div>

            <label class="field !mb-0 mt-1 border-t border-divider pt-[15px]">
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
                class="mp-input min-h-[72px] resize-y px-[13px] py-[11px]"
                :placeholder="$t('orders.checkout.notePlaceholder')"
              ></textarea>
            </label>
            <p v-if="placeError" class="mp-field-error mt-3">{{ placeError }}</p>
          </div>
        </div>
      </div>

      <!-- The price card is the one that gets clicked, so it carries the action:
           total, then the commit, then the way back, then the condition. -->
      <div class="card content-start overflow-hidden">
        <div class="px-[22px] pb-1 pt-5">
          <h2 class="mb-1 font-display text-[17px] font-bold tracking-[-0.02em] text-ink">
            {{ $t('orders.checkout.price') }}
          </h2>
          <div
            v-for="row in priceRows"
            :key="row.key"
            class="flex items-baseline justify-between gap-3.5 border-t border-divider py-3"
          >
            <span class="min-w-0">
              <span class="block text-sm font-semibold text-ink">{{ row.label }}</span>
              <span v-if="row.sub" class="num mt-px block text-xs text-ink-muted">
                {{ row.sub }}
              </span>
            </span>
            <span class="num flex-none whitespace-nowrap text-[14.5px] font-semibold text-ink">
              {{ row.value }}
            </span>
          </div>
        </div>
        <div class="border-t border-divider bg-sunk px-[22px] pb-5 pt-4">
          <div class="flex items-baseline justify-between gap-3">
            <span class="text-[13.5px] font-semibold text-ink-soft">
              {{ $t('orders.checkout.total') }}
            </span>
            <span
              class="num font-display text-[27px] font-bold leading-[1.1] tracking-[-0.03em] text-ink"
            >
              {{ formatTiyin(quote.total_tiyin) }}
            </span>
          </div>
          <button
            type="button"
            class="mp-button mp-button-primary mt-4 h-[46px] w-full rounded-xl text-[15px]"
            :disabled="!canPlace"
            @click="place"
          >
            {{ placing ? $t('orders.checkout.placing') : $t('orders.checkout.place') }}
          </button>
          <RouterLink
            :to="rolePath(`/workshop/orders/cutting/${draftId}`)"
            class="mp-button mt-1.5 h-10 w-full rounded-[11px] text-[13.5px] font-semibold text-ink-nav hover:bg-neutral-soft"
          >
            <!-- Its own key, not the shared `orders.action.backToDrawing`: that
                 label also titles the revision-review screen, where the
                 destination is not the step the reader just came from. -->
            {{ $t('orders.checkout.back') }}
          </RouterLink>
          <p class="mt-2.5 text-center text-[12.5px] leading-[1.45] text-ink-muted">
            {{ $t('orders.checkout.autoConfirm') }}
          </p>
        </div>
      </div>
    </div>
  </section>
</template>
