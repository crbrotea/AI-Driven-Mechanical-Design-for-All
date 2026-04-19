import { describe, it, expect } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useInterpretStream } from './useInterpretStream'

describe('useInterpretStream', () => {
  it('streams events and captures final intent', async () => {
    const { result } = renderHook(() => useInterpretStream())
    await act(async () => {
      await result.current.start('design a flywheel', 'test-sid')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    expect(result.current.intent?.type).toBe('Flywheel_Rim')
    expect(result.current.events.length).toBeGreaterThan(0)
  })
})
