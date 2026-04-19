import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useSession } from './useSession'

describe('useSession', () => {
  it('returns session data on success', async () => {
    const { result } = renderHook(() => useSession('test-sid'))
    await waitFor(() => expect(result.current.session).not.toBeNull())
    expect(result.current.session?.session_id).toBe('test-sid')
    expect(result.current.session?.current_intent?.type).toBe('Flywheel_Rim')
  })

  it('returns error for 404', async () => {
    const { result } = renderHook(() => useSession('expired'))
    await waitFor(() => expect(result.current.error).toBeDefined())
  })

  it('returns null when sessionId is null', () => {
    const { result } = renderHook(() => useSession(null))
    expect(result.current.session).toBeNull()
    expect(result.current.isLoading).toBe(false)
  })
})
