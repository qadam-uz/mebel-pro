import { expect, test, type Page } from '@playwright/test'

import {
  adminPassword,
  continueButton,
  expectOk,
  ownerReadyPassword,
  passwordLabel,
  platformToken,
  provisionWorkshop,
  readyOwnerToken,
  runId,
  seedPlatform,
} from './helpers'

// QAD-180 — desktop paints at `zoom: 90%` on the root (≥769px) and viewport
// units do not participate in `zoom`: a `100vh` panel computes 900px and paints
// 810px, leaving a 10% strip of page background. The trap that let this ship
// for so long is that `getComputedStyle().height` reports the *correct* 900px
// the whole time — only the rendered rect is wrong. So every assertion here
// measures `getBoundingClientRect()` against `window.innerHeight`, never the
// computed style, and runs on both sides of the 769px zoom cutoff.

const DESKTOP = { width: 1440, height: 900 }
const SHORT_LAPTOP = { width: 1440, height: 700 }
const PHONE = { width: 375, height: 812 }

/** Rendered height of the first match, and the viewport it must fill. */
async function renderedFill(page: Page, selector: string) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel)
    if (!el) throw new Error(`no element matched ${sel}`)
    return {
      rendered: el.getBoundingClientRect().height,
      viewport: window.innerHeight,
      zoom: document.documentElement.currentCSSZoom ?? 1,
    }
  }, selector)
}

/** Asserts the rendered rect covers the viewport exactly (±1px), retrying. */
async function expectFillsViewport(page: Page, selector: string) {
  const { rendered, viewport } = await renderedFill(page, selector)
  // A shortfall of exactly 10% is the original defect; 11% over is the
  // mirror-image mistake of compensating where no zoom is in effect.
  expect(
    Math.abs(rendered - viewport),
    `${selector} rendered ${rendered}px into a ${viewport}px viewport`,
  ).toBeLessThanOrEqual(1)
}

test('login surfaces fill the viewport on both sides of the zoom cutoff (QAD-180)', async ({
  page,
}) => {
  for (const viewport of [DESKTOP, PHONE]) {
    await page.setViewportSize(viewport)

    await page.goto('/workshop/auth/login')
    await expect(page.getByRole('heading', { name: 'Kirish' })).toBeVisible()
    await expectFillsViewport(page, 'main')

    await page.goto('/client/auth/login')
    await expect(page.getByRole('heading', { name: 'Mijoz kabinetiga kirish' })).toBeVisible()
    await expectFillsViewport(page, 'main')

    await page.goto('/admin/auth/login')
    await expect(page.getByRole('heading', { name: 'Admin paneliga kirish' })).toBeVisible()
    await expectFillsViewport(page, '.admin-auth-wrap')
  }

  // The zoom is what makes this test worth keeping: below 769px it is absent,
  // so a fix that over-corrects (111% tall) would still pass the desktop pass.
  await page.setViewportSize(DESKTOP)
  await page.goto('/workshop/auth/login')
  expect((await renderedFill(page, 'main')).zoom).toBeCloseTo(0.9, 2)
  await page.setViewportSize(PHONE)
  await page.goto('/workshop/auth/login')
  expect((await renderedFill(page, 'main')).zoom).toBeCloseTo(1, 2)
})

