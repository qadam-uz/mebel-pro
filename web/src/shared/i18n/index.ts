// Minimal reactive i18n — a flat-key lookup over a namespaced dictionary.
// v1 is Uzbek-only; the locale is reactive so swapping in ru/en later is just
// registering another catalog and calling setLocale().
//
// Usage in setup: const { t } = useI18n(); t('nav.orders'); t('auth.lockout', { time: '14:05' })

import { computed, ref } from 'vue'
import type { App, InjectionKey } from 'vue'
import { uz } from './uz'

export type Locale = 'uz'

const catalogs: Record<Locale, Record<string, unknown>> = { uz }

const locale = ref<Locale>('uz')

export function setLocale(next: Locale): void {
  if (catalogs[next]) locale.value = next
}

function lookup(catalog: Record<string, unknown>, key: string): string | undefined {
  const value = key.split('.').reduce<unknown>((acc, part) => {
    if (acc && typeof acc === 'object' && part in (acc as Record<string, unknown>)) {
      return (acc as Record<string, unknown>)[part]
    }
    return undefined
  }, catalog)
  return typeof value === 'string' ? value : undefined
}

function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (_, name: string) =>
    name in params ? String(params[name]) : `{${name}}`,
  )
}

// Translate a flat key. Returns the key itself if missing (visible in dev).
export function t(key: string, params?: Record<string, string | number>): string {
  const template = lookup(catalogs[locale.value], key)
  if (template === undefined) {
    if (import.meta.env.DEV) console.warn(`[i18n] missing key: ${key}`)
    return key
  }
  return interpolate(template, params)
}

export const I18N_KEY: InjectionKey<typeof t> = Symbol('i18n')

export function useI18n() {
  return { t, locale: computed(() => locale.value), setLocale }
}

// Install $t globally so templates can use it without importing.
export const i18n = {
  install(app: App) {
    app.config.globalProperties.$t = t
    app.provide(I18N_KEY, t)
  },
}

export { uz }
