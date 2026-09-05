// What the client SPA ships of the uz catalog.
//
// Eleven of the fourteen namespaces: no `finance`, `inventory` or
// `workshopAdmin` — nothing the client renders reaches a key in them, and
// together they are ~46 kB of the catalog. `pnpm i18n:check` walks the client's
// module graph and fails if a reachable file uses a namespace missing here, so
// this list cannot silently fall behind the screens.

import catalog from '@/shared/i18n/locales/uz/catalog.json'
import client from '@/shared/i18n/locales/uz/client.json'
import common from '@/shared/i18n/locales/uz/common.json'
import cutting from '@/shared/i18n/locales/uz/cutting.json'
import formats from '@/shared/i18n/locales/uz/formats.json'
import forms from '@/shared/i18n/locales/uz/forms.json'
import locale from '@/shared/i18n/locales/uz/locale.json'
import nav from '@/shared/i18n/locales/uz/nav.json'
import orders from '@/shared/i18n/locales/uz/orders.json'
import routes from '@/shared/i18n/locales/uz/routes.json'
import shell from '@/shared/i18n/locales/uz/shell.json'

import type { RoleCatalog } from '@/shared/i18n'

export const clientCatalog: RoleCatalog = {
  uz: {
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
  },
  loadRu: () => import('@/shared/i18n/catalogs/client.ru').then((module) => module.clientRu),
}
