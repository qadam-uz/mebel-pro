import { workshopRoutes } from '@/apps/workshop/routes'
import { mountRoleApp } from '@/shared/app/createRoleApp'
import { workshopConfig } from '@/shared/app/roleConfig'

mountRoleApp(workshopConfig, workshopRoutes, '/workshop')
