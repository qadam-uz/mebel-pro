<script setup lang="ts">
import { workshopStatusUz } from '@/shared/app/workshopUi'
import { formatDate, formatTiyin } from '@/shared/formatters'
import type { PayableOrder } from '@/shared/stores/finance'

// One row of the order-payment picker. The balance is what the operator is
// about to act on, so it leads in the danger colour with the order total
// demoted beneath it — the two numbers are easy to confuse and paying the
// total twice is the expensive mistake. On an order with nothing paid yet the
// two are the same number, and printing it twice reads as a rendering fault,
// so the total only appears once it says something the balance doesn't.
defineProps<{ order: PayableOrder | undefined }>()
</script>

<template>
  <span v-if="order" class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
    <span class="min-w-0">
      <!-- The name is the second identifier the operator reads, so on a narrow
           screen it drops to its own full-width line instead of being clipped
           to five characters beside the order number. -->
      <span class="flex flex-wrap items-baseline gap-x-2">
        <b class="font-mono text-[12px] text-ink">{{ order.order_number }}</b>
        <span class="min-w-0 grow basis-28 truncate font-bold">{{ order.contact_name }}</span>
      </span>
      <span class="mt-0.5 block text-[11px] leading-tight text-ink-muted">
        {{ order.contact_phone }} · {{ formatDate(order.created_at) }} ·
        {{ workshopStatusUz[order.status] ?? order.status }}
      </span>
    </span>
    <span class="text-right">
      <b class="block font-mono text-[13px] text-danger">{{ formatTiyin(order.balance_tiyin) }}</b>
      <small
        v-if="order.total_tiyin !== order.balance_tiyin"
        class="block font-mono text-[11px] text-ink-muted"
      >
        {{ formatTiyin(order.total_tiyin) }}
      </small>
    </span>
  </span>
</template>
