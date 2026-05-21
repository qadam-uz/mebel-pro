// Auth API helpers — thin wrappers over the /auth/* endpoints, one per
// principal. The Pinia auth store calls these; screens call the store.

import type { ClientTokens, Me, SessionInfo, Tokens } from '@/shared/types'
import { api } from './client'

export interface Credentials {
  login: string
  password: string
}

export function loginPlatform(creds: Credentials): Promise<Tokens> {
  return api.post<Tokens>('/auth/platform/login', creds, { auth: false })
}

export function loginWorkshop(creds: Credentials): Promise<Tokens> {
  return api.post<Tokens>('/auth/workshop/login', creds, { auth: false })
}

// The Telegram Login Widget payload (id, hash, auth_date, …) is forwarded as-is.
export function loginClientTelegram(payload: Record<string, unknown>): Promise<ClientTokens> {
  return api.post<ClientTokens>('/auth/client/telegram', payload, { auth: false })
}

export function fetchMe(): Promise<Me> {
  return api.get<Me>('/auth/me')
}

export function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return api.post<void>('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}

export function logout(): Promise<void> {
  return api.post<void>('/auth/logout')
}

export function logoutAll(): Promise<void> {
  return api.post<void>('/auth/logout-all')
}

export function listSessions(): Promise<SessionInfo[]> {
  return api.get<SessionInfo[]>('/auth/sessions')
}

export function revokeSession(id: string): Promise<void> {
  return api.del<void>(`/auth/sessions/${id}`)
}

export function telegramConfig(): Promise<{ bot_username: string }> {
  return api.get<{ bot_username: string }>('/auth/telegram-config', { auth: false })
}
