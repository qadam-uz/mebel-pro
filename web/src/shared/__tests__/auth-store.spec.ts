import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { Me } from '@/shared/types'

// Mock the auth API so the store never touches the network.
vi.mock('@/shared/api/auth', () => ({
  fetchMe: vi.fn(),
  loginWorkshop: vi.fn(),
  loginPlatform: vi.fn(),
  loginClientTelegram: vi.fn(),
  changePassword: vi.fn(),
  logout: vi.fn(),
}))

import * as authApi from '@/shared/api/auth'
import { createAuthStore } from '@/shared/stores/auth'

const fetchMe = vi.mocked(authApi.fetchMe)
const loginWorkshop = vi.mocked(authApi.loginWorkshop)

const ownerMe: Me = {
  principal_type: 'workshop_user',
  id: 'u01',
  full_name: 'Hasan Karimov',
  phone: '+998901003030',
  force_password_change: false,
  workshop_id: 'ws-01',
  is_owner: true,
  home_branch_id: 'yunusobod',
  grants: [],
  first_name: null,
  photo_url: null,
}

const staffMe: Me = {
  ...ownerMe,
  id: 'u02',
  full_name: 'Aziza Rasulova',
  is_owner: false,
  grants: [
    { permission: 'manage_orders', branch_id: 'yunusobod' },
    { permission: 'manage_orders', branch_id: 'chilonzor' },
  ],
}

const useAuth = createAuthStore({ app: 'workshop' })

describe('auth store — can()', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    fetchMe.mockReset()
    loginWorkshop.mockReset()
  })

  it('owner is allowed everywhere', () => {
    const auth = useAuth()
    auth.me = ownerMe
    expect(auth.isOwner).toBe(true)
    expect(auth.can('manage_finance')).toBe(true)
    expect(auth.can('process_production', 'any-branch')).toBe(true)
  })

  it('staff is allowed only on granted (permission, branch) pairs', () => {
    const auth = useAuth()
    auth.me = staffMe
    expect(auth.can('manage_orders')).toBe(true) // holds it on some branch
    expect(auth.can('manage_orders', 'yunusobod')).toBe(true)
    expect(auth.can('manage_orders', 'yangiyol')).toBe(false) // not granted there
    expect(auth.can('manage_finance')).toBe(false) // not granted at all
  })

  it('login stores tokens and loads the principal', async () => {
    loginWorkshop.mockResolvedValue({
      access_token: 'a',
      refresh_token: 'r',
      token_type: 'bearer',
    })
    fetchMe.mockResolvedValue(ownerMe)
    const auth = useAuth()
    await auth.loginWorkshop({ login: 'hasan', password: 'secret' })
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.me?.id).toBe('u01')
    expect(localStorage.getItem('mp.workshop.tokens')).toContain('"access":"a"')
  })

  it('branch selection persists per app', () => {
    const auth = useAuth()
    auth.selectBranch('chilonzor')
    expect(auth.selectedBranch).toBe('chilonzor')
    expect(auth.branchScope).toBe('chilonzor')
    expect(localStorage.getItem('mp.workshop.branch')).toBe('chilonzor')
    auth.selectBranch('all')
    expect(auth.branchScope).toBe(null)
    expect(localStorage.getItem('mp.workshop.branch')).toBe(null)
  })
})
