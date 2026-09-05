// The app's single i18n instance — one per SPA, since each role mounts its own.
//
// Three locales, two catalogs: `uz` (Latin) is written by hand and `ru` is its
// translation, while `uz-Cyrl` is derived from `uz` at load time — see
// `transliterate.ts` for why the Cyrillic script is not a third file.
//
// The *messages* are not compiled in here. A role installs its own catalog at
// bootstrap (`installCatalog`, called by `mountRoleApp` with
// `shared/i18n/catalogs/<role>.ts`), so a SPA carries the namespaces it renders
// and no others — the whole catalog is ~145 kB of the client's initial JS, and
// three of its namespaces are workshop-only. `uz` still ships in the entry
// chunk, because it is both the default locale and the source `uz-Cyrl` is
// derived from; `ru` stays a dynamic import per role, so an Uzbek user never
// downloads it.

import { createI18n } from 'vue-i18n'

import { transliterateMessages, type MessageTree } from '@/shared/i18n/transliterate'
import cyrillicOverrides from '@/shared/i18n/overrides/uz-Cyrl.json'
import type { MessageSchema, RoleMessages } from '@/shared/i18n/locales/uz/schema'

export type { MessageSchema, Namespace, RoleMessages } from '@/shared/i18n/locales/uz/schema'

/** One role's slice of the catalog: the uz namespaces it renders, plus the
 *  loader for the ru translation of exactly those. */
export interface RoleCatalog {
  uz: RoleMessages
  loadRu: () => Promise<RoleMessages>
}

export const LOCALES = ['uz', 'uz-Cyrl', 'ru'] as const
export type Locale = (typeof LOCALES)[number]

export const DEFAULT_LOCALE: Locale = 'uz'

/** A language is always named in itself — a Russian speaker looking for their
 *  language scans for "Русский", not for its Uzbek name. */
export const LOCALE_NAMES: Readonly<Record<Locale, string>> = {
  uz: "O'zbekcha",
  'uz-Cyrl': 'Ўзбекча',
  ru: 'Русский',
}

/** Two-letter badge for the collapsed switcher. */
export const LOCALE_SHORT_NAMES: Readonly<Record<Locale, string>> = {
  uz: 'UZ',
  'uz-Cyrl': 'ЎЗ',
  ru: 'RU',
}

const STORAGE_KEY = 'mp-locale:v1'

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (LOCALES as readonly string[]).includes(value)
}

/** Resolved synchronously, before the app mounts, so the first paint is already
 *  in the right language.
 *
 *  Deliberately **not** sniffed from `navigator.languages`: a Russian-localised
 *  Windows is the norm in Uzbekistan and says nothing about which language the
 *  operator wants their tools in. Sniffing would flip every existing workshop —
 *  people who have used the Uzbek app for months — into Russian on deploy day.
 *  The app stays Uzbek until someone picks otherwise, and then remembers. */
export function initialLocale(): Locale {
  const stored = storage()?.getItem(STORAGE_KEY)
  return isLocale(stored) ? stored : DEFAULT_LOCALE
}

/** Russian agrees its nouns with the number in front of them, which vue-i18n's
 *  default rule (one form, then the rest) cannot express. Messages carry three
 *  forms — `1 деталь | 2 детали | 5 деталей` — and `Intl.PluralRules` picks
 *  between them, so the rule is the platform's, not ours. */
const RU_PLURAL_ORDER = ['one', 'few', 'many'] as const

export function russianPluralIndex(
  count: number,
  choicesLength: number,
  rules: Pick<Intl.PluralRules, 'select'> = new Intl.PluralRules('ru-RU'),
): number {
  if (choicesLength < 2) return 0
  const category = rules.select(Math.abs(count))
  const index = RU_PLURAL_ORDER.indexOf(category as (typeof RU_PLURAL_ORDER)[number])
  if (index === -1 || index >= choicesLength) return choicesLength - 1
  return index
}

// Declaring the *whole* uz catalog as the message schema is what makes
// `t('a.b.c')` a compile-time check: a key that no locale file defines fails
// `vue-tsc` rather than rendering its own path into the UI. It stays the union
// of all fourteen namespaces even though a role ships a subset — narrowing the
// type per role would mean a per-role `t`, and every shared component would
// have to be written against a generic one. The subset is enforced at runtime
// instead, by `pnpm i18n:check` (which walks each role's module graph) and by
// `catalogs.spec.ts`.
declare module 'vue-i18n' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type -- an interface is the only shape a module augmentation can take
  export interface DefineLocaleMessage extends MessageSchema {}
}

