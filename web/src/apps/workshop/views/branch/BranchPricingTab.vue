<script setup lang="ts">
// Branch Pricing tab (owner only) — cutting model + rate + edge-banding-rate
// grid. Save with an unsaved-changes guard. Mirrors prototype pricing section.
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState, FormField } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { sumToTiyin, tiyinToSum } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopAuth } from '../../store'
import * as api from '../../api'
import type { CuttingModel } from '../../api/types'

const props = defineProps<{ branchId: string }>()
const toast = useToast()
const auth = useWorkshopAuth()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const saving = ref(false)

const model = ref<CuttingModel>('per_sheet')
const rate = ref(0)
const edgeRates = ref<{ thickness: string; rate: number }[]>([])

// snapshot for the dirty check
const snapshot = ref('')

function serialise(): string {
  return JSON.stringify({
    model: model.value,
    rate: rate.value,
    edges: edgeRates.value.map((e) => [e.thickness, e.rate]),
  })
}

const dirty = computed(() => serialise() !== snapshot.value)
const canWrite = computed(() => auth.isOwner)

async function load() {
  loading.value = true
  error.value = null
  try {
    const p = await api.getPricing(props.branchId)
    model.value = p.cutting_model ?? 'per_sheet'
    rate.value = tiyinToSum(p.cutting_rate_tiyin)
    edgeRates.value = Object.entries(p.edge_banding_rates).map(([thickness, tiyin]) => ({
      thickness,
      rate: tiyinToSum(Number(tiyin)),
    }))
    snapshot.value = serialise()
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

function addThickness() {
  edgeRates.value.push({ thickness: '', rate: 0 })
}

function removeThickness(i: number) {
  edgeRates.value.splice(i, 1)
}

async function save() {
  saving.value = true
  try {
    const edge_banding_rates: Record<string, number> = {}
    for (const e of edgeRates.value) {
      if (e.thickness.trim()) edge_banding_rates[e.thickness.trim()] = sumToTiyin(e.rate)
    }
    await api.setPricing(props.branchId, {
      cutting_model: model.value,
      cutting_rate_tiyin: sumToTiyin(rate.value),
      edge_banding_rates,
    })
    toast.ok(t('workshop.pricingSaved'))
    snapshot.value = serialise()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

onBeforeRouteLeave(() => {
  if (dirty.value && !window.confirm(t('workshop.unsavedGuard'))) return false
  return true
})

onMounted(load)
</script>

<template>
  <div style="margin-top: 16px">
    <ErrorState v-if="error" :error="error" :retry="load" />

    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 50%" /></div>
    </div>

    <div v-else-if="!canWrite" class="banner warn">
      <div class="ic">!</div>
      <div class="grow">{{ t('workshop.pricingOwnerOnly') }}</div>
    </div>

    <template v-else>
      <section class="card">
        <div class="card-h">
          <h2>{{ t('workshop.pricingModel') }}</h2>
        </div>
        <div class="card-b">
          <div class="field">
            <label>{{ t('workshop.pricingModel') }}</label>
            <select v-model="model">
              <option value="per_sheet">{{ t('workshop.perSheet') }}</option>
              <option value="per_cut">{{ t('workshop.perCut') }}</option>
            </select>
          </div>
          <FormField v-model.number="rate" type="number" :label="t('workshop.cuttingRate')" />
        </div>
      </section>

      <section class="card" style="margin-top: 14px">
        <div class="card-h">
          <h2>{{ t('workshop.edgeBandingRates') }}</h2>
          <button class="btn btn-outline btn-sm" type="button" @click="addThickness">
            {{ t('workshop.addThickness') }}
          </button>
        </div>
        <div class="card-b">
          <div
            v-for="(e, i) in edgeRates"
            :key="i"
            style="display: flex; gap: 10px; align-items: flex-end; margin-bottom: 10px"
          >
            <FormField v-model="e.thickness" :label="t('workshop.thicknessMm')" style="flex: 1" />
            <FormField
              v-model.number="e.rate"
              type="number"
              :label="t('workshop.ratePerMetre')"
              style="flex: 1"
            />
            <button class="btn btn-ghost btn-sm" type="button" @click="removeThickness(i)">
              ✕
            </button>
          </div>
        </div>
      </section>

      <div style="margin-top: 14px">
        <button class="btn btn-acc" type="button" :disabled="saving || !dirty" @click="save">
          {{ t('workshop.saveChanges') }}
        </button>
      </div>
    </template>
  </div>
</template>
