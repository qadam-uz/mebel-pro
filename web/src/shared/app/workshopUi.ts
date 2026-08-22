import { translate, translatePlural } from '@/shared/i18n'
import type { OrderStatus } from '@/shared/stores/orders'
import type { BranchStatus, StockTransactionType } from '@/shared/stores/workshop'

// Labels are resolved on every call, never captured in a module-level const: a
// record built at import time would freeze at whatever locale happened to be
// active then, and a language switch would leave the words already on screen.

export function workshopStatusUz(status: OrderStatus): string {
  return translate(`workshopAdmin.orderStatus.${status}`)
}

export function workshopStatusHint(status: OrderStatus): string {
  return translate(`workshopAdmin.orderStatusHint.${status}`)
}

export function orderPillClass(status: OrderStatus) {
  if (status === 'completed') return 'pill p-dn'
  if (status === 'cancelled') return 'pill p-bad'
  if (status === 'ready') return 'pill p-rdy'
  if (status === 'cutting') return 'pill p-cut'
  if (status === 'edge_banding') return 'pill p-eb'
  if (status === 'confirmed') return 'pill p-conf'
  return 'pill p-new'
}

// A saved walk-in draft carries no DB status; its readiness is derived from
// whether a cutting result has been chosen. `has_result` → ready for checkout;
// otherwise the operator still has parts to finish.
export function workshopDraftStatus(hasResult: boolean): { label: string; pill: string } {
  return hasResult
    ? { label: translate('workshopAdmin.draft.ready'), pill: 'pill p-rdy' }
    : { label: translate('workshopAdmin.draft.editing'), pill: 'pill p-new' }
}

export function branchStatusUz(status: BranchStatus): string {
  return translate(`workshopAdmin.branchStatus.${status}`)
}

export function branchPillClass(status: BranchStatus) {
  if (status === 'active') return 'pill p-ok'
  if (status === 'temporarily_closed') return 'pill p-warn'
  return 'pill p-dn'
}

const STOCK_TRANSACTION_TYPES: ReadonlySet<string> = new Set<StockTransactionType>([
  'stock_in',
  'stock_in_void',
  'consume',
  'restore',
  'adjust',
])

export function stockTransactionTypeLabel(type: StockTransactionType) {
  return STOCK_TRANSACTION_TYPES.has(type) ? translate(`workshopAdmin.stockType.${type}`) : type
}

// The job is done — the books just went below zero because an arrival was never
// recorded. Informational only: raised as a `warn` toast next to the success
// one, never as danger, and never in place of completing the transition (QAD-150).
export function stockShortfallMessage(): string {
  return translate('workshopAdmin.stock.shortfall')
}

const PERMISSION_CODES: ReadonlySet<string> = new Set([
  'view_orders',
  'manage_orders',
  'process_production',
  'manage_catalog',
  'manage_inventory',
  'manage_finance',
  'view_finance_reports',
  'record_order_payment',
])

/** Operator name for a permission; an unknown code stays visible as itself. */
export function permissionLabel(permission: string): string {
  return PERMISSION_CODES.has(permission)
    ? translate(`workshopAdmin.permission.${permission}`)
    : permission
}

export function grantSummary(
  isOwner: boolean,
  grants: Array<{ permission: string; branch_id: string }>,
) {
  if (isOwner) return translate('workshopAdmin.staff.ownerGrants')
  if (grants.length === 0) return translate('workshopAdmin.staff.noGrants')
  const branches = new Set(grants.map((grant) => grant.branch_id))
  const permissions = new Set(grants.map((grant) => grant.permission))
  // Two counted nouns, so two messages: one plural rule cannot agree both, and
  // `·` separates fields rather than joining a sentence.
  return [
    translatePlural('workshopAdmin.staff.permissionCount', permissions.size),
    translatePlural('workshopAdmin.staff.branchCount', branches.size),
  ].join(' · ')
}

/**
 * The workshop's own name for chrome that shows the tenant, or `null` when
 * neither source has one and the caller should fall back to the generic label.
 *
 * Two sources, in this order: the owner-only settings row (so a rename shows
 * without a reload) and the `me` principal, which carries the name for staff —
 * the settings read 403s for them (QAD-168).
 */
export function workshopTenantName(...candidates: Array<string | null | undefined>) {
  for (const candidate of candidates) {
    const trimmed = candidate?.trim()
    if (trimmed) return trimmed
  }
  return null
}

