import { describe, expect, it } from 'vitest'

import {
  persistStoredContext,
  readStoredContext,
  workshopContextStorageKey,
} from '@/shared/app/contextStorage'
import type { DropdownOption } from '@/shared/app/roleConfig'

const options: DropdownOption[] = [
  { value: 'branch-1', label: 'Branch 1', meta: 'open', status: 'active' },
  { value: 'branch-2', label: 'Branch 2', meta: 'closed', status: 'pending' },
]

describe('workshop context storage', () => {
  it('scopes context values to principal and session', () => {
    expect(workshopContextStorageKey('user-1', 'session-1')).toBe(
      'mp:workshop-context:user-1:session-1',
    )
  })

  it('restores only values that still exist in current options', () => {
    const storage = new MapBackedStorage()
    const key = workshopContextStorageKey('user-1', 'session-1')
    storage.setItem(key, 'branch-2')

    expect(readStoredContext(storage, key, options)).toBe('branch-2')
    expect(readStoredContext(storage, key, options.slice(0, 1))).toBeNull()
  })

  it('persists valid values and removes invalid or empty context values', () => {
    const storage = new MapBackedStorage()
    const key = workshopContextStorageKey('user-1', 'session-1')

    persistStoredContext(storage, key, 'branch-1', options)
    expect(storage.getItem(key)).toBe('branch-1')

    persistStoredContext(storage, key, 'none', options)
    expect(storage.getItem(key)).toBeNull()

    persistStoredContext(storage, key, 'branch-3', options)
    expect(storage.getItem(key)).toBeNull()
  })
})

class MapBackedStorage implements Storage {
  private readonly values = new Map<string, string>()

  get length() {
    return this.values.size
  }

  clear(): void {
    this.values.clear()
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null
  }

  key(index: number): string | null {
    return Array.from(this.values.keys())[index] ?? null
  }

  removeItem(key: string): void {
    this.values.delete(key)
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value)
  }
}
