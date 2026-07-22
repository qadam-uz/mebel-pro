import type { InjectionKey } from 'vue'

import { useOrdersStore, type OrderDetail, type OrderQuote } from '@/shared/stores/orders'

/**
 * Role adapter for the shared cutting editor (`CuttingEditorView.vue`).
 *
 * Exactly one editor module serves both the client and workshop SPAs;
 * everything role-specific — the new-draft route name, link targets, how the
 * branch is acquired — is injected through this contract so the editor body
 * (autosave flush, CB-15 hydration guard, optimise→navigate handoff, leave
 * guards) stays role-agnostic and moves between roles untouched.
 *
 * Transport (deliberate choice): each app's route records attach a FACTORY
 * under `meta.cuttingEditorAdapter`; the view resolves it once per mount and
 * `provide`s the result under `cuttingEditorAdapterKey` for descendants. Route
 * meta keeps the shared view free of role imports (no per-app wrapper
 * component, no app-level provide in `main.ts`), and a factory — not a plain
 * object — lets the workshop app compute the fixed branch from live state at
 * mount time instead of freezing it into a static route record.
 */
export interface CuttingEditorAdapter {
  /** Route name of the unsaved-editor route — drives the editor's `isNewDraft`. */
  newRouteName: string
  /** Role-prefixed link targets; the consumer passes them through `useRolePath`. */
  paths: {
    drafts: string
    editor(id: string): string
    result(id: string): string
    checkout(draftId: string): string
    orderDetail(orderId: string): string
  }
  /**
   * Fixed-branch mode (workshop): when `fixed` is set the editor hides the
   * branch picker, never calls the client-only branch-options endpoint, and
   * seeds the draft's branch from `fixed.id` at creation — a later change of
   * the app's current branch must not retarget an in-progress draft.
   */
  branch: { fixed?: { id: string; name: string } }
  /** Role-scoped price quote for the draft's chosen result (client vs workshop endpoint). */
  quoteForDraft: (draftId: string, branchId: string) => Promise<OrderQuote>
  /**
   * Order-revision support (workshop only): present when the role can edit a
   * placed order through this editor (orders.md "Revising a placed order").
   * `reviewPath` replaces the checkout target for a revision draft; `loadOrder`
   * feeds the "editing order #N" strip. Absent on the client adapter — clients
   * never see revision drafts.
   */
  orderRevision?: {
    reviewPath(draftId: string): string
    loadOrder(orderId: string): Promise<OrderDetail>
  }
}

export type CuttingEditorAdapterFactory = () => CuttingEditorAdapter

export const cuttingEditorAdapterKey: InjectionKey<CuttingEditorAdapter> =
  Symbol('cuttingEditorAdapter')

/**
 * Today's client SPA behavior, verbatim — and the zero-config default when a
 * route carries no adapter (mirrors the cutting store's default `'client'`
 * scope: the client app needs zero configuration).
 */
export function clientCuttingEditorAdapter(): CuttingEditorAdapter {
  const orders = useOrdersStore()
  return {
    newRouteName: 'client-cutting-new',
    paths: {
      drafts: '/c/cutting/drafts',
      editor: (id: string) => `/c/cutting/${id}`,
      result: (id: string) => `/c/cutting/${id}/result`,
      checkout: (draftId: string) => `/c/orders/new/${draftId}`,
      orderDetail: (orderId: string) => `/c/orders/${orderId}`,
    },
    branch: {},
    quoteForDraft: (draftId, branchId) => orders.quoteForDraft(draftId, branchId),
  }
}
