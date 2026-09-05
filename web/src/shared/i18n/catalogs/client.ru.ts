// The ru half of `client.ts` — the same namespaces, fetched only when someone
// switches to Russian. Its own module so the switch costs one chunk rather than
// one request per namespace.

import catalog from '@/shared/i18n/locales/ru/catalog.json'
import client from '@/shared/i18n/locales/ru/client.json'
import common from '@/shared/i18n/locales/ru/common.json'
import cutting from '@/shared/i18n/locales/ru/cutting.json'
import formats from '@/shared/i18n/locales/ru/formats.json'
import forms from '@/shared/i18n/locales/ru/forms.json'
import locale from '@/shared/i18n/locales/ru/locale.json'
import nav from '@/shared/i18n/locales/ru/nav.json'
import orders from '@/shared/i18n/locales/ru/orders.json'
import routes from '@/shared/i18n/locales/ru/routes.json'
import shell from '@/shared/i18n/locales/ru/shell.json'

import type { RoleMessages } from '@/shared/i18n/locales/uz/schema'

export const clientRu: RoleMessages = {
  catalog,
  client,
  common,
  cutting,
  formats,
  forms,
  locale,
  nav,
  orders,
  routes,
  shell,
}
