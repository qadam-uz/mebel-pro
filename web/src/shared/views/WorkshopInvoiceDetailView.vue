<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { apiErrorCode, apiTraceId } from '@/shared/api/client'
import { traceLine } from '@/shared/app/errorTrace'
import { useRolePath } from '@/shared/app/paths'
import { workshopPermissions as p } from '@/shared/app/workshopPermissions'
import ActionMenu, { type ActionMenuItem } from '@/shared/components/ActionMenu.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { useToast } from '@/shared/composables/useToast'
import { useWorkshopPermissions } from '@/shared/composables/useWorkshopPermissions'
import { formatDate, formatDateTime, formatStockQuantity, formatTiyin } from '@/shared/formatters'
import {
  useWorkshopStore,
  type InvoicePaymentStatus,
  type SupplierInvoice,
} from '@/shared/stores/workshop'

/**
 * One arrival document, read as a whole — a page with its own URL, so a ledger
 * row, a bell entry, a colleague's link and a reload all land on the same thing.
 *
 * The everyday actions (write the expense, correct the paper) stay in the
 * action row; the destructive one sits in the overflow, where it cannot be hit
 * by a mis-aimed click on its neighbour.
 */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const rolePath = useRolePath()
const workshop = useWorkshopStore()
const permissions = useWorkshopPermissions()
const toast = useToast()

const invoiceId = computed(() =>
  typeof route.params.invoice_id === 'string' ? route.params.invoice_id : '',
)
const invoice = ref<SupplierInvoice | null>(null)
const loading = ref(false)
const loadError = ref<string | null>(null)
const loadTraceId = ref<string | null>(null)

const voidOpen = ref(false)
const voidReason = ref('')
const voidBusy = ref(false)
const voidError = ref<string | null>(null)

const canUseInventory = computed(() => permissions.can(p.manageInventory))
// The expense hand-off is offered only to users who could open the ledger anyway.
const canSeeFinance = computed(() => permissions.isOwner.value || permissions.can(p.manageFinance))
const voided = computed(() => invoice.value?.status === 'voided')
const backLink = computed(() => rolePath('/workshop/inventory?tab=invoices'))

function paymentStatusPill(status: InvoicePaymentStatus) {
  if (status === 'paid') return { cls: 'pill p-ok', text: t('inventory.invoices.paid') }
  if (status === 'partial') return { cls: 'pill p-warn', text: t('inventory.invoices.partial') }
  return { cls: 'pill p-bad', text: t('inventory.invoices.unpaid') }
}

const menuItems = computed<ActionMenuItem[]>(() => [
  { label: t('inventory.detail.actionVoid'), icon: 'ban', danger: true, disabled: voidBusy.value },
])

