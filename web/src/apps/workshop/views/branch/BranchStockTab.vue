<script setup lang="ts">
// Branch Stock tab — stock list (low-stock highlighted), Record stock-in
// (qty + supplier picker w/ inline add + receipt note), Adjust (signed delta +
// mandatory reason), inline min-stock, transactions log.
import { computed, onMounted, ref } from 'vue'
import { ApiError } from '@/shared/api'
import { AppModal, FormField } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtDateTime } from '@/shared/format'
import { useToast } from '@/shared/composables/useToast'
import * as api from '../../api'
import type { Material, StockItem, StockTransaction, Supplier } from '../../api/types'

const props = defineProps<{ branchId: string }>()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const stock = ref<StockItem[]>([])
const materials = ref<Material[]>([])
const suppliers = ref<Supplier[]>([])
const txns = ref<StockTransaction[]>([])

const materialName = (id: string) => materials.value.find((m) => m.id === id)?.name ?? id
const lowStock = (i: StockItem) => i.on_hand <= i.min_stock

// stock-in modal
const stockInOpen = ref(false)
const siMaterial = ref('')
const siQty = ref(0)
const siSupplier = ref('')
const siNote = ref('')
const saving = ref(false)

// inline supplier add
const addingSupplier = ref(false)
const newSupplierName = ref('')

// adjust modal
const adjustOpen = ref(false)
const adjMaterial = ref('')
const adjDelta = ref(0)
const adjReason = ref('')

const txnTypeLabel = (type: string) =>
  ({
    stock_in: t('workshop.txnStockIn'),
    consume: t('workshop.txnConsume'),
    restore: t('workshop.txnRestore'),
    adjust: t('workshop.txnAdjust'),
  })[type] ?? type

