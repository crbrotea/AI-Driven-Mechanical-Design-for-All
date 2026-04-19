const STORAGE_KEY = 'mechdesign-session-id'

export function getOrCreateSessionId(): string {
  if (typeof window === 'undefined') return ''
  const existing = window.localStorage.getItem(STORAGE_KEY)
  if (existing) return existing
  const fresh = crypto.randomUUID()
  window.localStorage.setItem(STORAGE_KEY, fresh)
  return fresh
}

export function clearSession(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(STORAGE_KEY)
}

export function setSessionId(id: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, id)
}
