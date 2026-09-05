import ClientShell from '@/apps/client/ClientShell.vue'
import { clientRoutes } from '@/apps/client/routes'
import { mountRoleApp } from '@/shared/app/createRoleApp'
import { clientConfig } from '@/shared/app/roleConfig'

mountRoleApp(clientConfig, clientRoutes, '/client', { shell: ClientShell })
