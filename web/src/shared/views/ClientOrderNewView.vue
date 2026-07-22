<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import {
  clientErrorLabel,
  draftDisplayName,
  formatPercent,
  formatPhone,
  formatTodayHours,
  isUzPhone,
  normalizeUzPhone,
} from '@/shared/app/clientUi'
import { useRolePath } from '@/shared/app/paths'
import PhoneInput from '@/shared/components/PhoneInput.vue'
import { useToast } from '@/shared/composables/useToast'
import { formatTiyin } from '@/shared/formatters'
import { useAuthStore } from '@/shared/stores/auth'
import { materialLabel, metres, useCuttingStore } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderQuote } from '@/shared/stores/orders'

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
const canPlace = computed(
  () =>
    Boolean(quote.value) && contactName.value.trim().length > 0 && isUzPhone(contactPhone.value),
)
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
const materialNames = computed(() => {
  const result = chosenResult.value
  if (!result) return []
  const materialIds = [...new Set(result.parts_snapshot.map((part) => part.material_id))]
  return materialIds.map((id) => {
    const snapshot = result.material_snapshots[id]
    if (!snapshot) return id
    const name = String(snapshot.name ?? snapshot.title ?? id)
    const manufacturer = String(snapshot.manufacturer_name ?? '')
    return manufacturer && !name.includes(manufacturer) ? `${manufacturer} ${name}` : name
  })
})

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
    localError.value = clientErrorLabel(
      orders.error,
      "Tanlangan filial uchun narxni hisoblab bo'lmadi.",
    )
  } finally {
    quoteLoading.value = false
  }
}

