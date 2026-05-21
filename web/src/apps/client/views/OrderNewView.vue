<script setup lang="ts">
// Order create wizard at /c/orders/new/:draftId. Two steps with a sticky
// summary: (1) branch pick (from the cutting's branches indicator), (2)
// checkout (contact + review). Places the order, then routes to its detail.
//
// Endpoint note: there is no per-branch pricing-preview endpoint, so the branch
// cards show name only; the final breakdown surfaces on the order detail after
// placement (derived from the order POST response).
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { AppStepper, ErrorState, FormField } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtPhone } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { useClientAuth } from '../store'
import * as clientApi from '../api'
import type { BranchAvailability, BranchesIndicator, Draft, Material } from '../api/types'
import { materialById, materialShortLabel } from '../lib/cutting'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const auth = useClientAuth()

const draftId = computed(() => String(route.params.draftId))

const loading = ref(true)
const loadError = ref<ApiError | null>(null)
const blocked = ref<string | null>(null)
const draft = ref<Draft | null>(null)
const materials = ref<Material[]>([])
const branches = ref<BranchesIndicator | null>(null)

const step = ref<'branch' | 'checkout'>('branch')
const branchId = ref<string | null>(null)
const placing = ref(false)

const profileName = computed(() => auth.me?.first_name ?? auth.me?.full_name ?? '')
const profilePhone = computed(() => auth.me?.phone ?? '')

const contactName = ref('')
const contactPhone = ref('')
const phoneErr = ref(false)

const selectedBranch = computed<BranchAvailability | null>(
  () => branches.value?.branches.find((b) => b.branch_id === branchId.value) ?? null,
)

// summary figures from the draft snapshot
const summary = computed(() => {
  const snapshot = draft.value?.parts_snapshot ?? []
  const totalParts = snapshot.reduce((a, p) => a + (p.quantity || 0), 0)
  const matIds = [...new Set(snapshot.map((p) => p.material_id).filter(Boolean))]
  const matLabel = matIds
    .map((id) => materialShortLabel(materialById(materials.value, id)))
    .filter(Boolean)
    .join(' · ')
  return { totalParts, matLabel }
})

async function load() {
  loading.value = true
  loadError.value = null
  blocked.value = null
  try {
    const [d, mats, br] = await Promise.all([
      clientApi.getDraft(draftId.value),
      clientApi.listMaterials(),
      clientApi.draftBranches(draftId.value),
    ])
    draft.value = d
    materials.value = mats
    branches.value = br
    if (!d.chosen_result_id) {
      blocked.value = t('client.draftNotUsable')
    }
    contactName.value = profileName.value
    contactPhone.value = profilePhone.value
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 404 || e.status === 403) blocked.value = t('client.draftNotUsable')
      else loadError.value = e
    } else throw e
  } finally {
    loading.value = false
  }
}

function pickBranch(id: string) {
  branchId.value = id
  step.value = 'checkout'
}

function phoneOk(): boolean {
  return /^\+998\d{9}$/.test(contactPhone.value.replace(/\s/g, ''))
}

function resetField(field: 'name' | 'phone') {
  if (field === 'name') contactName.value = profileName.value
  else contactPhone.value = profilePhone.value
  toast.ok(t('client.resetDone'))
}

