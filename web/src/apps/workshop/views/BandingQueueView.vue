<script setup lang="ts">
// Edger workspace — edge_banding orders assigned to me. Tablet-friendly
// .q-card list, one action: Banding done. Mirrors prototype banding-queue.html.
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { ErrorState } from '@/shared/ui'
import { t } from '@/shared/i18n'
import { useToast } from '@/shared/composables/useToast'
import * as api from '../api'
import type { OrderCard } from '../api/types'
import { relativeAge } from '../lib/orders'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const router = useRouter()
const toast = useToast()

const loading = ref(true)
const error = ref<ApiError | null>(null)
const orders = ref<OrderCard[]>([])
const confirmId = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    orders.value = (await api.myBanding()).orders
  } catch (e) {
    if (e instanceof ApiError) error.value = e
    else throw e
  } finally {
    loading.value = false
  }
}

async function doDone(reason: string) {
  void reason
  if (!confirmId.value) return
  const id = confirmId.value
  try {
    const order = await api.getOrder(id)
    await api.bandingDone(id, { expected_version: order.version })
    toast.ok(t('workshop.actionDone'))
    await load()
  } catch (e) {
    if (e instanceof ApiError) toast.warn(e.status === 409 ? t('workshop.conflict') : e.detail)
    else toast.warn(t('common.loadFailedBody'))
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ t('workshop.bandingQueueTitle') }}</h1>
        <p class="sub">{{ t('workshop.bandingQueueSub') }}</p>
      </div>
    </div>

    <ErrorState v-if="error" :error="error" :retry="load" />

    <div v-else-if="loading" class="queue-grid">
      <div class="q-card"><div class="sk sk-line" style="width: 60%" /></div>
    </div>

    <div v-else class="queue-grid">
      <section class="queue-col">
        <h2>
          {{ t('workshop.awaitingBanding') }} <span class="ct">{{ orders.length }}</span>
        </h2>
        <div v-if="orders.length === 0" class="empty">
          <div class="ic">∅</div>
          <h3>{{ t('workshop.queueEmpty') }}</h3>
          <p>{{ t('workshop.bandingQueueEmptyBody') }}</p>
        </div>
        <div v-for="o in orders" :key="o.id" class="q-card">
          <div class="top">
            <div>
              <div class="id">{{ o.order_number }}</div>
              <h4>{{ o.contact_name || '—' }}</h4>
              <div class="meta">
                <b>{{ o.item_count }} {{ t('workshop.partsCount') }}</b> ·
                {{ relativeAge(o.created_at) }}
              </div>
            </div>
            <span class="assigned-tag">{{ t('workshop.assignedToYou') }}</span>
          </div>
          <div class="act">
            <button class="btn btn-acc" type="button" @click="confirmId = o.id">
              {{ t('workshop.actBandingDone') }}
            </button>
            <button
              class="btn btn-outline"
              type="button"
              @click="router.push(`/workshop/orders/${o.id}`)"
            >
              {{ t('workshop.detailsLink') }}
            </button>
          </div>
        </div>
      </section>
    </div>

    <ConfirmDialog
      :open="confirmId !== null"
      :title="t('workshop.bandingDoneTitle')"
      :message="t('workshop.bandingDoneMsg')"
      :ok-text="t('common.confirm')"
      @update:open="(v) => !v && (confirmId = null)"
      @confirm="doDone"
    />
  </div>
</template>
