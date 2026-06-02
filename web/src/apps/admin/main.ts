import { adminRoutes } from '@/apps/admin/routes'
import { mountRoleApp } from '@/shared/app/createRoleApp'
import { adminConfig } from '@/shared/app/roleConfig'

mountRoleApp(adminConfig, adminRoutes, '/admin')