async function placeOrder() {
  if (!branchId.value) {
    toast.warn(t('client.pickBranchFirst'))
    return
  }
  if (!contactName.value.trim()) {
    toast.warn(t('client.enterName'))
    return
  }
  if (!phoneOk()) {
    phoneErr.value = true
    toast.warn(t('client.enterPhone'))
    return
  }
  phoneErr.value = false
  placing.value = true
  try {
    const order = await clientApi.placeOrder({
      draft_id: draftId.value,
      branch_id: branchId.value,
      contact_name: contactName.value.trim(),
      contact_phone: contactPhone.value.replace(/\s/g, ''),
    })
    toast.ok(t('client.orderPlaced'))
    router.push({ path: `/c/orders/${order.id}`, query: { placed: '1' } })
  } catch (e) {
    if (e instanceof ApiError) {
      toast.warn(e.detail)
      // a draft no longer usable → bounce to drafts
      if (e.code === 'cutting_result_not_usable') router.push('/c/cutting/drafts')
    } else throw e
  } finally {
    placing.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <button class="back" type="button" @click="router.push(`/c/cutting/${draftId}`)">
      {{ t('client.backToCutting') }}
    </button>

    <div v-if="loading" class="card" style="padding: 24px; margin-top: 12px">
      <div class="sk sk-line" style="width: 40%" />
      <div class="sk sk-line" style="width: 100%; margin-top: 16px; height: 80px" />
    </div>

    <ErrorState v-else-if="loadError" :error="loadError" :retry="load" />

    <div v-else-if="blocked" class="st-empty" style="margin-top: 24px">
      <div class="ic">!</div>
      <h3>{{ t('client.draftNotUsable') }}</h3>
      <RouterLink class="btn btn-outline" :to="`/c/cutting/${draftId}`">{{
        t('client.backToCutting')
      }}</RouterLink>
    </div>

    <template v-else>
      <AppStepper
        :steps="[t('client.stepBranch'), t('client.stepCheckout')]"
        :current="step === 'branch' ? 0 : 1"
        style="margin: 14px 0 18px"
      />

      <div class="wizard-grid">
        <div>
          <!-- BRANCH STEP -->
          <template v-if="step === 'branch'">
            <div class="page-head" style="margin-bottom: 14px">
              <div>
                <h1>{{ t('client.orderNewBranchTitle') }}</h1>
                <p class="sub">{{ t('client.orderNewBranchSub') }}</p>
              </div>
            </div>

            <div v-if="!branches || branches.branches.length === 0" class="st-empty">
              <div class="ic">!</div>
              <h3>{{ t('client.noBranchTitle') }}</h3>
              <p
                v-html="
                  t('client.noBranchBody', {
                    names: (branches?.uncovered_material_ids ?? [])
                      .map(
                        (id) => materialShortLabel(materialById(materials, id)) || id.slice(0, 6),
                      )
                      .join(' · '),
                  })
                "
              />
              <RouterLink class="btn btn-outline" :to="`/c/cutting/${draftId}`">{{
                t('client.backToCutting')
              }}</RouterLink>
            </div>

            <article
              v-for="b in branches.branches"
              v-else
              :key="b.branch_id"
              class="br-card"
              tabindex="0"
              role="button"
              @click="pickBranch(b.branch_id)"
              @keydown.enter.prevent="pickBranch(b.branch_id)"
              @keydown.space.prevent="pickBranch(b.branch_id)"
            >
              <div class="br-hd">
                <div>
                  <div class="br-nm">{{ b.name }}</div>
                </div>
                <span class="open-aff">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path d="M9 6l6 6-6 6" />
                  </svg>
                </span>
              </div>
            </article>
          </template>

          <!-- CHECKOUT STEP -->
          <template v-else>
            <div class="page-head" style="margin-bottom: 14px">
              <div>
                <h1>{{ t('client.orderNewCheckoutTitle') }}</h1>
                <p class="sub">{{ t('client.orderNewCheckoutSub') }}</p>
              </div>
            </div>

            <section class="card" style="margin-bottom: 14px">
              <div class="card-h">
                <h2>{{ t('client.contactTitle') }}</h2>
              </div>
              <div class="card-b">
                <div class="banner info" style="margin-bottom: 14px">
                  <div class="ic">i</div>
                  <div class="grow">{{ t('client.contactNote') }}</div>
                </div>
                <FormField
                  :label="t('client.contactName')"
                  :model-value="contactName"
                  @update:model-value="contactName = $event"
                >
                  <template #default="{ id, describedBy }">
                    <div style="display: flex; gap: 8px; align-items: center">
                      <input
                        :id="id"
                        v-model="contactName"
                        :aria-describedby="describedBy"
                        style="flex: 1"
                      />
                      <button
                        class="btn btn-ghost btn-sm"
                        type="button"
                        @click="resetField('name')"
                      >
                        {{ t('client.resetToProfile') }}
                      </button>
                    </div>
                  </template>
                </FormField>
                <FormField
                  :label="t('client.contactPhone')"
                  :error="phoneErr ? t('client.enterPhone') : undefined"
                >
                  <template #default="{ id, describedBy }">
                    <div style="display: flex; gap: 8px; align-items: center">
                      <input
                        :id="id"
                        v-model="contactPhone"
                        inputmode="tel"
                        :aria-describedby="describedBy"
                        :style="phoneErr ? 'flex:1;border-color:var(--danger)' : 'flex:1'"
                      />
                      <button
                        class="btn btn-ghost btn-sm"
                        type="button"
                        @click="resetField('phone')"
                      >
                        {{ t('client.resetToProfile') }}
                      </button>
                    </div>
                  </template>
                </FormField>
              </div>
            </section>

            <section class="card">
              <div class="card-h">
                <h2>{{ t('client.reviewTitle') }}</h2>
              </div>
              <div class="card-b">
                <div class="row-item">
                  <div>
                    <div class="nm">{{ t('client.reviewBranch') }}</div>
                  </div>
                  <div class="meta">
                    <b>{{ selectedBranch?.name }}</b>
                    <button class="edit-link" type="button" @click="step = 'branch'">
                      {{ t('common.edit') }}
                    </button>
                  </div>
                </div>
                <div class="row-item">
                  <div>
                    <div class="nm">{{ t('client.reviewPickup') }}</div>
                  </div>
                  <div class="meta">{{ t('client.reviewPickupText') }}</div>
                </div>
                <div class="row-item">
                  <div>
                    <div class="nm">{{ t('client.reviewContact') }}</div>
                  </div>
                  <div class="meta">
                    {{ contactName || '—' }} · {{ fmtPhone(contactPhone) || '—' }}
                  </div>
                </div>
                <button
                  class="btn btn-acc btn-block"
                  type="button"
                  :disabled="placing"
                  style="margin-top: 16px"
                  @click="placeOrder"
                >
                  {{ t('client.placeOrderBtn') }}
                </button>
              </div>
            </section>
          </template>
        </div>

        <!-- summary aside -->
        <aside>
          <div class="card sum">
            <div class="card-h">
              <h2 style="font-size: 16px">{{ t('client.summaryCutting') }}</h2>
            </div>
            <div class="card-b">
              <div class="sm-row">
                <span>{{ t('client.summaryParts') }}</span
                ><span class="v">{{ summary.totalParts }}</span>
              </div>
              <div class="sm-row">
                <span>{{ t('client.summaryMaterials') }}</span
                ><span
                  class="v"
                  style="font: 500 11.5px var(--f-mono); text-align: right; max-width: 160px"
                  >{{ summary.matLabel }}</span
                >
              </div>
              <div v-if="selectedBranch" class="sm-section">
                <h4>{{ selectedBranch.name }}</h4>
                <p class="muted" style="font-size: 12.5px; margin: 6px 0 0">
                  {{ t('client.priceFrozen') }}
                </p>
              </div>
              <div
                v-else
                class="sm-section"
                style="font: 500 12px var(--f-ui); color: var(--ink-6)"
              >
                {{ t('client.summaryPickBranch') }}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.wizard-grid {
  display: grid;
  gap: 20px;
  grid-template-columns: 1fr;
}
@media (min-width: 860px) {
  .wizard-grid {
    grid-template-columns: minmax(0, 1fr) 280px;
    align-items: start;
  }
}
.sum {
  position: sticky;
  top: 88px;
}
.sm-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  font: 500 13px var(--f-ui);
  color: var(--ink-8);
  border-bottom: 1px solid var(--line);
}
.sm-row .v {
  color: var(--ink-12);
  font-weight: 600;
}
.sm-section {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.sm-section h4 {
  font: 600 13px var(--f-display);
  margin: 0;
  color: var(--ink-12);
}
.br-card {
  background: var(--elev);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 18px 22px;
  margin-bottom: 12px;
  cursor: pointer;
  transition:
    border-color 0.12s,
    transform 0.12s;
}
.br-card:hover {
  border-color: var(--ink-12);
  transform: translateY(-1px);
}
.br-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.br-hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.br-nm {
  font: 600 16px var(--f-display);
  color: var(--ink-12);
}
.open-aff svg {
  width: 18px;
  height: 18px;
  color: var(--accent);
}
.edit-link {
  margin-left: 8px;
  background: none;
  border: 0;
  color: var(--accent);
  cursor: pointer;
  font: 500 12px var(--f-ui);
  text-decoration: underline;
}
</style>
