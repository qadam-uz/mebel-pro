<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import {
  clientErrorLabel,
  formatPercent,
  formatPhone,
  formatTodayHours,
  isUzPhone,
  normalizeUzPhone,
} from '@/shared/app/clientUi'
import Icon from '@/shared/components/AppIcon.vue'
import ClientErrorState from '@/shared/components/ClientErrorState.vue'
import { useToast } from '@/shared/composables/useToast'
import { useRolePath } from '@/shared/app/paths'
import { formatTiyin } from '@/shared/formatters'
import { materialLabel, metres, useCuttingStore } from '@/shared/stores/cutting'
import { useAuthStore } from '@/shared/stores/auth'
import { useOrdersStore, type OrderQuote } from '@/shared/stores/orders'

const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const auth = useAuthStore()
const cutting = useCuttingStore()
const orders = useOrdersStore()
const toast = useToast()

const draftId = computed(() => String(route.params.draft_id))
const step = ref<'branch' | 'checkout'>('branch')
const selectedBranchId = ref<string | null>(null)
const quoteByBranch = ref<Record<string, OrderQuote>>({})
const quoteErrors = ref<Record<string, string>>({})
const quoteErrorCodes = ref<Record<string, string | null>>({})
const quotesTraceId = ref<string | null>(null)
const quotesLoading = ref(false)
const contactName = ref('')
const contactPhone = ref('')
const placing = ref(false)
const localError = ref<string | null>(null)

const draft = computed(() => cutting.currentDraft)
const chosenResult = computed(() =>
  draft.value?.results.find((result) => result.id === draft.value?.chosen_result_id),
)
const activeBranches = computed(() =>
  cutting.branchOptions.filter((branch) => branch.status === 'active'),
)
const branchRows = computed(() =>
  [...activeBranches.value].sort((left, right) => {
    const leftHasQuote = Boolean(quoteByBranch.value[left.branch_id])
    const rightHasQuote = Boolean(quoteByBranch.value[right.branch_id])
    if (leftHasQuote !== rightHasQuote) return leftHasQuote ? -1 : 1
    return `${left.workshop_name} ${left.branch_name}`.localeCompare(
      `${right.workshop_name} ${right.branch_name}`,
    )
  }),
)
const preferredBranch = computed(() =>
  draft.value?.preferred_branch_id
    ? (activeBranches.value.find(
        (branch) => branch.branch_id === draft.value?.preferred_branch_id,
      ) ?? null)
    : null,
)
// Every active branch failed to quote.
const quotesFailedAll = computed(
  () =>
    !quotesLoading.value &&
    activeBranches.value.length > 0 &&
    Object.keys(quoteByBranch.value).length === 0,
)
const hasNotCarriedFailure = computed(() =>
  Object.values(quoteErrorCodes.value).some(
    (code) => code != null && NOT_CARRIED_CODES.includes(code),
  ),
)
// CB-19/115: all branches failed and at least one lacks a material in the set →
// name the materials and point back to the editor to fix them.
const showCarryRecovery = computed(() => quotesFailedAll.value && hasNotCarriedFailure.value)
// CB-21: all branches failed for some other reason (network/system) → a generic
// retryable page error.
const showQuotesError = computed(() => quotesFailedAll.value && !hasNotCarriedFailure.value)
const draftMaterialNames = computed(() => {
  const result = chosenResult.value
  if (!result) return []
  const ids = new Set<string>()
  for (const part of result.parts_snapshot) {
    if (part.material_id) ids.add(part.material_id)
    for (const side of ['edge_top', 'edge_bottom', 'edge_left', 'edge_right'] as const) {
      const edge = part[side]
      if (edge?.material_id) ids.add(edge.material_id)
    }
  }
  return [...ids].map((id) => materialName(id)).filter(Boolean)
})
const inactiveBranches = computed(() =>
  cutting.branchOptions.filter((branch) => branch.status !== 'active'),
)
const selectedQuote = computed(() =>
  selectedBranchId.value ? (quoteByBranch.value[selectedBranchId.value] ?? null) : null,
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
  if (!chosenResult.value || !draft.value) return []
  const materialIds = [
    ...new Set(draft.value.parts_snapshot.map((part) => part.material_id).filter(Boolean)),
  ]
  return materialIds.map((id) => materialName(id)).filter(Boolean)
})
const canPlace = computed(
  () =>
    Boolean(selectedQuote.value) &&
    contactName.value.trim().length > 0 &&
    isUzPhone(contactPhone.value),
)