const txnMaterialName = computed(() => {
  const byStockItem = new Map(stock.value.map((s) => [s.id, s.material_id]))
  return (stockItemId: string) => materialName(byStockItem.get(stockItemId) ?? '')
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const [st, mats, sup, tx] = await Promise.all([
      api.listStock(props.branchId),
      api.listMaterials(),
      api.listSuppliers(),
      api.listStockTransactions(props.branchId, { limit: 50 }),
    ])
    stock.value = st
    materials.value = mats
    suppliers.value = sup
    txns.value = tx
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

async function addSupplier() {
  if (!newSupplierName.value.trim()) return
  try {
    const created = await api.createSupplier({ name: newSupplierName.value.trim() })
    suppliers.value.push(created)
    siSupplier.value = created.id
    newSupplierName.value = ''
    addingSupplier.value = false
    toast.ok(t('workshop.supplierAdded'))
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  }
}

async function doStockIn() {
  if (!siMaterial.value || !siSupplier.value || siQty.value <= 0) return
  saving.value = true
  try {
    await api.stockIn(props.branchId, {
      material_id: siMaterial.value,
      quantity: siQty.value,
      supplier_id: siSupplier.value,
      note: siNote.value.trim() || null,
    })
    toast.ok(t('workshop.stockInDone'))
    stockInOpen.value = false
    siMaterial.value = ''
    siQty.value = 0
    siSupplier.value = ''
    siNote.value = ''
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

async function doAdjust() {
  if (!adjMaterial.value || !adjReason.value.trim() || adjDelta.value === 0) return
  saving.value = true
  try {
    await api.stockAdjust(props.branchId, {
      material_id: adjMaterial.value,
      delta: adjDelta.value,
      note: adjReason.value.trim(),
    })
    toast.ok(t('workshop.stockAdjusted'))
    adjustOpen.value = false
    adjMaterial.value = ''
    adjDelta.value = 0
    adjReason.value = ''
    await load()
  } catch (e) {
    toast.warn(e instanceof ApiError ? e.detail : t('common.loadFailedBody'))
  } finally {
    saving.value = false
  }
}

async function saveMin(item: StockItem, min: number) {
  try {
    await api.setMinStock(props.branchId, item.material_id, min)
    toast.ok(t('workshop.minStockSaved'))
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
        <button class="btn btn-acc btn-sm" type="button" @click="stockInOpen = true">
          {{ t('workshop.recordStockIn') }}
        </button>
        <button class="btn btn-outline btn-sm" type="button" @click="adjustOpen = true">
          {{ t('workshop.adjustStock') }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>
    <div v-else-if="stock.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.stockEmpty') }}</h3>
      <p>{{ t('workshop.stockEmptyBody') }}</p>
    </div>
    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.materialColName') }}</th>
            <th class="right">{{ t('workshop.onHandCol') }}</th>
            <th class="right">{{ t('workshop.minStockCol') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in stock" :key="i.id">
            <td class="nm">{{ materialName(i.material_id) }}</td>
            <td class="amt" :class="{ 'warn-text': lowStock(i) }">{{ i.on_hand }}</td>
            <td class="right">
              <input
                type="number"
                :value="i.min_stock"
                style="width: 80px"
                @change="saveMin(i, Number(($event.target as HTMLInputElement).value))"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <section class="card" style="margin-top: 16px">
      <div class="card-h">
        <h2>{{ t('workshop.transactionsLog') }}</h2>
      </div>
      <div class="card-b" style="padding-top: 0">
        <div v-if="txns.length === 0" class="st-empty" style="border: 0">
          <div class="ic">∅</div>
          <p>{{ t('workshop.txnEmpty') }}</p>
        </div>
        <table v-else class="tbl">
          <thead>
            <tr>
              <th>{{ t('workshop.txnDate') }}</th>
              <th>{{ t('workshop.materialColName') }}</th>
              <th>{{ t('workshop.txnType') }}</th>
              <th class="right">{{ t('workshop.txnQty') }}</th>
              <th class="right">{{ t('workshop.txnBalance') }}</th>
              <th>{{ t('workshop.txnNote') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="x in txns" :key="x.id">
              <td style="font-size: 11.5px; color: var(--ink-6)">
                {{ fmtDateTime(x.created_at) }}
              </td>
              <td>{{ txnMaterialName(x.stock_item_id) }}</td>
              <td>{{ txnTypeLabel(x.type) }}</td>
              <td class="amt">{{ x.quantity > 0 ? '+' : '' }}{{ x.quantity }}</td>
              <td class="amt">{{ x.balance_after }}</td>
              <td style="color: var(--ink-7); font-size: 12px">{{ x.note ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- STOCK-IN -->
    <AppModal v-model:open="stockInOpen" :title="t('workshop.stockInTitle')">
      <div class="field">
        <label>{{ t('workshop.materialColName') }}</label>
        <select v-model="siMaterial">
          <option value="" disabled>{{ t('workshop.pickMaterial') }}</option>
          <option v-for="i in stock" :key="i.id" :value="i.material_id">
            {{ materialName(i.material_id) }}
          </option>
        </select>
      </div>
      <FormField v-model.number="siQty" type="number" :label="t('workshop.quantity')" />
      <div class="field">
        <label>{{ t('workshop.supplier') }}</label>
        <div v-if="!addingSupplier" style="display: flex; gap: 8px">
          <select v-model="siSupplier" style="flex: 1">
            <option value="" disabled>—</option>
            <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
          <button class="btn btn-outline btn-sm" type="button" @click="addingSupplier = true">
            {{ t('workshop.addSupplier') }}
          </button>
        </div>
        <div v-else style="display: flex; gap: 8px">
          <input
            v-model="newSupplierName"
            :placeholder="t('workshop.supplierName')"
            style="flex: 1"
          />
          <button class="btn btn-acc btn-sm" type="button" @click="addSupplier">
            {{ t('common.save') }}
          </button>
        </div>
      </div>
      <FormField v-model="siNote" :label="t('workshop.receiptNote')" />
      <template #footer>
        <button class="btn btn-outline" type="button" @click="stockInOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button
          class="btn btn-acc"
          type="button"
          :disabled="saving || !siMaterial || !siSupplier || siQty <= 0"
          @click="doStockIn"
        >
          {{ t('common.save') }}
        </button>
      </template>
    </AppModal>

    <!-- ADJUST -->
    <AppModal v-model:open="adjustOpen" :title="t('workshop.adjustTitle')">
      <div class="field">
        <label>{{ t('workshop.materialColName') }}</label>
        <select v-model="adjMaterial">
          <option value="" disabled>{{ t('workshop.pickMaterial') }}</option>
          <option v-for="i in stock" :key="i.id" :value="i.material_id">
            {{ materialName(i.material_id) }}
          </option>
        </select>
      </div>
      <FormField v-model.number="adjDelta" type="number" :label="t('workshop.delta')" />
      <FormField v-model="adjReason" :label="t('workshop.adjustReason')" required />
      <template #footer>
        <button class="btn btn-outline" type="button" @click="adjustOpen = false">
          {{ t('common.cancel') }}
        </button>
        <button
          class="btn btn-acc"
          type="button"
          :disabled="saving || !adjMaterial || !adjReason.trim() || adjDelta === 0"
          @click="doAdjust"
        >
          {{ t('common.save') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>
