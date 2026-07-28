import type { CuttingEditorAdapter } from '@/shared/app/cuttingEditorAdapter'
import { useOrdersStore } from '@/shared/stores/orders'
import { useWorkshopStore } from '@/shared/stores/workshop'

/**
 * Workshop-app adapter for the shared cutting editor: a fixed branch (the
 * topbar context) and staff link targets under `/workshop/orders/...`.
 * Resolved once at editor mount (the factory reads the workshop store at that
 * moment), so switching the topbar branch afterward never retargets an
 * in-progress draft.
 */
export function workshopCuttingEditorAdapter(): CuttingEditorAdapter {
  const workshop = useWorkshopStore()
  const orders = useOrdersStore()
  const branchId = workshop.selectedBranchContext
  const branch = workshop.branches.find((item) => item.id === branchId)
  return {
    newRouteName: 'workshop-order-cutting-new',
    paths: {
      drafts: '/workshop/orders/drafts',
      editor: (id: string) => `/workshop/orders/cutting/${id}`,
      result: (id: string) => `/workshop/orders/cutting/${id}/result`,
      checkout: (draftId: string) => `/workshop/orders/new/${draftId}/checkout`,
      orderDetail: (orderId: string) => `/workshop/orders/${orderId}`,
    },
    branch: {
      ...(branch
        ? {
            fixed: {
              id: branch.id,
              name: branch.name,
              kerfMm: branch.kerf_mm,
              edgeTrimMm: branch.edge_trim_mm,
            },
          }
        : {}),
      // Live, unlike `fixed` above: on a cold load into the editor the store's
      // branch context lands after this factory runs, so a frozen copy would be
      // null forever. Only ever used to seed a draft with no branch bound.
      context: () => workshop.selectedBranchContext,
    },
    // Resolve live from the store so a resumed draft's frozen branch (which may
    // differ from the topbar) is named correctly in the locked-branch strip.
    branchNameById: (id) => workshop.branches.find((item) => item.id === id)?.name ?? null,
    quoteForDraft: (draftId, quoteBranchId) => orders.quoteWorkshopBranch(draftId, quoteBranchId),
    orderRevision: {
      reviewPath: (draftId: string) => `/workshop/orders/edit/${draftId}/review`,
      loadOrder: (orderId: string) => orders.fetchWorkshopOrder(orderId),
    },
  }
}
