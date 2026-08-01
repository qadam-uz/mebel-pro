import { useRouter } from 'vue-router'

import { useRolePath } from '@/shared/app/paths'
import { useToast } from '@/shared/composables/useToast'
import { translate } from '@/shared/i18n'
import { useOnboardingStore } from '@/shared/stores/onboarding'

// The "system leads" thread between setup steps (docs/ref/features/onboarding.md):
// after a step-relevant save, refetch the derived status and point the owner at
// whatever remains — or announce completion. Returns true when it showed a toast,
// so the caller can skip its generic save toast instead of stacking two.

export function useOnboardingContinuation() {
  const onboarding = useOnboardingStore()
  const toast = useToast()
  const router = useRouter()
  const rolePath = useRolePath()

  async function notifyProgress(): Promise<boolean> {
    const before = onboarding.status
    if (!onboarding.isEligible || !before || before.setup_complete) return false
    const after = await onboarding.refresh()
    if (!after) return false
    // Guided-thread toasts linger past the 4 s default: they carry the owner's
    // next move, so they must survive a moment of reading and deciding.
    if (after.setup_complete) {
      toast.success(translate('workshopAdmin.onboarding.setupComplete'), 8000)
      return true
    }
    if (!before.branch_configured && after.branch_configured && !after.materials_added) {
      toast.action(
        translate('workshopAdmin.onboarding.pricingSaved'),
        translate('workshopAdmin.onboarding.openCatalog'),
        () => {
          onboarding.queueHint('catalog-add')
          void router.push(rolePath('/workshop/catalog'))
        },
        'success',
        8000,
      )
      return true
    }
    if (!before.materials_added && after.materials_added && !after.branch_configured) {
      const target = after.first_branch_id
        ? `/workshop/branches/${after.first_branch_id}`
        : '/workshop/branches'
      toast.action(
        translate('workshopAdmin.onboarding.materialAdded'),
        translate('workshopAdmin.onboarding.openPricing'),
        () => {
          onboarding.queueHint('branch-pricing')
          void router.push(rolePath(target))
        },
        'success',
        8000,
      )
      return true
    }
    return false
  }

  return { notifyProgress }
}
