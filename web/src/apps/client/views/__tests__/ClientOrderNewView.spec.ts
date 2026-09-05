import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clientConfig, roleConfigKey } from '@/shared/app/roleConfig'
import ClientOrderNewView from '@/apps/client/views/ClientOrderNewView.vue'
import { useAuthStore, type MeResponse } from '@/shared/stores/auth'
import { useCuttingStore, type CuttingDraft } from '@/shared/stores/cutting'
import { useOrdersStore, type OrderQuote } from '@/shared/stores/orders'

const routes = [
  {
    path: '/c/orders/new/:draft_id',
    name: 'client-order-new',
    component: ClientOrderNewView,
  },
  { path: '/c/orders/:id', name: 'client-order-detail', component: { template: '<div />' } },
  { path: '/c/cutting/:id', name: 'client-cutting-editor', component: { template: '<div />' } },
  {
    path: '/c/cutting/:id/result',
    name: 'client-cutting-result',
    component: { template: '<div />' },
  },
]

function clientMe(overrides: Partial<MeResponse> = {}): MeResponse {
  return {
    principal_type: 'client',
    principal_id: 'client-1',
    session_id: 'session-1',
    password_reset_required: false,
    workshop_id: null,
    workshop_name: null,
    is_owner: false,
    grants: [],
    login: null,
    full_name: null,
    phone: '+998901112233',
    name: 'Dilshod',
    preferred_branch_id: 'branch-1',
    pinned_workshop_name: 'Mebel Master',
    pinned_branch_name: 'Yunusobod filiali',
    status: 'active',
    ...overrides,
  }
}

function draft(): CuttingDraft {
  return {
    id: 'draft-1',
    name: 'Oshxona shkafi',
    preferred_branch_id: 'branch-1',
    chosen_result_id: 'result-1',
    parts_snapshot: [],
    own_panel_counts: {},
    own_edge_material_ids: [],
    revision_of_order_id: null,
    results: [
      {
        id: 'result-1',
        order_id: null,
        status: 'candidate',
        parts_snapshot: [{ quantity: 5 }],
        panels_used_by_material: { 'panel-1': 3 },
        edge_consumed_shop_by_material: { 'edge-1': 15_200 },
        edge_consumed_own_by_material: {},
        total_cut_length_mm: 0,
        panels: [
          {
            id: 'panel-a',
            material_id: 'panel-1',
            placements: [{}, {}, {}, {}, {}],
            offcuts: [],
            waste_area_mm2: 0,
          },
        ],
      },
    ],
  } as unknown as CuttingDraft
}

function quote(): OrderQuote {
  return {
    draft_id: 'draft-1',
    branch_id: 'branch-1',
    workshop_name: 'Mebel Master',
    branch_name: 'Yunusobod filiali',
    branch_address: 'Amir Temur 108',
    branch_phone: '+998712007878',
    branch_additional_phones: [],
    branch_latitude: null,
    branch_longitude: null,
    panels_used: 3,
    cutting_rate_tiyin: 60_000,
    total_tiyin: 51_445_800,
    material_lines: [],
    edge_lines: [
      {
        material_id: 'edge-1',
        material_name: 'Egger H1145 · 2×22 mm',
        consumed_mm: 15_200,
        own: false,
        metre_price_tiyin: 240_000,
        material_cost_tiyin: 3_648_000,
        service_cost_tiyin: 117_800,
        line_total_tiyin: 3_765_800,
      },
    ],
  } as unknown as OrderQuote
}

