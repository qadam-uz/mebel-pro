import { config } from '@vue/test-utils'

import { i18n } from '@/shared/i18n'

// jsdom parses and styles but never lays out, so it ships no
// `Element.prototype.scrollIntoView` at all — calling it throws instead of
// no-opping. Components that keep an active row in view (SearchCombobox,
// CuttingResultOverview, CuttingResultSheets, OnboardingSpotlight, the cutting
// editor) call it from ordinary open/select paths, so without this stub a test
// that merely opens a dropdown dies on an unhandled rejection thrown far from
// whatever it was asserting.
//
// A no-op is the entire contract: with no layout there is no scroll position to
// assert, so scrolling correctness belongs to the manual pass, not to jsdom.
Element.prototype.scrollIntoView = function scrollIntoView() {}

// Node now exposes its own `localStorage` on `globalThis`, and under vitest it
// shadows jsdom's with an object carrying no Storage methods at all — reading
// it succeeds, calling `setItem` on it throws. Every spec that touched browser
// storage grew its own in-memory shim to work around it; installing one real
// Storage here is the same fix written once, and it makes the default test
// environment behave like the browser the code was written against.
function memoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() {
      return values.size
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  }
}

Object.defineProperty(window, 'localStorage', { configurable: true, value: memoryStorage() })

// Every mounted component can reach `$t`, exactly as it can in the app. Tests
// assert the *rendered message*, not a key echo: a spec that passes against
// stubbed keys would keep passing after a catalog entry was deleted, which is
// the one regression the copy contract cares about.
config.global.plugins = [...(config.global.plugins ?? []), i18n]
