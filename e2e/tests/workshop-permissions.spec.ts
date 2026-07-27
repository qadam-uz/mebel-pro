/**
 * The workshop permission matrix, as invariants rather than a grid (QAD-173).
 *
 * QAD-130 walked permission × route by hand and found seven defects. A pass/fail
 * table for every cell would be slow, brittle, and unread; what actually broke
 * were three properties that hold for *every* persona, so those are what this
 * file locks:
 *
 *   1. No rendered link bounces. Every in-app link the app actually draws for a
 *      persona must open — none may be turned away by the router guard and land
 *      back on `/workshop` (QAD-170).
 *   2. The sidebar is exactly the grant set. No entry the grant does not unlock,
 *      none missing that it does.
 *   3. A refused route never flashes. Its heading must never reach the DOM on
 *      the way to the redirect.
 *
 * Plus two cheap assertions on the same page visits, because both were real
 * defects: a page a persona is entitled to answers with **no 403** anywhere in
 * its network traffic (QAD-168, QAD-169), and an order a persona may not read
 * shows the permission copy rather than a transport error (QAD-171).
 *
 * The `web/` unit suites own what can be decided without a browser —
 * `workshopNav.spec.ts` the sidebar projection, `routeMatrix.spec.ts` the
 * route-meta allowance. This file is deliberately the integration half: what the
 * browser renders, and what the server answers, for a real single-grant user.
 *
 * Cost control: the whole matrix shares one seeded workshop per Playwright
 * worker (a worker-scoped fixture), and every persona is provisioned through the
 * API. The tests only navigate — they never mutate — so sharing is safe.
 */
import {
  expect,
  test as base,
  type APIRequestContext,
  type Locator,
  type Page,
} from '@playwright/test'

import { baseUrl } from '../env'
import {
  expectOk,
  ownerReadyPassword,
  phoneFor,
  placeClientOrderViaApi,
  seedOrderableBranch,
} from './helpers'

const homePath = '/workshop'
const staffTempPassword = 'StaffTemp123'
const staffReadyPassword = 'StaffReady123'
/**
 * How long a page gets to finish loading before the crawl reads its links.
 * Above the 5s assertion default on purpose: these tests open thirty-odd screens
 * back to back, and a slow one must widen the wait, never shrink the crawl.
 */
const settleTimeout = 20_000

interface Account {
  login: string
  password: string
}

interface Persona {
  /** Grant under test — the permission name, or the owner/no-grant edges. */
  key: string
  /** The exact sidebar labels this grant must produce, in order. */
  sidebar: string[]
  /** A route this persona must be refused, and the heading that must not flash. */
  refused: { path: string; heading: string } | null
}

/**
 * One row per permission, plus the two edges (owner, no grants). Written against
 * the current permission set: `view_dashboard` was renamed `view_orders` in
 * QAD-166 and now honestly means read-only order access — which is why it
 * unlocks no sidebar entry of its own and cannot open the orders board.
 */
const personas: Persona[] = [
  {
    key: 'owner',
    sidebar: [
      'Asosiy',
      'Buyurtmalar',
      'Kesish',
      'Krom',
      'Ombor',
      'Material katalogi',
      'Tushum va xarajat',
      'Qarzdorlik',
      'Xodimlar mehnati',
      'Filiallar',
      'Xodimlar',
      'Sozlamalar',
    ],
    refused: null,
  },
  {
    key: 'no grants',
    sidebar: ['Asosiy'],
    refused: { path: '/workshop/inventory', heading: 'Ombor' },
  },
  {
    key: 'view_orders',
    sidebar: ['Asosiy'],
    refused: { path: '/workshop/orders', heading: 'Buyurtmalar' },
  },
  {
    key: 'manage_orders',
    sidebar: ['Asosiy', 'Buyurtmalar'],
    refused: { path: '/workshop/catalog', heading: 'Material katalogi' },
  },
  {
    key: 'process_production',
    sidebar: ['Asosiy', 'Kesish', 'Krom'],
    refused: { path: '/workshop/inventory', heading: 'Ombor' },
  },
  {
    key: 'manage_inventory',
    sidebar: ['Asosiy', 'Ombor'],
    refused: { path: '/workshop/settings/users', heading: 'Xodimlar' },
  },
  {
    key: 'manage_catalog',
    sidebar: ['Asosiy', 'Material katalogi'],
    refused: { path: '/workshop/finance/expenses', heading: 'Tushum va xarajat' },
  },
  {
    key: 'manage_finance',
    sidebar: ['Asosiy', 'Tushum va xarajat', 'Qarzdorlik', 'Xodimlar mehnati'],
    refused: { path: '/workshop/inventory', heading: 'Ombor' },
  },
  {
    key: 'view_finance_reports',
    sidebar: ['Asosiy', 'Xodimlar mehnati'],
    refused: { path: '/workshop/finance/debts', heading: 'Qarzdorlik' },
  },
]

