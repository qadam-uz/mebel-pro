import AdminShell from '@/apps/admin/AdminShell.vue'
import { adminRoutes } from '@/apps/admin/routes'
import { mountRoleApp } from '@/shared/app/createRoleApp'
import { adminConfig } from '@/shared/app/roleConfig'

/** The platform shell's `<main>` is the skip-link target; moving focus there on
 *  every navigation is what keeps a keyboard user out of the sidebar after a
 *  route change. */
function focusAdminContent(toMeta: Record<string, unknown>) {
  if (toMeta.layout === 'auth') return
  requestAnimationFrame(() => {
    document.getElementById('admin-content')?.focus({ preventScroll: true })
  })
}

mountRoleApp(adminConfig, adminRoutes, '/admin', {
  shell: AdminShell,
  onAfterNavigate: (to) => focusAdminContent(to.meta),
})