test('workshop sidebar fills the viewport and keeps every nav item reachable (QAD-180)', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `viewport-admin-${id}`
  await seedPlatform(adminLogin)
  const token = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, token, id)
  const ownerToken = await readyOwnerToken(request, setup)
  // Priced up front so the first-run onboarding spotlight (owned by
  // onboarding.spec.ts) stays out of the sidebar's way.
  await expectOk(
    await request.put(`/api/v1/workshop/branches/${setup.branch.id}/pricing`, {
      headers: { Authorization: `Bearer ${ownerToken}` },
      data: { cutting_rate_tiyin: 50_000, edge_banding_rate_tiyin: 20_000 },
    }),
  )

  await page.setViewportSize(SHORT_LAPTOP)
  await page.goto('/workshop/')
  await page.getByLabel('Login').fill(setup.ownerLogin)
  await page.getByLabel(passwordLabel).fill(ownerReadyPassword)
  await page.getByRole('button', { name: continueButton }).click()
  await expect(page.getByRole('heading', { name: 'Asosiy' })).toBeVisible()

  await expectFillsViewport(page, '.workshop-sidebar')

  // The sidebar clips its overflow, so the nav has to be the scroller and
  // everything around it has to stay put — otherwise the last groups are not
  // merely below the fold, they are unreachable. The redesign put four fixed
  // blocks around the nav instead of two (brand, branch card, `+ Yangi
  // buyurtma`, and the account button at the bottom); each of them is the only
  // way to reach what it does, so each is asserted pinned by name. An owner has
  // the most nav entries, which is why this runs as one.
  const pinnedBlocks = ['.workshop-brand', '.workshop-branch-card', '.workshop-create']

  const nav = await page.evaluate((pinned) => {
    const sidebar = document.querySelector('.workshop-sidebar')!
    const region = sidebar.querySelector(':scope > .workshop-nav') as HTMLElement
    const links = Array.from(region.querySelectorAll('a'))
    const missing = pinned.filter((selector) => !sidebar.querySelector(`:scope > ${selector}`))
    const tops = new Map(
      pinned
        .filter((selector) => !missing.includes(selector))
        .map((selector) => [
          selector,
          sidebar.querySelector(`:scope > ${selector}`)!.getBoundingClientRect().top,
        ]),
    )
    const cardBottom = sidebar
      .querySelector(':scope > .workshop-user-card')!
      .getBoundingClientRect().bottom

    const unreachable: string[] = []
    for (const link of links) {
      link.scrollIntoView({ block: 'nearest' })
      const box = link.getBoundingClientRect()
      const band = region.getBoundingClientRect()
      if (box.bottom > band.bottom + 0.5 || box.top < band.top - 0.5) {
        unreachable.push(link.textContent?.trim().replace(/\s+/g, ' ') ?? '?')
      }
    }
    region.scrollTop = region.scrollHeight

    return {
      linkCount: links.length,
      unreachable,
      overflowY: getComputedStyle(region).overflowY,
      overscrollBehaviorY: getComputedStyle(region).overscrollBehaviorY,
      missing,
      // Head and foot must not have moved while the nav scrolled, and the page
      // behind the nav must not have scrolled either.
      drifted: [...tops]
        .filter(
          ([selector, top]) =>
            sidebar.querySelector(`:scope > ${selector}`)!.getBoundingClientRect().top !== top,
        )
        .map(([selector]) => selector),
      cardStayedPinned:
        sidebar.querySelector(':scope > .workshop-user-card')!.getBoundingClientRect().bottom ===
        cardBottom,
      pageScrollTop: document.scrollingElement?.scrollTop ?? 0,
    }
  }, pinnedBlocks)

  expect(nav.linkCount).toBeGreaterThan(0)
  expect(nav.unreachable, 'nav links that cannot be scrolled into view').toEqual([])
  expect(nav.overflowY).toBe('auto')
  expect(nav.overscrollBehaviorY).toBe('contain')
  expect(nav.missing, 'sidebar blocks the shell did not render').toEqual([])
  expect(nav.drifted, 'sidebar blocks that scrolled away with the nav').toEqual([])
  expect(nav.cardStayedPinned).toBe(true)
  expect(nav.pageScrollTop).toBe(0)

  // Taller viewport: still flush, and no scrollbar when the nav already fits.
  await page.setViewportSize(DESKTOP)
  await expectFillsViewport(page, '.workshop-sidebar')
})

test('superadmin shell fills the viewport in both axes (QAD-180)', async ({ page }, testInfo) => {
  const adminLogin = `viewport-shell-${runId(testInfo)}`
  await seedPlatform(adminLogin)

  await page.setViewportSize(DESKTOP)
  await page.goto('/admin/')
  await page.getByLabel('Login').fill(adminLogin)
  await page.getByLabel(passwordLabel).fill(adminPassword)
  await page.getByRole('button', { name: continueButton }).click()
  await expect(page.getByRole('heading', { name: 'Asosiy' })).toBeVisible()

  await expectFillsViewport(page, '.admin-sidebar')

  // `.admin-app` caps itself with a viewport width unit, which the same zoom
  // shrinks by 10% — the horizontal twin of the same defect.
  const width = await page.evaluate(() => {
    const app = document.querySelector('.admin-app')!
    return { rendered: app.getBoundingClientRect().width, viewport: window.innerWidth }
  })
  expect(
    Math.abs(width.rendered - width.viewport),
    `.admin-app rendered ${width.rendered}px into a ${width.viewport}px viewport`,
  ).toBeLessThanOrEqual(1)
})
