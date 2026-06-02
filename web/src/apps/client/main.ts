import { mountRoleApp } from '@/shared/app/createRoleApp'
import { clientConfig } from '@/shared/app/roleConfig'
import { clientRoutes } from '@/apps/client/routes'

mountRoleApp(clientConfig, clientRoutes, '/client')
