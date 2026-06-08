<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import FormSelect from '@/shared/components/FormSelect.vue'
import type { ChoiceOption } from '@/shared/components/controlTypes'
import { formatTiyin } from '@/shared/formatters'
import { metres, useCuttingStore } from '@/shared/stores/cutting'
import { useAuthStore } from '@/shared/stores/auth'
import { useOrdersStore } from '@/shared/stores/orders'

const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const auth = useAuthStore()
const cutting = useCuttingStore()
const orders = useOrdersStore()

const draftId = computed(() => String(route.params.draft_id))
const branchId = ref<string | null>(null)
const contactName = ref('')
const contactPhone = ref('')
const placing = ref(false)
const localError = ref<string | null>(null)

const draft = computed(() => cutting.currentDraft)
const chosenResult = computed(() =>
  draft.value?.results.find((result) => result.id === draft.value?.chosen_result_id),
)
const branchChoices = computed<ChoiceOption[]>(() =>
  cutting.branchOptions
    .filter((branch) => branch.status === 'active')
    .map((branch) => ({
      value: branch.branch_id,
      label: `${branch.workshop_name} · ${branch.branch_name}`,
      meta: branch.status,
    })),
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

watch(branchId, (value) => {
  if (!value) {
    orders.currentQuote = null
    return
  }
  void orders.loadQuote(draftId.value, value)
})

async function placeOrder() {
  if (!branchId.value) {
    localError.value = 'Choose a branch.'
    return
  }
  if (!contactName.value.trim()) {
    localError.value = 'Enter contact name.'
    return
  }
  if (!/^\+998\d{9}$/.test(contactPhone.value.replace(/\s/g, ''))) {
    localError.value = 'Phone must be +998XXXXXXXXX.'
    return
  }
  placing.value = true
  localError.value = null
  try {
    const order = await orders.createClientOrder({
      draft_id: draftId.value,
      branch_id: branchId.value,
      contact_name: contactName.value,
      contact_phone: contactPhone.value.replace(/\s/g, ''),
    })
    await router.push(rolePath(`/c/orders/${order.id}?new=1`))
  } catch {
    localError.value = orders.error ?? 'Order could not be placed.'
  } finally {
    placing.value = false
  }
}

onMounted(async () => {
  contactName.value = auth.me?.name ?? ''
  contactPhone.value = auth.me?.phone ?? '+998'
  await cutting.loadDraft(draftId.value)
  await cutting.loadBranchOptions()
  branchId.value =
    draft.value?.preferred_branch_id &&
    branchChoices.value.some((item) => item.value === draft.value?.preferred_branch_id)
      ? draft.value.preferred_branch_id
      : (branchChoices.value[0]?.value ?? null)
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <RouterLink :to="rolePath(`/c/cutting/${draftId}`)" class="text-sm font-bold text-accent">
          Cutting editor
        </RouterLink>
        <h1 class="mt-2 font-serif text-3xl font-semibold text-ink">Place order</h1>
        <p class="mt-2 max-w-2xl text-base text-ink-soft">
          Choose a branch, review the frozen price, and share contact details with the workshop.
        </p>
      </div>
    </div>

    <section v-if="cutting.loading" class="mp-surface p-5" aria-live="polite">
      Loading cutting
    </section>
    <section v-else-if="cutting.error" class="mp-surface p-5 text-danger">
      Cutting could not be loaded. trace {{ cutting.traceId ?? 'unavailable' }}
    </section>
    <section v-else-if="!draft || !chosenResult" class="mp-surface p-5">
      <div class="rounded-lg border border-dashed border-hairline-strong bg-sunk p-5">
        <h2 class="font-serif text-2xl font-semibold text-ink">No chosen result</h2>
        <p class="mt-2 text-sm text-ink-soft">Optimise the cutting and choose a result first.</p>
      </div>
    </section>

    <template v-else>
      <section class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div class="space-y-5">
          <div class="mp-surface p-5">
            <h2 class="font-serif text-xl font-semibold text-ink">Branch</h2>
            <p class="mt-1 text-sm text-ink-soft">
              Only active branches are available for new orders.
            </p>
            <div class="mt-4">
              <FormSelect v-model="branchId" label="Pickup branch" :options="branchChoices" />
            </div>
            <div
              v-if="orders.error && !orders.currentQuote"
              class="mt-4 rounded-md bg-danger-soft p-3 text-sm text-danger"
            >
              {{ orders.error }} · trace {{ orders.traceId ?? 'unavailable' }}
            </div>
          </div>

          <div class="mp-surface p-5">
            <h2 class="font-serif text-xl font-semibold text-ink">Contact</h2>
            <div class="mt-3 rounded-md bg-success-soft p-3 text-sm font-semibold text-success">
              This is shared with the workshop so they can call you about your order.
            </div>
            <div class="mt-4 grid gap-3 md:grid-cols-2">
              <label class="grid gap-1 text-sm font-bold text-ink">
                Name
                <input v-model="contactName" class="mp-input" autocomplete="name" />
              </label>
              <label class="grid gap-1 text-sm font-bold text-ink">
                Phone
                <input v-model="contactPhone" class="mp-input" autocomplete="tel" inputmode="tel" />
              </label>
            </div>
          </div>
        </div>

        <aside class="mp-surface h-fit p-5 xl:sticky xl:top-6">
          <h2 class="font-serif text-xl font-semibold text-ink">Summary</h2>
          <div class="mt-4 grid gap-3 text-sm">
            <div class="flex justify-between gap-3">
              <span class="text-ink-soft">Parts</span>
              <span class="font-mono font-bold text-ink">{{ draft.parts_snapshot.length }}</span>
            </div>
            <div class="flex justify-between gap-3">
              <span class="text-ink-soft">Panels</span>
              <span class="font-mono font-bold text-ink">{{ totalPanels }}</span>
            </div>
            <div class="flex justify-between gap-3">
              <span class="text-ink-soft">Edge tape</span>
              <span class="font-mono font-bold text-ink">{{ metres(totalEdge) }}</span>
            </div>
          </div>

          <div class="mt-5 border-t border-hairline pt-4">
            <div v-if="orders.quoteLoading" class="text-sm font-bold text-ink-soft">
              Pricing branch
            </div>
            <template v-else-if="orders.currentQuote">
              <div class="grid gap-2 text-sm">
                <div class="flex justify-between gap-3">
                  <span class="text-ink-soft">Cutting</span>
                  <span class="font-mono font-bold">{{
                    formatTiyin(orders.currentQuote.subtotal_cutting_tiyin)
                  }}</span>
                </div>
                <div class="flex justify-between gap-3">
                  <span class="text-ink-soft">Materials</span>
                  <span class="font-mono font-bold">{{
                    formatTiyin(orders.currentQuote.subtotal_materials_tiyin)
                  }}</span>
                </div>
                <div class="flex justify-between gap-3">
                  <span class="text-ink-soft">Edge banding</span>
                  <span class="font-mono font-bold">{{
                    formatTiyin(orders.currentQuote.subtotal_edge_banding_tiyin)
                  }}</span>
                </div>
                <div class="mt-2 flex justify-between gap-3 border-t border-hairline pt-3">
                  <span class="font-extrabold text-ink">Total</span>
                  <span class="font-mono text-lg font-extrabold text-accent">
                    {{ formatTiyin(orders.currentQuote.total_tiyin) }}
                  </span>
                </div>
              </div>
            </template>
            <div v-else class="text-sm text-ink-soft">Choose a branch to see the price.</div>
          </div>

          <div v-if="localError" class="mt-4 rounded-md bg-danger-soft p-3 text-sm text-danger">
            {{ localError }}
          </div>

          <button
            type="button"
            class="mp-button mp-button-primary mt-5 w-full"
            :disabled="placing || orders.quoteLoading || !orders.currentQuote"
            @click="placeOrder"
          >
            {{ placing ? 'Placing' : 'Place order' }}
          </button>
        </aside>
      </section>
    </template>
  </section>
</template>
