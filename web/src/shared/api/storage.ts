// Per-app token storage. The three SPAs share an origin in dev (all on
// :5173) and may share one in prod, so tokens are namespaced by app key to
// keep the client / workshop / admin sessions from colliding in localStorage.

export type AppKey = 'client' | 'workshop' | 'admin'

interface StoredTokens {
  access: string
  refresh: string
}

const tokenKey = (app: AppKey) => `mp.${app}.tokens`
const branchKey = (app: AppKey) => `mp.${app}.branch`

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* storage unavailable (private mode / SSR) — auth degrades gracefully */
  }
}

export function getTokens(app: AppKey): StoredTokens | null {
  const raw = read(tokenKey(app))
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as StoredTokens
    if (parsed.access && parsed.refresh) return parsed
    return null
  } catch {
    return null
  }
}

export function setTokens(app: AppKey, tokens: StoredTokens): void {
  write(tokenKey(app), JSON.stringify(tokens))
}

export function setAccessToken(app: AppKey, access: string): void {
  const existing = getTokens(app)
  if (!existing) return
  setTokens(app, { ...existing, access })
}

export function clearTokens(app: AppKey): void {
  write(tokenKey(app), null)
}

// Workshop branch-picker selection persisted per app. 'all' = all branches.
export function getSelectedBranch(app: AppKey): string | null {
  return read(branchKey(app))
}

export function setSelectedBranch(app: AppKey, branchId: string | null): void {
  write(branchKey(app), branchId)
}
