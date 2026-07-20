<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { apiErrorCode } from '@/shared/api/client'
import { useRolePath } from '@/shared/app/paths'
import { workshopErrorMessage } from '@/shared/app/workshopUi'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatTiyin } from '@/shared/formatters'
import { useCuttingStore } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderDetail, type OrderQuote } from '@/shared/stores/orders'

// Revision review (orders.md "Revising a placed order"): the last stop before
// an order edit is applied — the current frozen price next to the new quote at
// the order's branch, the discount-reset note, then Save or Discard.
// Refresh-safe: everything is re-fetched from the draft id in the route.
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const toast = useToast()
const cutting = useCuttingStore()
const orders = useOrdersStore()

const draftId = computed(() => String(route.params.draft_id))
const loading = ref(true)
const loadError = ref<string | null>(null)
const order = ref<OrderDetail | null>(null)
const quote = ref<OrderQuote | null>(null)
const reason = ref('')
const applying = ref(false)
const applyError = ref<string | null>(null)
const discardOpen = ref(false)
const discarding = ref(false)

const totalDelta = computed(() =>
  order.value && quote.value ? quote.value.total_tiyin - order.value.total_tiyin : 0,
)
const editable = computed(
  () => order.value !== null && ['new', 'confirmed'].includes(order.value.status),
)

onMounted(async () => {
  loading.value = true
  loadError.value = null
  try {
    await cutting.loadDraft(draftId.value)
    const draft = cutting.currentDraft
    if (!draft) {
      loadError.value = workshopErrorMessage(cutting.error)
      return
    }
    if (!draft.revision_of_order_id) {
      // Not a revision draft — this screen has no meaning for it.
      void router.replace(rolePath('/workshop/orders'))
      return
    }
    if (!draft.chosen_result_id) {
      // Nothing chosen yet — back to the editor.
      void router.replace(rolePath(`/workshop/orders/cutting/${draftId.value}`))
      return
    }
    order.value = await orders.fetchWorkshopOrder(draft.revision_of_order_id)
    quote.value = await orders.quoteWorkshopBranch(draftId.value, order.value.branch_id)
  } catch (caught) {
    loadError.value = workshopErrorMessage(apiErrorCode(caught))
  } finally {
    loading.value = false
  }
})

async function apply() {
  const current = order.value
  if (!current || !editable.value || applying.value) return
  applyError.value = null
  applying.value = true
  try {
    const updated = await orders.applyRevision(current.id, {
      version: current.version,
      reason: reason.value.trim() || null,
    })
    toast.success('Buyurtma yangilandi.')
    void router.push(rolePath(`/workshop/orders/${updated.id}`))
  } catch {
    applyError.value = workshopErrorMessage(orders.actionError ?? 'order_action_failed')
    // A version conflict refetches server-side state in the store; mirror the
    // fresh version here so the retry carries it.
    if (orders.actionError === 'order_version_conflict' && orders.currentOrder) {
      order.value = orders.currentOrder
    }
  } finally {
    applying.value = false
  }
}