async function mountConfirmation(profilePhone: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/c/orders/new/draft-1')
  await router.isReady()

  const auth = useAuthStore()
  auth.accessToken = 'access-1'
  auth.me = clientMe({ phone: profilePhone })
  auth.status = 'authenticated'

  const cutting = useCuttingStore()
  vi.spyOn(cutting, 'loadDraft').mockImplementation(async () => {
    cutting.currentDraft = draft()
  })

  const orders = useOrdersStore()
  vi.spyOn(orders, 'quoteForDraft').mockResolvedValue(quote())
  const create = vi.spyOn(orders, 'createClientOrder').mockResolvedValue({ id: 'order-1' } as never)

  const wrapper = mount(ClientOrderNewView, {
    global: {
      plugins: [router],
      provide: { [roleConfigKey as symbol]: clientConfig },
      stubs: { Icon: true, BranchContact: true, RouterLink: { template: '<a><slot/></a>' } },
    },
  })
  await flushPromises()
  return { wrapper, create }
}

function phoneField(wrapper: Awaited<ReturnType<typeof mountConfirmation>>['wrapper']) {
  return wrapper.get('input[type="tel"]')
}

function submitButton(wrapper: Awaited<ReturnType<typeof mountConfirmation>>['wrapper']) {
  return wrapper.findAll('button').find((button) => button.text().includes('tasdiqlash'))!
}

/**
 * §7.7's phone rule. A Telegram sign-up can carry a foreign number into the
 * profile, and that number is prefilled here — so this is the one field on the
 * client that regularly arrives already invalid.
 */
describe('ClientOrderNewView — Uzbek numbers only (§7.7)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the foreign number as it is and refuses it on blur', async () => {
    const { wrapper } = await mountConfirmation('+79261234567')

    // Shown verbatim, not rewritten into a well-formed-but-wrong +998 number.
    expect((phoneField(wrapper).element as HTMLInputElement).value).toBe('+79261234567')
    // Nothing is flagged before the client has had a chance to touch it.
    expect(wrapper.text()).not.toContain("O'zbekiston raqami kerak")

    await phoneField(wrapper).trigger('blur')

    expect(wrapper.text()).toContain("O'zbekiston raqami kerak: +998 XX XXX XX XX")
    const field = phoneField(wrapper)
    expect(field.attributes('aria-invalid')).toBe('true')
    expect(field.attributes('aria-describedby')).toBe('order-phone-error')
    expect(field.classes()).toContain('border-danger')
  })

  it('keeps the submit disabled while the number is foreign', async () => {
    const { wrapper, create } = await mountConfirmation('+79261234567')

    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()

    await submitButton(wrapper).trigger('click')
    expect(create).not.toHaveBeenCalled()
  })

  it('accepts a +998 number and places the order with the edited contact', async () => {
    const { wrapper, create } = await mountConfirmation('+79261234567')

    await phoneField(wrapper).setValue('+998901112233')
    await phoneField(wrapper).trigger('blur')

    expect(wrapper.text()).not.toContain("O'zbekiston raqami kerak")
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()

    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ contact_phone: '+998901112233', contact_name: 'Dilshod' }),
    )
  })

  it('carries the four figures and no «Chiqim»', async () => {
    const { wrapper } = await mountConfirmation('+998901112233')

    const text = wrapper.text()
    expect(text).toContain('Detallar')
    expect(text).toContain('Listlar')
    expect(text).toContain('Kromka')
    expect(text).toContain('Foydali qoldiq')
    // Removed from the client (§7.7) — the workshop keeps them.
    expect(text).not.toContain('Chiqim')
    expect(text).not.toContain("Arra yo'li")
    // No «Profildan tiklash» link any more: the fields already hold the profile.
    expect(text).not.toContain('Profildan tiklash')
    // The Mijoz explanation is a label-style line, not an info banner.
    expect(text).toContain("Ustaxona siz bilan bog'lanishi uchun")
    // The subtitle is the draft name alone.
    expect(text).toContain('Oshxona shkafi')
  })

  it('names the tape on the Kromka receipt line', async () => {
    const { wrapper } = await mountConfirmation('+998901112233')

    const text = wrapper.text().replace(/ /g, ' ')
    expect(text).toContain('Kromka: Egger H1145 · 2×22 mm')
    expect(text).toContain('15.20 m · material + xizmat')
  })
})