async function load() {
  if (!invoiceId.value) return
  loading.value = true
  loadError.value = null
  loadTraceId.value = null
  try {
    invoice.value = await workshop.fetchSupplierInvoice(invoiceId.value)
  } catch (errorValue) {
    invoice.value = null
    loadError.value =
      apiErrorCode(errorValue) === 'invoice_not_found' ? 'invoice_not_found' : 'invoice_load_failed'
    loadTraceId.value = apiTraceId(errorValue)
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function openExpense() {
  const row = invoice.value
  if (!row) return
  await router.push(rolePath(`/workshop/finance/expenses?create=expense&invoice_id=${row.id}`))
}

function openVoidDialog() {
  voidReason.value = ''
  voidError.value = null
  voidOpen.value = true
}

async function confirmVoid() {
  const row = invoice.value
  const reason = voidReason.value.trim()
  if (!row || !reason) return
  voidBusy.value = true
  voidError.value = null
  try {
    invoice.value = await workshop.voidSupplierInvoice(row.id, reason)
    voidOpen.value = false
    toast.success(t('inventory.void.done', { number: row.invoice_no }))
    // The reversal moved stock and wrote movements: the Ombor tabs are stale.
    workshop.clearInventory()
  } catch (errorValue) {
    const code = apiErrorCode(errorValue)
    if (code === 'invoice_already_voided') {
      // Someone else got there first — show the document as it now is rather
      // than an error about a state the operator already wanted.
      voidOpen.value = false
      await load()
      workshop.clearInventory()
      return
    }
    voidError.value =
      code === 'invoice_has_payments' ? 'invoice_has_payments' : 'invoice_void_failed'
  } finally {
    voidBusy.value = false
  }
}
</script>

<template>
  <section>
    <RouterLink :to="backLink" class="back">{{ $t('inventory.form.back') }}</RouterLink>

    <div v-if="!canUseInventory" class="st-empty">
      <h3>{{ $t('inventory.page.noPermissionTitle') }}</h3>
      <p>{{ $t('inventory.page.noPermissionBody') }}</p>
    </div>

    <section v-else-if="loading" class="card p-5" aria-live="polite">
      <div class="grid gap-3">
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
      </div>
    </section>

    <section v-else-if="loadError" class="st-error" role="alert">
      <h3>
        {{
          loadError === 'invoice_not_found'
            ? $t('inventory.detail.notFound')
            : $t('inventory.detail.loadFailed')
        }}
      </h3>
      <p>{{ traceLine(loadTraceId) }}</p>
      <button type="button" class="mp-button mp-button-outline mt-3" @click="load">
        {{ $t('inventory.detail.retry') }}
      </button>
    </section>

    <template v-else-if="invoice">
      <div class="page-head mt-2">
        <div>
          <h1>
            {{ $t('inventory.detail.title', { number: invoice.invoice_no }) }}
            <span v-if="voided" class="pill p-bad ml-2 align-middle">
              <span class="pd"></span>{{ $t('inventory.invoices.voided') }}
            </span>
            <span
              v-else
              :class="paymentStatusPill(invoice.payment_status).cls"
              class="ml-2 align-middle"
            >
              <span class="pd"></span>{{ paymentStatusPill(invoice.payment_status).text }}
            </span>
          </h1>
          <p class="sub">
            {{ invoice.supplier_name ?? '—' }}
            · {{ $t('inventory.detail.recordedBy', { name: invoice.recorded_by_name ?? '—' }) }}
          </p>
        </div>
        <div v-if="!voided" class="tools">
          <button
            v-if="canSeeFinance"
            type="button"
            class="mp-button mp-button-outline min-h-9 px-3 text-xs"
            @click="openExpense"
          >
            {{ $t('inventory.detail.actionExpense') }}
          </button>
          <RouterLink
            :to="rolePath(`/workshop/inventory/invoices/${invoice.id}/edit`)"
            class="mp-button mp-button-primary min-h-9 px-3 text-xs no-underline"
          >
            {{ $t('inventory.detail.actionEdit') }}
          </RouterLink>
          <!-- The destructive action sits in the overflow; the two everyday
               ones stay in the row where the hand already is. -->
          <ActionMenu
            :items="menuItems"
            :label="$t('inventory.detail.menuAria', { invoice: invoice.invoice_no })"
            @select="openVoidDialog"
          />
        </div>
      </div>

      <div
        v-if="voided"
        class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger"
        role="status"
      >
        <strong class="block font-bold">{{ $t('inventory.detail.voidedTitle') }}</strong>
        <span class="block">{{ invoice.voided_reason }}</span>
        <small class="block">
          {{
            $t('inventory.detail.voidedMeta', {
              name: invoice.voided_by_name ?? '—',
              at: invoice.voided_at ? formatDateTime(invoice.voided_at) : '—',
            })
          }}
        </small>
      </div>

      <div class="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section class="card">
          <div class="card-h">
            <h2>{{ $t('inventory.detail.linesTitle') }}</h2>
            <small class="text-ink-muted">
              {{ formatDate(invoice.invoice_date) }} ·
              {{ $t('inventory.detail.enteredAt', { at: formatDateTime(invoice.created_at) }) }}
            </small>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th>{{ $t('inventory.invoice.columnMaterial') }}</th>
                  <th class="right">{{ $t('inventory.invoice.columnQuantity') }}</th>
                  <th class="right">{{ $t('inventory.invoice.columnPrice') }}</th>
                  <th class="right">{{ $t('inventory.invoice.columnAmount') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="line in invoice.lines" :key="line.transaction_id">
                  <td class="nm">{{ line.material_name }}</td>
                  <td class="amt">{{ formatStockQuantity(line.quantity, line.display_unit) }}</td>
                  <td class="amt">
                    {{ line.unit_price_tiyin !== null ? formatTiyin(line.unit_price_tiyin) : '—' }}
                  </td>
                  <td class="amt">
                    {{
                      line.total_price_tiyin !== null ? formatTiyin(line.total_price_tiyin) : '—'
                    }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- One line, not a ladder: with no document-level discount the line
               sum IS the total. -->
          <div
            class="flex items-center justify-between border-t border-hairline-strong px-4 py-3 text-base font-bold"
          >
            <span>{{ $t('inventory.invoice.total') }}</span>
            <span class="num">{{ formatTiyin(invoice.total_tiyin) }}</span>
          </div>
        </section>

        <!-- Settlement is a fact about a live document; a voided one owes
             nothing, so the block goes rather than showing a stale zero. -->
        <section v-if="!voided" class="card">
          <div class="card-h">
            <h2>{{ $t('inventory.detail.paymentsTitle') }}</h2>
          </div>
          <div class="card-b grid gap-2">
            <div class="flex items-center justify-between text-sm">
              <span class="text-ink-soft">{{ $t('inventory.detail.paidLabel') }}</span>
              <span class="num">{{ formatTiyin(invoice.paid_tiyin) }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-ink-soft">{{ $t('inventory.detail.outstandingLabel') }}</span>
              <span
                class="num"
                :class="invoice.outstanding_tiyin > 0 ? 'danger-text font-bold' : undefined"
              >
                {{ formatTiyin(invoice.outstanding_tiyin) }}
              </span>
            </div>
            <ul v-if="invoice.payments.length" class="grid gap-1">
              <li
                v-for="payment in invoice.payments"
                :key="payment.expense_id"
                class="flex items-center justify-between border-t border-hairline pt-1 text-sm"
                :class="payment.status === 'voided' ? 'text-ink-muted line-through' : undefined"
              >
                <span class="num">{{ formatDate(payment.spent_on) }}</span>
                <span class="flex items-center gap-2">
                  <small v-if="payment.status === 'voided'" class="pill p-dn no-underline">
                    <span class="pd"></span>{{ $t('inventory.detail.paymentVoided') }}
                  </small>
                  <span class="num">{{ formatTiyin(payment.amount_tiyin) }}</span>
                </span>
              </li>
            </ul>
            <p v-else class="text-sm text-ink-muted">{{ $t('inventory.detail.paymentsEmpty') }}</p>
          </div>
        </section>
      </div>
    </template>

    <ConfirmDialog
      :open="voidOpen"
      :title="$t('inventory.void.title')"
      :message="$t('inventory.void.message')"
      :confirm-label="$t('inventory.void.confirm')"
      :busy-label="$t('inventory.void.busy')"
      :busy="voidBusy"
      :confirm-disabled="voidReason.trim().length === 0"
      danger
      @cancel="voidOpen = false"
      @confirm="confirmVoid"
    >
      <label class="field !mb-0">
        <span>{{ $t('inventory.void.reasonLabel') }}</span>
        <textarea
          v-model="voidReason"
          class="mp-input min-h-20"
          rows="3"
          :placeholder="$t('inventory.void.reasonPlaceholder')"
          required
        ></textarea>
      </label>
      <p
        v-if="voidError"
        class="mt-2 rounded-md bg-danger-soft px-3 py-2 text-sm font-bold text-danger"
      >
        {{
          voidError === 'invoice_has_payments'
            ? $t('inventory.error.invoice_has_payments')
            : $t('inventory.error.invoice_void_failed')
        }}
      </p>
    </ConfirmDialog>
  </section>
</template>