async function discard() {
  const current = order.value
  if (discarding.value) return
  discarding.value = true
  try {
    await cutting.deleteDraft(draftId.value)
    toast.success('Tahrir bekor qilindi.')
    void router.push(rolePath(current ? `/workshop/orders/${current.id}` : '/workshop/orders'))
  } catch (caught) {
    discardOpen.value = false
    applyError.value = workshopErrorMessage(apiErrorCode(caught))
  } finally {
    discarding.value = false
  }
}
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Tahrirni saqlash</h1>
        <div class="sub">{{ order ? order.order_number : 'Buyurtma' }}</div>
      </div>
      <div class="tools">
        <RouterLink
          :to="rolePath(`/workshop/orders/cutting/${draftId}`)"
          class="mp-button mp-button-outline min-h-9 px-3 text-xs"
        >
          Chizmaga qaytish
        </RouterLink>
      </div>
    </div>

    <section v-if="loading" class="card p-5" aria-live="polite">
      <span class="sk-line"></span>
      <span class="sk-line mt-3"></span>
    </section>

    <section v-else-if="loadError" class="st-error" role="alert">
      <h3>Ma'lumotni yuklab bo'lmadi</h3>
      <p>{{ loadError }}</p>
      <button
        type="button"
        class="mp-button mp-button-outline mt-4 min-h-11 px-4"
        @click="router.go(0)"
      >
        Qayta urinish
      </button>
    </section>

    <section v-else-if="order && !editable" class="st-error" role="alert">
      <h3>Tahrirni endi qo'llab bo'lmaydi</h3>
      <p>
        Buyurtma holati o'zgargan — ishlab chiqarish boshlangan yoki buyurtma yopilgan. Ochiq
        tahrirni bekor qilishingiz mumkin.
      </p>
      <div class="mt-4 flex flex-wrap justify-center gap-2">
        <RouterLink
          :to="rolePath(`/workshop/orders/${order.id}`)"
          class="mp-button mp-button-outline min-h-11 px-4"
        >
          Buyurtmaga qaytish
        </RouterLink>
        <button
          type="button"
          class="mp-button mp-button-outline min-h-11 px-4 text-danger"
          @click="discardOpen = true"
        >
          Tahrirni bekor qilish
        </button>
      </div>
    </section>

    <div v-else-if="order && quote" class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div class="grid content-start gap-4">
        <div class="card">
          <div class="card-h"><h2>Narx taqqoslash</h2></div>
          <div class="card-b grid gap-2 text-sm">
            <div class="flex justify-between">
              <span class="text-ink-soft">Hozirgi jami</span>
              <span class="num">{{ formatTiyin(order.total_tiyin) }}</span>
            </div>
            <div class="flex justify-between font-bold">
              <span>Yangi jami</span>
              <span class="num">{{ formatTiyin(quote.total_tiyin) }}</span>
            </div>
            <div
              class="mt-1 flex justify-between border-t border-hairline pt-2"
              :class="totalDelta > 0 ? 'text-danger' : totalDelta < 0 ? 'text-success' : ''"
            >
              <span>Farq</span>
              <span class="num">
                {{ totalDelta > 0 ? '+' : '' }}{{ formatTiyin(totalDelta) }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="order.discount_tiyin > 0" class="banner warn" role="status">
          <div class="grow">
            Buyurtmadagi {{ formatTiyin(order.discount_tiyin) }} chegirma saqlashda bekor bo'ladi —
            kerak bo'lsa uni qaytadan kiriting.
          </div>
        </div>
        <p class="rounded-md bg-sunk p-3 text-sm text-ink-soft">
          Narx filialning joriy tariflari bo'yicha to'liq qayta hisoblanadi; mijozga buyurtma
          yangilangani haqida xabar boradi.
        </p>

        <div class="card">
          <div class="card-h">
            <h2>Sabab <small class="text-ink-muted">(ixtiyoriy)</small></h2>
          </div>
          <div class="card-b">
            <input
              v-model="reason"
              class="mp-input"
              placeholder="Masalan: mijoz o'lchamni o'zgartirdi"
            />
          </div>
        </div>
      </div>

      <div class="card content-start">
        <div class="card-h"><h2>Yangi narx</h2></div>
        <div class="card-b grid gap-2 text-sm">
          <div class="flex justify-between">
            <span class="text-ink-soft">Kesish</span>
            <span class="num">{{ formatTiyin(quote.subtotal_cutting_tiyin) }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-ink-soft">Material</span>
            <span class="num">{{ formatTiyin(quote.subtotal_materials_tiyin) }}</span>
          </div>
          <div v-if="quote.subtotal_edge_banding_tiyin > 0" class="flex justify-between">
            <span class="text-ink-soft">Krom</span>
            <span class="num">{{ formatTiyin(quote.subtotal_edge_banding_tiyin) }}</span>
          </div>
          <div class="mt-1 flex justify-between border-t border-hairline pt-2 font-bold">
            <span>Jami</span>
            <span class="num">{{ formatTiyin(quote.total_tiyin) }}</span>
          </div>
          <p v-if="applyError" class="mp-field-error">{{ applyError }}</p>
          <button
            type="button"
            class="mp-button mp-button-primary mt-3 w-full"
            :disabled="applying"
            @click="apply"
          >
            {{ applying ? 'Saqlanmoqda…' : "O'zgarishlarni saqlash" }}
          </button>
          <button
            type="button"
            class="mp-button mp-button-outline w-full text-danger"
            :disabled="applying || discarding"
            @click="discardOpen = true"
          >
            Tahrirni bekor qilish
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :open="discardOpen"
      title="Tahrirni bekor qilish"
      message="Tahrirdagi barcha o'zgarishlar o'chiriladi; buyurtma avvalgi holida qoladi."
      confirm-label="Ha, bekor qilinsin"
      cancel-label="Orqaga"
      busy-label="Bajarilmoqda"
      danger
      :busy="discarding"
      @cancel="discardOpen = false"
      @confirm="discard"
    />
  </section>
</template>
