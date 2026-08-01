// The uz (Latin) catalog — the source of truth for every locale. ru is a
// translation of it; uz-Cyrl is derived from it by `transliterate.ts`.
//
// One file per feature area, imported explicitly rather than by glob so the
// object's *type* is the schema `vue-i18n` type-checks every `t()` call
// against: a key that does not exist here fails `vue-tsc`, not the browser.

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

export const uz = {
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

export type MessageSchema = typeof uz