interface MatrixStack {
  /** A placed order in the branch — assigned to nobody, so a production read 404s. */
  orderId: string
  /** Signed-in-ready credentials, keyed by `Persona.key`. */
  accounts: Record<string, Account>
}

/**
 * Create a workshop user holding exactly `permissions` on the branch and walk it
 * past the forced temp-password change, so tests can sign in with one API call.
 */
async function readyStaff(
  request: APIRequestContext,
  ownerToken: string,
  options: { id: string; branchId: string; key: string; offset: number; permissions: string[] },
): Promise<Account> {
  const login = `pm-${options.key.replace(/\W+/g, '')}-${options.id}`
  const created = await request.post('/api/v1/workshop/users', {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      full_name: `Matrix ${options.key}`,
      phone: phoneFor(`${options.key}-${options.id}`, options.offset),
      login,
      home_branch_id: options.branchId,
      temp_password: staffTempPassword,
      grants: options.permissions.map((permission) => ({
        permission,
        branch_id: options.branchId,
      })),
    },
  })
  await expectOk(created)

  const signedIn = await request.post('/api/v1/auth/workshop/login', {
    data: { login, password: staffTempPassword },
  })
  await expectOk(signedIn)
  const changed = await request.post('/api/v1/auth/password/change', {
    headers: { Authorization: `Bearer ${(await signedIn.json()).access_token}` },
    data: { current_password: staffTempPassword, new_password: staffReadyPassword },
  })
  await expectOk(changed)
  return { login, password: staffReadyPassword }
}

// eslint-disable-next-line @typescript-eslint/no-empty-object-type -- no test-scoped fixtures
const test = base.extend<{}, { matrix: MatrixStack }>({
  matrix: [
    async ({ playwright }, use, workerInfo) => {
      const request = await playwright.request.newContext({ baseURL: baseUrl })
      const id = `pm${workerInfo.workerIndex}-${Date.now().toString(36).slice(-6)}`
      const seeded = await seedOrderableBranch(request, id)
      const placed = await placeClientOrderViaApi(request, {
        phone: phoneFor(id, 70),
        name: `Matrix Client ${id}`,
        branchId: seeded.branchId,
        panelId: seeded.panel.id,
        edgeId: seeded.edge.id,
      })

      const staff = await Promise.all(
        personas
          .filter((persona) => persona.key !== 'owner')
          .map(async (persona, index) => {
            const permissions = persona.key === 'no grants' ? [] : [persona.key]
            const account = await readyStaff(request, seeded.ownerAccess, {
              id,
              branchId: seeded.branchId,
              key: persona.key,
              offset: 80 + index,
              permissions,
            })
            return [persona.key, account] as const
          }),
      )

      await use({
        orderId: placed.order.id,
        accounts: {
          owner: { login: seeded.setup.ownerLogin, password: ownerReadyPassword },
          ...Object.fromEntries(staff),
        },
      })
      await request.dispose()
    },
    { scope: 'worker' },
  ],
})

/** Sign in without the login form: the refresh cookie lands in the page's context. */
async function signIn(page: Page, account: Account) {
  const response = await page.request.post('/api/v1/auth/workshop/login', {
    data: { login: account.login, password: account.password },
  })
  await expectOk(response)
}

/**
 * Record every `h1` that ever reaches the DOM, so a refused route can be shown
 * not to have rendered even for a frame. A plain post-redirect assertion cannot
 * see a flash; a MutationObserver installed before the app boots can.
 */
async function recordHeadings(page: Page) {
  await page.addInitScript(() => {
    const seen: string[] = []
    Object.defineProperty(window, '__renderedHeadings', { value: seen })
    const record = () => {
      document.querySelectorAll('h1').forEach((node) => {
        const text = node.textContent?.trim()
        if (text && !seen.includes(text)) seen.push(text)
      })
    }
    // `document`, not `documentElement` — an init script runs before the root
    // element exists, and observing null would throw the whole script away.
    new MutationObserver(record).observe(document, { childList: true, subtree: true })
    record()
  })
}

function renderedHeadings(page: Page) {
  return page.evaluate(() => (window as unknown as { __renderedHeadings: string[] }).__renderedHeadings)
}

/** Collect the API responses that were refused, for the zero-403 assertion. */
function watchForbidden(page: Page) {
  const refusals: string[] = []
  page.on('response', (response) => {
    if (response.status() !== 403) return
    const { pathname } = new URL(response.url())
    if (!pathname.startsWith('/api/')) return
    refusals.push(`${response.request().method()} ${pathname}`)
  })
  return refusals
}