function materialName(materialId: string) {
  const snapshot = chosenResult.value?.material_snapshots[materialId]
  if (!snapshot) return materialId
  const name = String(snapshot.name ?? snapshot.title ?? materialId)
  const manufacturer = String(snapshot.manufacturer_name ?? '')
  if (manufacturer && !name.includes(manufacturer)) return `${manufacturer} ${name}`
  return name
}

function branchTitle(
  quote: OrderQuote | null,
  fallback: { workshop_name: string; branch_name: string },
) {
  return quote?.branch_name ?? `${fallback.workshop_name} · ${fallback.branch_name}`
}

const NOT_CARRIED_CODES = ['branch_does_not_carry_panel', 'branch_does_not_carry_edge']

function quoteErrorLabel(errorCode: string | null | undefined) {
  if (errorCode === 'permission_denied' || errorCode === 'branch_closed')
    return 'Bu ustaxona hozir tanlash uchun yopiq.'
  if (errorCode && NOT_CARRIED_CODES.includes(errorCode))
    return "Bu ustaxonada kerakli material yo'q."
  if (errorCode === 'missing_cutting_rate' || errorCode === 'missing_edge_banding_rate')
    return 'Bu ustaxona narxlari hali sozlanmagan.'
  return 'Bu ustaxona hozircha buyurtma qabul qila olmaydi.'
}

function quoteBranch(branchId: string) {
  return quoteByBranch.value[branchId] ?? null
}

function selectBranch(branchId: string) {
  const quote = quoteBranch(branchId)
  if (!quote) return
  selectedBranchId.value = branchId
  step.value = 'checkout'
  localError.value = null
}

function gotoBranch() {
  step.value = 'branch'
  localError.value = null
}

function resetField(field: 'name' | 'phone') {
  if (field === 'name') contactName.value = auth.me?.name ?? ''
  else contactPhone.value = auth.me?.phone ?? '+998'
}

async function loadQuotes() {
  if (!chosenResult.value) return
  quotesLoading.value = true
  quoteByBranch.value = {}
  quoteErrors.value = {}
  quoteErrorCodes.value = {}
  quotesTraceId.value = null
  try {
    // The store attributes each branch its own error code (CB-20); we keep the
    // raw codes (for the aggregate recovery states) and map to Uzbek per card.
    const { quotes, errors, firstErrorTraceId } = await orders.quoteBranches(
      draftId.value,
      activeBranches.value.map((branch) => branch.branch_id),
    )
    quoteByBranch.value = quotes
    quoteErrorCodes.value = errors
    quotesTraceId.value = firstErrorTraceId
    quoteErrors.value = Object.fromEntries(
      Object.entries(errors).map(([branchId, code]) => [branchId, quoteErrorLabel(code)]),
    )
  } finally {
    quotesLoading.value = false
    // Pre-select the client's preferred branch when it can fulfil the order.
    if (
      !selectedBranchId.value &&
      preferredBranch.value &&
      quoteByBranch.value[preferredBranch.value.branch_id]
    ) {
      selectedBranchId.value = preferredBranch.value.branch_id
    }
  }
}

async function placeOrder() {
  if (!selectedBranchId.value || !selectedQuote.value) {
    localError.value = 'Avval ustaxonani tanlang.'
    step.value = 'branch'
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
      branch_id: selectedBranchId.value,
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
  contactPhone.value = auth.me?.phone ?? '+998'
  await cutting.loadDraft(draftId.value)
  // A draft already bound to an order can't be re-ordered — don't walk the user
  // through the whole wizard only to fail at submit; send them to the order (CB-18).
  const boundOrderId = cutting.currentDraft?.results.find((result) => result.order_id)?.order_id
  if (boundOrderId) {
    toast.warn('Bu chizma allaqachon buyurtma qilingan.')
    await router.replace(rolePath(`/c/orders/${boundOrderId}`))
    return
  }
  // The draft loaded but was never optimised/chosen — send the client back to
  // the editor to pick a result instead of a dead-end empty state (CB-116).
  if (cutting.currentDraft && !chosenResult.value) {
    toast.warn('Avval chizmani optimallashtiring va natijani tanlang.')
    await router.replace(rolePath(`/c/cutting/${draftId.value}`))
    return
  }
  await cutting.loadBranchOptions()
  await loadQuotes()
})
</script>

