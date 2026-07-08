import type { CuttingEditorAdapter } from '@/shared/app/cuttingEditorAdapter'
import { useWorkshopStore } from '@/shared/stores/workshop'

/**
 * Workshop-app adapter for the shared cutting editor: a fixed branch (the
 * topbar context), staff link targets under `/workshop/orders/...`, and no
 * client-profile default. Resolved once at editor mount (the factory reads the
 * workshop store at that moment), so switching the topbar branch afterward
 * never retargets an in-progress draft.
 */
export function workshopCuttingEditorAdapter(): CuttingEditorAdapter {
  const workshop = useWorkshopStore()
  const branchId = workshop.selectedBranchContext
  const branch = workshop.branches.find((item) => item.id === branchId)
  return {
    newRouteName: 'workshop-order-cutting-new',
    paths: {
      drafts: '/workshop/orders',
      editor: (id: string) => `/workshop/orders/cutting/${id}`,
      checkout: (draftId: string) => `/workshop/orders/new/${draftId}/checkout`,
      orderDetail: (orderId: string) => `/workshop/orders/${orderId}`,
    },
    branch: branch ? { fixed: { id: branch.id, name: branch.name } } : {},
    useProfileDefaultBranch: false,
  }
}
