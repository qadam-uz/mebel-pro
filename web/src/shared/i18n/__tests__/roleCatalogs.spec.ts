import { afterEach, describe, expect, it } from 'vitest'

import {
  DEFAULT_LOCALE,
  i18n,
  installCatalog,
  setLocale,
  type Namespace,
  type RoleCatalog,
} from '@/shared/i18n'
import { adminCatalog } from '@/shared/i18n/catalogs/admin'
import { clientCatalog } from '@/shared/i18n/catalogs/client'
import { workshopCatalog } from '@/shared/i18n/catalogs/workshop'
import { uz } from '@/shared/i18n/locales/uz'
import { ru } from '@/shared/i18n/locales/ru'

const ALL_NAMESPACES = Object.keys(uz).sort() as Namespace[]

/** What each SPA installs at bootstrap. The exclusions are the point of the
 *  split — a role that starts shipping a namespace it does not render puts its
 *  whole catalog back into that app's initial JS — so they are asserted by
 *  name, not derived from the module under test. */
const ROLES: ReadonlyArray<{
  name: string
  catalog: RoleCatalog
  excludes: Namespace[]
}> = [
  {
    name: 'client',
    catalog: clientCatalog,
    excludes: ['finance', 'inventory', 'workshopAdmin'],
  },
  {
    name: 'admin',
    catalog: adminCatalog,
    excludes: ['finance', 'inventory', 'orders', 'workshopAdmin'],
  },
  { name: 'workshop', catalog: workshopCatalog, excludes: [] },
]

/** Back to the all-namespaces catalog `test-setup` installs, so a spec that
 *  runs after this one in the same file still resolves every key. */
afterEach(async () => {
  installCatalog({ uz, loadRu: async () => ru })
  await setLocale(DEFAULT_LOCALE)
})

describe.each(ROLES)('$name catalog', ({ catalog, excludes }) => {
  const shipped = Object.keys(catalog.uz).sort()

  it('ships every namespace but the ones this role never renders', () => {
    expect(shipped).toEqual(ALL_NAMESPACES.filter((name) => !excludes.includes(name)))
  })

  it('names each namespace only once, and only namespaces that exist', () => {
    expect(new Set(shipped).size).toBe(shipped.length)
    for (const namespace of shipped) expect(ALL_NAMESPACES).toContain(namespace)
  })

  it('translates the same namespaces it ships in Uzbek', async () => {
    expect(Object.keys(await catalog.loadRu()).sort()).toEqual(shipped)
  })
})

describe('an installed role catalog', () => {
  it('resolves a client message in all three locales', async () => {
    installCatalog(clientCatalog)

    await setLocale('uz')
    expect(i18n.global.t('client.draft.untitled')).toBe('Nomsiz chizma')
    await setLocale('uz-Cyrl')
    expect(i18n.global.t('client.draft.untitled')).toBe('Номсиз чизма')
    await setLocale('ru')
    expect(i18n.global.t('client.draft.untitled')).toBe('Раскрой без названия')
  })

  it('carries the excluded namespaces in no locale', async () => {
    installCatalog(clientCatalog)
    const workshopOnly = 'workshopAdmin.orderStatus.new'

    for (const locale of ['uz', 'uz-Cyrl', 'ru'] as const) {
      await setLocale(locale)
      // vue-i18n renders an unknown key as its own path — the visible symptom
      // of a namespace a role renders but does not ship, and what
      // `pnpm i18n:check` exists to catch before a browser does.
      expect(i18n.global.t(workshopOnly), locale).toBe(workshopOnly)
    }
  })

  it('replaces the previous role wholesale', async () => {
    installCatalog(workshopCatalog)
    await setLocale('uz')
    expect(i18n.global.t('workshopAdmin.orderStatus.new')).not.toBe('workshopAdmin.orderStatus.new')

    installCatalog(clientCatalog)
    expect(i18n.global.t('workshopAdmin.orderStatus.new')).toBe('workshopAdmin.orderStatus.new')
  })
})