export function initials(name: string | null | undefined, fallback = 'MP') {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return fallback
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

/** Longest slug we prefill; a prefix that eats the field helps nobody. */
const LOGIN_PREFIX_MAX = 12

/**
 * Suggest a login prefix from the workshop name — "Mebel Pro" → `mebelpro_`.
 * Logins are unique across the whole platform, so an unprefixed `admin` is
 * usually already taken; steering the owner toward a workshop-shaped name
 * avoids the collision. Purely a suggestion: the field stays fully editable.
 */
export function loginPrefix(workshopName: string | null | undefined) {
  if (!workshopName) return ''
  const slug = workshopName
    .toLowerCase()
    // Decompose so an accented letter keeps its ASCII base once the marks go;
    // everything else non-alphanumeric (spaces, punctuation, the turned comma
    // in o‘/g‘) simply drops.
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]/g, '')
    .slice(0, LOGIN_PREFIX_MAX)
  return slug ? `${slug}_` : ''
}

// Every `APIError` code a workshop user can realistically trigger has its own
// entry under `workshopAdmin.error` (DESIGN.md, copy rule 2). The set is the
// catalog's key inventory: a code outside it is genuinely unexpected and gets
// the generic recovery line rather than a rendered key path.
const WORKSHOP_ERROR_CODES: ReadonlySet<string> = new Set([
  'permission_denied',
  'order_action_failed',
  'order_version_conflict',
  'order_edit_not_allowed',
  'order_has_unpriced_materials',
  'order_revision_not_found',
  'order_revision_branch_locked',
  'order_revision_failed',
  'cutting_already_started',
  'banding_already_started',
  'cutter_required',
  'edger_required',
  'cutting_complete_failed',
  'banding_complete_failed',
  'expense_save_failed',
  'income_save_failed',
  'ledger_void_failed',
  'statement_pdf_failed',
  'grants_save_failed',
  'password_reset_failed',
  'user_save_failed',
  'user_block_failed',
  'user_unblock_failed',
  'sessions_revoke_failed',
  'session_revoke_failed',
  // Finance ledger codes (QAD-123). The generic fallback is for genuinely
  // unexpected failures — a rejected save the operator can fix must say what
  // to fix, in the words the form uses.
  'order_required',
  'order_not_allowed',
  'scope_mismatch',
  'order_payment_exceeds_total',
  'order_not_found',
  'branch_required',
  'forbidden',
  'invalid_amount',
  'invalid_amount_range',
  'invalid_status',
  'ledger_not_recorded',
  'future_date_not_allowed',
  'description_required',
  'note_required',
  'reason_required',
  'income_not_found',
  'expense_not_found',
  'supplier_not_found',
  'client_not_found',
  'adjustment_not_found',
  'invalid_party',
])

export function workshopErrorMessage(code: string | null | undefined) {
  if (!code || !WORKSHOP_ERROR_CODES.has(code)) return translate('workshopAdmin.error.generic')
  return translate(`workshopAdmin.error.${code}`)
}

export interface DashboardSectionFailure {
  /** Section label shown to the operator; also the per-section dedupe key. */
  section: string
  code: string
  traceId: string | null
}

const DASHBOARD_FAILURE_CAUSES: ReadonlySet<string> = new Set([
  'permission_denied',
  'internal_error',
  'validation_error',
  'not_found',
])

/**
 * One diagnostic line per failed dashboard section: the named cause plus the
 * raw code and trace_id support needs to find the incident. The backend stamps
 * trace_id on every error body, so a missing trace means the response never
 * came from the app — reported as a connection failure rather than a
 * meaningless "trace_id: unavailable".
 */
export function dashboardFailureLine(failure: DashboardSectionFailure): string {
  if (failure.traceId === null) {
    return translate('workshopAdmin.dashboard.failureConnection', { section: failure.section })
  }
  const cause = DASHBOARD_FAILURE_CAUSES.has(failure.code)
    ? translate(`workshopAdmin.dashboard.failureCause.${failure.code}`)
    : translate('workshopAdmin.dashboard.failureCause.unknown')
  return translate('workshopAdmin.dashboard.failureLine', {
    section: failure.section,
    cause,
    code: failure.code,
    trace: failure.traceId,
  })
}