// All three locales are declared up front so `i18n.global.locale` accepts the
// whole union. All three start *empty*: `installCatalog` fills `uz` at
// bootstrap, and `loadMessages` fills the other two on demand. Until then
// `fallbackLocale` serves Uzbek, which is also what a half-finished ru catalog
// should do.
const messages = { uz: {}, 'uz-Cyrl': {}, ru: {} } as Record<Locale, MessageSchema>

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages,
  pluralRules: {
    ru: (choice, choicesLength) => russianPluralIndex(choice, choicesLength),
  },
  // A missing key is loud in the dev console and silent in tests, where
  // `catalogs.spec.ts` proves parity across all three locales far better than a
  // warning nobody reads. `fallbackWarn` stays off in every mode: a message
  // resolved from `uz` is the designed behaviour, not an incident.
  missingWarn: import.meta.env.DEV && import.meta.env.MODE !== 'test',
  fallbackWarn: false,
})

// The catalog the running app was booted with. Empty until a role installs
// one — an unmounted i18n resolves nothing, which is what a missing
// `installCatalog` should look like rather than a half-populated UI.
let catalog: RoleCatalog = { uz: {}, loadRu: async () => ({}) }
const loaded = new Set<Locale>()

/** Called once per SPA, before the first paint: `mountRoleApp` passes the role
 *  catalog from `shared/i18n/catalogs/`. Tests install one too — `test-setup`
 *  installs the full catalog so any component can be mounted in isolation.
 *
 *  Installing a second catalog replaces the first outright, including the
 *  locales derived from it, so a spec can swap roles without leaking the
 *  previous role's namespaces into the next one's assertions. */
export function installCatalog(next: RoleCatalog): void {
  catalog = next
  loaded.clear()
  // The messages `vue-i18n` was created with are the schema's shape; a role's
  // subset satisfies the same `t()` calls at runtime and is the whole point of
  // the split, so the cast is where the union type meets the shipped payload.
  i18n.global.setLocaleMessage(DEFAULT_LOCALE, catalog.uz as MessageSchema)
  i18n.global.setLocaleMessage('uz-Cyrl', {} as MessageSchema)
  i18n.global.setLocaleMessage('ru', {} as MessageSchema)
  loaded.add(DEFAULT_LOCALE)
}

async function loadMessages(locale: Locale): Promise<void> {
  if (loaded.has(locale)) return
  if (locale === 'uz-Cyrl') {
    // Derived from the role's uz subset, so the Cyrillic catalog carries
    // exactly the namespaces the Latin one does.
    const cyrillic = transliterateMessages(catalog.uz as MessageTree, cyrillicOverrides)
    i18n.global.setLocaleMessage('uz-Cyrl', cyrillic as unknown as MessageSchema)
  } else {
    i18n.global.setLocaleMessage('ru', (await catalog.loadRu()) as MessageSchema)
  }
  loaded.add(locale)
}

/** `lang` drives screen-reader pronunciation and the browser's own translation
 *  prompt; `data-locale` is the CSS hook for anything that has to differ per
 *  locale. Nothing uses it right now — it used to swap the sans family for the
 *  two Cyrillic locales, which the current two-family system made unnecessary
 *  (both Wix Madefor faces carry Cyrillic). Both attributes are set from one
 *  place so they can never disagree. */
function applyDocumentLocale(locale: Locale): void {
  if (typeof document === 'undefined') return
  document.documentElement.lang = locale
  document.documentElement.dataset.locale = locale
}

export async function setLocale(locale: Locale): Promise<void> {
  await loadMessages(locale)
  i18n.global.locale.value = locale
  applyDocumentLocale(locale)
  storage()?.setItem(STORAGE_KEY, locale)
}

/** Current locale, for components that need to branch on it rather than just
 *  read a message. */
export function currentLocale(): Locale {
  return i18n.global.locale.value
}

const INTL_TAGS: Readonly<Record<Locale, string>> = {
  uz: 'uz-UZ',
  'uz-Cyrl': 'uz-Cyrl-UZ',
  ru: 'ru-RU',
}

/** BCP-47 tag for `Intl.*`. All three currently agree on grouping (NBSP) and
 *  the decimal comma, so nothing moves today — but the formatters ask for the
 *  active locale rather than assuming that stays true. */
export function intlLocale(): string {
  return INTL_TAGS[currentLocale()]
}

/** `t` outside a component — the formatters are plain functions called from
 *  dozens of call sites, and threading a locale argument through all of them
 *  would buy nothing. Reading the composer keeps them reactive: `t` touches
 *  `locale`, so a computed that formats money re-runs when the language does. */
export function translate(key: string, named?: Record<string, unknown>): string {
  return named === undefined ? i18n.global.t(key) : i18n.global.t(key, named)
}

/** Plural form of `key` for `count`, interpolating it as `{n}`. */
export function translatePlural(key: string, count: number): string {
  return i18n.global.t(key, { n: count }, count)
}
