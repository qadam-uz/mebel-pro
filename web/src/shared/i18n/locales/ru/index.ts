// The **whole** ru catalog — a translation of `../uz`, which owns the key
// inventory. Like its uz counterpart this is the all-namespaces object the
// catalog specs compare against; the app loads a role's ru subset from
// `shared/i18n/catalogs/<role>.ru.ts` instead.

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

import type { MessageSchema } from '@/shared/i18n/locales/uz/schema'

export const ru: MessageSchema = {
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