function normalizePath(url: string) {
  const parsed = new URL(url)
  return (parsed.pathname.replace(/\/+$/, '') || '/') + parsed.search
}

/**
 * Collapse ids out of a path so a board listing twenty rows costs one visit, not
 * twenty: the invariant is per route guard, and every row shares one.
 */
function routeShape(path: string) {
  return path.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, ':id')
}

/** In-app workshop links the page is currently rendering, as normalized paths. */
async function renderedLinks(page: Page, scope?: Locator) {
  const hrefs = await (scope ?? page.locator('body')).locator('a[href]').evaluateAll((nodes) =>
    nodes
      .filter(
        (node) =>
          !(node as HTMLAnchorElement).target &&
          !(node as HTMLAnchorElement).hasAttribute('download'),
      )
      .map((node) => (node as HTMLAnchorElement).href),
  )
  const origin = new URL(page.url()).origin
  return hrefs
    .filter((href) => href.startsWith(`${origin}/`))
    .map(normalizePath)
    .filter((path) => path === homePath || path.startsWith(`${homePath}/`))
}

/**
 * Open a path and wait for the app to settle on it — heading painted and every
 * skeleton resolved. The wait is load-bearing, not politeness: half the links on
 * a screen are inside data that arrives after the heading, and collecting them
 * early silently shrinks the crawl to whatever happened to have rendered.
 */
async function open(page: Page, path: string) {
  await page.goto(path)
  await expect(page.locator('h1').first()).toBeVisible({ timeout: settleTimeout })
  await expect(page.locator('[aria-busy="true"], .sk, .sk-line')).toHaveCount(0, {
    timeout: settleTimeout,
  })
  await page.waitForLoadState('networkidle', { timeout: settleTimeout })
  return normalizePath(page.url())
}

test.describe('workshop permission matrix', () => {
  test.setTimeout(180_000)

  for (const persona of personas) {
    test(`${persona.key}: sidebar, rendered links, and refusals`, async ({
      page,
      matrix,
    }) => {
      const refusals = watchForbidden(page)
      await recordHeadings(page)
      await signIn(page, matrix.accounts[persona.key])
      await open(page, homePath)

      // 2. The sidebar is exactly what the grant unlocks — no more, no fewer.
      const nav = page
        .locator('aside[aria-label="Workshop navigation"]')
        .getByRole('navigation', { name: 'Asosiy navigatsiya' })
      const navLinks = nav.getByRole('link')
      await expect(navLinks).toHaveCount(persona.sidebar.length)
      for (const [index, label] of persona.sidebar.entries()) {
        await expect(navLinks.nth(index)).toContainText(label)
      }
      const sidebarTargets = await renderedLinks(page, nav)

      // 1. No rendered link bounces off the route guard. The pages the sidebar
      // reaches are the persona's whole working surface; every link they draw
      // must open.
      const startPages = [homePath, ...sidebarTargets.filter((path) => path !== homePath)]
      const candidates = new Map<string, string>()
      for (const start of startPages) {
        const landed = await open(page, start)
        expect(landed, `sidebar entry ${start} did not open`).toBe(start)
        for (const link of await renderedLinks(page)) {
          if (link === homePath) continue
          candidates.set(routeShape(link), link)
        }
      }

      const bounced: string[] = []
      for (const link of candidates.values()) {
        if (startPages.includes(link)) continue
        const landed = await open(page, link)
        if (landed === homePath) bounced.push(link)
      }
      expect(bounced, 'rendered links that the route guard refused').toEqual([])

      // A page the persona is entitled to answers with no 403 anywhere.
      expect(refusals, 'refused API calls on entitled pages').toEqual([])

      // 3. A refused route redirects home without ever rendering its heading.
      if (persona.refused) {
        const landed = await open(page, persona.refused.path)
        expect(landed).toBe(homePath)
        await expect(page.getByRole('heading', { level: 1, name: 'Asosiy' })).toBeVisible()
        const headings = await renderedHeadings(page)
        // The observer proves itself before it is trusted to prove a negative.
        expect(headings).toContain('Asosiy')
        expect(headings).not.toContain(persona.refused.heading)
      }
    })
  }

  test('an order the reader may not open names the permission, not the network (QAD-171)', async ({
    page,
    matrix,
  }) => {
    // `/workshop/orders/:order_id` admits process_production, but the data rule
    // behind it admits only the assignee — so an unassigned order 404s. That is
    // the ordinary case for production staff, and it must not read as an outage.
    await signIn(page, matrix.accounts.process_production)
    await page.goto(`/workshop/orders/${matrix.orderId}`)

    await expect(page.getByRole('heading', { name: "Bu buyurtmaga ruxsatingiz yo'q" })).toBeVisible()
    await expect(page.getByText('Internet aloqasini tekshirib')).toHaveCount(0)
  })
})