async function placeOrder() {
  if (!branchId.value || !quote.value) {
    localError.value = 'Tanlangan filial uchun narx tayyor emas.'
    return
  }
  if (!contactName.value.trim()) {
    localError.value = 'Ismni kiriting.'
    return
  }
  if (!isUzPhone(contactPhone.value)) {
    localError.value = "Telefon +998XXXXXXXXX shaklida bo'lishi kerak."
    return
  }
  placing.value = true
  localError.value = null
  try {
    const order = await orders.createClientOrder({
      draft_id: draftId.value,
      branch_id: branchId.value,
      contact_name: contactName.value.trim(),
      contact_phone: normalizeUzPhone(contactPhone.value),
    })
    toast.success('Buyurtma joylandi.')
    await router.push(rolePath(`/c/orders/${order.id}?new=1`))
  } catch {
    localError.value = clientErrorLabel(orders.error, 'Buyurtma yuborilmadi.')
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
    toast.warn('Bu chizma allaqachon buyurtma qilingan.')
    await router.replace(rolePath(`/c/orders/${boundOrderId}`))
    return
  }
  if (cutting.currentDraft && !chosenResult.value) {
    toast.warn('Avval chizmani optimallashtiring va natijani tanlang.')
    await router.replace(rolePath(`/c/cutting/${draftId.value}`))
    return
  }
  if (!branchId.value) {
    toast.warn('Avval chizma uchun filialni tanlang.')
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
      Natijaga qaytish
    </RouterLink>

    <div class="client-page-head">
      <div>
        <h1>Buyurtmani tasdiqlash</h1>
        <p class="sub">Filial, aloqa ma'lumotlari va yakuniy narxni tekshiring.</p>
      </div>
    </div>

    <section v-if="cutting.loading" class="grid gap-3" aria-live="polite">
      <div class="client-skeleton h-32"></div>
      <div class="client-skeleton h-64"></div>
    </section>

    <section v-else-if="cutting.error" class="client-error">
      <div class="client-error-icon">!</div>
      <h3>Chizma yuklanmadi</h3>
      <p>Buyurtma berish uchun chizma ma'lumotlarini qayta yuklash kerak.</p>
      <p class="client-trace">trace {{ cutting.traceId ?? 'unavailable' }}</p>
    </section>

    <section
      v-else-if="draft && chosenResult"
      class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_330px]"
    >
      <div class="grid min-w-0 gap-4">
        <section class="client-card">
          <div class="client-card-h"><h2>Olib ketish joyi</h2></div>
          <div class="client-card-b">
            <div v-if="quote" class="rounded-md bg-sunk p-4">
              <div class="font-serif text-lg font-semibold text-ink">{{ quote.branch_name }}</div>
              <div class="mt-1 font-mono text-xs text-ink-muted">{{ quote.branch_address }}</div>
              <div class="mt-1 text-xs text-ink-soft">
                Bugun: {{ formatTodayHours(quote.today_hours) }}
              </div>
              <div class="mt-2 font-mono text-xs text-ink-muted">
                Tel: {{ formatPhone(quote.branch_phone) }}
              </div>
            </div>
            <div v-else-if="quoteLoading" class="client-skeleton h-28"></div>
            <p v-else class="text-sm font-bold text-danger">Filial narxi yuklanmadi.</p>
            <p class="mt-3 text-xs text-ink-muted">
              Bu filial chizma yaratishda tanlangan. Uni almashtirish kerak bo'lsa, detallar
              sahifasiga qayting.
            </p>
          </div>
        </section>

        <section class="client-card">
          <div class="client-card-h"><h2>Aloqa ma'lumotlari</h2></div>
          <div class="client-card-b">
            <div class="client-banner success">
              <span class="font-mono font-black">i</span>
              <span>Bu ma'lumot ustaxona siz bilan bog'lanishi uchun ulashiladi.</span>
            </div>
            <div class="grid gap-3 md:grid-cols-2">
              <label class="grid gap-1 text-sm font-bold text-ink">
                Ism
                <input v-model="contactName" class="mp-input" autocomplete="name" />
                <button
                  type="button"
                  class="w-fit text-xs font-bold text-accent underline"
                  @click="resetField('name')"
                >
                  Profildan tiklash
                </button>
              </label>
              <label class="grid gap-1 text-sm font-bold text-ink">
                Telefon
                <PhoneInput v-model="contactPhone" required />
                <span v-if="contactPhone && !isUzPhone(contactPhone)" class="text-xs text-danger"
                  >Telefon +998XXXXXXXXX shaklida bo'lishi kerak</span
                >
                <button
                  type="button"
                  class="w-fit text-xs font-bold text-accent underline"
                  @click="resetField('phone')"
                >
                  Profildan tiklash
                </button>
              </label>
            </div>
          </div>
        </section>

        <section class="client-card">
          <div class="client-card-h"><h2>Yakuniy hisob</h2></div>
          <div class="client-card-b">
            <div class="grid gap-2 rounded-md bg-sunk p-4 font-mono text-xs">
              <div class="flex justify-between gap-4">
                <span class="text-ink-soft">Kesish xizmati</span
                ><span>{{ formatTiyin(quote?.subtotal_cutting_tiyin ?? 0) }}</span>
              </div>
              <div class="flex justify-between gap-4">
                <span class="text-ink-soft">Panel materiallar</span
                ><span>{{ formatTiyin(quote?.subtotal_materials_tiyin ?? 0) }}</span>
              </div>
              <div class="flex justify-between gap-4">
                <span class="text-ink-soft">Kromka</span
                ><span>{{ formatTiyin(quote?.subtotal_edge_banding_tiyin ?? 0) }}</span>
              </div>
              <div
                class="mt-2 flex justify-between gap-4 border-t border-hairline pt-3 text-sm font-extrabold text-accent"
              >
                <span>Jami</span><span>{{ formatTiyin(quote?.total_tiyin ?? 0) }}</span>
              </div>
            </div>
            <p class="mt-3 text-sm text-ink-soft">
              Onlayn to'lov yo'q. To'lov ustaxona bilan kelishilgan tartibda amalga oshiriladi.
            </p>
          </div>
        </section>

        <div class="flex justify-end">
          <button
            type="button"
            class="mp-button mp-button-primary"
            :disabled="placing || !canPlace"
            @click="placeOrder"
          >
            {{ placing ? 'Yuborilmoqda' : 'Buyurtmani tasdiqlash' }}
          </button>
        </div>
      </div>

      <aside class="client-card h-fit xl:sticky xl:top-24">
        <div class="client-card-h"><h2>Chizma haqida</h2></div>
        <div class="client-card-b">
          <div class="grid gap-2 text-sm">
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Chizma</span
              ><span class="text-xs font-bold text-ink">{{ draftDisplayName(draft) }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Qismlar</span
              ><span class="font-mono font-bold text-ink">{{ totalQuantity }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Panellar</span
              ><span class="font-mono font-bold text-ink">{{ totalPanels }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Kromka</span
              ><span class="font-mono font-bold text-ink">{{ metres(totalEdge) }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Chiqim</span
              ><span class="font-mono font-bold text-ink">{{
                formatPercent(chosenResult.waste_percentage)
              }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Materiallar</span
              ><span class="max-w-[190px] text-right font-mono text-xs font-bold text-ink">{{
                materialNames.join(' · ') || materialLabel(null)
              }}</span>
            </div>
          </div>
          <div v-if="localError" class="client-banner danger mt-4">
            <span class="font-mono font-black">!</span><span>{{ localError }}</span>
          </div>
          <button
            v-if="!quote && !quoteLoading"
            type="button"
            class="mp-button mp-button-outline mt-4 w-full"
            @click="loadQuote"
          >
            Qayta urinish
          </button>
        </div>
      </aside>
    </section>
  </section>
</template>
