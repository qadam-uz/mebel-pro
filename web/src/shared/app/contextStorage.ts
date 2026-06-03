import type { DropdownOption } from '@/shared/app/roleConfig'

export function workshopContextStorageKey(principalId: string, sessionId: string) {
  return `mp:workshop-context:${principalId}:${sessionId}`
}

export function readStoredContext(
  storage: Storage,
  key: string,
  options: DropdownOption[],
): string | null {
  const stored = storage.getItem(key)
  if (stored && options.some((option) => option.value === stored)) return stored
  return null
}

export function persistStoredContext(
  storage: Storage,
  key: string,
  value: string,
  options: DropdownOption[],
) {
  if (value !== 'none' && options.some((option) => option.value === value)) {
    storage.setItem(key, value)
    return
  }
  storage.removeItem(key)
}
