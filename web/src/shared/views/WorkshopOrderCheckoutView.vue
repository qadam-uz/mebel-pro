<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { isUzPhone, normalizeUzPhone } from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import { formatTiyin } from '@/shared/formatters'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useCuttingStore } from '@/shared/stores/cutting'
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
    <div class="page-head">
      <div>
        <h1>{{ $t('orders.checkout.title') }}</h1>
        <div class="sub">
          {{ quote ? quote.branch_name : $t('orders.checkout.branchFallback') }}
        </div>
      </div>
      <div class="tools">
        <RouterLink
          :to="rolePath(`/workshop/orders/cutting/${draftId}`)"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          {{ $t('orders.action.backToDrawing') }}
        </RouterLink>
      </div>
    </div>

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

    <div v-else-if="quote" class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div class="card">
        <div class="card-h">
          <h2>{{ $t('orders.checkout.client') }}</h2>
        </div>
        <div class="card-b grid gap-4">
          <label class="field">
            <span>{{ $t('orders.checkout.name') }}</span>
            <input v-model="contactName" class="mp-input" autocomplete="name" />
          </label>
          <label class="field">
            <span>{{ $t('orders.checkout.phone') }}</span>
            <PhoneInput v-model="contactPhone" />
            <span v-if="contactPhone && !isUzPhone(contactPhone)" class="mp-field-error">
              {{ $t('orders.checkout.phoneInvalid') }}
            </span>
          </label>
          <label class="field">
            <span
              >{{ $t('orders.checkout.note') }}
              <small class="text-ink-muted">{{ $t('orders.checkout.optional') }}</small></span
            >
            <input
              v-model="note"
              class="mp-input"
              :placeholder="$t('orders.checkout.notePlaceholder')"
            />
          </label>
          <p v-if="placeError" class="mp-field-error">{{ placeError }}</p>
        </div>
      </div>

      <div class="card content-start">
        <div class="card-h">
          <h2>{{ $t('orders.checkout.price') }}</h2>
        </div>
        <div class="card-b grid gap-2 text-sm">
          <div class="flex justify-between">
            <span class="text-ink-soft">{{ $t('orders.checkout.cutting') }}</span>
            <span class="num">{{ formatTiyin(quote.subtotal_cutting_tiyin) }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-ink-soft">{{ $t('orders.checkout.materials') }}</span>
            <span class="num">{{ formatTiyin(quote.subtotal_materials_tiyin) }}</span>
          </div>
          <div v-if="quote.subtotal_edge_banding_tiyin > 0" class="flex justify-between">
            <span class="text-ink-soft">{{ $t('orders.checkout.edge') }}</span>
            <span class="num">{{ formatTiyin(quote.subtotal_edge_banding_tiyin) }}</span>
          </div>
          <div class="mt-1 flex justify-between border-t border-hairline pt-2 font-bold">
            <span>{{ $t('orders.checkout.total') }}</span>
            <span class="num">{{ formatTiyin(quote.total_tiyin) }}</span>
          </div>
          <button
            type="button"
            class="mp-button mp-button-primary mt-3 w-full"
            :disabled="!canPlace"
            @click="place"
          >
            {{ placing ? $t('orders.checkout.placing') : $t('orders.checkout.place') }}
          </button>
          <p class="text-center text-xs text-ink-muted">{{ $t('orders.checkout.autoConfirm') }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
