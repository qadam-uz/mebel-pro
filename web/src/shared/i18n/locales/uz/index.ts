// The **whole** uz (Latin) catalog — every namespace in one object.
//
// The app does not load this: a role SPA assembles only the namespaces it
// renders, in `shared/i18n/catalogs/<role>.ts`. This module exists so the
// catalog specs and the test bootstrap can hold all fourteen namespaces at
// once; importing it from app code would put every namespace back into that
// role's bundle. The *type* every `t()` call is checked against lives in
// `./schema.ts`, which imports the same files with `import type` and therefore
// ships nothing.

import catalog from './catalog.json'
import client from './client.json'
import common from './common.json'
import cutting from './cutting.json'
import finance from './finance.json'
import formats from './formats.json'
import forms from './forms.json'
import inventory from './inventory.json'
import locale from './locale.json'
import nav from './nav.json'
import orders from './orders.json'
import routes from './routes.json'
import shell from './shell.json'
import workshopAdmin from './workshopAdmin.json'

import type { MessageSchema } from './schema'

export type { MessageSchema, Namespace, RoleMessages } from './schema'

export const uz: MessageSchema = {
  catalog,
  client,
  common,
  cutting,
  finance,
  formats,
  forms,
  inventory,
  locale,
  nav,
  orders,
  routes,
  shell,
  workshopAdmin,
}
