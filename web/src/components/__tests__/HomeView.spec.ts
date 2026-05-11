import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import HomeView from '@/views/HomeView.vue'

// Avoid hitting the network in unit tests.
vi.mock('@/api/client', () => ({
  api: { get: vi.fn().mockResolvedValue({ status: 'ok', env: 'test' }) },
}))

describe('HomeView', () => {
  it('renders the heading', () => {
    setActivePinia(createPinia())
    const wrapper = mount(HomeView)
    expect(wrapper.find('h1').text()).toBe('Mebel Pro')
  })
})
