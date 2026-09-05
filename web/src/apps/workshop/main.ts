import WorkshopShell from '@/apps/workshop/WorkshopShell.vue'
import { workshopRoutes } from '@/apps/workshop/routes'
import { mountRoleApp } from '@/shared/app/createRoleApp'
import { workshopConfig } from '@/shared/app/roleConfig'
import { workshopCatalog } from '@/shared/i18n/catalogs/workshop'
import { useCuttingStore } from '@/shared/stores/cutting'
import { useWorkshopStore } from '@/shared/stores/workshop'

mountRoleApp(workshopConfig, workshopRoutes, '/workshop', {
  shell: WorkshopShell,
  catalog: workshopCatalog,
  // The shared cutting store defaults to the client API surface ('/client/*');
  // the workshop SPA flips it to the '/workshop/*' mirror once at bootstrap.
  // Each SPA owns its Pinia instance, so this can never leak across apps.
  onBoot: (pinia) => {
    useCuttingStore(pinia).configureScope('workshop')
  },
  // A 403 means the grant set is stale (QAD-172), and the workshop sidebar is
  // built from the branch context as much as from the principal — so re-read it
  // alongside `me` before the bootstrap decides whether this page is still
  // allowed.
  onRevalidate: async (pinia) => {
    await useWorkshopStore(pinia)
      .loadBranchContext({ force: true })
      .catch(() => undefined)
  },
})
