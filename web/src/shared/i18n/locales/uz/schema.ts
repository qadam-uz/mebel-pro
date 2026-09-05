// The message *schema* — the union of every namespace, as a type only.
//
// `t('a.b.c')` is compile-time checked against this interface (see the
// `DefineLocaleMessage` augmentation in `shared/i18n/index.ts`), so it has to
// name all fourteen namespaces even though no single role ships all of them.
// Every import here is an `import type`, which the compiler erases: pulling the
// schema in costs a role bundle nothing, while `locales/uz/index.ts` — the full
// runtime catalog — is reachable only from tests.
//
// Adding a namespace means adding its file here **and** to the role catalogs in
// `shared/i18n/catalogs/` that render it.

import type CatalogMessages from './catalog.json'
import type ClientMessages from './client.json'
import type CommonMessages from './common.json'
import type CuttingMessages from './cutting.json'
import type FinanceMessages from './finance.json'
import type FormatsMessages from './formats.json'
import type FormsMessages from './forms.json'
import type InventoryMessages from './inventory.json'
import type LocaleMessages from './locale.json'
import type NavMessages from './nav.json'
import type OrdersMessages from './orders.json'
import type RoutesMessages from './routes.json'
import type ShellMessages from './shell.json'
import type WorkshopAdminMessages from './workshopAdmin.json'

// A type alias rather than an interface on purpose: an interface has no
// implicit index signature, so `MessageSchema` would stop being assignable to
// the recursive `MessageTree` the transliterator and the catalog specs walk.
export type MessageSchema = {
  catalog: typeof CatalogMessages
  client: typeof ClientMessages
  common: typeof CommonMessages
  cutting: typeof CuttingMessages
  finance: typeof FinanceMessages
  formats: typeof FormatsMessages
  forms: typeof FormsMessages
  inventory: typeof InventoryMessages
  locale: typeof LocaleMessages
  nav: typeof NavMessages
  orders: typeof OrdersMessages
  routes: typeof RoutesMessages
  shell: typeof ShellMessages
  workshopAdmin: typeof WorkshopAdminMessages
}

/** Every namespace name, as a type — a role catalog is a subset of these. */
export type Namespace = keyof MessageSchema

/** What a role actually ships: the namespaces it renders, nothing else. */
export type RoleMessages = Partial<MessageSchema>
