import { describe, it, expect, beforeEach } from 'vitest'
import { getOrCreateSessionId, clearSession, setSessionId } from './session-storage'

describe('session-storage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('generates a UUID on first call', () => {
    const id = getOrCreateSessionId()
    expect(id).toMatch(/^[0-9a-f-]{36}$/)
  })

  it('returns the same id on subsequent calls', () => {
    const id1 = getOrCreateSessionId()
    const id2 = getOrCreateSessionId()
    expect(id1).toBe(id2)
  })

  it('clearSession removes stored id', () => {
    getOrCreateSessionId()
    clearSession()
    expect(localStorage.getItem('mechdesign-session-id')).toBeNull()
  })

  it('setSessionId persists custom id', () => {
    setSessionId('custom-uuid')
    expect(getOrCreateSessionId()).toBe('custom-uuid')
  })
})
