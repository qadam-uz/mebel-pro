<script setup lang="ts">
import { formatTiyin } from '@/shared/formatters'
import type { ClientBranchOption } from '@/shared/stores/cutting'
defineProps<{
  branch: ClientBranchOption
  selected: boolean
  quote?: {
    total_tiyin: number
    panels_used: number
    subtotal_cutting_tiyin: number
    subtotal_materials_tiyin: number
    subtotal_edge_banding_tiyin: number
  }
  error?: string
}>()
defineEmits<{ select: [] }>()
</script>
<template>
  <button
    type="button"
    class="flex w-full items-start gap-3 border-b border-hairline px-3 py-3 text-left last:border-b-0"
    :class="[
      selected ? 'bg-accent-soft' : 'hover:bg-sunk',
      error ? 'cursor-not-allowed opacity-60' : '',
    ]"
    :disabled="Boolean(error)"
    :aria-pressed="selected"
    @click="$emit('select')"
  >
    <span class="min-w-0 flex-1"
      ><span class="flex flex-wrap items-center gap-2"
        ><b class="text-sm text-ink">{{ branch.branch_name }}</b
        ><span
          class="rounded-full px-2 py-0.5 text-[11px] font-bold"
          :class="
            branch.status === 'temporarily_closed'
              ? 'bg-warning-soft text-warning'
              : 'bg-success-soft text-success'
          "
          >{{
            branch.status === 'temporarily_closed'
              ? $t('workshopAdmin.branchRow.closed')
              : $t('workshopAdmin.branchRow.active')
          }}</span
        ></span
      ><span class="mt-1 block text-xs text-ink-muted">{{ branch.address }}</span
      ><span
        v-if="branch.closed_reason && branch.status === 'temporarily_closed'"
        class="block text-xs text-warning"
        >{{ branch.closed_reason }}</span
      ><span v-if="error" class="block text-xs text-danger">{{ error }}</span
      ><span
        v-if="selected && quote"
        class="mt-2 grid gap-1 border-t border-hairline pt-2 text-xs text-ink-soft"
        >{{
          $t('workshopAdmin.branchRow.cuttingService', {
            amount: formatTiyin(quote.subtotal_cutting_tiyin),
          })
        }}<br />{{
          $t('workshopAdmin.branchRow.materials', {
            amount: formatTiyin(quote.subtotal_materials_tiyin),
          })
        }}<br />{{
          $t('workshopAdmin.branchRow.edgeBanding', {
            amount: formatTiyin(quote.subtotal_edge_banding_tiyin),
          })
        }}</span
      ></span
    ><span
      v-if="quote || error"
      class="shrink-0 text-right text-sm font-bold"
      :class="error ? 'text-ink-muted' : 'text-ink'"
      >{{ quote ? formatTiyin(quote.total_tiyin) : '—'
      }}<small v-if="quote" class="mt-1 block text-[10px] text-ink-muted">{{
        $t('workshopAdmin.branchRow.unit', { n: quote.panels_used }, quote.panels_used)
      }}</small></span
    >
  </button>
</template>
