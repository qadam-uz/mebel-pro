<script setup lang="ts">
// Branch Materials tab — branch material selection: add from the platform
// picker, set price + min-stock, activate/deactivate.
import { computed, onMounted, ref } from 'vue'
import { ApiError } from '@/shared/api'
import { AppModal, FormField, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { sumToTiyin, tiyinToSum } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import * as api from '../../api'
import type { BranchMaterial, Material } from '../../api/types'

const props = defineProps<{ branchId: string }>()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const rows = ref<BranchMaterial[]>([])
const materials = ref<Material[]>([])

const addOpen = ref(false)
const newMaterialId = ref('')
const newPrice = ref(0)
const newMin = ref(0)
const saving = ref(false)

const materialName = (id: string) => materials.value.find((m) => m.id === id)?.name ?? id

// materials not yet added to this branch
const available = computed(() => {
  const added = new Set(rows.value.map((r) => r.material_id))
  return materials.value.filter((m) => !added.has(m.id))
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const [bm, mats] = await Promise.all([
      api.listBranchMaterials(props.branchId),
      api.listMaterials(),
    ])
    rows.value = bm
    materials.value = mats
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

async function add() {
  if (!newMaterialId.value) return
  saving.value = true
  try {
    await api.addBranchMaterial(props.branchId, {
      material_id: newMaterialId.value,
      price_tiyin: sumToTiyin(newPrice.value),
      min_stock: newMin.value,
    })
    toast.ok(t('workshop.materialAdded'))
    addOpen.value = false
    newMaterialId.value = ''
    newPrice.value = 0
    newMin.value = 0
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

async function savePrice(row: BranchMaterial, priceSum: number) {
  try {
    await api.editBranchMaterial(props.branchId, row.id, { price_tiyin: sumToTiyin(priceSum) })
    toast.ok(t('workshop.materialUpdated'))
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

async function saveMin(row: BranchMaterial, min: number) {
  try {
    await api.editBranchMaterial(props.branchId, row.id, { min_stock: min })
    toast.ok(t('workshop.materialUpdated'))
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

async function toggle(row: BranchMaterial) {
  try {
    await api.setBranchMaterialStatus(props.branchId, row.id, row.status !== 'active')
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

onMounted(load)
</script>

<template>
  <div style="margin-top: 16px">
    <div class="page-head" style="margin-bottom: 12px">
      <div />
      <div class="tools">
        <button
          class="btn btn-acc btn-sm"
          type="button"
          :disabled="available.length === 0"
          @click="addOpen = true"
        >
          {{ t('workshop.addMaterial') }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>
    <div v-else-if="rows.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.materialsEmpty') }}</h3>
      <p>{{ t('workshop.materialsEmptyBody') }}</p>
    </div>
    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.materialColName') }}</th>
            <th class="right">{{ t('workshop.priceCol') }}</th>
            <th class="right">{{ t('workshop.minStockCol') }}</th>
            <th>{{ t('workshop.colStatus') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td class="nm">{{ materialName(row.material_id) }}</td>
            <td class="right">
              <input
                type="number"
                :value="tiyinToSum(row.price_tiyin)"
                style="width: 110px"
                @change="savePrice(row, Number(($event.target as HTMLInputElement).value))"
              />
            </td>
            <td class="right">
              <input
                type="number"
                :value="row.min_stock"
                style="width: 80px"
                @change="saveMin(row, Number(($event.target as HTMLInputElement).value))"
              />
            </td>
            <td>
              <StatusBadge
                :tone="row.status === 'active' ? 'ok' : 'bad'"
                :label="row.status === 'active' ? t('workshop.statusActive') : t('common.none')"
              />
            </td>
            <td>
              <button class="btn btn-ghost btn-sm" type="button" @click="toggle(row)">
                {{ row.status === 'active' ? t('workshop.deactivate') : t('workshop.activate') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AppModal v-model:open="addOpen" :title="t('workshop.addMaterial')">
      <div class="field">
        <label>{{ t('workshop.pickMaterial') }}</label>
        <select v-model="newMaterialId">
          <option value="" disabled>{{ t('workshop.pickMaterial') }}</option>
          <option v-for="m in available" :key="m.id" :value="m.id">
            {{ m.name }} · {{ m.thickness_mm }}mm
          </option>
        </select>
      </div>
      <FormField v-model.number="newPrice" type="number" :label="t('workshop.priceTiyin')" />
      <FormField v-model.number="newMin" type="number" :label="t('workshop.minStock')" />
      <template #footer>
        <button class="btn btn-outline" type="button" @click="addOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button class="btn btn-acc" type="button" :disabled="saving || !newMaterialId" @click="add">
          {{ t('common.save') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>