<template>
  <section>
    <RouterLink :to="rolePath(`/c/cutting/${draftId}`)" class="client-back">
      <span aria-hidden="true">←</span>
      Chizmaga qaytish
    </RouterLink>

    <div class="client-page-head">
      <div>
        <h1>{{ step === 'branch' ? 'Ustaxonani tanlang' : 'Tasdiqlash' }}</h1>
        <p class="sub">
          {{
            step === 'branch'
              ? 'Materiallaringiz mavjud faol ustaxonalardan birini tanlang. Narx shu ustaxonaga muvofiq belgilanadi.'
              : `${selectedQuote?.branch_name ?? 'Tanlangan ustaxona'} uchun buyurtma tafsilotlarini tekshiring.`
          }}
        </p>
      </div>
    </div>

    <section v-if="cutting.loading" class="grid gap-3" aria-live="polite">
      <div class="client-skeleton h-28"></div>
      <div class="client-skeleton h-28"></div>
    </section>

    <section v-else-if="cutting.error" class="client-error">
      <div class="client-error-icon">!</div>
      <h3>Chizma yuklanmadi</h3>
      <p>Buyurtma berish uchun chizma ma'lumotlarini qayta yuklash kerak.</p>
      <p class="client-trace">trace {{ cutting.traceId ?? 'unavailable' }}</p>
    </section>

    <section v-else-if="!draft || !chosenResult" class="client-empty">
      <div class="client-empty-icon"><Icon name="box" /></div>
      <h3>Tanlangan natija yo'q</h3>
      <p>Buyurtma berishdan oldin chizmani optimallashtiring va natijani tanlang.</p>
      <RouterLink :to="rolePath(`/c/cutting/${draftId}`)" class="mp-button mp-button-primary mt-4">
        Chizmaga qaytish
      </RouterLink>
    </section>

    <section v-else class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_330px]">
      <div class="min-w-0">
        <div v-if="step === 'branch'" class="grid gap-3">
          <div v-if="quotesLoading" class="grid gap-3">
            <div class="client-skeleton h-32"></div>
            <div class="client-skeleton h-32"></div>
            <div class="client-skeleton h-32"></div>
          </div>

          <template v-else>
            <div v-if="activeBranches.length === 0" class="client-empty">
              <div class="client-empty-icon"><Icon name="alert" /></div>
              <h3>Faol ustaxona topilmadi</h3>
              <p>Hozir hech bir ustaxona mijoz buyurtmasi qabul qilmayapti.</p>
            </div>

            <div v-else-if="showCarryRecovery" class="client-empty">
              <div class="client-empty-icon"><Icon name="alert" /></div>
              <h3>Hech bir ustaxona bu kombinatsiyaga mos kelmaydi</h3>
              <p>
                Bu materiallarni hozir hech qaysi faol ustaxona tashimaydi:
                <b class="text-ink">{{ draftMaterialNames.join(' · ') }}</b
                >. Chizmaga qaytib ushbu qismlarni "O'zim olib kelaman"ga aylantiring yoki boshqa
                material tanlang.
              </p>
              <RouterLink
                :to="rolePath(`/c/cutting/${draftId}`)"
                class="mp-button mp-button-primary mt-4"
              >
                Chizmaga qaytish
              </RouterLink>
            </div>

            <ClientErrorState
              v-else-if="showQuotesError"
              title="Ustaxonalardan narx olinmadi"
              :trace-id="quotesTraceId"
              @retry="loadQuotes"
            />

            <template v-else>
              <button
                v-for="branch in branchRows"
                :key="branch.branch_id"
                type="button"
                class="client-card w-full p-0 text-left transition hover:-translate-y-0.5 hover:border-ink-soft"
                :class="[
                  selectedBranchId === branch.branch_id
                    ? 'border-accent ring-2 ring-accent-tint'
                    : '',
                  !quoteBranch(branch.branch_id)
                    ? 'cursor-not-allowed opacity-60 hover:translate-y-0'
                    : '',
                ]"
                :disabled="!quoteBranch(branch.branch_id)"
                @click="selectBranch(branch.branch_id)"
              >
                <div class="flex flex-wrap items-start justify-between gap-4 p-5">
                  <div class="min-w-0">
                    <h2 class="font-serif text-lg font-semibold text-ink">
                      {{ branchTitle(quoteBranch(branch.branch_id), branch) }}
                    </h2>
                    <span
                      v-if="
                        branch.branch_id === preferredBranch?.branch_id &&
                        quoteBranch(branch.branch_id)
                      "
                      class="client-pill client-pill-info mt-1 inline-block"
                    >
                      Tavsiya — afzal filial
                    </span>
                    <p class="mt-1 font-mono text-xs text-ink-muted">
                      {{
                        quoteBranch(branch.branch_id)?.branch_address ??
                        `${branch.workshop_name} · ${branch.branch_name}`
                      }}
                    </p>
                    <p class="mt-1 text-xs text-ink-soft">
                      Bugun: {{ formatTodayHours(branch.today_hours) }}
                    </p>
                  </div>
                  <div class="font-mono text-2xl font-extrabold text-accent">
                    {{
                      quoteBranch(branch.branch_id)
                        ? formatTiyin(quoteBranch(branch.branch_id)?.total_tiyin ?? 0)
                        : '-'
                    }}
                  </div>
                </div>

                <div class="mx-5 mb-5 rounded-md bg-sunk p-3 font-mono text-xs text-ink-soft">
                  <template v-if="quoteBranch(branch.branch_id)">
                    <div class="flex justify-between gap-4 py-1">
                      <span>Kesish xizmati</span>
                      <span class="text-ink">{{
                        formatTiyin(quoteBranch(branch.branch_id)?.subtotal_cutting_tiyin ?? 0)
                      }}</span>
                    </div>
                    <div class="flex justify-between gap-4 py-1">
                      <span>Materiallar</span>
                      <span class="text-ink">{{
                        formatTiyin(quoteBranch(branch.branch_id)?.subtotal_materials_tiyin ?? 0)
                      }}</span>
                    </div>
                    <div class="flex justify-between gap-4 py-1">
                      <span>Krom yopishtirish</span>
                      <span class="text-ink">{{
                        formatTiyin(quoteBranch(branch.branch_id)?.subtotal_edge_banding_tiyin ?? 0)
                      }}</span>
                    </div>
                  </template>
                  <div v-else class="text-ink-soft">
                    {{ quoteErrors[branch.branch_id] ?? 'Narx hisoblanmadi.' }}
                  </div>
                </div>
              </button>

              <article
                v-for="branch in inactiveBranches"
                :key="branch.branch_id"
                class="client-card p-5 opacity-60"
                aria-disabled="true"
              >
                <div class="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 class="font-serif text-lg font-semibold text-ink">
                      {{ branch.workshop_name }} · {{ branch.branch_name }}
                    </h2>
                    <p class="mt-1 font-mono text-xs text-ink-muted">
                      {{
                        branch.status === 'temporarily_closed'
                          ? (branch.closed_reason ?? 'vaqtincha yopiq')
                          : 'faol emas'
                      }}
                    </p>
                  </div>
                  <span class="client-pill client-pill-new">Yopiq</span>
                </div>
              </article>
            </template>
          </template>
        </div>

        <div v-else class="grid gap-4">
          <section class="client-card">
            <div class="client-card-h">
              <h2>Olib ketish</h2>
            </div>
            <div class="client-card-b">
              <p class="mb-3 text-sm text-ink-soft">
                Buyurtma tayyor bo'lgach tanlangan ustaxonadan olib ketasiz.
              </p>
              <div class="rounded-md bg-sunk p-4">
                <div class="font-serif text-lg font-semibold text-ink">
                  {{ selectedQuote?.branch_name }}
                </div>
                <div class="mt-1 font-mono text-xs text-ink-muted">
                  {{ selectedQuote?.branch_address }}
                </div>
                <div class="mt-1 text-xs text-ink-soft">
                  Bugun: {{ formatTodayHours(selectedQuote?.today_hours) }}
                </div>
                <div class="mt-2 font-mono text-xs text-ink-muted">
                  Tel: {{ formatPhone(selectedQuote?.branch_phone) }}
                </div>
              </div>
            </div>
          </section>

          <section class="client-card">
            <div class="client-card-h">
              <h2>Aloqa ma'lumotlari</h2>
            </div>
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
                  <input
                    v-model="contactPhone"
                    class="mp-input"
                    autocomplete="tel"
                    inputmode="tel"
                    placeholder="+998XXXXXXXXX"
                  />
                  <span v-if="contactPhone && !isUzPhone(contactPhone)" class="text-xs text-danger">
                    Telefon +998XXXXXXXXX shaklida bo'lishi kerak
                  </span>
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
            <div class="client-card-h">
              <h2>Tasdiqlash</h2>
            </div>
            <div class="client-card-b">
              <div class="grid gap-3 rounded-md bg-sunk p-4 text-sm">
                <div class="flex justify-between gap-4">
                  <span class="text-ink-soft">Ustaxona</span>
                  <span class="font-bold text-ink">
                    {{ selectedQuote?.branch_name }}
                    <button
                      type="button"
                      class="ml-2 text-xs text-accent underline"
                      @click="gotoBranch"
                    >
                      o'zgartirish
                    </button>
                  </span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-ink-soft">Olib ketish</span>
                  <span class="max-w-[58%] text-right font-bold text-ink">
                    {{ selectedQuote?.branch_address }}
                  </span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-ink-soft">Aloqa</span>
                  <span class="font-bold text-ink">
                    {{ contactName || '-' }} · {{ formatPhone(contactPhone) }}
                  </span>
                </div>
              </div>

              <div class="mt-4 rounded-md bg-sunk p-4 font-mono text-xs">
                <div class="flex justify-between gap-4 py-1">
                  <span class="text-ink-soft">Kesish xizmati</span>
                  <span class="text-ink">{{
                    formatTiyin(selectedQuote?.subtotal_cutting_tiyin ?? 0)
                  }}</span>
                </div>
                <div class="flex justify-between gap-4 py-1">
                  <span class="text-ink-soft">Panel materiallar</span>
                  <span class="text-ink">{{
                    formatTiyin(selectedQuote?.subtotal_materials_tiyin ?? 0)
                  }}</span>
                </div>
                <div class="flex justify-between gap-4 py-1">
                  <span class="text-ink-soft">Krom yopishtirish</span>
                  <span class="text-ink">{{
                    formatTiyin(selectedQuote?.subtotal_edge_banding_tiyin ?? 0)
                  }}</span>
                </div>
                <div
                  class="mt-2 flex justify-between gap-4 border-t border-hairline pt-3 text-sm font-extrabold text-accent"
                >
                  <span>Jami</span>
                  <span>{{ formatTiyin(selectedQuote?.total_tiyin ?? 0) }}</span>
                </div>
              </div>
            </div>
          </section>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <button type="button" class="mp-button mp-button-outline" @click="gotoBranch">
              ← Ustaxonani o'zgartirish
            </button>
            <button
              type="button"
              class="mp-button mp-button-primary"
              :disabled="placing || !canPlace"
              @click="placeOrder"
            >
              {{ placing ? 'Yuborilmoqda' : 'Buyurtma berish' }}
            </button>
          </div>
        </div>
      </div>

      <aside class="client-card h-fit xl:sticky xl:top-24">
        <div class="client-card-h">
          <h2>Chizma haqida</h2>
        </div>
        <div class="client-card-b">
          <div class="grid gap-2 text-sm">
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Chizma</span>
              <span class="font-mono text-xs font-bold text-ink">{{ draft.id.slice(0, 8) }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Qismlar</span>
              <span class="font-mono font-bold text-ink">{{ totalQuantity }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Panellar</span>
              <span class="font-mono font-bold text-ink">{{ totalPanels }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Krom</span>
              <span class="font-mono font-bold text-ink">{{ metres(totalEdge) }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Chiqim</span>
              <span class="font-mono font-bold text-ink">
                {{ formatPercent(chosenResult.waste_percentage) }}
              </span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-ink-soft">Materiallar</span>
              <span class="max-w-[190px] text-right font-mono text-xs font-bold text-ink">
                {{ materialNames.join(' · ') || materialLabel(null) }}
              </span>
            </div>
          </div>

          <div class="mt-4 border-t border-dashed border-hairline pt-4">
            <template v-if="selectedQuote">
              <h3 class="mb-2 text-xs font-extrabold uppercase text-ink-muted">
                {{ selectedQuote.branch_name }}
              </h3>
              <div class="grid gap-2 text-sm">
                <div class="flex justify-between gap-4">
                  <span class="text-ink-soft">Kesish xizmati</span>
                  <span class="font-mono font-bold text-ink">
                    {{ formatTiyin(selectedQuote.subtotal_cutting_tiyin) }}
                  </span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-ink-soft">Materiallar</span>
                  <span class="font-mono font-bold text-ink">
                    {{ formatTiyin(selectedQuote.subtotal_materials_tiyin) }}
                  </span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-ink-soft">Krom</span>
                  <span class="font-mono font-bold text-ink">
                    {{ formatTiyin(selectedQuote.subtotal_edge_banding_tiyin) }}
                  </span>
                </div>
                <div class="mt-2 flex justify-between gap-4 border-t border-hairline pt-3">
                  <span class="font-extrabold text-ink">Jami</span>
                  <span class="font-mono text-lg font-extrabold text-accent">
                    {{ formatTiyin(selectedQuote.total_tiyin) }}
                  </span>
                </div>
              </div>
            </template>
            <p v-else class="text-sm font-bold text-ink-muted">
              Ustaxonani tanlang — narx ko'rsatiladi.
            </p>
          </div>

          <div v-if="localError" class="client-banner danger mt-4">
            <span class="font-mono font-black">!</span>
            <span>{{ localError }}</span>
          </div>
        </div>
      </aside>
    </section>
  </section>
</template>
