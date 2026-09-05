// What the platform (admin) SPA ships of the uz catalog.
//
// Ten namespaces: the four workshop-facing ones — `finance`, `inventory`,
// `orders` and `workshopAdmin` — are ~62 kB of copy no platform screen renders.
// `client` is in the list because `shared/app/notificationPresenter` routes an
// inbox row through `clientUi` whatever the role.

import catalog from '@/shared/i18n/locales/uz/catalog.json'
import client from '@/shared/i18n/locales/uz/client.json'
import common from '@/shared/i18n/locales/uz/common.json'
import cutting from '@/shared/i18n/locales/uz/cutting.json'
import formats from '@/shared/i18n/locales/uz/formats.json'
import forms from '@/shared/i18n/locales/uz/forms.json'
import locale from '@/shared/i18n/locales/uz/locale.json'
import nav from '@/shared/i18n/locales/uz/nav.json'
import routes from '@/shared/i18n/locales/uz/routes.json'
import shell from '@/shared/i18n/locales/uz/shell.json'

import type { RoleCatalog } from '@/shared/i18n'

export const adminCatalog: RoleCatalog = {
  uz: {
    catalog,
    client,
    common,
    cutting,
    formats,
    forms,
    locale,
    nav,
    routes,
    shell,
  },
  loadRu: () => import('@/shared/i18n/catalogs/admin.ru').then((module) => module.adminRu),
}
