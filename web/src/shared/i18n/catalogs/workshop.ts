// What the workshop SPA ships of the uz catalog: all fourteen namespaces.
//
// The catalog grew around this app — orders, production, inventory, finance,
// the material catalog and the cutting editor all live here — so there is
// nothing to leave out. It is still assembled namespace by namespace rather
// than importing `locales/uz`, so the day a namespace stops being workshop
// copy, dropping it is one line.

import catalog from '@/shared/i18n/locales/uz/catalog.json'
import client from '@/shared/i18n/locales/uz/client.json'
import common from '@/shared/i18n/locales/uz/common.json'
import cutting from '@/shared/i18n/locales/uz/cutting.json'
import finance from '@/shared/i18n/locales/uz/finance.json'
import formats from '@/shared/i18n/locales/uz/formats.json'
import forms from '@/shared/i18n/locales/uz/forms.json'
import inventory from '@/shared/i18n/locales/uz/inventory.json'
import locale from '@/shared/i18n/locales/uz/locale.json'
import nav from '@/shared/i18n/locales/uz/nav.json'
import orders from '@/shared/i18n/locales/uz/orders.json'
import routes from '@/shared/i18n/locales/uz/routes.json'
import shell from '@/shared/i18n/locales/uz/shell.json'
import workshopAdmin from '@/shared/i18n/locales/uz/workshopAdmin.json'

import type { RoleCatalog } from '@/shared/i18n'

export const workshopCatalog: RoleCatalog = {
  uz: {
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
  },
  loadRu: () => import('@/shared/i18n/catalogs/workshop.ru').then((module) => module.workshopRu),
}
