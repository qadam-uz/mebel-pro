import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import OrderCompleteProductionModal from '@/shared/components/OrderCompleteProductionModal.vue'
import type { ProductionStockLine } from '@/shared/app/workshopOrderDetail'

const stockLines: ProductionStockLine[] = [
  { materialId: 'm-panel', kind: 'panel', name: 'LDSP Egger H1334', amount: '3 list' },
  { materialId: 'm-edge', kind: 'edge', name: 'Kromka 2x22 H1334', amount: '12.40 m' },
]

const workerOptions = [
  { value: 'w-1', label: 'Aziz Tursunov' },
  { value: 'w-2', label: 'Bobur Mirzo' },
]

function open(props: Partial<InstanceType<typeof OrderCompleteProductionModal>['$props']> = {}) {
  return mount(OrderCompleteProductionModal, {
    props: {
      open: true,
      stockLines,
      workerOptions,
      showCutter: true,
      showEdger: true,
      defaultCutterId: null,
      defaultEdgerId: null,
      ...props,
    },
    attachTo: document.body,
  })
}

function dialogText() {
  return document.querySelector('[role="dialog"]')?.textContent ?? ''
}

describe('OrderCompleteProductionModal', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('names the stock it will spend before the button', async () => {
    open()
    await nextTick()
    expect(dialogText()).toContain('Buyurtma tayyormi?')
    expect(dialogText()).toContain('Ombordan chiqim:')
    const lines = Array.from(
      document.querySelectorAll('[data-test="complete-stock-lines"] li'),
    ).map((node) => Array.from(node.children).map((child) => child.textContent?.trim()))
    // Panels in sheets, tape in metres — the money card's own figures.
    expect(lines).toEqual([
      ['LDSP Egger H1334', '3 list'],
      ['Kromka 2x22 H1334', '12.40 m'],
    ])
  })

  it('says so when the order spends nothing rather than showing an empty list', async () => {
    // A fully client-supplied order writes the events but touches no stock.
    open({ stockLines: [] })
    await nextTick()
    expect(document.querySelector('[data-test="complete-stock-lines"]')).toBeNull()
    expect(dialogText()).toContain("Bu buyurtmada ustaxona materiali yo'q")
  })

  it('offers the edger only when a side is banded, and the cutter only when uncredited', async () => {
    open({ showEdger: false })
    await nextTick()
    expect(dialogText()).toContain('Kim kesdi? (ixtiyoriy)')
    expect(dialogText()).not.toContain('Kim kromka yopishtirdi?')
    document.body.innerHTML = ''

    // A full→simple leftover already past the saw: the backend refuses a second
    // cutter credit, so the select is not offered at all.
    open({ showCutter: false })
    await nextTick()
    expect(dialogText()).not.toContain('Kim kesdi?')
    expect(dialogText()).toContain('Kim kromka yopishtirdi? (ixtiyoriy)')
  })

  it('completes with no worker at all — the picks are a reporting dimension', async () => {
    const wrapper = open()
    await nextTick()
    expect(dialogText()).toContain('Belgilanmagan')
    const confirm = Array.from(document.querySelectorAll('[role="dialog"] button')).find((node) =>
      node.textContent?.includes('Ha, tayyor'),
    ) as HTMLButtonElement
    // Never disabled for an empty pick: a shop with no worker accounts still
    // closes its orders.
    expect(confirm.disabled).toBe(false)
    confirm.click()
    expect(wrapper.emitted('confirm')?.[0]).toEqual([{ cutterUserId: null, edgerUserId: null }])
  })

  it("preselects the branch's last pick, and ignores one the branch no longer offers", async () => {
    const wrapper = open({ defaultCutterId: 'w-2', defaultEdgerId: 'w-gone' })
    await nextTick()
    const confirm = Array.from(document.querySelectorAll('[role="dialog"] button')).find((node) =>
      node.textContent?.includes('Ha, tayyor'),
    ) as HTMLButtonElement
    confirm.click()
    // The remembered cutter rides along; the stale edger falls back to empty
    // rather than sending an id this branch cannot resolve.
    expect(wrapper.emitted('confirm')?.[0]).toEqual([{ cutterUserId: 'w-2', edgerUserId: null }])
  })

  it('never credits a role whose select is hidden', async () => {
    // A remembered edger must not be submitted for an unbanded order.
    const wrapper = open({ showEdger: false, defaultCutterId: 'w-1', defaultEdgerId: 'w-2' })
    await nextTick()
    const confirm = Array.from(document.querySelectorAll('[role="dialog"] button')).find((node) =>
      node.textContent?.includes('Ha, tayyor'),
    ) as HTMLButtonElement
    confirm.click()
    expect(wrapper.emitted('confirm')?.[0]).toEqual([{ cutterUserId: 'w-1', edgerUserId: null }])
  })
})
