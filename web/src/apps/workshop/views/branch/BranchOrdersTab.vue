<script setup lang="ts">
// Branch Orders tab — orders scoped to this branch.
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState, StatusBadge } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { fmtTiyin } from '@/shared/format'
import * as api from '../../api'
import type { OrderCard } from '../../api/types'
import { relativeAge } from '../../lib/orders'

const props = defineProps<{ branchId: string }>()
const router = useRouter()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const orders = ref<OrderCard[]>([])

async function load() {
  loading.value = true
  error.value = null
  try {
    orders.value = (await api.listOrders({ branchId: props.branchId })).orders
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div style="margin-top: 16px">
    <ErrorState v-if="error" :error="error" :retry="load" />
    <div v-else-if="loading" class="card">
      <div class="card-b"><div class="sk sk-line" style="width: 60%" /></div>
    </div>
    <div v-else-if="orders.length === 0" class="st-empty">
      <div class="ic">∅</div>
      <h3>{{ t('workshop.ordersEmpty') }}</h3>
    </div>
    <div v-else class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th>{{ t('workshop.colId') }}</th>
            <th>{{ t('workshop.colClient') }}</th>
            <th>{{ t('workshop.colStatus') }}</th>
            <th class="right">{{ t('workshop.colAmount') }}</th>
            <th>{{ t('workshop.colTime') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="o in orders"
            :key="o.id"
            class="clickable"
            @click="router.push(`/workshop/orders/${o.id}`)"
          >
            <td class="id">{{ o.order_number }}</td>
            <td class="nm">{{ o.contact_name || '—' }}</td>
            <td><StatusBadge :state="o.status" /></td>
            <td class="amt">{{ fmtTiyin(o.total_tiyin) }}</td>
            <td style="font-size: 11.5px; color: var(--ink-6)">{{ relativeAge(o.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
